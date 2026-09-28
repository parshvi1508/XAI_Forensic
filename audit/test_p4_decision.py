from audit.p4_decision import classify_p4


def test_zero_boundary():
    assert classify_p4(0.5, 0.5) == "disconfirmed"  # delta = 0


def test_just_below_005():
    assert classify_p4(0.5, 0.5 - 0.04999) == "inconclusive"


def test_exact_005():
    assert classify_p4(0.5, 0.45) == "inconclusive"  # delta = 0.05, per amendment


def test_just_above_005():
    assert classify_p4(0.5, 0.5 - 0.05001) == "confirmed"


def test_shift_greater_than_anchor():
    assert classify_p4(0.4, 0.6) == "disconfirmed"  # negative delta


def test_nonfinite():
    assert classify_p4(float("nan"), 0.4) == "undetermined_nonfinite"
    assert classify_p4(0.4, float("inf")) == "undetermined_nonfinite"


def test_missing():
    assert classify_p4(None, 0.4) == "undetermined_missing"
    assert classify_p4(0.4, None) == "undetermined_missing"
