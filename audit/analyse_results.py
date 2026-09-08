"""
LIME Attribution Audit - Results Analysis

Reads raw CSVs from runner.py, computes stability and faithfulness aggregates,
writes stability_metrics.csv and summary.json.

Usage:
    python -m audit.analyse_results
"""

import csv
import json
import os
from collections import defaultdict

import numpy as np

from audit.config import (
    DELETION_CSV_PATH,
    FAITHFULNESS_THRESHOLD_DIRECTION,
    LIME_NUM_FEATURES,
    RAW_CSV_PATH,
    RESULTS_DIR,
    STABILITY_CSV_PATH,
    STABILITY_THRESHOLD_JACCARD,
    STABILITY_THRESHOLD_KENDALL,
    SUMMARY_PATH,
    TOP_K_FOR_JACCARD,
)
from audit.metrics import compute_pairwise_stability


def load_raw_attributions(path: str) -> dict:
    by_input = defaultdict(dict)
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("input_id") or not row.get("seed"):
                continue
            input_id = int(row["input_id"])
            seed = int(row["seed"])
            tokens = []
            for i in range(1, LIME_NUM_FEATURES + 1):
                t = row.get(f"token_{i}", "")
                w = float(row.get(f"weight_{i}", 0))
                if t:
                    tokens.append((t, w))
            by_input[input_id][seed] = {
                "tokens": tokens,
                "base_label": row["base_label"],
                "base_confidence": float(row["base_confidence"]),
                "base_positive_score": float(row["base_positive_score"]),
                "lime_score": float(row["lime_score"]),
                "duration_ms": int(row["duration_ms"]),
                "category": row["category"],
                "text": row["text"],
            }
    return dict(by_input)


def load_deletion_results(path: str) -> dict:
    by_input = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            by_input[int(row["input_id"])] = {
                "removed_token": row["removed_token"],
                "token_lime_weight": float(row["token_lime_weight"]),
                "original_label": row["original_label"],
                "original_positive_score": float(row["original_positive_score"]),
                "modified_label": row["modified_label"],
                "modified_positive_score": float(row["modified_positive_score"]),
                "confidence_delta": float(row["confidence_delta"]),
                "label_flipped": row["label_flipped"] == "True",
                "direction_correct": row["direction_correct"] == "True",
                "category": row["category"],
                "text": row["text"],
            }
    return by_input


def main():
    print("[1/5] Loading raw attributions...")
    raw = load_raw_attributions(RAW_CSV_PATH)
    total_rows = sum(len(seeds) for seeds in raw.values())
    print(f"  Loaded {len(raw)} inputs, {total_rows} total rows")

    print("[2/5] Loading deletion results...")
    deletions = load_deletion_results(DELETION_CSV_PATH)
    print(f"  Loaded {len(deletions)} deletion tests")

    print("[3/5] Computing pairwise stability for each input...")
    stability_rows = []

    for input_id in sorted(raw.keys()):
        seeds_data = raw[input_id]
        first = next(iter(seeds_data.values()))
        category = first["category"]
        text = first["text"]

        seed_tokens = {s: d["tokens"] for s, d in seeds_data.items()}
        pairwise = compute_pairwise_stability(seed_tokens, k=TOP_K_FOR_JACCARD)

        labels = [d["base_label"] for d in seeds_data.values()]
        confidences = [d["base_confidence"] for d in seeds_data.values()]

        mean_j = round(pairwise["mean_jaccard"], 4)
        stability_rows.append({
            "input_id": input_id,
            "category": category,
            "text": text[:80],
            "mean_jaccard_top5": mean_j,
            "min_jaccard_top5": round(pairwise["min_jaccard"], 4),
            "mean_kendall_tau": round(pairwise["mean_kendall_tau"], 4),
            "min_kendall_tau": round(pairwise["min_kendall_tau"], 4) if not np.isnan(pairwise["min_kendall_tau"]) else "NaN",
            "label_stable": len(set(labels)) == 1,
            "confidence_std": round(float(np.std(confidences)), 6),
            "top1_unanimous": pairwise["top1_unanimous"],
        })
        print(f"  [{input_id}] {category}: Jaccard={mean_j}, "
              f"top1_unanimous={pairwise['top1_unanimous']}")

    print(f"\n[4/5] Writing stability CSV...")
    with open(STABILITY_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["input_id", "category", "text", "mean_jaccard_top5",
                       "min_jaccard_top5", "mean_kendall_tau", "min_kendall_tau",
                       "label_stable", "confidence_std", "top1_unanimous"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(stability_rows)
    print(f"  Saved {len(stability_rows)} rows to {STABILITY_CSV_PATH}")

    print("[5/5] Computing summary aggregates...")
    jaccards = [r["mean_jaccard_top5"] for r in stability_rows]
    taus = [r["mean_kendall_tau"] for r in stability_rows if not isinstance(r["mean_kendall_tau"], str)]
    label_unstable = [r for r in stability_rows if not r["label_stable"]]
    top1_unanimous = [r for r in stability_rows if r["top1_unanimous"]]

    cat_stability = defaultdict(lambda: {"jaccards": [], "taus": []})
    for r in stability_rows:
        cat = r["category"]
        cat_stability[cat]["jaccards"].append(r["mean_jaccard_top5"])
        if not isinstance(r["mean_kendall_tau"], str):
            cat_stability[cat]["taus"].append(r["mean_kendall_tau"])

    del_direction_correct = [d for d in deletions.values() if d["direction_correct"]]
    del_flipped = [d for d in deletions.values() if d["label_flipped"]]
    del_deltas = [abs(d["confidence_delta"]) for d in deletions.values() if not np.isnan(d["confidence_delta"])]

    cat_faith = defaultdict(lambda: {"correct": 0, "flipped": 0, "total": 0, "deltas": []})
    for d in deletions.values():
        cat = d["category"]
        cat_faith[cat]["total"] += 1
        if d["direction_correct"]:
            cat_faith[cat]["correct"] += 1
        if d["label_flipped"]:
            cat_faith[cat]["flipped"] += 1
        if not np.isnan(d["confidence_delta"]):
            cat_faith[cat]["deltas"].append(abs(d["confidence_delta"]))

    env_path = os.path.join(RESULTS_DIR, "environment.json")
    env_info = {}
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            env_info = json.load(f)

    summary = {
        "experiment_metadata": env_info,
        "stability_summary": {
            "overall_mean_jaccard_top5": round(float(np.mean(jaccards)), 4) if jaccards else None,
            "overall_mean_kendall_tau": round(float(np.mean(taus)), 4) if taus else None,
            "inputs_with_perfect_jaccard": sum(1 for j in jaccards if j >= 1.0),
            "inputs_with_jaccard_below_threshold": sum(1 for j in jaccards if j < STABILITY_THRESHOLD_JACCARD),
            "inputs_with_label_instability": len(label_unstable),
            "inputs_with_unanimous_top1": len(top1_unanimous),
            "total_inputs": len(stability_rows),
            "threshold_jaccard": STABILITY_THRESHOLD_JACCARD,
            "threshold_kendall": STABILITY_THRESHOLD_KENDALL,
            "passes_jaccard_threshold": (float(np.mean(jaccards)) >= STABILITY_THRESHOLD_JACCARD) if jaccards else False,
            "passes_kendall_threshold": (float(np.mean(taus)) >= STABILITY_THRESHOLD_KENDALL) if taus else False,
            "per_category": {
                cat: {
                    "mean_jaccard": round(float(np.mean(v["jaccards"])), 4),
                    "mean_kendall_tau": round(float(np.mean(v["taus"])), 4) if v["taus"] else None,
                }
                for cat, v in cat_stability.items()
            },
            "label_unstable_inputs": [
                {"input_id": r["input_id"], "text": r["text"]}
                for r in label_unstable
            ],
        },
        "faithfulness_summary": {
            "total_deletion_tests": len(deletions),
            "direction_correct_count": len(del_direction_correct),
            "direction_correct_rate": round(len(del_direction_correct) / len(deletions), 4) if deletions else None,
            "label_flip_count": len(del_flipped),
            "label_flip_rate": round(len(del_flipped) / len(deletions), 4) if deletions else None,
            "mean_abs_confidence_delta": round(float(np.mean(del_deltas)), 4) if del_deltas else None,
            "threshold_direction_correct": FAITHFULNESS_THRESHOLD_DIRECTION,
            "passes_faithfulness_threshold": (
                len(del_direction_correct) / len(deletions) >= FAITHFULNESS_THRESHOLD_DIRECTION
            ) if deletions else False,
            "per_category": {
                cat: {
                    "direction_correct_rate": round(v["correct"] / v["total"], 4) if v["total"] else None,
                    "label_flip_rate": round(v["flipped"] / v["total"], 4) if v["total"] else None,
                    "mean_abs_delta": round(float(np.mean(v["deltas"])), 4) if v["deltas"] else None,
                }
                for cat, v in cat_faith.items()
            },
        },
    }

    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"  Saved to {SUMMARY_PATH}")

    ss = summary["stability_summary"]
    fs = summary["faithfulness_summary"]

    print("\n--- STABILITY RESULTS ---")
    print(f"  Mean Jaccard top-5:     {ss['overall_mean_jaccard_top5']}")
    print(f"  Mean Kendall tau:       {ss['overall_mean_kendall_tau']}")
    print(f"  Label-unstable inputs:  {ss['inputs_with_label_instability']}/{ss['total_inputs']}")
    print(f"  Top-1 unanimous:        {ss['inputs_with_unanimous_top1']}/{ss['total_inputs']}")
    print(f"  Passes Jaccard >= {STABILITY_THRESHOLD_JACCARD}:  {ss['passes_jaccard_threshold']}")
    print(f"  Passes Kendall >= {STABILITY_THRESHOLD_KENDALL}:  {ss['passes_kendall_threshold']}")

    print("\n--- FAITHFULNESS RESULTS ---")
    print(f"  Direction correct:      {fs['direction_correct_count']}/{fs['total_deletion_tests']}"
          f" ({fs['direction_correct_rate']})")
    print(f"  Label flips:            {fs['label_flip_count']}/{fs['total_deletion_tests']}"
          f" ({fs['label_flip_rate']})")
    print(f"  Mean |delta|:           {fs['mean_abs_confidence_delta']}")
    print(f"  Passes direction >= {FAITHFULNESS_THRESHOLD_DIRECTION}: {fs['passes_faithfulness_threshold']}")

    print("\n--- Per-category stability ---")
    for cat, v in ss["per_category"].items():
        print(f"  {cat:30s}  Jaccard={v['mean_jaccard']:.4f}  Tau={v['mean_kendall_tau']}")

    print("\n--- Per-category faithfulness ---")
    for cat, v in fs["per_category"].items():
        print(f"  {cat:30s}  DirCorrect={v['direction_correct_rate']}  FlipRate={v['label_flip_rate']}  |Delta|={v['mean_abs_delta']}")

    print("\nDone.")


if __name__ == "__main__":
    main()
