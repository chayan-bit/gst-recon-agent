"""Hybrid mode for the eval harness: one model call per document, then the code reconciler.

`make_generator(call, out)` returns a `Generate` for `eval.runner.run_eval`. The case record's `raw` is the
assembled ReconOutput JSON (scored by the same score() and eval metrics as end-to-end runs); the record also
keeps every per-document reply (`doc_raw`) and the reconciler trace (`trace`), the audit trail.
Per-document replies are cached under <out>/docs/<case_id>/<doc_id>.json, so re-running with --no-resume
re-reconciles stored replies without new model calls.
"""

from __future__ import annotations

import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from gst_recon.eval.prompts import build_doc_messages
from gst_recon.hybrid.docschema import MODEL_CATEGORIES, DocRecord
from gst_recon.hybrid.inputs import parse_header, split_docs, split_sections
from gst_recon.hybrid.reconcile import reconcile_prompt
from gst_recon.rewards.scoring import _fill
from gst_recon.schema import LinePurpose

Call = Callable[[list[dict]], dict[str, Any]]  # messages -> {text, prompt_tokens, completion_tokens, error, ...}
DOC_WORKERS = 4  # per case; the global in-flight cap is the run's --concurrency
_PURPOSES = {p.value for p in LinePurpose}


def _json_obj(text: str) -> dict | None:
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    for cand in (t, t[t.find("{"): t.rfind("}") + 1]):
        try:
            obj = json.loads(cand)
        except (ValueError, TypeError):
            continue
        if isinstance(obj, dict):
            return obj
    return None


def parse_doc(text: str) -> tuple[DocRecord | None, str]:
    """Lenient: missing fields read as 0/""/false, an unknown category or purpose reads as normal/business.
    Returns (record or None, problem description)."""
    obj = _json_obj(text)
    if obj is None:
        return None, "unparseable"
    lines = obj.get("line_items")
    if isinstance(lines, list):
        obj["line_items"] = [{**li, "itc_category": li.get("itc_category") if li.get("itc_category") in MODEL_CATEGORIES else "normal",
                              "purpose": li.get("purpose") if li.get("purpose") in _PURPOSES else "business"}
                             for li in lines if isinstance(li, dict)]
    obj.setdefault("doc_type", "invoice")
    try:
        return DocRecord.model_validate(_fill(obj, DocRecord)), ""
    except ValidationError as e:
        return None, f"invalid: {str(e)[:200]}"


def _cached(path: Path) -> dict | None:
    try:
        rec = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return rec if rec.get("error") is None else None


def make_generator(call: Call, out: Path, *, concurrency: int) -> Callable:
    gate = threading.BoundedSemaphore(max(1, concurrency))

    def one_doc(case_id: str, header: str, doc) -> dict:
        path = out / "docs" / case_id / f"{doc.doc_id}.json"
        hit = _cached(path)
        if hit is not None:
            return {**hit, "cached": True}
        with gate:
            r = call(build_doc_messages(header, doc.block))
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        tmp.write_text(json.dumps(r))
        tmp.replace(path)
        return r

    def gen(c) -> dict[str, Any]:
        t0 = time.perf_counter()
        try:
            sec = split_sections(c.prompt)
            header, docs = parse_header(sec["CASE"]).text, split_docs(sec["INVOICES"])
        except (KeyError, ValueError, StopIteration) as e:
            return {"text": "", "error": f"prompt parse: {e}"}
        with ThreadPoolExecutor(max_workers=DOC_WORKERS) as ex:
            replies = dict(zip([d.doc_id for d in docs], ex.map(lambda d: one_doc(c.case_id, header, d), docs)))
        records, problems = {}, {}
        for doc_id, r in replies.items():
            rec, why = parse_doc(r.get("text") or "") if not r.get("error") else (None, f"transport: {r['error'][:200]}")
            if rec is None:
                problems[doc_id] = why
            else:
                records[doc_id] = rec
        transport = [d for d, w in problems.items() if w.startswith("transport")]
        try:
            assembled, trace = reconcile_prompt(c.prompt, records)
            text = assembled.model_dump_json()
        except (KeyError, ValueError, StopIteration) as e:  # a prompt the parsers cannot read: scored as no output
            text, trace = "", {"reconcile_error": f"{type(e).__name__}: {e}"}
        fresh = [r for r in replies.values() if not r.get("cached")]
        return {"text": text, "latency_s": time.perf_counter() - t0,
                "prompt_tokens": sum(r.get("prompt_tokens") or 0 for r in replies.values()),
                "completion_tokens": sum(r.get("completion_tokens") or 0 for r in replies.values()),
                "finish_reason": "length" if any(r.get("finish_reason") == "length" for r in replies.values()) else "stop",
                "error": f"{len(transport)} document call(s) failed: {transport}" if transport else None,
                "n_docs": len(docs), "n_fresh_calls": len(fresh), "doc_problems": problems,
                "doc_raw": {d: r.get("text") or "" for d, r in replies.items()}, "trace": trace}

    return gen
