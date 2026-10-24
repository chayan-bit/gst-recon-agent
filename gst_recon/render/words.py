"""Amount in words, Indian numbering (thousand, lakh, crore)."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

_ONES = ("Zero One Two Three Four Five Six Seven Eight Nine Ten Eleven Twelve Thirteen Fourteen Fifteen "
         "Sixteen Seventeen Eighteen Nineteen").split()
_TENS = "_ _ Twenty Thirty Forty Fifty Sixty Seventy Eighty Ninety".split()


def _below_100(n: int) -> str:
    return _ONES[n] if n < 20 else _TENS[n // 10] + (f" {_ONES[n % 10]}" if n % 10 else "")


def _below_1000(n: int) -> str:
    hundreds, rest = divmod(n, 100)
    return " ".join(p for p in (f"{_ONES[hundreds]} Hundred" if hundreds else "", _below_100(rest) if rest else "") if p)


def integer_words(n: int) -> str:
    """0 -> 'Zero'; 123456 -> 'One Lakh Twenty Three Thousand Four Hundred Fifty Six'."""
    if n == 0:
        return "Zero"
    crore, n = divmod(n, 10_000_000)
    lakh, n = divmod(n, 100_000)
    thousand, n = divmod(n, 1000)
    parts = []
    if crore:
        parts.append(f"{integer_words(crore)} Crore")  # crores above 99 recurse: 100 crore = One Hundred Crore
    for value, name in ((lakh, "Lakh"), (thousand, "Thousand")):
        if value:
            parts.append(f"{_below_100(value)} {name}")
    if n:
        parts.append(_below_1000(n))
    return " ".join(parts)


def amount_in_words(amount: float, style: str = "rupees") -> str:
    """Rupees One Lakh Twenty Three Thousand Four Hundred Fifty Six and Fifty Paise Only.

    style: 'rupees' (default), 'inr' (INR ... Only), 'rs' (Rs. ... only).
    """
    paise_total = int((Decimal(str(abs(amount))) * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    rupees, paise = divmod(paise_total, 100)
    body = integer_words(rupees)
    pa = f" and {integer_words(paise)} Paise" if paise else ""
    sign = "Minus " if amount < 0 else ""
    if rupees == 0 and paise:  # "Fifty Paise Only", not "Zero and Fifty Paise Only"
        body, pa = integer_words(paise) + " Paise", ""
    if style == "inr":
        return f"INR {sign}{body}{pa} Only"
    if style == "rs":
        return f"Rs. {sign}{body}{pa} only"
    return f"Rupees {sign}{body}{pa} Only"
