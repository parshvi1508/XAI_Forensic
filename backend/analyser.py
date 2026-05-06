from transformers import pipeline
from lime.lime_text import LimeTextExplainer
import numpy as np

MODEL_A_NAME = "distilbert-base-uncased-finetuned-sst-2-english"
MODEL_B_NAME = "cardiffnlp/twitter-roberta-base-sentiment-latest"

# load both pipelines at module import time so FastAPI does not reload on each request
# top_k=None returns all class scores, which we need for LIME's predict_proba interface
model_a = pipeline("text-classification", model=MODEL_A_NAME, top_k=None)
model_b = pipeline("text-classification", model=MODEL_B_NAME, top_k=None)

print(f"loaded model A: {MODEL_A_NAME}")
print(f"loaded model B: {MODEL_B_NAME}")


def _get_positive_score(pipeline_output: list) -> float:
    # pipeline_output is a list of dicts like [{"label": "POSITIVE", "score": 0.99}]
    # label names differ between models so we look for anything containing "pos" case-insensitive
    for item in pipeline_output[0]:
        if "pos" in item["label"].lower():
            return item["score"]
    # if no positive label found, return 1 minus the highest score (handles binary case)
    return 1.0 - max(item["score"] for item in pipeline_output[0])


def _model_a_proba(texts: list[str]) -> np.ndarray:
    # LIME requires a function that takes a list of strings and returns a 2D array
    # shape: (n_samples, n_classes), columns are [negative_prob, positive_prob]
    results = []
    for text in texts:
        output = model_a(text, truncation=True, max_length=512)
        pos = _get_positive_score(output)
        results.append([1.0 - pos, pos])
    return np.array(results)


def explain_why(text: str) -> dict:
    # LIME perturbs the input by masking tokens and observing how predictions change
    # n_samples=300 is a tradeoff: lower is faster, higher is more accurate, 300 is enough for short texts
    # num_features=10 means we return the top 10 most influential tokens
    explainer = LimeTextExplainer(class_names=["negative", "positive"])
    explanation = explainer.explain_instance(
        text,
        _model_a_proba,
        num_features=10,
        num_samples=300,
    )

    base_output = model_a(text, truncation=True, max_length=512)
    pos_score = _get_positive_score(base_output)
    predicted_label = "positive" if pos_score >= 0.5 else "negative"

    token_weights = explanation.as_list()
    # as_list() returns [(token, weight), ...] where positive weight means token pushes toward positive class

    return {
        "label": predicted_label,
        "confidence": round(pos_score if predicted_label == "positive" else 1.0 - pos_score, 4),
        "tokens": [
            {"token": token, "weight": round(float(weight), 4)}
            for token, weight in token_weights
        ],
    }


def explain_flip(text: str) -> dict:
    # greedy counterfactual: mask each word one at a time, find the word whose removal most changes the prediction
    # this is O(n) in sentence length, fast enough for typical inputs
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
    # run both models and compute the absolute difference in their positive class confidence
    # a high divergence score means the models have different views, which is meaningful for XAI
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