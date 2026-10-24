"""Frontier baseline through the local Claude Code CLI (no API key): Claude Sonnet (via Claude Code CLI).

    python scripts/eval_frontier.py --cases data/rendered/test_iid data/rendered/test_ood --n-per-dir 50 --concurrency 2

Same task prompt, same scorer and same report as the SGLang runs. Prompt-only: the JSON Schema is in the
system prompt, there is no constrained decoding. Outputs go only under runs/eval/frontier/ (resumable per
case) and are never training data. Cases that errored are retried on the next invocation.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gst_recon.eval.cases import load_cases  # noqa: E402
from gst_recon.eval.prompts import with_schema  # noqa: E402
from gst_recon.eval.runner import run_eval  # noqa: E402

LABEL = "Claude Sonnet (via Claude Code CLI)"
OUT = Path("runs/eval/frontier")
# Exact invocation: prompt on stdin, schema + task in the system prompt, no tools, no session, no user settings/hooks.
CMD = ["claude", "-p", "--model", "{model}", "--output-format", "json", "--system-prompt", "{system}", "--tools", "",
       "--no-session-persistence", "--setting-sources", "", "--disable-slash-commands", "--strict-mcp-config"]


def claude_cli(prompt: str, model: str, timeout: float, retries: int, cwd: Path, cmd_prefix: list[str] | None = None,
               system: str | None = None, json_schema: dict | None = None) -> dict:
    """One CLI call. Never raises. Tokens count input + cache creation + cache reads; cost is the CLI's own total_cost_usd."""
    system = with_schema() if system is None else system
    cmd = [c.replace("{model}", model).replace("{system}", system) for c in CMD]
    if json_schema is not None:  # the CLI's structured output (a forced tool call), not grammar-constrained decoding
        cmd += ["--json-schema", json.dumps(json_schema, separators=(",", ":"))]
    if cmd_prefix:
        cmd = [*cmd_prefix, *cmd[1:]]
    err = ""
    for attempt in range(retries + 1):
        t0 = time.perf_counter()
        stderr = ""
        try:
            p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout, cwd=cwd)
            stderr = p.stderr[:200]
            data = json.loads(p.stdout)
            if data.get("is_error"):
                raise RuntimeError(str(data.get("result"))[:300])
            u = data.get("usage") or {}
            text = data.get("result") or (json.dumps(data["structured_output"]) if data.get("structured_output") else "")
            return {"text": text, "latency_s": time.perf_counter() - t0, "finish_reason": data.get("stop_reason"),
                    "prompt_tokens": sum(u.get(k, 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")),
                    "completion_tokens": u.get("output_tokens"), "cost_usd": data.get("total_cost_usd"), "error": None}
        except (subprocess.SubprocessError, OSError, ValueError, RuntimeError) as e:
            err = f"{type(e).__name__}: {e} {stderr}".strip()
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
    return {"text": "", "latency_s": None, "finish_reason": None, "prompt_tokens": None, "completion_tokens": None, "error": err}

# Clean `codex exec` call for hybrid per-document runs: no tools, skills, hooks, plugins, project docs or user config; the system
# message replaces the built-in instructions (model_instructions_file); the schema is --output-schema. About 6k tokens of
# harness-injected developer messages remain. CODEX_HOME must hold only auth.json (user config and AGENTS.md are never read).
CODEX_CLEAN = ["--skip-git-repo-check", "--ephemeral", "--ignore-user-config", "--ignore-rules", "--json", "-s", "read-only",
               "-c", 'approval_policy="never"', "-c", "project_doc_max_bytes=0", "-c", 'web_search="disabled"',
               "-c", "skills.include_instructions=false", "-c", "skills.bundled.enabled=false",
               *[a for f in ("shell_tool", "unified_exec", "multi_agent", "apps", "plugins", "skill_search", "view_image", "image_generation",
                             "computer_use", "browser_use", "browser_use_external", "goals", "hooks", "sleep_tool", "tool_suggest",
                             "shell_snapshot", "fast_mode") for a in ("-c", f"features.{f}=false")]]


def codex_cli(prompt: str, model: str, timeout: float, retries: int, cwd: Path, cmd_prefix: list[str] | None = None,
              system: str | None = None, json_schema: dict | None = None, effort: str = "medium", codex_home: str | None = None) -> dict:
    """One `codex exec` call. Never raises; retries with exponential backoff (rate limits included). Tokens are the turn's input
    tokens (cached included); there is no cost field."""
    err = ""
    env = {**os.environ, **({"CODEX_HOME": codex_home} if codex_home else {})}
    for attempt in range(retries + 1):
        t0 = time.perf_counter()
        stderr = ""
        try:
            with tempfile.TemporaryDirectory(dir=cwd) as td:
                td = Path(td)
                (td / "system.txt").write_text(system or "")
                cmd = [*(cmd_prefix or ["codex"]), "exec", "-m", model, *CODEX_CLEAN, "-c", f'model_reasoning_effort="{effort}"',
                       "-c", f'model_instructions_file="{td / "system.txt"}"', "-o", str(td / "last.txt")]
                if json_schema is not None:
                    (td / "schema.json").write_text(json.dumps(json_schema))
                    cmd += ["--output-schema", str(td / "schema.json")]
                p = subprocess.run([*cmd, "-"], input=prompt, capture_output=True, text=True, timeout=timeout, cwd=cwd, env=env)
                stderr = p.stderr[-200:]
                events = [e for e in (_jsonl(line) for line in p.stdout.splitlines()) if e]
                done = next((e for e in reversed(events) if e.get("type") == "turn.completed"), None)
                failed = next((e for e in reversed(events) if e.get("type") in ("turn.failed", "error")), None)
                text = (td / "last.txt").read_text() if (td / "last.txt").exists() else ""
                if done is None or not text.strip():
                    raise RuntimeError(f"exit {p.returncode}: {json.dumps(failed)[:300] if failed else 'no completed turn or empty reply'}")
            u = done.get("usage") or {}
            return {"text": text, "latency_s": time.perf_counter() - t0, "finish_reason": "stop", "prompt_tokens": u.get("input_tokens"),
                    "completion_tokens": u.get("output_tokens"), "cost_usd": None, "error": None}
        except (subprocess.SubprocessError, OSError, ValueError, RuntimeError) as e:
            err = f"{type(e).__name__}: {e} {stderr}".strip()
            if attempt < retries:
                time.sleep(5 * 2 ** attempt)
    return {"text": "", "latency_s": None, "finish_reason": None, "prompt_tokens": None, "completion_tokens": None, "error": err}


def _jsonl(line: str) -> dict | None:
    try:
        obj = json.loads(line)
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", type=Path, nargs="+", required=True)
    ap.add_argument("--n-per-dir", type=int, default=50, help="seeded sample per test split dir (default 50)")
    ap.add_argument("--concurrency", type=int, default=2, help="capped at 4: this runs on the Mac")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--out", type=Path, default=OUT, help="runs/eval/frontier or a sibling runs/eval/frontier-<name>")
    ap.add_argument("--label", default=LABEL, help="report row label (default: the Sonnet baseline's)")
    ap.add_argument("--timeout", type=float, default=600.0)
    ap.add_argument("--retries", type=int, default=1)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--truth-dir", type=Path, default=Path("data/truth"))
    ap.add_argument("--schema-mode", choices=("prompt", "flag"), default="prompt",
                    help="hybrid only: prompt = doc schema appended to the system prompt (the Sonnet hybrid run); "
                         "flag = the CLI's --json-schema structured output, system prompt unchanged")
    ap.add_argument("--backend", choices=("claude", "codex"), default="claude",
                    help="codex: `codex exec` per document (hybrid only; CODEX_HOME must hold only auth.json), schema via --output-schema")
    ap.add_argument("--effort", default="medium", help="codex reasoning effort")
    ap.add_argument("--mode", choices=("e2e", "hybrid"), default="e2e",
                    help="hybrid: one CLI call per document (DOC_SYSTEM_PROMPT + doc schema), code reconciles; "
                         "--out must then be a subdirectory of runs/eval/frontier")
    a = ap.parse_args(argv)
    parts = a.out.resolve().parts
    under = any(parts[i:i + 3] == ("runs", "eval", "frontier") for i in range(len(parts) - 2))
    sibling = parts[-3:-1] == ("runs", "eval") and parts[-1].startswith("frontier")
    if (a.mode == "e2e" and not sibling) or (a.mode == "hybrid" and not under):
        ap.error("--out must be runs/eval/frontier[-name] (hybrid: a subdirectory of runs/eval/frontier); "
                 "frontier outputs must never leave runs/eval/")
    if a.backend == "codex" and a.mode != "hybrid":
        ap.error("--backend codex needs --mode hybrid")
    if a.concurrency > (6 if a.backend == "codex" else 4):
        ap.error(f"concurrency is capped at {6 if a.backend == 'codex' else 4} on the Mac")
    work = a.out.resolve() / "cwd"  # neutral cwd: no project files or CLAUDE.md picked up
    work.mkdir(parents=True, exist_ok=True)
    cases = load_cases(a.cases, truth_dir=a.truth_dir if a.truth_dir.exists() else None, n_per_dir=a.n_per_dir, seed=a.seed)
    config = {"label": a.label, "model": f"claude {a.model} via `claude -p`", "endpoint": "claude CLI", "constrained": False,
              "schema_in_prompt": True, "cases": [str(p) for p in a.cases], "n_per_dir": a.n_per_dir, "invocation": CMD,
              "prices": {}}
    gen = lambda c: claude_cli(c.prompt, a.model, a.timeout, a.retries, work)  # noqa: E731
    if a.mode == "hybrid":
        from gst_recon.hybrid.docschema import doc_json_schema
        from gst_recon.hybrid.run import make_generator

        doc_system = lambda m: f"{m}\n\nThe JSON must conform to this JSON Schema:\n{json.dumps(doc_json_schema(), separators=(',', ':'))}"  # noqa: E731
        flag = a.schema_mode == "flag"
        if a.backend == "codex":
            call = lambda msgs: codex_cli(msgs[1]["content"], a.model, a.timeout, a.retries, work, system=msgs[0]["content"],  # noqa: E731
                                          json_schema=doc_json_schema(), effort=a.effort)
            config |= {"model": f"{a.model} via `codex exec` (effort {a.effort})", "endpoint": "codex exec", "invocation": CODEX_CLEAN,
                       "schema_in_prompt": False}
        else:
            call = lambda msgs: claude_cli(msgs[1]["content"], a.model, a.timeout, a.retries, work,  # noqa: E731
                                           system=msgs[0]["content"] if flag else doc_system(msgs[0]["content"]),
                                           json_schema=doc_json_schema() if flag else None)
        gen = make_generator(call, a.out, concurrency=a.concurrency)
        config |= {"label": f"{a.label} hybrid", "mode": "hybrid", "schema_mode": "output-schema" if a.backend == "codex" else a.schema_mode}
    agg = run_eval(cases, gen, a.out, config,
                   concurrency=a.concurrency, progress=lambda d, n: print(f"\r{d}/{n}", end="", file=sys.stderr, flush=True))
    print(file=sys.stderr)
    print((a.out / "table.md").read_text())
    return 1 if agg["n_errors"] == agg["n_cases"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
