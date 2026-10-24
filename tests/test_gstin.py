import random

import pytest

from gst_recon.sim.gstin import check_char, is_valid_gstin, make_gstin, random_pan

# GSTN's own sample/sandbox GSTINs (API docs and GSP sandbox), not businesses.
GSTN_SAMPLES = ["27AAPFU0939F1ZV", "33GSPTN0231G1ZM"]
# Synthetic: obviously fake PANs; their check chars come from the algorithm under test.
SYNTHETIC = [make_gstin(st, pan, ent) for st, pan, ent in
             (("07", "ABCDE1234F", "1"), ("29", "ZZZZZ9999Z", "2"), ("33", "AAAAA0000A", "9"), ("27", "QWERT5678Y", "A"))]
ALL = GSTN_SAMPLES + SYNTHETIC


def test_worked_example_gstn_sample():
    """Step-by-step check digit for GSTN's sample 27AAPFU0939F1ZV.
    Char values 0-9 -> 0-9, A-Z -> 10-35; factors alternate 1, 2 from the left;
    each product contributes quotient + remainder of division by 36."""
    first14 = "27AAPFU0939F1Z"
    values = [2, 7, 10, 10, 25, 15, 30, 0, 9, 3, 9, 15, 1, 35]
    products = [v * (1 if i % 2 == 0 else 2) for i, v in enumerate(values)]
    assert products == [2, 14, 10, 20, 25, 30, 30, 0, 9, 6, 9, 30, 1, 70]
    total = sum(p // 36 + p % 36 for p in products)
    assert total == 221 and total % 36 == 5
    assert (36 - 5) % 36 == 31  # value 31 = "V"
    assert check_char(first14) == "V"


@pytest.mark.parametrize("gstin", GSTN_SAMPLES)
def test_gstn_samples_validate(gstin):
    assert is_valid_gstin(gstin)
    assert check_char(gstin[:14]) == gstin[14]


@pytest.mark.parametrize("gstin", ALL)
def test_any_single_char_substitution_is_detected(gstin):
    for i in range(14):
        for c in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            if c != gstin[i]:
                assert not is_valid_gstin(gstin[:i] + c + gstin[i + 1:])


def test_rejects_bad_shape():
    for bad in ("", "27AAPFU0939F1Z", "27AAPFU0939F1ZVX", "2XAAPFU0939F1ZV", "27AAPFU0939F0ZV"):
        assert not is_valid_gstin(bad)


def test_lowercase_input_accepted():
    assert is_valid_gstin("27aapfu0939f1zv")


def test_generated_gstins_are_valid():
    rng = random.Random(7)
    for _ in range(500):
        g = make_gstin(rng.choice(["07", "27", "29", "33"]), random_pan(rng, rng.choice("CFP")))
        assert is_valid_gstin(g), g
