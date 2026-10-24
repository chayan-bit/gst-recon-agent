"""Number and date display formats used by documents, register and bank statement."""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()

DATE_FORMATS = ("DD-MM-YYYY", "DD/MM/YY", "D Mon YYYY", "DD-Mon-YY", "DD.MM.YYYY", "DD/MM/YYYY")
NUM_FORMATS = ("indian", "plain", "western")
# fmt_version 2 (train data only): wider per-supplier date styles; v1 cases keep DATE_FORMATS
MONTHS_LONG = "January February March April May June July August September October November December".split()
DATE_FORMATS_V2 = (*DATE_FORMATS, "YYYY-MM-DD", "DD.MM.YY", "DD-Mon-YYYY", "D Month YYYY", "Mon D, YYYY",
                   "DD Mon YYYY", "D/M/YYYY", "DD-MM-YY")


def fmt_date(d: date, style: str = "DD-MM-YYYY") -> str:
    if style == "DD-MM-YYYY":
        return f"{d.day:02d}-{d.month:02d}-{d.year}"
    if style == "DD/MM/YY":
        return f"{d.day:02d}/{d.month:02d}/{d.year % 100:02d}"
    if style == "DD/MM/YYYY":
        return f"{d.day:02d}/{d.month:02d}/{d.year}"
    if style == "DD.MM.YYYY":
        return f"{d.day:02d}.{d.month:02d}.{d.year}"
    if style == "D Mon YYYY":
        return f"{d.day} {MONTHS[d.month - 1]} {d.year}"
    if style == "DD-Mon-YY":
        return f"{d.day:02d}-{MONTHS[d.month - 1]}-{d.year % 100:02d}"
    if style == "YYYY-MM-DD":
        return d.isoformat()
    if style == "DD.MM.YY":
        return f"{d.day:02d}.{d.month:02d}.{d.year % 100:02d}"
    if style == "DD-Mon-YYYY":
        return f"{d.day:02d}-{MONTHS[d.month - 1]}-{d.year}"
    if style == "D Month YYYY":
        return f"{d.day} {MONTHS_LONG[d.month - 1]} {d.year}"
    if style == "Mon D, YYYY":
        return f"{MONTHS[d.month - 1]} {d.day}, {d.year}"
    if style == "DD Mon YYYY":
        return f"{d.day:02d} {MONTHS[d.month - 1]} {d.year}"
    if style == "D/M/YYYY":
        return f"{d.day}/{d.month}/{d.year}"
    if style == "DD-MM-YY":
        return f"{d.day:02d}-{d.month:02d}-{d.year % 100:02d}"
    raise ValueError(f"unknown date style {style!r}")


def _group_indian(digits: str) -> str:
    if len(digits) <= 3:
        return digits
    head, tail = digits[:-3], digits[-3:]
    groups = []
    while len(head) > 2:
        groups.append(head[-2:])
        head = head[:-2]
    if head:
        groups.append(head)
    return ",".join(reversed(groups)) + "," + tail


def fmt_amount(x: float, style: str = "indian", decimals: int = 2) -> str:
    """1234567.5 -> '12,34,567.50' (indian), '1234567.50' (plain), '1,234,567.50' (western)."""
    q = Decimal(str(abs(x))).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
    whole, _, frac = f"{q:f}".partition(".")
    if style == "indian":
        whole = _group_indian(whole)
    elif style == "western":
        whole = f"{int(whole):,}"
    elif style != "plain":
        raise ValueError(f"unknown number style {style!r}")
    out = whole + (f".{frac}" if decimals else "")
    return f"-{out}" if x < 0 and q != 0 else out
