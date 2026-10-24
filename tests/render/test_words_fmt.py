import pytest

from gst_recon.render.fmt import fmt_amount, fmt_date
from gst_recon.render.words import amount_in_words, integer_words
from datetime import date


@pytest.mark.parametrize("amount,expected", [
    (0, "Rupees Zero Only"),
    (1, "Rupees One Only"),
    (100, "Rupees One Hundred Only"),
    (1000, "Rupees One Thousand Only"),
    (99999, "Rupees Ninety Nine Thousand Nine Hundred Ninety Nine Only"),
    (100000, "Rupees One Lakh Only"),
    (123456.5, "Rupees One Lakh Twenty Three Thousand Four Hundred Fifty Six and Fifty Paise Only"),
    (1000000, "Rupees Ten Lakh Only"),
    (10000000, "Rupees One Crore Only"),
    (24123456.78, "Rupees Two Crore Forty One Lakh Twenty Three Thousand Four Hundred Fifty Six and Seventy Eight Paise Only"),
    (0.05, "Rupees Five Paise Only"),
    (1500000000, "Rupees One Hundred Fifty Crore Only"),
])
def test_amount_in_words_uses_indian_numbering(amount, expected):
    assert amount_in_words(amount) == expected


def test_amount_in_words_styles():
    assert amount_in_words(250, "inr") == "INR Two Hundred Fifty Only"
    assert amount_in_words(250, "rs") == "Rs. Two Hundred Fifty only"


def test_integer_words_round_trips_digit_patterns():
    assert integer_words(10_00_000) == "Ten Lakh"
    assert integer_words(1_01_01_001) == "One Crore One Lakh One Thousand One"


@pytest.mark.parametrize("x,style,expected", [
    (123456, "indian", "1,23,456.00"), (999.5, "indian", "999.50"), (1234567.891, "indian", "12,34,567.89"),
    (100000, "indian", "1,00,000.00"), (1234567.5, "western", "1,234,567.50"), (1234567.5, "plain", "1234567.50"),
    (-1500.5, "indian", "-1,500.50"), (0, "indian", "0.00"),
])
def test_fmt_amount(x, style, expected):
    assert fmt_amount(x, style) == expected


def test_fmt_date_variants():
    d = date(2025, 1, 12)
    assert [fmt_date(d, s) for s in ("DD-MM-YYYY", "DD/MM/YY", "D Mon YYYY", "DD-Mon-YY", "DD.MM.YYYY")] == [
        "12-01-2025", "12/01/25", "12 Jan 2025", "12-Jan-25", "12.01.2025"]
