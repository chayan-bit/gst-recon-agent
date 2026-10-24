from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from gst_recon.eval.__main__ import main
from gst_recon.eval.cases import load_cases

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "eval_baselines.py"


def test_length_buckets_and_truth_lookup_one_level_down(world):
    nested = world["tmp"] / "nested_truth" / "any_split"
    nested.mkdir(parents=True)
    for p in world["truth"].glob("*.json"):
        (nested / p.name).write_bytes(p.read_bytes())
    cases = load_cases(list(world["dirs"].values()), truth_dir=nested.parent)
    assert all(c.truth is not None for c in cases)
    assert {c.length_bucket for c in cases} == {"<=16k", "16-32k", ">32k"}


def test_baseline_script_and_report_with_length_split_difficulty_and_placeholders(world):
    spec = importlib.util.spec_from_file_location("eval_baselines", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["eval_baselines"] = mod
    spec.loader.exec_module(mod)
    root = world["tmp"] / "runs" / "eval"
    assert mod.main(["--cases", *map(str, world["dirs"].values()), "--truth-dir", str(world["truth"]), "--out-root", str(root),
                     "--n-train", "9"]) == 0
    agg = json.loads((root / "baseline-context-blind" / "aggregate.json").read_text())
    assert agg["n_errors"] == 0 and agg["overall"]["extraction_f1"]["mean"] == 1.0  # oracle extraction
    assert set(agg["breakdowns"]["length_bucket"]) == {"<=16k", "16-32k", ">32k"}
    assert "test_iid/easy" in agg["breakdowns"]["split_difficulty"]
    out = world["tmp"] / "r.md"
    main(["report", "--runs", str(root), "--out", str(out), "--placeholder", "student-base", "SFT", "SFT+GRPO"])
    md = out.read_text()
    assert "context-blind rules (oracle extraction and links)" in md and "SFT+GRPO (not run yet)" in md
    assert "By case prompt length" in md and "<=16k" in md and "By split and difficulty" in md


def test_manifest_write_and_verify_detects_changes(world, capsys):
    from gst_recon.eval import manifest

    rendered = world["dirs"]["test_iid"].parent
    out = world["tmp"] / "m.json"
    assert manifest.main(["write", "--rendered", str(rendered), "--out", str(out), "--seed", "test_iid=9001", "--seed", "test_ood=9002"]) == 0
    m = json.loads(out.read_text())
    assert m["splits"]["test_iid"]["seed"] == 9001 and m["splits"]["test_iid"]["n_cases"] == 3
    assert manifest.main(["verify", "--rendered", str(rendered), "--manifest", str(out)]) == 0
    victim = next(world["dirs"]["test_ood"].iterdir())
    (victim / "prompt.txt").write_text("tampered")
    assert manifest.main(["verify", "--rendered", str(rendered), "--manifest", str(out)]) == 1
    assert "content changed" in capsys.readouterr().out
