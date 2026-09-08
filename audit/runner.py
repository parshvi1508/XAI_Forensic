"""
LIME Attribution Audit - Experiment Runner

Runs LIME on 30 pre-registered inputs across 5 random seeds.
Measures attribution stability and deletion faithfulness.

Usage:
    python -m audit.runner                  # full run (30 inputs)
    python -m audit.runner --subset 3       # first 3 inputs only (for testing)
    python -m audit.runner --resume         # resume from last checkpoint
"""

import argparse
import csv
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone

import numpy as np
from lime.lime_text import LimeTextExplainer
from transformers import pipeline as hf_pipeline

from audit.config import (
    CANONICAL_SEED,
    DELETION_CSV_PATH,
    LIME_CLASS_NAMES,
    LIME_NUM_FEATURES,
    LIME_NUM_SAMPLES,
    MODEL_NAME,
    RANDOM_SEEDS,
    RAW_CSV_PATH,
    RESULTS_DIR,
    TEST_SET_PATH,
)


def load_test_set(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["inputs"]


def load_model(model_name: str):
    print(f"Loading model: {model_name}")
    model = hf_pipeline("text-classification", model=model_name, top_k=None)
    print("Model loaded.")
    return model


def get_positive_score(pipeline_output: list) -> float:
    for item in pipeline_output[0]:
        if "pos" in item["label"].lower():
            return item["score"]
    return 1.0 - max(item["score"] for item in pipeline_output[0])


def make_predict_fn(model):
    def predict_proba(texts: list[str]) -> np.ndarray:
        results = []
        for text in texts:
            output = model(text, truncation=True, max_length=512)
            pos = get_positive_score(output)
            results.append([1.0 - pos, pos])
        return np.array(results)
    return predict_proba


def run_lime_single(
    text: str,
    predict_fn,
    seed: int,
    num_samples: int = LIME_NUM_SAMPLES,
    num_features: int = LIME_NUM_FEATURES,
) -> dict:
    np.random.seed(seed)
    explainer = LimeTextExplainer(
        class_names=LIME_CLASS_NAMES,
        random_state=seed,
    )
    explanation = explainer.explain_instance(
        text,
        predict_fn,
        num_features=num_features,
        num_samples=num_samples,
    )
    token_weights = explanation.as_list()
    sorted_by_abs = sorted(token_weights, key=lambda x: abs(x[1]), reverse=True)

    return {
        "tokens": sorted_by_abs,
        "lime_score": explanation.score,
        "intercept": explanation.intercept.get(1, 0.0),
    }


def run_deletion_test(
    text: str,
    top_token: str,
    predict_fn,
) -> dict:
    words = text.split()
    masked_words = [w for w in words if w != top_token]

    if not masked_words or masked_words == words:
        for i, w in enumerate(words):
            if top_token.lower() in w.lower():
                masked_words = words[:i] + words[i + 1:]
                break

    if not masked_words:
        return {
            "modified_text": "",
            "modified_label": "error",
            "modified_positive_score": float("nan"),
            "confidence_delta": float("nan"),
            "label_flipped": False,
            "direction_correct": False,
        }

    masked_text = " ".join(masked_words)
    proba = predict_fn([masked_text])
    modified_pos = float(proba[0][1])
    modified_label = "positive" if modified_pos >= 0.5 else "negative"

    return {
        "modified_text": masked_text,
        "modified_label": modified_label,
        "modified_positive_score": modified_pos,
    }


def get_environment_info():
    import lime
    import scipy
    import sklearn
    import torch
    import transformers

    return {
        "model": MODEL_NAME,
        "lime_version": getattr(lime, "__version__", "0.2.0.1"),
        "torch_version": torch.__version__,
        "transformers_version": transformers.__version__,
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "sklearn_version": sklearn.__version__,
        "python_version": sys.version,
        "platform": platform.platform(),
        "seeds": RANDOM_SEEDS,
        "num_samples": LIME_NUM_SAMPLES,
        "num_features": LIME_NUM_FEATURES,
    }


RAW_FIELDNAMES = (
    ["input_id", "category", "text", "seed", "base_label", "base_confidence",
     "base_positive_score"]
    + [f"token_{i}" for i in range(1, LIME_NUM_FEATURES + 1)]
    + [f"weight_{i}" for i in range(1, LIME_NUM_FEATURES + 1)]
    + ["lime_score", "duration_ms"]
)

DELETION_FIELDNAMES = [
    "input_id", "category", "text", "removed_token", "token_lime_weight",
    "original_label", "original_positive_score",
    "modified_label", "modified_positive_score",
    "confidence_delta", "label_flipped", "direction_correct",
]


def load_completed_raw(path: str) -> tuple[set[tuple[int, int]], dict]:
    """Load existing raw CSV, return (completed pairs, canonical results)."""
    completed = set()
    canonical = {}
    if not os.path.exists(path):
        return completed, canonical
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("input_id") or not row.get("seed"):
                continue
            input_id = int(row["input_id"])
            seed = int(row["seed"])
            completed.add((input_id, seed))
            if seed == CANONICAL_SEED:
                tokens = []
                for i in range(1, LIME_NUM_FEATURES + 1):
                    t = row.get(f"token_{i}", "")
                    w = float(row.get(f"weight_{i}", 0))
                    if t:
                        tokens.append((t, w))
                base_pos = float(row["base_positive_score"])
                canonical[input_id] = {
                    "tokens": tokens,
                    "base_label": row["base_label"],
                    "base_pos": base_pos,
                    "base_conf": float(row["base_confidence"]),
                }
    return completed, canonical


def load_completed_deletions(path: str) -> set[int]:
    """Load existing deletion CSV, return set of completed input_ids."""
    completed = set()
    if not os.path.exists(path):
        return completed
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            completed.add(int(row["input_id"]))
    return completed


def main():
    parser = argparse.ArgumentParser(description="LIME Attribution Audit Runner")
    parser.add_argument("--subset", type=int, default=None,
                        help="Run only first N inputs (for testing)")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from checkpoint, skip completed (input_id, seed) pairs")
    args = parser.parse_args()

    print("[1/7] Creating results directory...")
    os.makedirs(RESULTS_DIR, exist_ok=True)

    print("[2/7] Loading test set...")
    inputs = load_test_set(TEST_SET_PATH)
    print(f"  Loaded {len(inputs)} inputs from {TEST_SET_PATH}")
    if args.subset:
        inputs = inputs[:args.subset]
        print(f"  Subset mode: using first {args.subset} inputs")

    completed_raw = set()
    canonical_results = {}
    completed_del = set()

    if args.resume:
        print("[3/7] Loading checkpoint data...")
        completed_raw, canonical_results = load_completed_raw(RAW_CSV_PATH)
        completed_del = load_completed_deletions(DELETION_CSV_PATH)
        print(f"  Found {len(completed_raw)} completed raw rows")
        print(f"  Found {len(completed_del)} completed deletion rows")
        print(f"  Found {len(canonical_results)} canonical (seed=42) results")
    else:
        print("[3/7] Fresh run (no checkpoint)")

    print("[4/7] Loading model...")
    model = load_model(MODEL_NAME)
    predict_fn = make_predict_fn(model)
    print("  Predict function ready")

    print("[5/7] Collecting environment info...")
    env_info = get_environment_info()
    print(f"  Python {sys.version.split()[0]}, torch {env_info['torch_version']}")
    print(f"  LIME {env_info['lime_version']}, numpy {env_info['numpy_version']}")

    total_pairs = len(inputs) * len(RANDOM_SEEDS)
    remaining = total_pairs - len(completed_raw)
    print(f"\n[6/7] Starting LIME attribution runs")
    print(f"  {len(inputs)} inputs x {len(RANDOM_SEEDS)} seeds = {total_pairs} total calls")
    print(f"  {remaining} remaining\n")

    start_total = time.perf_counter()

    raw_mode = "a" if args.resume and os.path.exists(RAW_CSV_PATH) else "w"
    write_header = raw_mode == "w"

    with open(RAW_CSV_PATH, raw_mode, newline="", encoding="utf-8") as raw_f:
        raw_writer = csv.DictWriter(raw_f, fieldnames=RAW_FIELDNAMES)
        if write_header:
            raw_writer.writeheader()

        for idx, inp in enumerate(inputs):
            input_id = inp["id"]
            text = inp["text"]
            category = inp["category"]

            if not text.strip():
                print(f"  [{input_id}/30] SKIP empty/whitespace input")
                continue

            print(f"  [{input_id}/30] Running base prediction...")
            base_proba = predict_fn([text])
            base_pos = float(base_proba[0][1])
            base_label = "positive" if base_pos >= 0.5 else "negative"
            base_conf = base_pos if base_label == "positive" else 1.0 - base_pos
            print(f"    Base: {base_label} (pos_score={base_pos:.6f}, conf={base_conf:.6f})")

            for seed_idx, seed in enumerate(RANDOM_SEEDS):
                if (input_id, seed) in completed_raw:
                    print(f"    Seed {seed}: already done, skipping")
                    continue

                elapsed = time.perf_counter() - start_total
                print(f"    Seed {seed} ({seed_idx + 1}/{len(RANDOM_SEEDS)}), "
                      f"elapsed {elapsed:.0f}s...")

                start_call = time.perf_counter()
                print(f"      Running LIME ({LIME_NUM_SAMPLES} perturbations)...")
                try:
                    result = run_lime_single(text, predict_fn, seed)
                except Exception as e:
                    print(f"      ERROR: {e}")
                    continue

                duration_ms = round((time.perf_counter() - start_call) * 1000)
                tokens = result["tokens"]
                top_token = tokens[0][0] if tokens else "N/A"
                top_weight = tokens[0][1] if tokens else 0.0
                print(f"      Done in {duration_ms}ms. Top token: '{top_token}' (weight={top_weight:.4f})")

                row = {
                    "input_id": input_id,
                    "category": category,
                    "text": text,
                    "seed": seed,
                    "base_label": base_label,
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
                raw_f.flush()
                print(f"      Saved to CSV (flushed)")

                if seed == CANONICAL_SEED:
                    canonical_results[input_id] = {
                        "tokens": tokens,
                        "base_label": base_label,
                        "base_pos": base_pos,
                        "base_conf": base_conf,
                    }

    print(f"\nRaw attributions saved to {RAW_CSV_PATH}")
    print(f"\n[7/7] Running deletion faithfulness tests...")

    from audit.metrics import faithfulness_direction_correct

    del_mode = "a" if args.resume and os.path.exists(DELETION_CSV_PATH) else "w"
    del_write_header = del_mode == "w"

    with open(DELETION_CSV_PATH, del_mode, newline="", encoding="utf-8") as del_f:
        del_writer = csv.DictWriter(del_f, fieldnames=DELETION_FIELDNAMES)
        if del_write_header:
            del_writer.writeheader()

        for inp in inputs:
            input_id = inp["id"]
            text = inp["text"]
            category = inp["category"]

            if input_id in completed_del:
                print(f"  [{input_id}] Deletion already done, skipping")
                continue

            if input_id not in canonical_results:
                print(f"  [{input_id}] No canonical result, skipping")
                continue

            canon = canonical_results[input_id]
            if not canon["tokens"]:
                print(f"  [{input_id}] No tokens in canonical, skipping")
                continue

            top_token = canon["tokens"][0][0]
            top_weight = canon["tokens"][0][1]

            print(f"  [{input_id}] Removing top token '{top_token}' (weight={top_weight:.4f})...")
            deletion = run_deletion_test(text, top_token, predict_fn)

            if deletion["modified_label"] == "error":
                print(f"  [{input_id}] Deletion failed (empty result)")
                continue

            delta = deletion["modified_positive_score"] - canon["base_pos"]
            flipped = deletion["modified_label"] != canon["base_label"]
            dir_correct = faithfulness_direction_correct(top_weight, delta)
            print(f"    Result: {canon['base_label']} -> {deletion['modified_label']}, "
                  f"delta={delta:.6f}, flipped={flipped}, dir_correct={dir_correct}")

            row = {
                "input_id": input_id,
                "category": category,
                "text": text,
                "removed_token": top_token,
                "token_lime_weight": round(top_weight, 6),
                "original_label": canon["base_label"],
                "original_positive_score": round(canon["base_pos"], 6),
                "modified_label": deletion["modified_label"],
                "modified_positive_score": round(deletion["modified_positive_score"], 6),
                "confidence_delta": round(delta, 6),
                "label_flipped": flipped,
                "direction_correct": dir_correct,
            }
            del_writer.writerow(row)
            del_f.flush()

    total_time = time.perf_counter() - start_total
    print(f"Deletion faithfulness saved to {DELETION_CSV_PATH}")
    print(f"\nTotal experiment time: {total_time:.1f}s ({total_time / 60:.1f} min)")

    env_info["run_timestamp"] = datetime.now(timezone.utc).isoformat()
    env_info["total_duration_seconds"] = round(total_time, 1)
    env_info["resumed"] = args.resume
    env_path = os.path.join(RESULTS_DIR, "environment.json")
    with open(env_path, "w", encoding="utf-8") as f:
        json.dump(env_info, f, indent=2)
    print(f"Environment info saved to {env_path}")


if __name__ == "__main__":
    main()
