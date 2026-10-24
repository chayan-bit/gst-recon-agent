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
        mod.main([*base, "--out", str(world["tmp"] / "runs" / "eval" / "frontier"), "--concurrency", "5"])


def test_frontier_label_and_sibling_out_dir_keep_the_sonnet_outputs_separate(world, monkeypatch):
    mod = _load()
    exe = fake_claude(world["tmp"], world["targets"])
    monkeypatch.setattr(mod, "CMD", [str(exe), *mod.CMD[1:]])
    out = world["tmp"] / "runs" / "eval" / "frontier-haiku"
    rc = mod.main(["--cases", *map(str, world["dirs"].values()), "--n-per-dir", "2", "--out", str(out), "--model", "claude-haiku-5-5",
                   "--label", "Claude Haiku 5.5 (via Claude Code CLI)", "--truth-dir", str(world["truth"])])
    agg = json.loads((out / "aggregate.json").read_text())
    assert rc == 0 and agg["label"] == "Claude Haiku 5.5 (via Claude Code CLI)"
    assert not (world["tmp"] / "runs" / "eval" / "frontier").exists()


def test_claude_cli_json_schema_flag_is_passed_and_structured_output_is_the_fallback_text(tmp_path):
    mod = _load()
    exe = tmp_path / "claude"
    exe.write_text(f"""#!{sys.executable}
import json, sys
argv = sys.argv[1:]
print(json.dumps({{"is_error": False, "result": "", "structured_output": {{"schema": json.loads(argv[argv.index("--json-schema") + 1])}},
                  "stop_reason": "tool_use", "total_cost_usd": 0.01, "usage": {{"input_tokens": 1, "output_tokens": 2}}}}))
""")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    r = mod.claude_cli("p", "claude-haiku-5-5", 30, 0, tmp_path, cmd_prefix=[str(exe)], system="s", json_schema={"type": "object"})
    assert r["error"] is None and json.loads(r["text"]) == {"schema": {"type": "object"}} and r["cost_usd"] == 0.01


def _fake_codex(tmp_path: Path, mode: str) -> Path:
    """Fake `codex`: ok writes -o <file> and a turn.completed event; fail emits turn.failed and exits 1."""
    exe = tmp_path / f"codex-{mode}"
    exe.write_text(f"""#!{sys.executable}
import json, sys
a = sys.argv[1:]
prompt = sys.stdin.read()
if {mode!r} == "fail":
    print(json.dumps({{"type": "turn.failed", "error": {{"message": "rate limit"}}}})); sys.exit(1)
cfg = [a[i + 1] for i, x in enumerate(a) if x == "-c" and a[i + 1].startswith("model_instructions_file=")][0]
sysmsg = open(cfg.split("=", 1)[1].strip('"')).read()
schema = json.load(open(a[a.index("--output-schema") + 1]))
open(a[a.index("-o") + 1], "w").write(json.dumps({{"echo": prompt, "system": sysmsg, "schema": schema, "ignore": "--ignore-user-config" in a}}))
print(json.dumps({{"type": "turn.completed", "usage": {{"input_tokens": 7, "output_tokens": 3}}}}))
""")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return exe


def test_codex_cli_passes_system_schema_and_clean_flags_and_parses_the_last_message(tmp_path):
    mod = _load()
    r = mod.codex_cli("doc text", "gpt-6-luna", 30, 0, tmp_path, cmd_prefix=[str(_fake_codex(tmp_path, "ok"))], system="SYS",
                      json_schema={"type": "object"})
    out = json.loads(r["text"])
    assert r["error"] is None and r["prompt_tokens"] == 7 and r["completion_tokens"] == 3
    assert out == {"echo": "doc text", "system": "SYS", "schema": {"type": "object"}, "ignore": True}
    assert list(tmp_path.glob("tmp*")) == []  # per-call temp dir is removed


def test_codex_cli_maps_failures_to_the_error_field_after_retries(tmp_path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    r = mod.codex_cli("p", "gpt-6-luna", 30, 2, tmp_path, cmd_prefix=[str(_fake_codex(tmp_path, "fail"))], system="s")
    assert r["text"] == "" and "rate limit" in r["error"]


def test_effort_flag_is_appended_to_the_invocation_and_recorded(world, monkeypatch):
    mod = _load()
    exe = fake_claude(world["tmp"], world["targets"])
    monkeypatch.setattr(mod, "CMD", [str(exe), *mod.CMD[1:]])
    monkeypatch.setenv("MAX_THINKING_TOKENS", "0")
    out = world["tmp"] / "runs" / "eval" / "frontier-low"
    mod.main(["--cases", str(world["dirs"]["test_iid"]), "--n-per-dir", "1", "--out", str(out), "--claude-effort", "low",
              "--truth-dir", str(world["truth"])])
    cfg = json.loads((out / "config.json").read_text())
    assert cfg["invocation"][-2:] == ["--effort", "low"] and cfg["env"] == {"MAX_THINKING_TOKENS": "0"}
