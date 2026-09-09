"""
Generate charts for LIME audit results.
"""

import csv
import os

import matplotlib.pyplot as plt
import numpy as np


CATEGORY_COLORS = {
    "negation_minimal_pairs": "#e63946",
    "lexical_shortcuts": "#457b9d",
    "ambiguity": "#2a9d8f",
    "distribution_style_shift": "#e9c46a",
    "strong_baselines": "#f4a261",
    "edge_cases": "#264653",
}

CATEGORY_LABELS = {
    "negation_minimal_pairs": "Negation",
    "lexical_shortcuts": "Lexical Shortcuts",
    "ambiguity": "Ambiguity",
    "distribution_style_shift": "Distribution Shift",
    "strong_baselines": "Strong Baselines",
    "edge_cases": "Edge Cases",
}

STABILITY_THRESHOLD = 0.6


def load_stability(output_dir):
    rows = []
    path = os.path.join(output_dir, "stability_metrics.csv")
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "input_id": int(row["input_id"]),
                "category": row["category"],
                "text": row["text"],
                "mean_jaccard": float(row["mean_jaccard_top5"]),
                "ci_lower": float(row.get("jaccard_ci_lower", row["mean_jaccard_top5"])),
                "ci_upper": float(row.get("jaccard_ci_upper", row["mean_jaccard_top5"])),
            })
    return rows


def load_deletion(output_dir):
    rows = []
    path = os.path.join(output_dir, "deletion_faithfulness.csv")
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("status") == "skipped_empty":
                continue
            entry = {
                "input_id": int(row["input_id"]),
                "category": row["category"],
                "confidence_delta": abs(float(row["confidence_delta"])),
                "label_flipped": row["label_flipped"] == "True",
            }
            if row.get("delta_top3") and row["delta_top3"] != "":
                entry["delta_top3"] = abs(float(row["delta_top3"]))
                entry["flipped_top3"] = row["flipped_top3"] == "True"
            if row.get("delta_top5") and row["delta_top5"] != "":
                entry["delta_top5"] = abs(float(row["delta_top5"]))
                entry["flipped_top5"] = row["flipped_top5"] == "True"
            rows.append(entry)
    return rows


def chart_jaccard(stability_rows, output_dir):
    sorted_rows = sorted(stability_rows, key=lambda r: r["mean_jaccard"])
    fig, ax = plt.subplots(figsize=(12, 6))

    x = np.arange(len(sorted_rows))
    colors = [CATEGORY_COLORS.get(r["category"], "#888") for r in sorted_rows]
    means = [r["mean_jaccard"] for r in sorted_rows]
    ci_lower = [r["mean_jaccard"] - r["ci_lower"] for r in sorted_rows]
    ci_upper = [r["ci_upper"] - r["mean_jaccard"] for r in sorted_rows]

    ax.bar(x, means, color=colors, edgecolor="white", linewidth=0.5)
    ax.errorbar(x, means, yerr=[ci_lower, ci_upper], fmt="none", ecolor="#333333",
                capsize=3, linewidth=1)
    ax.axhline(y=STABILITY_THRESHOLD, color="#cc0000", linestyle="--",
               linewidth=1.5, label=f"Threshold ({STABILITY_THRESHOLD})")

    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in CATEGORY_COLORS.values()]
    labels = list(CATEGORY_LABELS.values())
    ax.legend(handles, labels, loc="upper left", fontsize=8, ncol=2)

    ax.set_xlabel("Inputs (sorted by stability)", fontsize=11)
    ax.set_ylabel("Mean Jaccard Top-5 Overlap", fontsize=11)
    ax.set_title("LIME Attribution Stability Across 5 Random Seeds", fontsize=13, fontweight="bold")
    ax.set_ylim(0, 1.1)
    ax.set_xticks([])

    fig.tight_layout()
    path = os.path.join(output_dir, "chart_jaccard_by_input.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Saved: {path}")


def chart_faithfulness(deletion_rows, output_dir):
    cat_deltas = {}
    for row in deletion_rows:
        cat = row["category"]
        if cat not in cat_deltas:
            cat_deltas[cat] = {"top1": [], "top3": [], "top5": [], "flip1": [], "flip3": [], "flip5": []}
        cat_deltas[cat]["top1"].append(row["confidence_delta"])
        cat_deltas[cat]["flip1"].append(row["label_flipped"])
        if "delta_top3" in row:
            cat_deltas[cat]["top3"].append(row["delta_top3"])
            cat_deltas[cat]["flip3"].append(row.get("flipped_top3", False))
        if "delta_top5" in row:
            cat_deltas[cat]["top5"].append(row["delta_top5"])
            cat_deltas[cat]["flip5"].append(row.get("flipped_top5", False))

    display_order = [
        "strong_baselines", "distribution_style_shift", "edge_cases",
        "ambiguity", "negation_minimal_pairs", "lexical_shortcuts",
    ]
    cats_present = [c for c in display_order if c in cat_deltas]
    if not cats_present:
        cats_present = list(cat_deltas.keys())

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))
    x = np.arange(len(cats_present))
    width = 0.25

    means_1 = [np.mean(cat_deltas[c]["top1"]) if cat_deltas[c]["top1"] else 0 for c in cats_present]
    means_3 = [np.mean(cat_deltas[c]["top3"]) if cat_deltas[c]["top3"] else 0 for c in cats_present]
    means_5 = [np.mean(cat_deltas[c]["top5"]) if cat_deltas[c]["top5"] else 0 for c in cats_present]

    ax1.bar(x - width, means_1, width, label="Top-1 removed", color="#264653")
    ax1.bar(x, means_3, width, label="Top-3 removed", color="#2a9d8f")
    ax1.bar(x + width, means_5, width, label="Top-5 removed", color="#e9c46a")

    ax1.set_xlabel("Category", fontsize=10)
    ax1.set_ylabel("Mean |Confidence Delta|", fontsize=10)
    ax1.set_title("Impact of Removing Top-K Tokens", fontsize=12, fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels([CATEGORY_LABELS.get(c, c) for c in cats_present], rotation=30, ha="right", fontsize=8)
    ax1.legend(fontsize=8)
    ax1.set_ylim(0, 1.1)

    flip1 = [np.mean(cat_deltas[c]["flip1"]) * 100 if cat_deltas[c]["flip1"] else 0 for c in cats_present]
    flip3 = [np.mean(cat_deltas[c]["flip3"]) * 100 if cat_deltas[c]["flip3"] else 0 for c in cats_present]
    flip5 = [np.mean(cat_deltas[c]["flip5"]) * 100 if cat_deltas[c]["flip5"] else 0 for c in cats_present]

    ax2.bar(x - width, flip1, width, label="Top-1 removed", color="#264653")
    ax2.bar(x, flip3, width, label="Top-3 removed", color="#2a9d8f")
    ax2.bar(x + width, flip5, width, label="Top-5 removed", color="#e9c46a")

    ax2.set_xlabel("Category", fontsize=10)
    ax2.set_ylabel("Label Flip Rate (%)", fontsize=10)
    ax2.set_title("Label Flip Rate by Deletion Depth", fontsize=12, fontweight="bold")
    ax2.set_xticks(x)
    ax2.set_xticklabels([CATEGORY_LABELS.get(c, c) for c in cats_present], rotation=30, ha="right", fontsize=8)
    ax2.legend(fontsize=8)
    ax2.set_ylim(0, 110)

    fig.tight_layout()
    path = os.path.join(output_dir, "chart_faithfulness_bars.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Saved: {path}")


def generate_charts(output_dir):
    print("Generating charts...")
    stability = load_stability(output_dir)
    deletion = load_deletion(output_dir)
    chart_jaccard(stability, output_dir)
    chart_faithfulness(deletion, output_dir)
    print("Done.")
