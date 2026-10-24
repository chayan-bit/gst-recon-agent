"""Deterministic, disjoint train / test_iid / test_ood assignment of everything textual.

- Concepts: per family, about a quarter (families with >= 3 concepts) are held
  out entirely for test_ood.
- Surface forms: each in-distribution concept's core phrases are split; about a
  quarter (at least one) are held out for the test splits. Variants of a core
  phrase (case, abbreviation, typo) stay with their core, so near-duplicates never leak.
- Remarks, profile headers and their slot fillers: same core-level split.
- Buyer profiles, states, supplier-name vocabulary and invoice-number formats:
  a held-out subset is used only by test_ood.

test_iid = same concepts, profiles, states and vocabulary as train, held-out phrasing.
test_ood = held-out concepts preferred, held-out profiles (60% of cases),
held-out states, name vocabulary and number formats, held-out phrasing.
"""

from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from typing import Sequence

from gst_recon.schema import BusinessProfile as P
from gst_recon.schema import LinePurpose as U
from gst_recon.sim import catalog as cat
from gst_recon.sim import lexicon as lex
from gst_recon.sim.concepts import CONCEPTS, Concept

SPLITS = ("train", "test_iid", "test_ood")
OOD_PROFILES = (P.DRIVING_SCHOOL, P.CATERER, P.AUTO_WORKSHOP)
P_OOD_PROFILE = 0.6
P_OOD_CONCEPT = 0.7  # test_ood: chance to draw a held-out concept when the family has one


def check_split(split: str) -> str:
    if split not in SPLITS:
        raise ValueError(f"split must be one of {SPLITS}, got {split!r}")
    return split


def _h(*key: object) -> str:
    return hashlib.sha256("\x1f".join(map(str, key)).encode()).hexdigest()


def holdout(items: Sequence, frac: float, *key: object, min_held: int = 1) -> tuple[tuple, tuple]:
    """(kept, held) with a deterministic hash order; held never empties `kept`."""
    if len(items) < 2:
        return tuple(items), ()
    order = sorted(items, key=lambda x: _h(*key, x))
    n = min(len(items) - 1, max(min_held, round(frac * len(items))))
    held = set(order[:n])
    return tuple(x for x in items if x not in held), tuple(x for x in items if x in held)


# ------------------------------------------------------------------ surface forms

ABBREV = {
    "Services": "Svcs", "services": "svcs", "Service": "Svc", "service": "svc", "Charges": "Chgs",
    "charges": "chgs", "Membership": "Mbrshp", "membership": "mbrshp", "Annual": "Ann.", "annual": "ann.",
    "Maintenance": "Maint.", "maintenance": "maint.", "Construction": "Constrn", "construction": "constrn",
    "Contract": "Contr.", "contract": "contr.", "subscription": "subscr.", "with": "w/", "and": "&",
    "assembly": "assy", "Assembly": "Assy", "machine": "m/c", "Machine": "M/c", "professional": "prof.",
    "electrical": "elec.", "Electrical": "Elec.", "installation": "instln", "corporate": "corp.",
    "Corporate": "Corp.", "inch": "in", "Accommodation": "Accomm.", "accommodation": "accomm.",
    "Television": "TV", "refrigerator": "fridge", "Refrigerator": "Fridge", "Printer": "Prntr", "printer": "prntr",
    "transformer": "trfr", "bearing": "brg", "Bearing": "Brg", "Cement": "Cmt", "cement": "cmt", "box": "bx",
    "Beverages": "Bev.", "fees": "fee", "Supply": "Sply", "supply": "sply", "works": "wrks", "Works": "Wrks",
}
QUALIFIERS = (" - Q3", " (Lot 2)", " - batch 07", " (as per PO)", " - Phase II", " x1 set", " - Sr. 4", " (rev.1)")


def _abbrev_or_qualify(core: str) -> str:
    out = " ".join(ABBREV.get(w, w) for w in core.split(" "))
    return out if out != core else core + QUALIFIERS[int(_h("q", core), 16) % len(QUALIFIERS)]


def _typo(core: str) -> str:
    words = core.split(" ")
    idx = [i for i, w in enumerate(words) if re.fullmatch(r"[A-Za-z]{5,}", w)]
    if not idx:
        return core + "."
    i = idx[int(_h("t", core), 16) % len(idx)]
    w = words[i]
    j = 1 + int(_h("j", core), 16) % (len(w) - 2)
    words[i] = w[:j] + w[j + 1] + w[j] + w[j + 2:] if w[j] != w[j + 1] else w[:j] + w[j + 1:]
    return " ".join(words)


TAGS = ("(std)", "- spl", "(new)", "- regular", "(A grade)", "- local")


def _truncate_or_tag(core: str) -> str:
    """Billing software often cuts long descriptions; short ones get a trade tag."""
    words = core.split(" ")
    if len(words) >= 4:
        return " ".join(words[:3]) + "..."
    return f"{core} {TAGS[int(_h('tag', core), 16) % len(TAGS)]}"


@lru_cache(maxsize=None)
def surface_forms(core: str) -> tuple[str, ...]:
    """The core phrase plus deterministic variants: UPPER case, abbreviated (or
    qualified), one typo, and truncated (or tagged)."""
    return tuple(dict.fromkeys((core, core.upper(), _abbrev_or_qualify(core), _typo(core), _truncate_or_tag(core))))


def all_forms(c: Concept) -> tuple[str, ...]:
    return tuple(dict.fromkeys(f for core in c.forms for f in surface_forms(core)))


# ----------------------------------------------------------------- assignments


@lru_cache(maxsize=None)
def ood_concepts() -> frozenset[str]:
    held: set[str] = set()
    for fam in dict.fromkeys(c.family for c in CONCEPTS):
        ids = [c.id for c in CONCEPTS if c.family == fam]
        if len(ids) >= 3:
            held |= set(holdout(ids, 0.25, "concept", fam)[1])
    return frozenset(held)


@lru_cache(maxsize=None)
def _core_split(pool: tuple[str, ...], key: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return holdout(pool, 0.25, "core", key)


def concept_cores(c: Concept, split: str) -> tuple[str, ...]:
    if c.id in ood_concepts():
        return c.forms if split == "test_ood" else ()
    train, held = _core_split(c.forms, c.id)
    return train if split == "train" else held


def concept_forms(c: Concept, split: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(f for core in concept_cores(c, split) for f in surface_forms(core)))


def text_pool(pool: Sequence[str], key: str, split: str) -> tuple[str, ...]:
    train, held = _core_split(tuple(pool), key)
    return train if split == "train" else held


def _vocab(pool: Sequence, key: str, split: str, frac: float = 0.3) -> tuple:
    kept, held = holdout(tuple(pool), frac, "vocab", key)
    return held if split == "test_ood" else kept


class View:
    """Everything the generator may draw for one split."""

    def __init__(self, split: str):
        self.split = check_split(split)

    def concepts(self, family: str, ood_only: bool = False) -> list[Concept]:
        fam = [c for c in CONCEPTS if c.family == family and concept_cores(c, self.split)]
        return [c for c in fam if c.id in ood_concepts()] if ood_only else fam

    def forms(self, c: Concept) -> tuple[str, ...]:
        return concept_forms(c, self.split)

    def profiles(self, held_out: bool) -> list[P]:
        if self.split == "test_ood" and held_out:
            return list(OOD_PROFILES)
        return [p for p in P if p not in OOD_PROFILES]

    @property
    def states(self) -> tuple[str, ...]:
        return _vocab(sorted(cat.STATES), "states", self.split, 0.25)

    @property
    def name_prefix(self) -> tuple[str, ...]:
        return _vocab(cat.NAME_PREFIX, "prefix", self.split)

    @property
    def name_core(self) -> tuple[str, ...]:
        return _vocab(cat.NAME_CORE, "core", self.split)

    @property
    def number_formats(self) -> tuple[str, ...]:
        return _vocab(cat.NUMBER_FORMATS, "numfmt", self.split, 0.25)

    def headers(self, profile: P) -> tuple[str, ...]:
        return text_pool(lex.PROFILE_HEADERS[profile], f"header:{profile.value}", self.split)

    def trade_headers(self, line: str) -> tuple[str, ...]:
        return text_pool(lex.TRADE_LINES[line][1], f"trade:{line}", self.split)

    def slots(self, profile: P) -> tuple[str, ...]:
        return text_pool(lex.PROFILE_SLOTS[profile], f"slot:{profile.value}", self.split)

    def remarks(self, purpose: U) -> tuple[str, ...]:
        return text_pool(lex.REMARKS[purpose], f"remark:{purpose.value}", self.split)

    @property
    def neutral_remarks(self) -> tuple[str, ...]:
        return text_pool(lex.NEUTRAL_REMARKS, "remark:neutral", self.split)
