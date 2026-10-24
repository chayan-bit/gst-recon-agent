"""CLI: python -m gst_recon.eval {run,report}  (see gst_recon/eval/README.md)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from gst_recon.eval import report as rep
from gst_recon.eval.cases import load_cases
from gst_recon.eval.client import chat, json_schema_format
from gst_recon.eval.prompts import build_messages
from gst_recon.eval.runner import run_eval


def _price(a: argparse.Namespace) -> dict:
    return {k: getattr(a, k) for k in ("gpu_hour_usd", "api_in_per_mtok", "api_out_per_mtok") if getattr(a, k) is not None}


def cmd_run(a: argparse.Namespace) -> int:
    truth = a.truth_dir if a.truth_dir and a.truth_dir.exists() else None
    cases = load_cases(a.cases, truth_dir=truth, n_per_dir=a.n_per_dir, seed=a.seed)
    fmt = json_schema_format() if a.constrained else None
    extra = json.loads(a.extra_body) if a.extra_body else {}
    if a.no_thinking:
        extra.setdefault("chat_template_kwargs", {"enable_thinking": False})
    api_key = a.api_key or "EMPTY"

    def gen(c):
        return chat(a.endpoint, a.model, build_messages(c.prompt, schema_in_prompt=not a.constrained and a.schema_in_prompt),
                    response_format=fmt, max_tokens=a.max_tokens, temperature=a.temperature, timeout=a.timeout,
                    api_key=api_key, extra=extra, retries=a.retries)

    config = {"label": a.label or a.out.name, "model": a.model, "endpoint": a.endpoint, "constrained": a.constrained,
              "schema_in_prompt": (not a.constrained) and a.schema_in_prompt, "max_tokens": a.max_tokens,
              "temperature": a.temperature, "extra_body": extra, "cases": [str(p) for p in a.cases], "n_per_dir": a.n_per_dir,
              "truth_dir": str(truth) if truth else None, "prices": _price(a)}
    agg = run_eval(cases, gen, a.out, config, concurrency=a.concurrency, resume=not a.no_resume,
                   progress=lambda d, n: print(f"\r{d}/{n}", end="", file=sys.stderr, flush=True))
    print(file=sys.stderr)
    print((a.out / "table.md").read_text())
    return 1 if agg["n_errors"] == agg["n_cases"] else 0


def cmd_report(a: argparse.Namespace) -> int:
    runs = rep.load_runs(a.runs)
    if not runs:
        print("no run directories with aggregate.json found", file=sys.stderr)
        return 2
    order = {k: i for i, k in enumerate(a.order or [])}
    runs.sort(key=lambda r: order.get(r["label"], order.get(Path(r["dir"]).name, len(order))))
    base = rep.load_baselines(a.baselines)
    appendices = [p.read_text() for p in a.append or []]
    md = rep.report_md(runs, base, a.ref, appendices)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(md)
    png = rep.chart(runs, base, a.chart or a.out.with_suffix(".png"))
    print(f"wrote {a.out} and {png} ({len(runs)} runs)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m gst_recon.eval")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="send rendered cases to an OpenAI-compatible endpoint and score the replies")
    r.add_argument("--endpoint", required=True, help="e.g. http://localhost:30000/v1")
    r.add_argument("--model", required=True)
    r.add_argument("--cases", type=Path, nargs="+", required=True, help="dir(s) of rendered case dirs, e.g. data/rendered/test_iid")
    r.add_argument("--out", type=Path, required=True, help="runs/eval/<name>/")
    r.add_argument("--label", help="name shown in reports (default: out dir name)")
    r.add_argument("--constrained", action=argparse.BooleanOptionalAction, default=False,
                   help="send response_format json_schema (grammar-constrained decoding); default unconstrained")
    r.add_argument("--schema-in-prompt", action=argparse.BooleanOptionalAction, default=True,
                   help="unconstrained runs only: append the JSON Schema to the system prompt")
    r.add_argument("--concurrency", type=int, default=16)
    r.add_argument("--max-tokens", type=int, default=8192)
    r.add_argument("--temperature", type=float, default=0.0)
    r.add_argument("--retries", type=int, default=2, help="per-request retries on 5xx/429/connection errors")
    r.add_argument("--timeout", type=float, default=900.0)
    r.add_argument("--no-thinking", action="store_true", help='send chat_template_kwargs {"enable_thinking": false} (Qwen3)')
    r.add_argument("--extra-body", help="JSON object merged into the request body")
    r.add_argument("--api-key", help="bearer token (SGLang ignores it unless started with --api-key)")
    r.add_argument("--n-per-dir", type=int, help="seeded random sample of this many cases per --cases dir")
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--truth-dir", type=Path, default=Path("data/truth"),
                   help="truth Case JSONs, for context-dependent document detection (default data/truth if present)")
    r.add_argument("--no-resume", action="store_true", help="regenerate cases even if cached under --out")
    r.add_argument("--gpu-hour-usd", type=float, help="price of the serving GPU per hour, for the cost estimate")
    r.add_argument("--api-in-per-mtok", type=float, help="closed API list price, USD per million input tokens")
    r.add_argument("--api-out-per-mtok", type=float, help="closed API list price, USD per million output tokens")
    r.set_defaults(fn=cmd_run)
    p = sub.add_parser("report", help="comparison table and bar chart across run directories")
    p.add_argument("--runs", type=Path, nargs="+", required=True, help="run dirs, or parents of run dirs (shell globs fine)")
    p.add_argument("--out", type=Path, required=True, help="reports/results.md (PNG goes next to it)")
    p.add_argument("--chart", type=Path, help="PNG path (default: --out with .png)")
    p.add_argument("--baselines", type=Path, help="JSON from `python -m gst_recon.sim.audit --json FILE` (trivial baselines)")
    p.add_argument("--ref", help="run label or dir name to compute paired differences against")
    p.add_argument("--order", nargs="+", help="run labels or dir names in display order")
    p.add_argument("--append", type=Path, nargs="+", help="markdown files appended verbatim (e.g. the AuditKIT section)")
    p.set_defaults(fn=cmd_report)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
