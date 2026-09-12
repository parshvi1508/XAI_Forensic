"""
E5: Temperature Scaling Experiment

Hypothesis: If LIME's faithfulness failure on strong baselines is caused by model
overconfidence (flat decision surface), then calibrating the model's temperature
should reduce confidence on those inputs and make deletion tests more discriminating.

If the paradox (near-zero deletion delta) persists after calibration → problem is LIME.
If it disappears → problem was overconfidence, not LIME.

Steps:
1. Load SST-2 validation set (872 examples) from HuggingFace datasets
2. Fit temperature T on validation logits to minimise cross-entropy
3. Create a temperature-scaled predictor wrapper
4. Re-run the 30-input LIME audit with the calibrated predictor
5. Save results to audit/results/e5_temperature_scaling/
6. Compare strong_baselines faithfulness before and after calibration

Usage:
    python -m audit.e5_temperature_scaling
    python -m audit.e5_temperature_scaling --subset 5   # test on first 5 inputs
"""

import argparse
import csv
import json
import os
import time

import numpy as np
from scipy.optimize import minimize_scalar
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import torch

from audit.config import (
    CANONICAL_SEED,
    LIME_CLASS_NAMES,
    LIME_NUM_FEATURES,
    LIME_NUM_SAMPLES,
    MODEL_NAME,
    RANDOM_SEEDS,
    RESULTS_DIR,
    TEST_SET_PATH,
)
from audit.runner import (
    load_test_set,
    run_lime_single,
    run_deletion_test,
)
from lime_audit.metrics import faithfulness_direction_correct


E5_RESULTS_DIR = os.path.join(RESULTS_DIR, "e5_temperature_scaling")
E5_SUMMARY_PATH = os.path.join(E5_RESULTS_DIR, "summary.json")
E5_RAW_CSV = os.path.join(E5_RESULTS_DIR, "raw_attributions.csv")
E5_DEL_CSV = os.path.join(E5_RESULTS_DIR, "deletion_faithfulness.csv")


def _get_logits(model, tokenizer, texts: list[str], batch_size: int = 16) -> np.ndarray:
    """Run model and return raw logits [n, 2] without temperature scaling."""
    all_logits = []
    model.eval()
    with torch.no_grad():
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            enc = tokenizer(batch, padding=True, truncation=True,
                            max_length=512, return_tensors="pt")
            out = model(**enc)
            all_logits.append(out.logits.cpu().numpy())
    return np.vstack(all_logits)


def fit_temperature(logits: np.ndarray, labels: np.ndarray) -> float:
    """Find scalar temperature T that minimises cross-entropy on validation set."""
    def neg_log_likelihood(T):
        scaled = logits / T
        exp = np.exp(scaled - scaled.max(axis=1, keepdims=True))
        probs = exp / exp.sum(axis=1, keepdims=True)
        probs = np.clip(probs, 1e-10, 1.0)
        return -float(np.mean(np.log(probs[np.arange(len(labels)), labels])))

    result = minimize_scalar(neg_log_likelihood, bounds=(0.1, 10.0), method="bounded")
    return float(result.x)


def make_temperature_predict_fn(model, tokenizer, temperature: float):
    """Return a predict_proba function that applies temperature scaling."""
    model.eval()

    def predict_proba(texts: list[str]) -> np.ndarray:
        results = []
        with torch.no_grad():
            for text in texts:
                enc = tokenizer([text], padding=True, truncation=True,
                                max_length=512, return_tensors="pt")
                logits = model(**enc).logits.cpu().numpy()[0]
                scaled = logits / temperature
                exp = np.exp(scaled - scaled.max())
                probs = exp / exp.sum()
                results.append([probs[0], probs[1]])
        return np.array(results)

    return predict_proba


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--subset", type=int, default=None,
                        help="Run only first N inputs (for testing)")
    args = parser.parse_args()

    os.makedirs(E5_RESULTS_DIR, exist_ok=True)
    print("E5: Temperature Scaling Experiment")

    print("\n[1/6] Loading SST-2 validation set...")
    try:
        from datasets import load_dataset
    except ImportError:
        print("ERROR: 'datasets' not installed. Run: pip install datasets")
        return

    sst2 = load_dataset("nyu-mll/glue", "sst2", split="validation")
    val_texts = [ex["sentence"] for ex in sst2]
    val_labels = [ex["label"] for ex in sst2]
    print(f"  Loaded {len(val_texts)} validation examples")

    print("[2/6] Loading model and running on validation set...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    raw_model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
    logits = _get_logits(raw_model, tokenizer, val_texts)
    print(f"  Logits shape: {logits.shape}")

    print("[3/6] Fitting temperature...")
    T = fit_temperature(logits, np.array(val_labels))
    print(f"  Optimal temperature T = {T:.4f}")
    print(f"  (T=1.0 = no scaling, T>1 = softer, T<1 = sharper)")

    calibrated_predict_fn = make_temperature_predict_fn(raw_model, tokenizer, T)

    print("[4/6] Loading test set...")
    inputs = load_test_set(TEST_SET_PATH)
    if args.subset:
        inputs = inputs[:args.subset]
        print(f"  Subset: {args.subset} inputs")
    print(f"  {len(inputs)} inputs to process")

    raw_fieldnames = (
        ["input_id", "category", "text", "seed", "base_label", "base_confidence",
         "base_positive_score"]
        + [f"token_{i}" for i in range(1, LIME_NUM_FEATURES + 1)]
        + [f"weight_{i}" for i in range(1, LIME_NUM_FEATURES + 1)]
        + ["lime_score", "duration_ms"]
    )
    del_fieldnames = [
        "input_id", "category", "text", "status",
        "removed_token", "token_lime_weight",
        "original_label", "original_positive_score",
        "modified_label", "modified_positive_score",
        "confidence_delta", "label_flipped", "direction_correct",
    ]

    canonical_results = {}
    print(f"\n[5/6] Running LIME with calibrated predictor...")

    with open(E5_RAW_CSV, "w", newline="", encoding="utf-8") as raw_f:
        raw_writer = csv.DictWriter(raw_f, fieldnames=raw_fieldnames)
        raw_writer.writeheader()

        for inp in inputs:
            input_id = inp["id"]
            text = inp["text"]
            category = inp["category"]

            if not text.strip():
                continue

            base_proba = calibrated_predict_fn([text])
            base_pos = float(base_proba[0][1])
            base_label = "positive" if base_pos >= 0.5 else "negative"
            base_conf = base_pos if base_label == "positive" else 1.0 - base_pos
            print(f"  [{input_id}] {category}: {base_label} (conf={base_conf:.4f})")

            for seed in RANDOM_SEEDS:
                start = time.perf_counter()
                try:
                    result = run_lime_single(text, calibrated_predict_fn, seed)
                except Exception as e:
                    print(f"    Seed {seed} ERROR: {e}")
                    continue
                duration_ms = round((time.perf_counter() - start) * 1000)
                tokens = result["tokens"]

                row = {
                    "input_id": input_id, "category": category, "text": text,
                    "seed": seed, "base_label": base_label,
                    "base_confidence": round(base_conf, 6),
                    "base_positive_score": round(base_pos, 6),
                    "lime_score": round(result["lime_score"], 6),
                    "duration_ms": duration_ms,
                }
                for i in range(LIME_NUM_FEATURES):
                    if i < len(tokens):
                        row[f"token_{i + 1}"] = tokens[i][0]
                        row[f"weight_{i + 1}"] = round(tokens[i][1], 6)
                    else:
                        row[f"token_{i + 1}"] = ""
                        row[f"weight_{i + 1}"] = 0.0
                raw_writer.writerow(row)

                if seed == CANONICAL_SEED:
                    canonical_results[input_id] = {
                        "tokens": tokens, "base_label": base_label,
                        "base_pos": base_pos, "base_conf": base_conf,
                    }

    print(f"\n[6/6] Running deletion tests...")
    del_results = {}
    with open(E5_DEL_CSV, "w", newline="", encoding="utf-8") as del_f:
        del_writer = csv.DictWriter(del_f, fieldnames=del_fieldnames)
        del_writer.writeheader()

        for inp in inputs:
            input_id = inp["id"]
            text = inp["text"]
            category = inp["category"]

            if not text.strip() or input_id not in canonical_results:
                continue

            canon = canonical_results[input_id]
            if not canon["tokens"]:
                continue

            top_token, top_weight = canon["tokens"][0]
            deletion = run_deletion_test(text, top_token, calibrated_predict_fn)

            if deletion["modified_label"] == "error":
                del_results[input_id] = {"status": "skipped_single_token"}
                del_writer.writerow({
                    "input_id": input_id, "category": category, "text": text,
                    "status": "skipped_single_token",
                    "removed_token": top_token, "token_lime_weight": round(top_weight, 6),
                    "original_label": canon["base_label"],
                    "original_positive_score": round(canon["base_pos"], 6),
                    "modified_label": "", "modified_positive_score": "",
                    "confidence_delta": "", "label_flipped": "", "direction_correct": "",
                })
                continue

            delta = deletion["modified_positive_score"] - canon["base_pos"]
            flipped = deletion["modified_label"] != canon["base_label"]
            dir_correct = faithfulness_direction_correct(top_weight, delta)

            del_results[input_id] = {
                "status": "tested", "delta": delta, "flipped": flipped,
                "dir_correct": dir_correct, "category": category,
            }
            del_writer.writerow({
                "input_id": input_id, "category": category, "text": text,
                "status": "tested",
                "removed_token": top_token, "token_lime_weight": round(top_weight, 6),
                "original_label": canon["base_label"],
                "original_positive_score": round(canon["base_pos"], 6),
                "modified_label": deletion["modified_label"],
                "modified_positive_score": round(deletion["modified_positive_score"], 6),
                "confidence_delta": round(delta, 6),
                "label_flipped": flipped,
                "direction_correct": dir_correct,
            })

    tested = {k2: v for k2, v in del_results.items() if v.get("status") == "tested"}
    n_correct = sum(1 for v in tested.values() if v["dir_correct"])
    n_flipped = sum(1 for v in tested.values() if v["flipped"])
    mean_delta = float(np.mean([abs(v["delta"]) for v in tested.values()])) if tested else None

    from collections import defaultdict
    by_cat = defaultdict(lambda: {"correct": 0, "flipped": 0, "total": 0, "deltas": []})
    for v in tested.values():
        cat = v["category"]
        by_cat[cat]["total"] += 1
        if v["dir_correct"]:
            by_cat[cat]["correct"] += 1
        if v["flipped"]:
            by_cat[cat]["flipped"] += 1
        by_cat[cat]["deltas"].append(abs(v["delta"]))

    summary = {
        "temperature": round(T, 6),
        "n_val_examples": len(val_texts),
        "n_tested": len(tested),
        "direction_correct_rate": round(n_correct / len(tested), 4) if tested else None,
        "label_flip_rate": round(n_flipped / len(tested), 4) if tested else None,
        "mean_abs_delta": round(mean_delta, 6) if mean_delta else None,
        "per_category": {
            cat: {
                "total": v["total"],
                "direction_correct_rate": round(v["correct"] / v["total"], 4) if v["total"] else None,
                "label_flip_rate": round(v["flipped"] / v["total"], 4) if v["total"] else None,
                "mean_abs_delta": round(float(np.mean(v["deltas"])), 6) if v["deltas"] else None,
            }
            for cat, v in by_cat.items()
        },
    }

    with open(E5_SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\n--- E5 RESULTS (T={T:.4f}) ---")
    print(f"  Direction correct:  {n_correct}/{len(tested)} ({summary['direction_correct_rate']})")
    print(f"  Label flip rate:    {n_flipped}/{len(tested)} ({summary['label_flip_rate']})")
    print(f"  Mean |delta|:       {summary['mean_abs_delta']}")
    print(f"\n  Per-category:")
    for cat, v in summary["per_category"].items():
        print(f"    {cat:30s} DirCorr={v['direction_correct_rate']} Flip={v['label_flip_rate']} |D|={v['mean_abs_delta']}")

    strong = summary["per_category"].get("strong_baselines", {})
    if strong:
        print(f"\n  KEY FINDING: strong_baselines after calibration:")
        print(f"    Dir correct: {strong['direction_correct_rate']}, Flip: {strong['label_flip_rate']}, "
              f"|D|: {strong['mean_abs_delta']}")
        if strong.get("mean_abs_delta") is not None:
            if strong["mean_abs_delta"] < 0.01:
                print("  → Paradox PERSISTS after calibration → problem is LIME, not overconfidence")
            else:
                print("  → Paradox GONE after calibration → problem was overconfidence")

    print(f"\nSaved to {E5_RESULTS_DIR}")


if __name__ == "__main__":
    main()
