"""GSTIN structure and mod-36 check digit.

GSTIN = 2-digit state code + 10-char PAN + entity number (1-9, A-Z)
        + 'Z' (default) + check character.
Check character: Luhn mod-N algorithm over base-36 digits (0-9, A-Z) with
factors alternating 1, 2 from the left, as used by GSTN.
"""

from __future__ import annotations

import random
import re
import string

CHARSET = string.digits + string.ascii_uppercase  # value of a char = its index
_SHAPE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")

# PAN 4th char = holder type: C company, F firm, P individual, H HUF, A AOP, T trust
PAN_HOLDER_TYPES = "CFPHAT"


def check_char(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14.upper()):
        product = CHARSET.index(ch) * (1 if i % 2 == 0 else 2)
        total += product // 36 + product % 36
    return CHARSET[(36 - total % 36) % 36]


def is_valid_gstin(gstin: str) -> bool:
    g = gstin.strip().upper()
    return bool(_SHAPE.match(g)) and check_char(g[:14]) == g[14]


def random_pan(rng: random.Random, holder_type: str = "C", name: str = "") -> str:
    letters = string.ascii_uppercase
    fifth = name[:1].upper() if name[:1].isalpha() else rng.choice(letters)
    return (
        "".join(rng.choice(letters) for _ in range(3))
        + holder_type
        + fifth
        + f"{rng.randrange(1, 10000):04d}"
        + rng.choice(letters)
    )


def make_gstin(state_code: str, pan: str, entity: str = "1") -> str:
    first14 = f"{state_code}{pan}{entity}Z"
    return first14 + check_char(first14)
