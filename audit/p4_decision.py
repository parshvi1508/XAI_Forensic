"""P4 stress-slice decision rule. Pure fn, unit-tested."""
import math


def classify_p4(j_anchor, j_shift):
    if j_anchor is None or j_shift is None:
        return "undetermined_missing"
    if not (math.isfinite(j_anchor) and math.isfinite(j_shift)):
        return "undetermined_nonfinite"
    delta = j_anchor - j_shift  # unrounded
    if delta > 0.05:
        return "confirmed"
    if delta > 0.0:
        return "inconclusive"  # includes exact 0.05 by amendment
    return "disconfirmed"
