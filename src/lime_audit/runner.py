"""
LIME Audit Runner - runs LIME on test inputs, measures stability and faithfulness.
"""

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

from lime_audit.config import (
    CANONICAL_SEED,
    LIME_CLASS_NAMES,
    LIME_NUM_FEATURES,
    LIME_NUM_SAMPLES,
    RANDOM_SEEDS,
)
from lime_audit.metrics import faithfulness_direction_correct


def _get_default_test_set_path():
    return os.path.join(os.path.dirname(__file__), "default_test_set.json")


def load_test_set(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["inputs"]


def load_model(model_name: str):
    print(f"Loading model: {model_name}")
    model = hf_pipeline("text-classification", model=model_name, top_k=None)
    print("Model loaded.")
    return model


_POSITIVE_LABELS = {"POSITIVE", "positive"}


def get_positive_score(pipeline_output: list) -> float:
    for item in pipeline_output[0]:
        if item["label"] in _POSITIVE_LABELS:
            return item["score"]
    known = [item["label"] for item in pipeline_output[0]]
    raise ValueError(
        f"No positive label found in {known}. "
        f"Expected one of: {_POSITIVE_LABELS}"
    )


def make_predict_fn(model):
    def predict_proba(texts: list[str]) -> np.ndarray:
        results = []
        for text in texts:
            output = model(text, truncation=True, max_length=512)
            pos = get_positive_score(output)
            results.append([1.0 - pos, pos])
        return np.array(results)
    return predict_proba


import re as _re

# Tokenizer mismatch note: LIME splits on whitespace; HuggingFace WordPiece splits further
# (e.g., "I'm" → ["i", "'", "m"]). This is a fundamental method-level mismatch that cannot
# be fixed by a parameter — LIME perturbation operates on whitespace tokens, not subword tokens.
# The function below partially reduces mismatch by expanding common contractions before LIME sees
# the text, so LIME's whitespace tokens better align with WordPiece word-level groups.
# Limitation: only helps for the listed contraction patterns; compound nouns and rare forms
# are unchanged. The WordPiece mismatch count may drop from mean 1.55 → ~0.8 on this test set.
_CONTRACTION_EXPANSIONS = [
    (_re.compile(r"\b(I|you|he|she|we|they|it|who|that)'m\b", _re.IGNORECASE), r"\1 'm"),
    (_re.compile(r"\b(is|are|was|were|have|has|had|do|does|did|would|could|should|will|can|might|must|shall|need|dare)'t\b", _re.IGNORECASE), r"\1 't"),
    (_re.compile(r"\b(I|you|he|she|we|they|it|who|that)'ve\b", _re.IGNORECASE), r"\1 've"),
    (_re.compile(r"\b(I|you|he|she|we|they|it|who|that)'ll\b", _re.IGNORECASE), r"\1 'll"),
    (_re.compile(r"\b(I|you|he|she|we|they|it|who|that)'d\b", _re.IGNORECASE), r"\1 'd"),
    (_re.compile(r"\b(I|you|he|she|we|they|it|who|that|let)'re\b", _re.IGNORECASE), r"\1 're"),
]


def expand_contractions(text: str) -> str:
    """Insert space before apostrophe suffixes to reduce LIME/WordPiece mismatch.

    Partial mitigation only — does not eliminate the mismatch, just reduces it
    for the most common English contraction patterns.
    """
    for pattern, replacement in _CONTRACTION_EXPANSIONS:
        text = pattern.sub(replacement, text)
    return text


def run_lime_single(
    text,
    predict_fn,
    seed,
    num_samples=LIME_NUM_SAMPLES,
    num_features=LIME_NUM_FEATURES,
    expand_contractions_before_lime=False,
):
    # Optionally expand contractions to partially reduce tokenizer mismatch.
    # Default off to preserve backward compatibility with existing results.
    lime_text = expand_contractions(text) if expand_contractions_before_lime else text
    np.random.seed(seed)
    explainer = LimeTextExplainer(class_names=LIME_CLASS_NAMES, random_state=seed)
    explanation = explainer.explain_instance(lime_text, predict_fn, num_features=num_features, num_samples=num_samples)
    token_weights = explanation.as_list()
    sorted_by_abs = sorted(token_weights, key=lambda x: abs(x[1]), reverse=True)
    return {"tokens": sorted_by_abs, "lime_score": explanation.score, "intercept": explanation.intercept.get(1, 0.0)}


def run_deletion_test(text, top_token, predict_fn):
    words = text.split()

    first_idx = None
    for i, w in enumerate(words):
        if w == top_token:
            first_idx = i
            break
    if first_idx is None:
        for i, w in enumerate(words):
            if top_token.lower() in w.lower():
                first_idx = i
                break

    if first_idx is None:
        return {"modified_text": text, "modified_label": "error", "modified_positive_score": float("nan")}

    masked_words = words[:first_idx] + words[first_idx + 1:]

    if not masked_words:
        return {"modified_text": "", "modified_label": "error", "modified_positive_score": float("nan")}
    masked_text = " ".join(masked_words)
    proba = predict_fn([masked_text])
    modified_pos = float(proba[0][1])
    return {"modified_text": masked_text, "modified_label": "positive" if modified_pos >= 0.5 else "negative", "modified_positive_score": modified_pos}


def run_deletion_topk(text, top_tokens, predict_fn):
    words = text.split()
    token_set = set(top_tokens)
    masked_words = [w for w in words if w not in token_set]
    if not masked_words:
        return {"modified_text": "", "modified_label": "error", "modified_positive_score": float("nan")}
    masked_text = " ".join(masked_words)
    proba = predict_fn([masked_text])
    modified_pos = float(proba[0][1])
    return {"modified_text": masked_text, "modified_label": "positive" if modified_pos >= 0.5 else "negative", "modified_positive_score": modified_pos}


def get_environment_info(model_name):
    import lime
    import scipy
    import sklearn
    import torch
    import transformers
    return {
        "model": model_name,
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
    ["input_id", "category", "text", "seed", "base_label", "base_confidence", "base_positive_score"]
    + [f"token_{i}" for i in range(1, LIME_NUM_FEATURES + 1)]
    + [f"weight_{i}" for i in range(1, LIME_NUM_FEATURES + 1)]
    + ["lime_score", "duration_ms"]
)

DELETION_FIELDNAMES = [
    "input_id", "category", "text", "status",
    "removed_token", "token_lime_weight",
    "original_label", "original_positive_score",
    "modified_label", "modified_positive_score",
    "confidence_delta", "label_flipped", "direction_correct",
    "removed_top3", "delta_top3", "flipped_top3",
    "removed_top5", "delta_top5", "flipped_top5",
]


def run_audit(model_name: str, test_set_path: str = None, output_dir: str = None):
    if test_set_path is None:
        test_set_path = _get_default_test_set_path()
    if output_dir is None:
        output_dir = os.path.join(os.getcwd(), "lime_audit_results")

    os.makedirs(output_dir, exist_ok=True)
    raw_csv = os.path.join(output_dir, "raw_attributions.csv")
    del_csv = os.path.join(output_dir, "deletion_faithfulness.csv")

    inputs = load_test_set(test_set_path)
    print(f"Loaded {len(inputs)} inputs")

    model = load_model(model_name)
    predict_fn = make_predict_fn(model)
    env_info = get_environment_info(model_name)

    start_total = time.perf_counter()
    skipped_inputs = []
    canonical_results = {}

    with open(raw_csv, "w", newline="", encoding="utf-8") as raw_f:
        raw_writer = csv.DictWriter(raw_f, fieldnames=RAW_FIELDNAMES)
        raw_writer.writeheader()

        for inp in inputs:
            input_id = inp["id"]
            text = inp["text"]
            category = inp.get("category", "uncategorized")

            if not text.strip():
                skipped_inputs.append({"input_id": input_id, "category": category, "reason": "empty_or_whitespace"})
                print(f"  [{input_id}] SKIP empty input")
                continue

            base_proba = predict_fn([text])
            base_pos = float(base_proba[0][1])
            base_label = "positive" if base_pos >= 0.5 else "negative"
            base_conf = base_pos if base_label == "positive" else 1.0 - base_pos
            print(f"  [{input_id}] {base_label} ({base_conf:.4f})")

            for seed in RANDOM_SEEDS:
                start_call = time.perf_counter()
                try:
                    result = run_lime_single(text, predict_fn, seed)
                except Exception as e:
                    print(f"    Seed {seed}: ERROR {e}")
                    continue

                duration_ms = round((time.perf_counter() - start_call) * 1000)
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
                raw_f.flush()

                if seed == CANONICAL_SEED:
                    canonical_results[input_id] = {
                        "tokens": tokens, "base_label": base_label,
                        "base_pos": base_pos, "base_conf": base_conf,
                    }

    print(f"\nRunning deletion faithfulness tests...")

    with open(del_csv, "w", newline="", encoding="utf-8") as del_f:
        del_writer = csv.DictWriter(del_f, fieldnames=DELETION_FIELDNAMES)
        del_writer.writeheader()

        for inp in inputs:
            input_id = inp["id"]
            text = inp["text"]
            category = inp.get("category", "uncategorized")

            if not text.strip():
                row = {"input_id": input_id, "category": category, "text": repr(text), "status": "skipped_empty"}
                for field in DELETION_FIELDNAMES:
                    row.setdefault(field, "")
                del_writer.writerow(row)
                del_f.flush()
                continue

            if input_id not in canonical_results:
                continue

            canon = canonical_results[input_id]
            if not canon["tokens"]:
                continue

            top_token = canon["tokens"][0][0]
            top_weight = canon["tokens"][0][1]
            deletion = run_deletion_test(text, top_token, predict_fn)

            if deletion["modified_label"] == "error":
                row = {"input_id": input_id, "category": category, "text": text,
                       "status": "skipped_single_token",
                       "removed_token": top_token, "token_lime_weight": round(top_weight, 6),
                       "original_label": canon["base_label"],
                       "original_positive_score": round(canon["base_pos"], 6)}
                for field in DELETION_FIELDNAMES:
                    row.setdefault(field, "")
                del_writer.writerow(row)
                del_f.flush()
                continue

            delta = deletion["modified_positive_score"] - canon["base_pos"]
            flipped = deletion["modified_label"] != canon["base_label"]
            dir_correct = faithfulness_direction_correct(top_weight, delta)

            top3_tokens = [t for t, _ in canon["tokens"][:3]]
            del3 = run_deletion_topk(text, top3_tokens, predict_fn)
            delta3 = flipped3 = ""
            if del3["modified_label"] != "error":
                delta3 = round(del3["modified_positive_score"] - canon["base_pos"], 6)
                flipped3 = del3["modified_label"] != canon["base_label"]

            top5_tokens = [t for t, _ in canon["tokens"][:5]]
            del5 = run_deletion_topk(text, top5_tokens, predict_fn)
            delta5 = flipped5 = ""
            if del5["modified_label"] != "error":
                delta5 = round(del5["modified_positive_score"] - canon["base_pos"], 6)
                flipped5 = del5["modified_label"] != canon["base_label"]

            row = {
                "input_id": input_id, "category": category, "text": text,
                "status": "tested",
                "removed_token": top_token,
                "token_lime_weight": round(top_weight, 6),
                "original_label": canon["base_label"],
                "original_positive_score": round(canon["base_pos"], 6),
                "modified_label": deletion["modified_label"],
                "modified_positive_score": round(deletion["modified_positive_score"], 6),
                "confidence_delta": round(delta, 6),
                "label_flipped": flipped,
                "direction_correct": dir_correct,
                "removed_top3": "|".join(top3_tokens),
                "delta_top3": delta3, "flipped_top3": flipped3,
                "removed_top5": "|".join(top5_tokens),
                "delta_top5": delta5, "flipped_top5": flipped5,
            }
            del_writer.writerow(row)
            del_f.flush()

    total_time = time.perf_counter() - start_total

    env_info["run_timestamp"] = datetime.now(timezone.utc).isoformat()
    env_info["total_duration_seconds"] = round(total_time, 1)
    env_info["skipped_inputs"] = skipped_inputs
    env_path = os.path.join(output_dir, "environment.json")
    with open(env_path, "w", encoding="utf-8") as f:
        json.dump(env_info, f, indent=2)

    print(f"\nAudit complete in {total_time:.1f}s ({total_time / 60:.1f} min)")
    print(f"Results in: {output_dir}")
    return output_dir
