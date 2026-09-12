"""
E4: LIME vs Random Token Deletion Baseline

For each tested input, compare LIME's top-1 deletion delta against the mean
deletion delta from removing a randomly chosen token (10 trials, fixed seed).

Reads existing data; does NOT re-run LIME. Requires one model load (~30s).

Usage:
    python -m audit.e4_random_baseline
    python -m audit.e4_random_baseline --k 3    # compare top-k removal vs random-k
"""

import argparse
import csv
import json
import os
import random

import numpy as np

from audit.config import DELETION_CSV_PATH, MODEL_NAME, RAW_CSV_PATH, RESULTS_DIR
from audit.runner import get_positive_score, load_model, make_predict_fn

_RANDOM_TRIALS = 10
_RANDOM_SEED = 99


def load_canonical_lime(raw_path: str) -> dict[int, dict]:
    """Return {input_id: {tokens, base_pos, base_label, text, category}} for seed=42."""
    canon = {}
    with open(raw_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if int(row["seed"]) != 42:
                continue
            iid = int(row["input_id"])
            tokens = []
            for i in range(1, 11):
                t = row.get(f"token_{i}", "")
                w = row.get(f"weight_{i}", 0)
                if t:
                    tokens.append((t, float(w)))
            canon[iid] = {
                "tokens": tokens,
                "base_pos": float(row["base_positive_score"]),
                "base_label": row["base_label"],
                "text": row["text"],
                "category": row["category"],
            }
    return canon


def load_lime_deltas(del_path: str) -> dict[int, float]:
    """Return {input_id: abs(confidence_delta)} for tested inputs."""
    deltas = {}
    with open(del_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("status") not in (None, "", "tested"):
                continue
            delta = row.get("confidence_delta", "")
            if delta and delta not in ("", "nan"):
                deltas[int(row["input_id"])] = abs(float(delta))
    return deltas


def run_random_deletion(text: str, k: int, predict_fn, rng: random.Random) -> dict | None:
    words = text.split()
    if len(words) <= k:
        return None
    indices = rng.sample(range(len(words)), k)
    masked = [w for i, w in enumerate(words) if i not in set(indices)]
    if not masked:
        return None
    removed = [words[i] for i in sorted(indices)]
    proba = predict_fn([" ".join(masked)])
    return {
        "removed": removed,
        "modified_pos": float(proba[0][1]),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--k", type=int, default=1, help="Number of tokens to delete (default 1)")
    args = parser.parse_args()

    k = args.k
    out_path = os.path.join(RESULTS_DIR, f"e4_random_baseline_k{k}.json")
    out_csv = os.path.join(RESULTS_DIR, f"e4_random_baseline_k{k}.csv")

    print(f"E4: LIME vs Random Deletion Baseline (k={k})")
    print(f"  Random trials per input: {_RANDOM_TRIALS}")
    print(f"  Random seed: {_RANDOM_SEED}")

    print("\n[1/4] Loading existing LIME data...")
    canon = load_canonical_lime(RAW_CSV_PATH)
    lime_deltas = load_lime_deltas(DELETION_CSV_PATH)
    tested_ids = sorted(lime_deltas.keys())
    print(f"  {len(tested_ids)} inputs with LIME deletion results")

    print("[2/4] Loading model (needed for random deletion calls)...")
    model = load_model(MODEL_NAME)
    predict_fn = make_predict_fn(model)

    rng = random.Random(_RANDOM_SEED)
    results = []

    print(f"\n[3/4] Running random deletions ({_RANDOM_TRIALS} trials × {len(tested_ids)} inputs)...")
    for input_id in tested_ids:
        if input_id not in canon:
            print(f"  [{input_id}] No canonical LIME data, skipping")
            continue

        c = canon[input_id]
        text = c["text"]
        words = text.split()

        if len(words) <= k:
            print(f"  [{input_id}] Only {len(words)} words, can't delete {k}, skipping")
            continue

        lime_top_k = [t for t, _ in c["tokens"][:k]]
        lime_abs_delta = lime_deltas.get(input_id, float("nan"))

        random_abs_deltas = []
        for _ in range(_RANDOM_TRIALS):
            r = run_random_deletion(text, k, predict_fn, rng)
            if r is not None:
                delta = abs(r["modified_pos"] - c["base_pos"])
                random_abs_deltas.append(delta)

        if not random_abs_deltas:
            print(f"  [{input_id}] All random trials failed, skipping")
            continue

        mean_random = float(np.mean(random_abs_deltas))
        lime_wins = lime_abs_delta > mean_random

        results.append({
            "input_id": input_id,
            "category": c["category"],
            "text": text[:80],
            "base_label": c["base_label"],
            "n_words": len(words),
            "lime_top_k": lime_top_k,
            "lime_abs_delta": round(lime_abs_delta, 6),
            "mean_random_abs_delta": round(mean_random, 6),
            "lime_wins": lime_wins,
            "lime_vs_random_ratio": round(lime_abs_delta / mean_random, 4) if mean_random > 0 else None,
            "random_deltas": [round(d, 6) for d in random_abs_deltas],
        })
        print(f"  [{input_id}] {c['category']}: LIME|Δ|={lime_abs_delta:.4f}  "
              f"Random|Δ|={mean_random:.4f}  LIME_wins={lime_wins}")

    print(f"\n[4/4] Computing summary...")
    lime_wins_count = sum(1 for r in results if r["lime_wins"])
    lime_deltas_arr = np.array([r["lime_abs_delta"] for r in results])
    random_deltas_arr = np.array([r["mean_random_abs_delta"] for r in results])

    summary = {
        "k": k,
        "random_trials": _RANDOM_TRIALS,
        "random_seed": _RANDOM_SEED,
        "n_inputs": len(results),
        "lime_wins": lime_wins_count,
        "lime_wins_rate": round(lime_wins_count / len(results), 4) if results else None,
        "mean_lime_abs_delta": round(float(np.mean(lime_deltas_arr)), 6),
        "mean_random_abs_delta": round(float(np.mean(random_deltas_arr)), 6),
        "median_lime_abs_delta": round(float(np.median(lime_deltas_arr)), 6),
        "median_random_abs_delta": round(float(np.median(random_deltas_arr)), 6),
        "inputs": results,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"  Saved to {out_path}")

    fieldnames = ["input_id", "category", "text", "base_label", "n_words",
                  "lime_top_k", "lime_abs_delta", "mean_random_abs_delta",
                  "lime_wins", "lime_vs_random_ratio"]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({k2: r[k2] for k2 in fieldnames})
    print(f"  CSV saved to {out_csv}")

    print(f"\n--- E4 RESULTS (k={k}) ---")
    print(f"  n inputs:            {summary['n_inputs']}")
    print(f"  LIME beats random:   {lime_wins_count}/{len(results)} ({summary['lime_wins_rate']})")
    print(f"  Mean LIME |Δ|:       {summary['mean_lime_abs_delta']}")
    print(f"  Mean random |Δ|:     {summary['mean_random_abs_delta']}")
    print(f"  Median LIME |Δ|:     {summary['median_lime_abs_delta']}")
    print(f"  Median random |Δ|:   {summary['median_random_abs_delta']}")


if __name__ == "__main__":
    main()
