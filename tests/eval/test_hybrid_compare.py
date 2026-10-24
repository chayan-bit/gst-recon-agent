"""scripts/eval_hybrid_compare.py: pooled case means and the paired bootstrap against stored reference runs."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "eval_hybrid_compare.py"


def _load():
    spec = importlib.util.spec_from_file_location("eval_hybrid_compare", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["eval_hybrid_compare"] = mod
    spec.loader.exec_module(mod)
    return mod


def _write(d: Path, rows: list[tuple[str, str, float]]) -> Path:
    d.mkdir(parents=True)
    (d / "scores.jsonl").write_text("\n".join(json.dumps({"case_id": c, "split": s, "metrics": {"itc_invoice": v}}) for c, s, v in rows))
    return d


def test_load_scores_merges_dirs_and_filters_by_split(tmp_path):
    mod = _load()
    a = _write(tmp_path / "a", [("c1", "test_iid", 1.0), ("c2", "realworld", 0.0)])
    b = _write(tmp_path / "b", [("c3", "test_ood", 0.5)])
    assert set(mod.load_scores([a, b])) == {"c1", "c2", "c3"}
    assert set(mod.load_scores([a, b], {"test_iid", "test_ood"})) == {"c1", "c3"}


def test_paired_reports_mean_delta_and_a_small_p_for_a_constant_gain():
    mod = _load()
    ids = [f"c{i}" for i in range(20)]
    run = {i: {"itc_invoice": 0.9} for i in ids}
    ref = {i: {"itc_invoice": 0.6} for i in ids}
    delta, lo, hi, p = mod.paired(run, ref, ids, "itc_invoice", reps=500)
    assert delta == pytest.approx(0.3) and lo == pytest.approx(0.3) and hi == pytest.approx(0.3) and p < 0.01
