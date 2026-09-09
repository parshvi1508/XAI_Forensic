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
from audit.metrics import bootstrap_ci, compute_pairwise_stability, count_tokenizer_mismatch


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
            status = row.get("status", "tested")
            if status == "skipped_empty":
                by_input[int(row["input_id"])] = {
                    "status": "skipped_empty",
                    "category": row["category"],
                    "text": row["text"],
                }
                continue
            entry = {
                "status": "tested",
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
            if row.get("delta_top3") and row["delta_top3"] != "":
                entry["delta_top3"] = float(row["delta_top3"])
                entry["flipped_top3"] = row["flipped_top3"] == "True"
            if row.get("delta_top5") and row["delta_top5"] != "":
                entry["delta_top5"] = float(row["delta_top5"])
                entry["flipped_top5"] = row["flipped_top5"] == "True"
            by_input[int(row["input_id"])] = entry
    return by_input


def main():
    print("[1/5] Loading raw attributions...")
    raw = load_raw_attributions(RAW_CSV_PATH)
    total_rows = sum(len(seeds) for seeds in raw.values())
    print(f"  Loaded {len(raw)} inputs, {total_rows} total rows")

    print("[2/5] Loading deletion results...")
    deletions = load_deletion_results(DELETION_CSV_PATH)
    print(f"  Loaded {len(deletions)} deletion tests")

    print("[3/6] Computing pairwise stability and tokenizer mismatch for each input...")
    stability_rows = []

    from audit.config import MODEL_NAME

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
        jaccard_ci = bootstrap_ci(pairwise["all_jaccards"])

        tok_mismatch = count_tokenizer_mismatch(text, MODEL_NAME)

        stability_rows.append({
            "input_id": input_id,
            "category": category,
            "text": text[:80],
            "mean_jaccard_top5": mean_j,
            "jaccard_ci_lower": round(jaccard_ci[0], 4),
            "jaccard_ci_upper": round(jaccard_ci[1], 4),
            "min_jaccard_top5": round(pairwise["min_jaccard"], 4),
            "mean_kendall_tau": round(pairwise["mean_kendall_tau"], 4),
            "min_kendall_tau": round(pairwise["min_kendall_tau"], 4) if not np.isnan(pairwise["min_kendall_tau"]) else "NaN",
            "label_stable": len(set(labels)) == 1,
            "confidence_std": round(float(np.std(confidences)), 6),
            "top1_unanimous": pairwise["top1_unanimous"],
            "lime_token_count": tok_mismatch["lime_token_count"],
            "wordpiece_token_count": tok_mismatch["wordpiece_token_count"],
            "token_mismatch": tok_mismatch["token_mismatch"],
        })
        print(f"  [{input_id}] {category}: Jaccard={mean_j} [{jaccard_ci[0]:.2f}, {jaccard_ci[1]:.2f}], "
              f"token_mismatch={tok_mismatch['token_mismatch']}")

    print(f"\n[4/6] Writing stability CSV...")
    with open(STABILITY_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["input_id", "category", "text", "mean_jaccard_top5",
                       "jaccard_ci_lower", "jaccard_ci_upper",
                       "min_jaccard_top5", "mean_kendall_tau", "min_kendall_tau",
                       "label_stable", "confidence_std", "top1_unanimous",
                       "lime_token_count", "wordpiece_token_count", "token_mismatch"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(stability_rows)
    print(f"  Saved {len(stability_rows)} rows to {STABILITY_CSV_PATH}")

    print("[5/6] Computing summary aggregates...")
    jaccards = [r["mean_jaccard_top5"] for r in stability_rows]
    taus = [r["mean_kendall_tau"] for r in stability_rows if not isinstance(r["mean_kendall_tau"], str)]
    label_unstable = [r for r in stability_rows if not r["label_stable"]]
    top1_unanimous = [r for r in stability_rows if r["top1_unanimous"]]

    overall_jaccard_ci = bootstrap_ci(jaccards) if jaccards else (None, None)

    mismatches = [r["token_mismatch"] for r in stability_rows]

    cat_stability = defaultdict(lambda: {"jaccards": [], "taus": []})
    for r in stability_rows:
        cat = r["category"]
        cat_stability[cat]["jaccards"].append(r["mean_jaccard_top5"])
        if not isinstance(r["mean_kendall_tau"], str):
            cat_stability[cat]["taus"].append(r["mean_kendall_tau"])

    tested_deletions = {k: v for k, v in deletions.items() if v.get("status") != "skipped_empty"}
    skipped_deletions = {k: v for k, v in deletions.items() if v.get("status") == "skipped_empty"}

    del_direction_correct = [d for d in tested_deletions.values() if d["direction_correct"]]
    del_flipped = [d for d in tested_deletions.values() if d["label_flipped"]]
    del_deltas = [abs(d["confidence_delta"]) for d in tested_deletions.values() if not np.isnan(d["confidence_delta"])]

    del3_deltas = [abs(d["delta_top3"]) for d in tested_deletions.values() if "delta_top3" in d]
    del3_flipped = [d for d in tested_deletions.values() if d.get("flipped_top3")]
    del5_deltas = [abs(d["delta_top5"]) for d in tested_deletions.values() if "delta_top5" in d]
    del5_flipped = [d for d in tested_deletions.values() if d.get("flipped_top5")]

    cat_faith = defaultdict(lambda: {"correct": 0, "flipped": 0, "total": 0, "deltas": [],
                                      "deltas_top3": [], "flipped_top3": 0,
                                      "deltas_top5": [], "flipped_top5": 0})
    for d in tested_deletions.values():
        cat = d["category"]
        cat_faith[cat]["total"] += 1
        if d["direction_correct"]:
            cat_faith[cat]["correct"] += 1
        if d["label_flipped"]:
            cat_faith[cat]["flipped"] += 1
        if not np.isnan(d["confidence_delta"]):
            cat_faith[cat]["deltas"].append(abs(d["confidence_delta"]))
        if "delta_top3" in d:
            cat_faith[cat]["deltas_top3"].append(abs(d["delta_top3"]))
            if d.get("flipped_top3"):
                cat_faith[cat]["flipped_top3"] += 1
        if "delta_top5" in d:
            cat_faith[cat]["deltas_top5"].append(abs(d["delta_top5"]))
            if d.get("flipped_top5"):
                cat_faith[cat]["flipped_top5"] += 1

    env_path = os.path.join(RESULTS_DIR, "environment.json")
    env_info = {}
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            env_info = json.load(f)

    summary = {
        "experiment_metadata": env_info,
        "stability_summary": {
            "overall_mean_jaccard_top5": round(float(np.mean(jaccards)), 4) if jaccards else None,
            "overall_jaccard_ci_95": [round(overall_jaccard_ci[0], 4), round(overall_jaccard_ci[1], 4)] if overall_jaccard_ci[0] is not None else None,
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
                    "jaccard_ci_95": [round(x, 4) for x in bootstrap_ci(v["jaccards"])] if len(v["jaccards"]) > 1 else None,
                    "mean_kendall_tau": round(float(np.mean(v["taus"])), 4) if v["taus"] else None,
                }
                for cat, v in cat_stability.items()
            },
            "label_unstable_inputs": [
                {"input_id": r["input_id"], "text": r["text"]}
                for r in label_unstable
            ],
        },
        "tokenizer_mismatch_summary": {
            "mean_mismatch": round(float(np.mean(mismatches)), 2),
            "max_mismatch": int(np.max(mismatches)),
            "inputs_with_mismatch": sum(1 for m in mismatches if m != 0),
            "total_inputs": len(mismatches),
        },
        "faithfulness_summary": {
            "total_deletion_tests": len(tested_deletions),
            "skipped_inputs": len(skipped_deletions),
            "direction_correct_count": len(del_direction_correct),
            "direction_correct_rate": round(len(del_direction_correct) / len(tested_deletions), 4) if tested_deletions else None,
            "label_flip_count": len(del_flipped),
            "label_flip_rate": round(len(del_flipped) / len(tested_deletions), 4) if tested_deletions else None,
            "mean_abs_confidence_delta": round(float(np.mean(del_deltas)), 4) if del_deltas else None,
            "threshold_direction_correct": FAITHFULNESS_THRESHOLD_DIRECTION,
            "passes_faithfulness_threshold": (
                len(del_direction_correct) / len(tested_deletions) >= FAITHFULNESS_THRESHOLD_DIRECTION
            ) if tested_deletions else False,
            "top3_deletion": {
                "mean_abs_delta": round(float(np.mean(del3_deltas)), 4) if del3_deltas else None,
                "flip_count": len(del3_flipped),
                "flip_rate": round(len(del3_flipped) / len(del3_deltas), 4) if del3_deltas else None,
            },
            "top5_deletion": {
                "mean_abs_delta": round(float(np.mean(del5_deltas)), 4) if del5_deltas else None,
                "flip_count": len(del5_flipped),
                "flip_rate": round(len(del5_flipped) / len(del5_deltas), 4) if del5_deltas else None,
            },
            "per_category": {
                cat: {
                    "direction_correct_rate": round(v["correct"] / v["total"], 4) if v["total"] else None,
                    "label_flip_rate": round(v["flipped"] / v["total"], 4) if v["total"] else None,
                    "mean_abs_delta": round(float(np.mean(v["deltas"])), 4) if v["deltas"] else None,
                    "mean_abs_delta_top3": round(float(np.mean(v["deltas_top3"])), 4) if v["deltas_top3"] else None,
                    "flip_rate_top3": round(v["flipped_top3"] / len(v["deltas_top3"]), 4) if v["deltas_top3"] else None,
                    "mean_abs_delta_top5": round(float(np.mean(v["deltas_top5"])), 4) if v["deltas_top5"] else None,
                    "flip_rate_top5": round(v["flipped_top5"] / len(v["deltas_top5"]), 4) if v["deltas_top5"] else None,
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
    ts = summary["tokenizer_mismatch_summary"]

    print("\n--- STABILITY RESULTS ---")
    ci = ss['overall_jaccard_ci_95']
    ci_str = f" [{ci[0]}, {ci[1]}]" if ci else ""
    print(f"  Mean Jaccard top-5:     {ss['overall_mean_jaccard_top5']}{ci_str} 95% CI")
    print(f"  Mean Kendall tau:       {ss['overall_mean_kendall_tau']}")
    print(f"  Label-unstable inputs:  {ss['inputs_with_label_instability']}/{ss['total_inputs']}")
    print(f"  Top-1 unanimous:        {ss['inputs_with_unanimous_top1']}/{ss['total_inputs']}")
    print(f"  Passes Jaccard >= {STABILITY_THRESHOLD_JACCARD}:  {ss['passes_jaccard_threshold']}")
    print(f"  Passes Kendall >= {STABILITY_THRESHOLD_KENDALL}:  {ss['passes_kendall_threshold']}")

    print("\n--- TOKENIZER MISMATCH ---")
    print(f"  Mean mismatch:          {ts['mean_mismatch']} extra WordPiece tokens")
    print(f"  Max mismatch:           {ts['max_mismatch']}")
    print(f"  Inputs with mismatch:   {ts['inputs_with_mismatch']}/{ts['total_inputs']}")

    print("\n--- FAITHFULNESS RESULTS ---")
    print(f"  Direction correct:      {fs['direction_correct_count']}/{fs['total_deletion_tests']}"
          f" ({fs['direction_correct_rate']})")
    print(f"  Label flips (top-1):    {fs['label_flip_count']}/{fs['total_deletion_tests']}"
          f" ({fs['label_flip_rate']})")
    print(f"  Mean |delta| (top-1):   {fs['mean_abs_confidence_delta']}")
    t3 = fs['top3_deletion']
    print(f"  Mean |delta| (top-3):   {t3['mean_abs_delta']}, flip rate: {t3['flip_rate']}")
    t5 = fs['top5_deletion']
    print(f"  Mean |delta| (top-5):   {t5['mean_abs_delta']}, flip rate: {t5['flip_rate']}")
    print(f"  Skipped inputs:         {fs['skipped_inputs']}")
    print(f"  Passes direction >= {FAITHFULNESS_THRESHOLD_DIRECTION}: {fs['passes_faithfulness_threshold']}")

    print("\n--- Per-category stability ---")
    for cat, v in ss["per_category"].items():
        ci_cat = v.get('jaccard_ci_95')
        ci_cat_str = f" [{ci_cat[0]}, {ci_cat[1]}]" if ci_cat else ""
        print(f"  {cat:30s}  Jaccard={v['mean_jaccard']:.4f}{ci_cat_str}  Tau={v['mean_kendall_tau']}")

    print("\n--- Per-category faithfulness (top-1 / top-3 / top-5) ---")
    for cat, v in fs["per_category"].items():
        print(f"  {cat:30s}  DirCorr={v['direction_correct_rate']}  "
              f"Flip1={v['label_flip_rate']}  |D1|={v['mean_abs_delta']}  "
              f"|D3|={v.get('mean_abs_delta_top3', 'N/A')}  "
              f"|D5|={v.get('mean_abs_delta_top5', 'N/A')}")

    print(f"\n[6/6] Saving summary...")
    print("\nDone.")


if __name__ == "__main__":
    main()
