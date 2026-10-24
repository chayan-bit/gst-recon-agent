"""scripts/eval_auditkit.py end to end against the stub server. Needs AuditKIT: run with the AuditKIT venv
(PYTHONPATH=. .venv-auditkit/bin/python -m pytest tests/eval/test_auditkit_script.py); skipped elsewhere."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("auditkit")

from gst_recon.eval.__main__ import main as eval_main  # noqa: E402

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "eval_auditkit.py"


def _script():
    spec = importlib.util.spec_from_file_location("eval_auditkit", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["eval_auditkit"] = mod
    spec.loader.exec_module(mod)
    return mod


def _run(world, model, name):
    out = world["tmp"] / "runs" / "eval" / name
    eval_main(["run", "--endpoint", world["stub"].url, "--model", model, "--cases", *map(str, world["dirs"].values()),
               "--out", str(out), "--truth-dir", str(world["truth"]), "--retries", "0"])
    return out


def test_precomputed_and_api_sources_compare_with_fingerprints(world, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # AuditKIT writes its cache/experiment DB relative to the cwd/home
    mod = _script()
    base, good = _run(world, "noisy", "base"), _run(world, "perfect", "sft")
    out = world["tmp"] / "ak"
    rc = mod.main(["--cases", *map(str, world["dirs"].values()), "--truth-dir", str(world["truth"]),
                   "--run", f"base={base}", "--run", f"sft={good}", "--api", f"live=perfect@{world['stub'].url}",
                   "--out", str(out), "--concurrency", "2"])
    assert rc == 0
    doc = json.loads((out / "auditkit_compare.json").read_text())
    assert set(doc["runs"]) == {"base", "sft", "live"} and doc["baseline"] == "base"
    assert all(len(r["fingerprint"]) >= 8 for r in doc["runs"].values())
    assert doc["runs"]["sft"]["fingerprint"] != doc["runs"]["base"]["fingerprint"]
    assert doc["runs"]["sft"]["headline"]["composite"] == pytest.approx(1.0)
    assert doc["runs"]["live"]["headline"]["composite"] == pytest.approx(1.0)  # AuditKIT queried the stub through api:
    sig = doc["comparisons"]["sft"]["composite"]
    assert sig["auditkit"]["delta"] > 0 and sig["corrected"]["p_value_corrected"] < 0.05
    md = (out / "auditkit_compare.md").read_text()
    assert "fingerprint" in md and "corrected p" in md
