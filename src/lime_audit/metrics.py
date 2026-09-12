"""Stability and faithfulness metrics for LIME audit."""

import numpy as np
from scipy import stats
from itertools import combinations
from transformers import AutoTokenizer


def jaccard_top_k(tokens_a: list[str], tokens_b: list[str], k: int = 5) -> float:
    set_a = set(tokens_a[:k])
    set_b = set(tokens_b[:k])
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def kendall_tau_top_k(
    ranking_a: list[tuple[str, float]],
    ranking_b: list[tuple[str, float]],
) -> float:
    tokens_a = {t: i for i, (t, _) in enumerate(ranking_a)}
    tokens_b = {t: i for i, (t, _) in enumerate(ranking_b)}
    common = sorted(set(tokens_a.keys()) & set(tokens_b.keys()))
    if len(common) < 2:
        return float("nan")
    ranks_a = [tokens_a[t] for t in common]
    ranks_b = [tokens_b[t] for t in common]
    tau, _ = stats.kendalltau(ranks_a, ranks_b)
    return tau


def confidence_delta(original_pos: float, modified_pos: float) -> float:
    return modified_pos - original_pos


def faithfulness_direction_correct(token_weight: float, conf_delta: float) -> bool:
    if abs(token_weight) < 1e-6 or abs(conf_delta) < 1e-6:
        return True
    return (token_weight > 0 and conf_delta < 0) or (token_weight < 0 and conf_delta > 0)


def bootstrap_ci(
    values: list[float],
    n_bootstrap: int = 10000,
    alpha: float = 0.05,
    rng_seed: int = 42,
) -> tuple[float, float]:
    rng = np.random.RandomState(rng_seed)
    arr = np.array(values)
    boot_means = np.array([
        np.mean(rng.choice(arr, size=len(arr), replace=True))
        for _ in range(n_bootstrap)
    ])
    lower = float(np.percentile(boot_means, 100 * alpha / 2))
    upper = float(np.percentile(boot_means, 100 * (1 - alpha / 2)))
    return lower, upper


def expected_calibration_error(
    predicted_probs: list[float],
    true_labels: list[int],
    n_bins: int = 10,
) -> dict:
    probs = np.array(predicted_probs)
    labels = np.array(true_labels)
    brier = float(np.mean((probs - labels) ** 2))
    bin_edges = np.linspace(0, 1, n_bins + 1)
    bin_data = []
    ece = 0.0
    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        mask = (probs >= lo) & (probs < hi) if i < n_bins - 1 else (probs >= lo) & (probs <= hi)
        count = int(mask.sum())
        if count == 0:
            bin_data.append({"bin_lo": round(float(lo), 2), "bin_hi": round(float(hi), 2),
                             "count": 0, "mean_predicted": None, "mean_actual": None, "gap": None})
            continue
        mean_pred = float(probs[mask].mean())
        mean_actual = float(labels[mask].mean())
        gap = abs(mean_pred - mean_actual)
        ece += gap * count
        bin_data.append({"bin_lo": round(float(lo), 2), "bin_hi": round(float(hi), 2),
                         "count": count, "mean_predicted": round(mean_pred, 4),
                         "mean_actual": round(mean_actual, 4), "gap": round(gap, 4)})
    ece = float(ece / len(probs)) if len(probs) > 0 else 0.0
    return {"ece": round(ece, 4), "brier": round(brier, 4), "n_bins": n_bins,
            "n_samples": len(probs), "bin_data": bin_data}


def confidence_bucket_analysis(
    inputs: list[dict],
    buckets: list[tuple[float, float]] = None,
) -> dict:
    if buckets is None:
        buckets = [(0.0, 0.9), (0.9, 0.99), (0.99, 1.001)]
    result = {}
    for lo, hi in buckets:
        label = f"{lo:.2f}-{hi:.2f}"
        subset = [x for x in inputs if lo <= x["confidence"] < hi]
        if not subset:
            result[label] = {"count": 0}
            continue
        dir_correct = sum(1 for x in subset if x["direction_correct"])
        flipped = sum(1 for x in subset if x["label_flipped"])
        deltas = [x["abs_delta"] for x in subset]
        result[label] = {
            "count": len(subset),
            "direction_correct_rate": round(dir_correct / len(subset), 4),
            "label_flip_rate": round(flipped / len(subset), 4),
            "mean_abs_delta": round(float(np.mean(deltas)), 6),
            "max_abs_delta": round(float(np.max(deltas)), 6),
            "min_abs_delta": round(float(np.min(deltas)), 6),
            "input_ids": [x.get("input_id") for x in subset],
        }
    return result


def count_tokenizer_mismatch(text: str, model_name_or_tokenizer) -> dict:
    lime_tokens = text.split()
    if isinstance(model_name_or_tokenizer, str):
        tokenizer = AutoTokenizer.from_pretrained(model_name_or_tokenizer)
    else:
        tokenizer = model_name_or_tokenizer
    wp_tokens = tokenizer.tokenize(text)
    return {
        "lime_token_count": len(lime_tokens),
        "wordpiece_token_count": len(wp_tokens),
        "token_mismatch": len(wp_tokens) - len(lime_tokens),
    }


def compute_pairwise_stability(
    seed_results: dict[int, list[tuple[str, float]]],
    k: int = 5,
) -> dict:
    seeds = sorted(seed_results.keys())
    jaccards = []
    taus = []

    for s1, s2 in combinations(seeds, 2):
        tokens_a = [t for t, _ in seed_results[s1]]
        tokens_b = [t for t, _ in seed_results[s2]]
        jaccards.append(jaccard_top_k(tokens_a, tokens_b, k))
        taus.append(kendall_tau_top_k(seed_results[s1], seed_results[s2]))

    top1_tokens = [seed_results[s][0][0] if seed_results[s] else "" for s in seeds]

    return {
        "mean_jaccard": float(np.mean(jaccards)),
        "min_jaccard": float(np.min(jaccards)),
        "mean_kendall_tau": float(np.nanmean(taus)),
        "min_kendall_tau": float(np.nanmin(taus)) if not all(np.isnan(taus)) else float("nan"),
        "top1_unanimous": len(set(top1_tokens)) == 1 and top1_tokens[0] != "",
        "all_jaccards": jaccards,
        "all_taus": taus,
    }
