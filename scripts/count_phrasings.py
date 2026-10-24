"""Count the item phrasings the simulator can produce: cores and distinct case-folded surface forms.

Run from the repo root: python scripts/count_phrasings.py
"""

from __future__ import annotations

from gst_recon.sim.concepts import CONCEPTS
from gst_recon.sim.splits import all_forms


def main() -> None:
    per_concept = {c.id: {f.casefold() for f in all_forms(c)} for c in CONCEPTS}
    distinct = set().union(*per_concept.values())
    sizes = [len(v) for v in per_concept.values()]
    print(f"concepts: {len(CONCEPTS)}")
    print(f"core phrases: {sum(len(c.forms) for c in CONCEPTS)}")
    print(f"surface forms before case-folding: {sum(len(all_forms(c)) for c in CONCEPTS)}")
    print(f"distinct case-folded forms per concept: min {min(sizes)}, max {max(sizes)}")
    print(f"distinct case-folded forms summed over concepts: {sum(sizes)}")
    print(f"distinct case-folded forms across all concepts: {len(distinct)}")
    assert min(sizes) >= 32, "RULES.md promises at least 32 distinct forms per concept"


if __name__ == "__main__":
    main()
