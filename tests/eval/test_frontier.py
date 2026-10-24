"""eval_frontier.py against a fake `claude` executable (no network, no tokens)."""

from __future__ import annotations

import importlib.util
import json
import stat
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "eval_frontier.py"


def _load():
    spec = importlib.util.spec_from_file_location("eval_frontier", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["eval_frontier"] = mod
    spec.loader.exec_module(mod)
    return mod


def fake_claude(tmp_path: Path, targets: dict) -> Path:
    """Reads the prompt from stdin, answers with that case's target inside claude's JSON envelope."""
    (tmp_path / "targets.json").write_text(json.dumps(targets))
    exe = tmp_path / "claude"
    exe.write_text(f"""#!{sys.executable}
import json, sys
prompt = sys.stdin.read()
cid = prompt.split("\\n", 1)[0].removeprefix("CASE_ID: ")
t = json.load(open({str(tmp_path / 'targets.json')!r}))[cid]
print(json.dumps({{"is_error": False, "result": "```json\\n" + json.dumps(t) + "\\n```", "stop_reason": "end_turn",
                  "total_cost_usd": 0.05, "usage": {{"input_tokens": 3, "cache_creation_input_tokens": 700,
                  "cache_read_input_tokens": 300, "output_tokens": 150}}}}))
""")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return exe


def test_frontier_runs_scores_and_stays_under_runs_eval(world, monkeypatch):
    mod = _load()
    exe = fake_claude(world["tmp"], world["targets"])
    monkeypatch.setattr(mod, "CMD", [str(exe), *mod.CMD[1:]])
    out = world["tmp"] / "runs" / "eval" / "frontier"
    rc = mod.main(["--cases", *map(str, world["dirs"].values()), "--n-per-dir", "2", "--out", str(out),
                   "--truth-dir", str(world["truth"])])
    agg = json.loads((out / "aggregate.json").read_text())
    assert rc == 0 and agg["label"] == "Claude Sonnet (via Claude Code CLI)" and agg["n_cases"] == 4
    assert agg["overall"]["composite"]["mean"] == pytest.approx(1.0)
    assert agg["cost_per_1000_cases"]["api_usd"] == pytest.approx(50.0)
    rec = json.loads(next((out / "cases").glob("*.json")).read_text())
    assert rec["prompt_tokens"] == 1003 and rec["completion_tokens"] == 150
    assert (out / "DO_NOT_TRAIN").exists()


def test_frontier_refuses_other_output_dirs_and_high_concurrency(world):
    mod = _load()
    base = ["--cases", str(world["dirs"]["test_iid"])]
    with pytest.raises(SystemExit):
        mod.main([*base, "--out", str(world["tmp"] / "elsewhere")])
    with pytest.raises(SystemExit):
        mod.main([*base, "--out", str(world["tmp"] / "runs" / "eval" / "frontier"), "--concurrency", "4"])
