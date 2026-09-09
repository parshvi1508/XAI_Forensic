"""
Analyse LIME audit results - compute stability and faithfulness aggregates.
"""

import csv
import json
import os
from collections import defaultdict

import numpy as np

from lime_audit.config import (
    FAITHFULNESS_THRESHOLD_DIRECTION,
    LIME_NUM_FEATURES,
    STABILITY_THRESHOLD_JACCARD,
    STABILITY_THRESHOLD_KENDALL,
    TOP_K_FOR_JACCARD,
)
from lime_audit.metrics import bootstrap_ci, compute_pairwise_stability, count_tokenizer_mismatch


def load_raw_attributions(path, num_features=LIME_NUM_FEATURES):
    by_input = defaultdict(dict)
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("input_id") or not row.get("seed"):
                continue
            input_id = int(row["input_id"])
            seed = int(row["seed"])
            tokens = []
            for i in range(1, num_features + 1):
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


def load_deletion_results(path):
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


def analyse(output_dir, model_name):
    raw_csv = os.path.join(output_dir, "raw_attributions.csv")
    del_csv = os.path.join(output_dir, "deletion_faithfulness.csv")
    stability_csv = os.path.join(output_dir, "stability_metrics.csv")
    summary_path = os.path.join(output_dir, "summary.json")

    print("[1/4] Loading raw attributions...")
    raw = load_raw_attributions(raw_csv)
    print(f"  {len(raw)} inputs loaded")

    print("[2/4] Loading deletion results...")
    deletions = load_deletion_results(del_csv)
    print(f"  {len(deletions)} deletion tests loaded")

    print("[3/4] Computing stability and tokenizer mismatch...")
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
        jaccard_ci = bootstrap_ci(pairwise["all_jaccards"])
        tok_mismatch = count_tokenizer_mismatch(text, model_name)

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

    fieldnames = [
        "input_id", "category", "text", "mean_jaccard_top5",
        "jaccard_ci_lower", "jaccard_ci_upper",
        "min_jaccard_top5", "mean_kendall_tau", "min_kendall_tau",
        "label_stable", "confidence_std", "top1_unanimous",
        "lime_token_count", "wordpiece_token_count", "token_mismatch",
    ]
    with open(stability_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(stability_rows)
    print(f"  Saved stability CSV: {stability_csv}")

    print("[4/4] Computing summary...")
    jaccards = [r["mean_jaccard_top5"] for r in stability_rows]
    taus = [r["mean_kendall_tau"] for r in stability_rows if not isinstance(r["mean_kendall_tau"], str)]
    overall_jaccard_ci = bootstrap_ci(jaccards) if jaccards else (None, None)
    mismatches = [r["token_mismatch"] for r in stability_rows]

    cat_stability = defaultdict(lambda: {"jaccards": [], "taus": []})
    for r in stability_rows:
        cat = r["category"]
        cat_stability[cat]["jaccards"].append(r["mean_jaccard_top5"])
        if not isinstance(r["mean_kendall_tau"], str):
            cat_stability[cat]["taus"].append(r["mean_kendall_tau"])

    tested = {k: v for k, v in deletions.items() if v.get("status") != "skipped_empty"}
    skipped = {k: v for k, v in deletions.items() if v.get("status") == "skipped_empty"}

    del_correct = [d for d in tested.values() if d["direction_correct"]]
    del_flipped = [d for d in tested.values() if d["label_flipped"]]
    del_deltas = [abs(d["confidence_delta"]) for d in tested.values() if not np.isnan(d["confidence_delta"])]

    del3_deltas = [abs(d["delta_top3"]) for d in tested.values() if "delta_top3" in d]
    del3_flipped = [d for d in tested.values() if d.get("flipped_top3")]
    del5_deltas = [abs(d["delta_top5"]) for d in tested.values() if "delta_top5" in d]
    del5_flipped = [d for d in tested.values() if d.get("flipped_top5")]

    env_path = os.path.join(output_dir, "environment.json")
    env_info = {}
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            env_info = json.load(f)

    cat_faith = defaultdict(lambda: {"correct": 0, "flipped": 0, "total": 0, "deltas": [],
                                      "deltas_top3": [], "flipped_top3": 0,
                                      "deltas_top5": [], "flipped_top5": 0})
    for d in tested.values():
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

    summary = {
        "experiment_metadata": env_info,
        "stability_summary": {
            "overall_mean_jaccard_top5": round(float(np.mean(jaccards)), 4) if jaccards else None,
            "overall_jaccard_ci_95": [round(overall_jaccard_ci[0], 4), round(overall_jaccard_ci[1], 4)] if overall_jaccard_ci[0] is not None else None,
            "overall_mean_kendall_tau": round(float(np.mean(taus)), 4) if taus else None,
            "inputs_with_perfect_jaccard": sum(1 for j in jaccards if j >= 1.0),
            "inputs_with_jaccard_below_threshold": sum(1 for j in jaccards if j < STABILITY_THRESHOLD_JACCARD),
            "inputs_with_label_instability": sum(1 for r in stability_rows if not r["label_stable"]),
            "inputs_with_unanimous_top1": sum(1 for r in stability_rows if r["top1_unanimous"]),
            "total_inputs": len(stability_rows),
            "threshold_jaccard": STABILITY_THRESHOLD_JACCARD,
            "threshold_kendall": STABILITY_THRESHOLD_KENDALL,
            "per_category": {
                cat: {
                    "mean_jaccard": round(float(np.mean(v["jaccards"])), 4),
                    "jaccard_ci_95": [round(x, 4) for x in bootstrap_ci(v["jaccards"])] if len(v["jaccards"]) > 1 else None,
                    "mean_kendall_tau": round(float(np.mean(v["taus"])), 4) if v["taus"] else None,
                }
                for cat, v in cat_stability.items()
            },
        },
        "tokenizer_mismatch_summary": {
            "mean_mismatch": round(float(np.mean(mismatches)), 2),
            "max_mismatch": int(np.max(mismatches)),
            "inputs_with_mismatch": sum(1 for m in mismatches if m != 0),
            "total_inputs": len(mismatches),
        },
        "faithfulness_summary": {
            "total_deletion_tests": len(tested),
            "skipped_inputs": len(skipped),
            "direction_correct_count": len(del_correct),
            "direction_correct_rate": round(len(del_correct) / len(tested), 4) if tested else None,
            "label_flip_count": len(del_flipped),
            "label_flip_rate": round(len(del_flipped) / len(tested), 4) if tested else None,
            "mean_abs_confidence_delta": round(float(np.mean(del_deltas)), 4) if del_deltas else None,
            "threshold_direction_correct": FAITHFULNESS_THRESHOLD_DIRECTION,
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

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    ss = summary["stability_summary"]
    fs = summary["faithfulness_summary"]
    ts = summary["tokenizer_mismatch_summary"]

    print(f"\n--- STABILITY ---")
    ci = ss.get("overall_jaccard_ci_95")
    ci_str = f" [{ci[0]}, {ci[1]}]" if ci else ""
    print(f"  Mean Jaccard top-5: {ss['overall_mean_jaccard_top5']}{ci_str}")
    print(f"  Mean Kendall tau:   {ss['overall_mean_kendall_tau']}")

    print(f"\n--- TOKENIZER MISMATCH ---")
    print(f"  Mean mismatch: {ts['mean_mismatch']} extra WordPiece tokens")

    print(f"\n--- FAITHFULNESS ---")
    print(f"  Direction correct: {fs['direction_correct_rate']}")
    print(f"  Flip rate (top-1): {fs['label_flip_rate']}")
    t3 = fs["top3_deletion"]
    t5 = fs["top5_deletion"]
    print(f"  Mean |delta| top-3: {t3['mean_abs_delta']}, flip rate: {t3['flip_rate']}")
    print(f"  Mean |delta| top-5: {t5['mean_abs_delta']}, flip rate: {t5['flip_rate']}")

    print(f"\nSaved: {summary_path}")
    return summary_path
