"""Run cases through a generator, persist per-case JSON (resumable), score, aggregate."""

from __future__ import annotations

import hashlib
import json
import statistics
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np

from gst_recon.eval.cases import EvalCase
from gst_recon.eval.cost import cost_per_1000
from gst_recon.eval.guard import mark_eval_dir
from gst_recon.eval.metrics import case_metrics
from gst_recon.eval.prompts import SYSTEM_PROMPT
from gst_recon.eval.stats import breakdowns, summarize
from gst_recon.rewards import parse_output
from gst_recon.schema import output_json_schema

Generate = Callable[[EvalCase], dict[str, Any]]  # -> {text, latency_s, prompt_tokens, completion_tokens, error, ...}


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_text(text)
    tmp.replace(path)


def _git_sha() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              cwd=Path(__file__).parent, timeout=5).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def fingerprint_prompts() -> dict[str, str]:
    h = lambda s: hashlib.sha256(s.encode()).hexdigest()[:12]  # noqa: E731
    return {"system_prompt": h(SYSTEM_PROMPT), "output_schema": h(json.dumps(output_json_schema(), sort_keys=True))}


def _case_path(out: Path, case_id: str) -> Path:
    return out / "cases" / f"{case_id}.json"


def generate_all(cases: list[EvalCase], gen: Generate, out: Path, *, concurrency: int, resume: bool = True,
                 progress: Callable[[int, int], None] | None = None) -> dict[str, Any]:
    """Call `gen` for each case not already cached; write cases/<id>.json. Returns fresh-request stats."""
    (out / "cases").mkdir(parents=True, exist_ok=True)
    todo = [c for c in cases if not (resume and _usable(_case_path(out, c.case_id)))]
    stats = {"n_requests": 0, "prompt_tokens": 0, "completion_tokens": 0, "wall_s": 0.0}

    def work(c: EvalCase) -> tuple[EvalCase, dict]:
        return c, gen(c)

    t0 = time.perf_counter()
    done = 0
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as ex:
        for fut in as_completed([ex.submit(work, c) for c in todo]):
            c, r = fut.result()
            rec = {"case_id": c.case_id, "split": c.split, "difficulty": c.difficulty, "ocr_recall": c.meta.get("ocr_recall"),
                   "ocr_bucket": c.ocr_bucket, "length_bucket": c.length_bucket, "raw": r.get("text", ""), "parsed": parse_output(r.get("text", "")),
                   **{k: v for k, v in r.items() if k != "text"}}
            _atomic_write(_case_path(out, c.case_id), json.dumps(rec))
            stats["n_requests"] += 1
            stats["prompt_tokens"] += r.get("prompt_tokens") or 0
            stats["completion_tokens"] += r.get("completion_tokens") or 0
            done += 1
            if progress:
                progress(done, len(todo))
    stats["wall_s"] = time.perf_counter() - t0
    return stats


def _usable(path: Path) -> bool:
    """A cached case counts as done unless it is missing or recorded a transport error."""
    try:
        return json.loads(path.read_text()).get("error") is None
    except (OSError, ValueError):
        return False


def _accumulate_run_stats(out: Path, fresh: dict[str, Any]) -> dict[str, Any]:
    p = out / "run_stats.json"
    total = json.loads(p.read_text()) if p.exists() else {"n_requests": 0, "prompt_tokens": 0, "completion_tokens": 0, "wall_s": 0.0}
    for k in total:
        total[k] += fresh.get(k, 0)
    _atomic_write(p, json.dumps(total, indent=1))
    return total


def score_all(cases: list[EvalCase], out: Path) -> list[dict]:
    """Rescore every cached case from its stored raw output (so scorer fixes apply without regenerating)."""
    records = []
    for c in cases:
        p = _case_path(out, c.case_id)
        rec = json.loads(p.read_text()) if p.exists() else {"case_id": c.case_id, "split": c.split, "difficulty": c.difficulty,
                                                           "ocr_recall": c.meta.get("ocr_recall"), "raw": "", "error": "missing"}
        rec |= {"split": c.split, "difficulty": c.difficulty, "ocr_bucket": c.ocr_bucket, "length_bucket": c.length_bucket}
        rec["metrics"] = case_metrics(rec.get("raw", ""), c)
        records.append(rec)
    return records


def aggregate(records: list[dict], config: dict, run_stats: dict, ctx_sources: set[str]) -> dict[str, Any]:
    lat = [r["latency_s"] for r in records if r.get("latency_s") is not None]
    n_req, wall = run_stats["n_requests"], run_stats["wall_s"]
    agg = {
        "label": config["label"], "config": config, "n_cases": len(records),
        "n_errors": sum(1 for r in records if r.get("error")),
        "n_context_overflow": sum(1 for r in records if "context length" in (r.get("error") or "")),
        "n_truncated": sum(1 for r in records if r.get("finish_reason") == "length"),
        "context_source": "truth" if ctx_sources == {"truth"} else "proxy (no truth Case JSON; BLOCKED-reason docs)",
        "overall": summarize(records), "breakdowns": breakdowns(records),
        "throughput": {
            "n_requests": n_req, "wall_s": wall,
            "req_per_s": n_req / wall if wall > 0 else None,
            "out_tok_per_s": run_stats["completion_tokens"] / wall if wall > 0 else None,
            "mean_prompt_tokens": run_stats["prompt_tokens"] / n_req if n_req else None,
            "mean_completion_tokens": run_stats["completion_tokens"] / n_req if n_req else None,
            "latency_p50_s": statistics.median(lat) if lat else None,
            "latency_p95_s": float(np.percentile(lat, 95)) if lat else None,
        },
    }
    prices = config.get("prices") or {}
    agg["cost_per_1000_cases"] = cost_per_1000(
        n_requests=n_req, wall_s=wall, prompt_tokens=run_stats["prompt_tokens"],
        completion_tokens=run_stats["completion_tokens"], gpu_hour_usd=prices.get("gpu_hour_usd"),
        api_in_per_mtok=prices.get("api_in_per_mtok"), api_out_per_mtok=prices.get("api_out_per_mtok"))
    costs = [r["cost_usd"] for r in records if r.get("cost_usd") is not None]
    if costs and agg["cost_per_1000_cases"]["api_usd"] is None:  # CLI-reported list-basis cost, e.g. the frontier baseline
        agg["cost_per_1000_cases"]["api_usd"] = sum(costs) / len(costs) * 1000
        agg["cost_per_1000_cases"]["api_usd_source"] = "measured: total_cost_usd reported by the claude CLI (list basis)"
    return agg


def run_eval(cases: list[EvalCase], gen: Generate, out: Path, config: dict, *, concurrency: int, resume: bool = True,
             progress: Callable[[int, int], None] | None = None) -> dict[str, Any]:
    """Generate (resumable), score, write aggregate.json and table.md; returns the aggregate."""
    from gst_recon.eval.report import run_table_md  # local: report pulls matplotlib lazily, keep import order simple

    out.mkdir(parents=True, exist_ok=True)
    mark_eval_dir(out)
    config = {**config, "concurrency": concurrency, "git_sha": _git_sha(), "fingerprints": fingerprint_prompts(),
              "started": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    _atomic_write(out / "config.json", json.dumps(config, indent=1))
    fresh = generate_all(cases, gen, out, concurrency=concurrency, resume=resume, progress=progress)
    run_stats = _accumulate_run_stats(out, fresh)
    records = score_all(cases, out)
    agg = aggregate(records, config, run_stats, {r["metrics"]["context_source"] for r in records})
    _atomic_write(out / "aggregate.json", json.dumps(agg, indent=1))
    _atomic_write(out / "scores.jsonl", "\n".join(json.dumps({k: r[k] for k in ("case_id", "split", "difficulty", "ocr_bucket", "length_bucket", "metrics", "error", "latency_s",
                                                                                 "prompt_tokens", "completion_tokens") if k in r}) for r in records) + "\n")
    _atomic_write(out / "table.md", run_table_md(agg))
    return agg
