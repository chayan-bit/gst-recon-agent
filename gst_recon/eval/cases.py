"""Load rendered cases: <dir>/<case_id>/{prompt.txt,target.json,meta.json} (+ optional truth Case JSON)."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path

from gst_recon.schema import Case

FULL_RECALL = 0.9999  # meta.ocr_recall is rounded to 4 dp


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    prompt: str
    target: dict
    meta: dict
    truth: Case | None = field(default=None, compare=False)

    @property
    def split(self) -> str:
        return str(self.meta.get("split", "unknown"))

    @property
    def difficulty(self) -> str:
        return str(self.meta.get("difficulty", "unknown"))

    @property
    def ocr_bucket(self) -> str:
        r = self.meta.get("ocr_recall")
        return "unknown" if r is None else "full" if r >= FULL_RECALL else "partial"


def _load_truth(truth_dir: Path | None, case_id: str) -> Case | None:
    if truth_dir is None or not (truth_dir / f"{case_id}.json").exists():
        return None
    return Case.model_validate_json((truth_dir / f"{case_id}.json").read_text())


def load_cases(dirs: list[Path], *, truth_dir: Path | None = None, n_per_dir: int | None = None,
               seed: int = 0) -> list[EvalCase]:
    """All cases under each dir (a dir of case dirs). `n_per_dir` takes a seeded random sample of
    that size from each, so a sample mixes difficulties; the result is sorted by case_id per dir."""
    out: list[EvalCase] = []
    for d in dirs:
        ids = sorted(p.parent.name for p in Path(d).glob("*/meta.json"))
        if not ids:
            raise FileNotFoundError(f"no <case_id>/meta.json under {d}")
        if n_per_dir is not None and n_per_dir < len(ids):
            ids = sorted(random.Random(f"{seed}:{d}").sample(ids, n_per_dir))
        for cid in ids:
            c = Path(d) / cid
            out.append(EvalCase(cid, (c / "prompt.txt").read_text(), json.loads((c / "target.json").read_text()),
                                json.loads((c / "meta.json").read_text()), _load_truth(truth_dir, cid)))
    return out
