import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from analyser import explain_why, explain_flip


def test_seed_determinism():
    """Same (text, seed) must return identical token weights."""
    text = "I am not entirely unhappy with this result."
    r1 = explain_why(text, seed=42)
    r2 = explain_why(text, seed=42)
    assert r1["tokens"] == r2["tokens"]
    assert r1["label"] == r2["label"]
    assert r1["confidence"] == r2["confidence"]


def test_high_confidence_attribution_warning():
    """Confidence > 0.95 must set attribution_warning flag."""
    r = explain_why("This is the best product I have ever purchased.", seed=42)
    assert r["confidence"] > 0.95
    assert r.get("attribution_warning") is True


def test_lime_flip_consistency_logging():
    """Log whether LIME top token agrees with FLIP top word.
    Not an assertion (they CAN differ), but drift should be visible."""
    text = "I loved this movie despite the bad acting."
    r_lime = explain_why(text, seed=42)
    r_flip = explain_flip(text)
    lime_top = r_lime["tokens"][0]["token"]
    flip_top = r_flip["key_word"]
    print(f"LIME top: {lime_top}, FLIP top: {flip_top}, agree: {lime_top == flip_top}")
