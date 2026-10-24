"""Hybrid run events: one streamed model call per document, then the code reconciler (gst_recon.hybrid).

Events: start {docs}, doc_start, tok {doc_id}, doc_done {stats, valid}, doc_error, reconciling, assembled {text, trace, problems},
done {stats}. Live and replay emit the same stream; the reconciler always runs for real on the (live or recorded) replies.
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from gst_recon.eval.prompts import build_doc_messages
from gst_recon.hybrid.docschema import DocRecord, doc_json_schema
from gst_recon.hybrid.inputs import parse_header, split_docs, split_sections
from gst_recon.hybrid.reconcile import reconcile_prompt
from gst_recon.hybrid.run import parse_doc

from . import stream

DOC_MAX_TOKENS = 4096  # same cap as `python -m gst_recon.eval run --mode hybrid`


def split_case(prompt: str) -> tuple[str, list]:
    """(case header block, document sections) exactly as the eval harness slices prompt.txt."""
    sec = split_sections(prompt)
    return parse_header(sec["CASE"]).text, split_docs(sec["INVOICES"])


def doc_request(header: str, block: str, model: str, constrained: bool, max_tokens: int = DOC_MAX_TOKENS) -> dict[str, Any]:
    body: dict[str, Any] = {"model": model, "messages": build_doc_messages(header, block, schema_in_prompt=not constrained),
                            "max_tokens": max_tokens, "temperature": 0.0, "stream": True, "stream_options": {"include_usage": True}}
    if constrained:
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": "doc", "schema": doc_json_schema()}}
    return body


def doc_validity(text: str) -> dict:
    """Strict check of one reply against the per-document schema (the reconciler itself reads leniently)."""
    try:
        DocRecord.model_validate_json(text)
    except ValidationError as e:
        bad_json = any(x["type"] in ("json_invalid", "json_type") for x in e.errors())
        return {"json": not bad_json, "schema": False}
    return {"json": True, "schema": True}


def assemble(prompt: str, texts: dict[str, str]) -> dict:
    """Per-document replies -> {text: ReconOutput JSON, trace, problems}. Runs the real reconciler."""
    records, problems = {}, {}
    for doc_id, text in texts.items():
        rec, why = parse_doc(text)
        if rec is None:
            problems[doc_id] = why
        else:
            records[doc_id] = rec
    t0 = time.perf_counter()
    out, trace = reconcile_prompt(prompt, records)
    return {"text": out.model_dump_json(), "trace": trace, "problems": problems,
            "reconcile_ms": round((time.perf_counter() - t0) * 1000)}


def total_stats(docs: list[dict], reconcile_ms: int) -> dict:
    """Aggregate of the per-document call stats (calls run one after another)."""
    s = [d["stats"] for d in docs]
    toks = sum(x["completion_tokens"] or 0 for x in s)
    decode = sum(x["latency_s"] - (x["ttft_s"] or 0) for x in s)
    return {"ttft_s": s[0]["ttft_s"] if s else None, "latency_s": round(sum(x["latency_s"] for x in s) + reconcile_ms / 1000, 3),
            "completion_tokens": toks, "prompt_tokens": sum(x["prompt_tokens"] or 0 for x in s),
            "tps": round(toks / decode, 1) if decode > 0 and toks > 1 else None, "docs": len(s), "reconcile_ms": reconcile_ms,
            "finish_reason": "length" if any(x["finish_reason"] == "length" for x in s) else "stop"}


async def _finish(prompt: str, docs: list[dict]) -> AsyncIterator[dict]:
    yield {"type": "reconciling"}
    res = assemble(prompt, {d["doc_id"]: "".join(c[1] for c in d["chunks"]) for d in docs})
    yield {"type": "assembled", "text": res["text"], "trace": res["trace"], "problems": res["problems"]}
    yield {"type": "done", "stats": total_stats(docs, res["reconcile_ms"])}


async def live(base_url: str, api_key: str, prompt: str, model: str, constrained: bool, record: dict | None = None,
               max_tokens: int = DOC_MAX_TOKENS) -> AsyncIterator[dict]:
    header, sections = split_case(prompt)
    yield {"type": "start", "mode": "live", "kind": "hybrid", "model": model, "constrained": constrained,
           "docs": [d.doc_id for d in sections]}
    done: list[dict] = []
    for sec in sections:
        yield {"type": "doc_start", "doc_id": sec.doc_id}
        body = doc_request(header, sec.block, model, constrained, max_tokens)
        async for ev in stream.complete(base_url, api_key, body, doc_id=sec.doc_id):
            if ev["type"] == "tok":
                yield ev
            elif ev["type"] == "error":
                yield {**ev, "type": "doc_error"}
            else:
                text = "".join(c[1] for c in ev["chunks"])
                done.append({"doc_id": sec.doc_id, "stats": ev["stats"], "chunks": ev["chunks"]})
                yield {"type": "doc_done", "doc_id": sec.doc_id, "stats": ev["stats"], "valid": doc_validity(text)}
    if len(done) < len(sections):
        yield {"type": "error", "message": f"{len(sections) - len(done)} document call(s) failed."}
        return
    if record is not None and all(d["stats"]["finish_reason"] == "stop" for d in done):
        stream.save_hybrid_recording(record, model, constrained, done)
    async for ev in _finish(prompt, done):
        yield ev


async def replay(path: Path, prompt: str, speed: float) -> AsyncIterator[dict]:
    """Re-emit a hybrid recording: each document's tokens at their recorded pacing, then the real reconciler."""
    rec = json.loads(path.read_text())
    yield {"type": "start", "mode": "replay", "kind": "hybrid", "model": rec["model"], "constrained": rec["constrained"],
           "speed": speed, "recorded_at": rec.get("recorded_at"), "docs": [d["doc_id"] for d in rec["docs"]]}
    for d in rec["docs"]:
        yield {"type": "doc_start", "doc_id": d["doc_id"]}
        async for ev in stream._emit(d["chunks"], speed, doc_id=d["doc_id"]):
            yield ev
        text = "".join(c[1] for c in d["chunks"])
        yield {"type": "doc_done", "doc_id": d["doc_id"], "stats": d["stats"], "valid": doc_validity(text)}
    async for ev in _finish(prompt, rec["docs"]):
        yield ev
