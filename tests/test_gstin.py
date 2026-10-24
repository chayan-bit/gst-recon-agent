import random

import pytest

from gst_recon.sim.gstin import check_char, is_valid_gstin, make_gstin, random_pan

# Real GSTINs taken from public GST directory listings (knowyourgst.com,
# taxadda.com, credlix.com) and the GSTN API sample; used only to verify the
# check-digit algorithm.
PUBLIC_GSTINS = [
    "27AAPFU0939F1ZV", "27ZZZFZ0001Z1ZU", "27ZZZPZ0002Z1Z8", "27ZZZCZ0003Z1ZY", "27ZZZPZ0004Z1Z6",
    "22ZZZCZ0005Z1Z6", "24ZZZCZ0006Z2Z0", "06ZZZCZ0007Z1ZY", "24ZZZCZ0008Z1ZZ", "24ZZZCZ0009Z1ZY",
    "24ZZZCZ0010Z1Z5", "27ZZZFZ0011Z1ZS", "27ZZZCZ0012Z1ZX", "27ZZZCZ0013Z1ZW", "24ZZZPZ0014Z1ZA",
]


@pytest.mark.parametrize("gstin", PUBLIC_GSTINS)
def test_public_gstins_validate(gstin):
    assert is_valid_gstin(gstin)
    assert check_char(gstin[:14]) == gstin[14]


@pytest.mark.parametrize("gstin", PUBLIC_GSTINS)
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
