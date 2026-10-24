"""Run events for the UI: live tokens from SGLang (OpenAI-compatible stream) or a replay of a recorded run.

Events are plain dicts: start, tok {t}, done {stats}, error {message}. A finished live run is recorded
(with per-chunk timing) so the same run can be replayed later at its real speed when the endpoint is down.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx

from gst_recon.eval.client import chat_url, json_schema_format
from gst_recon.eval.prompts import build_messages


def request_body(prompt: str, model: str, constrained: bool, max_tokens: int) -> dict[str, Any]:
    """The exact request the eval harness sends: constrained runs pass the schema as response_format,
    unconstrained runs get the same JSON Schema appended to the system prompt."""
    body: dict[str, Any] = {"model": model, "messages": build_messages(prompt, schema_in_prompt=not constrained),
                            "max_tokens": max_tokens, "temperature": 0.0, "stream": True,
                            "stream_options": {"include_usage": True}}
    if constrained:
        body["response_format"] = json_schema_format()
    return body


def _stats(t0: float, t_first: float | None, t_end: float, usage: dict, chunks: int, finish: str | None) -> dict:
    n = usage.get("completion_tokens") or chunks
    decode = t_end - t_first if t_first else 0.0
    return {"ttft_s": round(t_first - t0, 3) if t_first else None, "latency_s": round(t_end - t0, 3),
            "completion_tokens": n, "prompt_tokens": usage.get("prompt_tokens"),
            "tps": round(n / decode, 1) if decode > 0 and n > 1 else None, "finish_reason": finish}


async def live(base_url: str, api_key: str, body: dict, record: dict | None = None) -> AsyncIterator[dict]:
    """Stream one completion. `record` (meta to store) makes the run replayable."""
    t0 = time.perf_counter()
    t_first: float | None = None
    usage: dict = {}
    finish: str | None = None
    chunks: list[list] = []
    yield {"type": "start", "mode": "live", "model": body["model"], "constrained": "response_format" in body}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(900, connect=5)) as client:
            async with client.stream("POST", chat_url(base_url), json=body, headers={"Authorization": f"Bearer {api_key}"}) as r:
                if r.status_code != 200:
                    detail = (await r.aread()).decode(errors="replace")[:300]
                    yield {"type": "error", "message": f"SGLang answered HTTP {r.status_code}: {detail}"}
                    return
                async for line in r.aiter_lines():
                    if not line.startswith("data:") or line.strip() == "data: [DONE]":
                        continue
                    data = json.loads(line[5:])
                    usage = data.get("usage") or usage
                    for ch in data.get("choices") or []:
                        finish = ch.get("finish_reason") or finish
                        text = (ch.get("delta") or {}).get("content")
                        if text:
                            now = time.perf_counter()
                            t_first = t_first or now
                            chunks.append([round((now - t0) * 1000), text])
                            yield {"type": "tok", "t": text}
    except (httpx.HTTPError, ValueError) as e:
        yield {"type": "error", "message": f"{type(e).__name__}: {e}"}
        return
    stats = _stats(t0, t_first, time.perf_counter(), usage, len(chunks), finish)
    if record is not None and finish == "stop":
        save_recording(record, body, stats, chunks)
    yield {"type": "done", "stats": stats}


# ------------------------------------------------------------------ recordings

def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", s)


def save_recording(record: dict, body: dict, stats: dict, chunks: list[list]) -> Path:
    d = Path(record["dir"])
    d.mkdir(parents=True, exist_ok=True)
    constrained = "response_format" in body
    path = d / f"{_slug(record['case_id'])}__{_slug(body['model'])}__{'con' if constrained else 'unc'}.json"
    path.write_text(json.dumps({"case_id": record["case_id"], "model": body["model"], "constrained": constrained,
                                "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "stats": stats, "chunks": chunks},
                               separators=(",", ":")))
    return path


def list_recordings(d: Path) -> list[dict]:
    out = []
    for p in sorted(d.glob("*.json")) if d.is_dir() else []:
        try:
            rec = json.loads(p.read_text())
            out.append({k: rec[k] for k in ("case_id", "model", "constrained", "recorded_at")} | {"path": p})
        except (ValueError, KeyError):
            continue  # a half-written or foreign file is not a recording
    return out


def pick_recording(d: Path, case_id: str, model: str, constrained: bool) -> Path | None:
    """Best recording for the request: exact, then same model, then anything for the case."""
    mine = [r for r in list_recordings(d) if r["case_id"] == case_id]
    for ok in (lambda r: r["model"] == model and r["constrained"] == constrained, lambda r: r["model"] == model, lambda r: True):
        for r in mine:
            if ok(r):
                return r["path"]
    return None


async def replay(path: Path, speed: float) -> AsyncIterator[dict]:
    """Re-emit a recording with its original inter-token timing divided by `speed` (inf = instant)."""
    rec = json.loads(path.read_text())
    yield {"type": "start", "mode": "replay", "model": rec["model"], "constrained": rec["constrained"],
           "speed": speed, "recorded_at": rec.get("recorded_at")}
    start = time.perf_counter()
    for off_ms, text in rec["chunks"]:
        wait = start + off_ms / 1000 / speed - time.perf_counter()
        if wait > 0.002 and speed != float("inf"):
            await asyncio.sleep(wait)
        yield {"type": "tok", "t": text}
    yield {"type": "done", "stats": rec["stats"]}
