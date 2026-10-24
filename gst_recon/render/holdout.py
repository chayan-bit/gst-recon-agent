"""Deterministic in-distribution vs held-out (OOD) presentation choices.

`train` and `test_iid` draw only from the in-distribution pools; `test_ood`
draws from the held-out items about half of the time (and otherwise from the
in-distribution pools), so a model never trained on them can be probed.
Held out: two invoice layouts, one label synonym per label group (the last
listed) plus the last two date formats.
"""

from __future__ import annotations

import random
from typing import Sequence

SPLITS = ("train", "test_iid", "test_ood")
OOD_LAYOUTS = ("saas_two_column", "handwritten_bill")
OOD_DATE_FORMATS = ("DD.MM.YYYY", "DD-Mon-YY")
P_OOD = 0.5
OOD_LAYOUT_BOOST = 3  # weight multiplier of held-out layouts in test_ood


def check_split(split: str) -> str:
    if split not in SPLITS:
        raise ValueError(f"split must be one of {SPLITS}, got {split!r}")
    return split


def pick(rng: random.Random, pool: Sequence[str], ood: Sequence[str], split: str) -> str:
    """Pick from `pool` honouring the split. Always consumes the same rng draws."""
    held = [x for x in pool if x in ood]
    base = [x for x in pool if x not in ood] or list(pool)
    r, choice = rng.random(), rng.random()
    use = held if (split == "test_ood" and held and r < P_OOD) else base
    return use[int(choice * len(use))]
