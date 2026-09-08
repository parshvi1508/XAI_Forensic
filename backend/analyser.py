import functools
import json
import logging

from transformers import pipeline
from lime.lime_text import LimeTextExplainer
import numpy as np

logger = logging.getLogger("xai_forensics")

MODEL_A_NAME = "distilbert-base-uncased-finetuned-sst-2-english"
MODEL_A_REVISION = "714eb0fa89d2f80546fda750413ed43d93601a13"
MODEL_B_NAME = "cardiffnlp/twitter-roberta-base-sentiment-latest"
MODEL_B_REVISION = "3216a57f2a0d9c45a2e6c20157c20c49fb4bf9c7"

# top_k=None needed for LIME's predict_proba interface
model_a = pipeline("text-classification", model=MODEL_A_NAME, revision=MODEL_A_REVISION, top_k=None)
model_b = pipeline("text-classification", model=MODEL_B_NAME, revision=MODEL_B_REVISION, top_k=None)

logger.info("loaded model A: %s", MODEL_A_NAME)
logger.info("loaded model B: %s", MODEL_B_NAME)


_POSITIVE_LABELS = {"POSITIVE", "positive"}


def _get_positive_score(pipeline_output: list) -> float:
    for item in pipeline_output[0]:
        if item["label"] in _POSITIVE_LABELS:
            return item["score"]
    known = [item["label"] for item in pipeline_output[0]]
    raise ValueError(
        f"No positive label found in {known}. "
        f"Expected one of: {_POSITIVE_LABELS}"
    )


def _model_a_proba(texts: list[str]) -> np.ndarray:
    results = []
    for text in texts:
        output = model_a(text, truncation=True, max_length=512)
        pos = _get_positive_score(output)
        results.append([1.0 - pos, pos])
    return np.array(results)


@functools.lru_cache(maxsize=128)
def _explain_why_cached(text: str, seed: int) -> str:
    np.random.seed(seed)
    explainer = LimeTextExplainer(
        class_names=["negative", "positive"],
        random_state=seed,
    )
    explanation = explainer.explain_instance(
        text,
        _model_a_proba,
        num_features=10,
        num_samples=300,
    )

    base_output = model_a(text, truncation=True, max_length=512)
    pos_score = _get_positive_score(base_output)
    predicted_label = "positive" if pos_score >= 0.5 else "negative"
    confidence = round(pos_score if predicted_label == "positive" else 1.0 - pos_score, 4)

    token_weights = explanation.as_list()

    result = {
        "label": predicted_label,
        "confidence": confidence,
        "attribution_warning": confidence > 0.95,
        "tokens": [
            {"token": token, "weight": round(float(weight), 4)}
            for token, weight in token_weights
        ],
    }
    return json.dumps(result)


def explain_why(text: str, seed: int = 42) -> dict:
    return json.loads(_explain_why_cached(text, seed))


def explain_flip(text: str) -> dict:
    words = text.split()
    base_output = model_a(text, truncation=True, max_length=512)
    base_pos = _get_positive_score(base_output)
    base_label = "positive" if base_pos >= 0.5 else "negative"

    best_flip_word = None
    best_abs_delta = 0.0
    best_masked_text = text
    best_modified_pos = base_pos
    flipped = False

    for i, word in enumerate(words):
        masked_words = words[:i] + words[i + 1 :]
        if not masked_words:
            continue
        masked_text = " ".join(masked_words)
        output = model_a(masked_text, truncation=True, max_length=512)
        pos = _get_positive_score(output)
        new_label = "positive" if pos >= 0.5 else "negative"

        abs_delta = abs(pos - base_pos)
        if abs_delta > best_abs_delta:
            best_abs_delta = abs_delta
            best_flip_word = word
            best_masked_text = masked_text
            best_modified_pos = pos
            flipped = new_label != base_label

    modified_label = "positive" if best_modified_pos >= 0.5 else "negative"

    return {
        "original_text": text,
        "original_label": base_label,
        "original_confidence": round(base_pos if base_label == "positive" else 1.0 - base_pos, 4),
        "key_word": best_flip_word,
        "modified_text": best_masked_text,
        "modified_label": modified_label,
        "modified_confidence": round(best_modified_pos if modified_label == "positive" else 1.0 - best_modified_pos, 4),
        "flipped": flipped,
        "delta": round(best_modified_pos - base_pos, 4),
    }


def explain_disagree(text: str) -> dict:
    output_a = model_a(text, truncation=True, max_length=512)
    output_b = model_b(text, truncation=True, max_length=512)

    pos_a = _get_positive_score(output_a)
    pos_b = _get_positive_score(output_b)

    label_a = "positive" if pos_a >= 0.5 else "negative"
    label_b = "positive" if pos_b >= 0.5 else "negative"

    divergence = round(abs(pos_a - pos_b), 4)

    return {
        "model_a": {
            "name": MODEL_A_NAME,
            "label": label_a,
            "confidence": round(pos_a if label_a == "positive" else 1.0 - pos_a, 4),
            "positive_score": round(pos_a, 4),
        },
        "model_b": {
            "name": MODEL_B_NAME,
            "label": label_b,
            "confidence": round(pos_b if label_b == "positive" else 1.0 - pos_b, 4),
            "positive_score": round(pos_b, 4),
        },
        "divergence": divergence,
        "models_agree": label_a == label_b,
    }
