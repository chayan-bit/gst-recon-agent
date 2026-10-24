"""FastAPI backend for the demo UI: cases, model list, streamed runs (live or replay), table view model.

Config (env): SGLANG_BASE_URL (default http://127.0.0.1:30000/v1), SGLANG_API_KEY, DEMO_CASE_DIRS (":"-separated;
default <repo>/examples), DEMO_RECORDINGS (default demo/recordings), DEMO_RECORD=0 to stop saving live runs.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import hybrid, stream
from .cases import Registry, detail, summary
from .view import build_view

HERE = Path(__file__).resolve().parent
DEMO_DIR = HERE.parent
REPO = DEMO_DIR.parent
STATIC = DEMO_DIR / "static"

BASE_URL = os.environ.get("SGLANG_BASE_URL", "http://127.0.0.1:30000/v1").rstrip("/")
API_KEY = os.environ.get("SGLANG_API_KEY", "EMPTY")
RECORDINGS = Path(os.environ.get("DEMO_RECORDINGS", DEMO_DIR / "recordings"))
RECORD = os.environ.get("DEMO_RECORD", "1") != "0"
ROOT_URL = BASE_URL.removesuffix("/v1")
DEFAULT_MAX_TOKENS = 16000

registry = Registry([Path(p) for p in os.environ.get("DEMO_CASE_DIRS", str(REPO / "examples")).split(":") if p])
run_lock = asyncio.Lock()  # one generation at a time: the demo must never pile load onto a shared GPU
app = FastAPI(title="gst-recon demo")


async def _get(url: str, timeout: float = 6.0) -> dict | list | None:
    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.get(url, headers={"Authorization": f"Bearer {API_KEY}"})
            return r.json() if r.status_code == 200 else None
    except (httpx.HTTPError, ValueError):
        return None


def _reconciler_version() -> str:
    """Short sha of the last commit that touched gst_recon/hybrid (the code reconciler), or "" outside a git checkout."""
    try:
        r = subprocess.run(["git", "log", "-1", "--format=%h", "--", "gst_recon/hybrid"], cwd=REPO, capture_output=True, text=True, timeout=3)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


RECONCILER = _reconciler_version()


@app.get("/api/health")
async def health() -> dict:
    models = await _get(f"{BASE_URL}/models")
    load = await _get(f"{ROOT_URL}/get_load") if models else None
    row = load[0] if isinstance(load, list) and load else {}
    return {"live": models is not None, "running": row.get("num_reqs"), "waiting": row.get("num_waiting_reqs"),
            "recordings": len(stream.list_recordings(RECORDINGS)), "recording_enabled": RECORD, "reconciler": RECONCILER}


KNOWN_LABELS = {"teacher": "Teacher 30B", "base:perdoc": "Per-document (PERDOC)", "base:grpo": "Fine-tuned (GRPO)"}


def _model_entry(name: str) -> dict:
    base, _, adapter = name.partition(":")
    label = KNOWN_LABELS.get(name) or ("Base model" if not adapter else f"Fine-tuned ({adapter.upper()})")
    return {"name": name, "label": label, "adapter": adapter or None, "base": base}


@app.get("/api/models")
async def models() -> dict:
    """Names to send as `model`: a base model, or `base:adapter` for each LoRA that /v1/models reports.
    Models that only exist as recordings (e.g. a bigger model run earlier) are listed with recorded_only."""
    data = await _get(f"{BASE_URL}/models")
    served = []
    if isinstance(data, dict) and data.get("data"):
        served = [f"{m['parent']}:{m['id']}" if m.get("parent") else m["id"] for m in data["data"]]
    recorded = sorted({r["model"] for r in stream.list_recordings(RECORDINGS)} - set(served))
    entries = [_model_entry(n) for n in sorted(served, key=lambda n: (":" in n, n))]
    entries += [{**_model_entry(n), "recorded_only": True} for n in sorted(recorded, key=lambda n: (":" in n, n))]
    return {"models": entries, "source": "server" if served else "recordings"}


@app.get("/api/cases")
def cases() -> list[dict]:
    return [summary(c) for c in registry.all()]


class DirBody(BaseModel):
    path: str


@app.post("/api/cases/dir")
def add_case_dir(body: DirBody) -> dict:
    """Open another case directory (a case itself, or a directory of cases)."""
    root = Path(body.path).expanduser()
    if not root.is_dir():
        raise HTTPException(404, f"not a directory: {body.path}")
    n = registry.add(root)
    if n == 0:
        raise HTTPException(422, "no <case>/prompt.txt found there")
    return {"added": n, "cases": [summary(c) for c in registry.all()]}


def _case(case_id: str):
    c = registry.get(case_id)
    if c is None:
        raise HTTPException(404, f"unknown case {case_id}")
    return c


@app.get("/api/cases/{case_id}")
def case_detail(case_id: str) -> dict:
    return detail(_case(case_id))


@app.get("/api/cases/{case_id}/images/{doc_id}")
def case_image(case_id: str, doc_id: str) -> FileResponse:
    path = _case(case_id).images.get(doc_id.upper())
    if path is None:
        raise HTTPException(404, "no scan for this document")
    return FileResponse(path, headers={"Cache-Control": "max-age=3600"})


class RunBody(BaseModel):
    case_id: str
    model: str = "base"
    constrained: bool = True
    mode: str = "live"  # live | replay
    kind: str = "e2e"  # e2e (one call returns everything) | hybrid (one call per document, code reconciles)
    max_tokens: int | None = None
    speed: float = 1.0  # replay only


def _max_tokens(meta: dict, asked: int | None) -> int:
    """Same cap rule as the eval harness: 2x the reference length + 1000, so a degenerate loop ends."""
    target = meta.get("target_tokens")
    return asked or (min(DEFAULT_MAX_TOKENS, int(2 * target) + 1000) if target else DEFAULT_MAX_TOKENS)


@app.post("/api/run")
async def run(body: RunBody) -> StreamingResponse:
    case = _case(body.case_id)

    async def events():
        if run_lock.locked():
            yield {"type": "error", "message": "A run is already in progress."}
            return
        async with run_lock:
            rec = {"dir": str(RECORDINGS), "case_id": body.case_id} if RECORD else None
            if body.mode == "replay":
                path = stream.pick_recording(RECORDINGS, body.case_id, body.model, body.constrained, body.kind)
                if path is None:
                    yield {"type": "error", "message": "No recording for this case yet. Run it live once to record it."}
                    return
                speed = max(body.speed, 0.1)
                events = hybrid.replay(path, case.prompt, speed) if body.kind == "hybrid" else stream.replay(path, speed)
            elif body.kind == "hybrid":
                events = hybrid.live(BASE_URL, API_KEY, case.prompt, body.model, body.constrained, rec, body.max_tokens or hybrid.DOC_MAX_TOKENS)
            else:
                req = stream.request_body(case.prompt, body.model, body.constrained, _max_tokens(case.meta, body.max_tokens))
                events = stream.live(BASE_URL, API_KEY, req, rec)
            async for ev in events:
                yield ev

    async def ndjson():
        async for ev in events():
            yield json.dumps(ev, separators=(",", ":")) + "\n"

    return StreamingResponse(ndjson(), media_type="application/x-ndjson", headers={"Cache-Control": "no-store"})


class ViewBody(BaseModel):
    case_id: str
    text: str
    final: bool = False
    traces: dict | None = None  # doc_id -> JSON, shown per row (hybrid mode decision trace)


@app.post("/api/view")
def view(body: ViewBody) -> dict:
    return build_view(body.text, _case(body.case_id).target, final=body.final, traces=body.traces)


@app.get("/results")
def results() -> FileResponse:
    return FileResponse(STATIC / "results.html", headers={"Cache-Control": "no-store"})


@app.get("/built")
def built() -> FileResponse:
    return FileResponse(STATIC / "built.html", headers={"Cache-Control": "no-store"})


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})


app.mount("/static", StaticFiles(directory=STATIC), name="static")
