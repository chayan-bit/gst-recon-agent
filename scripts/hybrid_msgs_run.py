"""Run per-document requests from a dir of messages.json files, as `eval run --mode hybrid --constrained` sends them.

    python scripts/hybrid_msgs_run.py IN_DIR OUT_DIR --endpoint http://127.0.0.1:30400/v1 --model base:perdoc

Every IN_DIR/**/messages.json (a chat message list, e.g. from build_doc_messages) gets one grammar-constrained
call with doc_json_schema; the reply goes to OUT_DIR/<same relative dir>/reply.json with the raw text, token
counts, finish reason, error and whether it parses as a DocRecord. Existing replies are kept (resume). Output
files are owner-only (dirs 0700, files 0600) because the inputs may be client documents.
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from gst_recon.eval.client import chat
from gst_recon.hybrid.docschema import doc_json_schema
from gst_recon.hybrid.run import parse_doc


def _write_private(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=1)


def run(in_dir: Path, out_dir: Path, call: Callable[[list[dict]], dict], concurrency: int = 8) -> dict:
    todo = [(m, out_dir / m.parent.relative_to(in_dir) / "reply.json") for m in sorted(in_dir.rglob("messages.json"))]
    todo = [(m, o) for m, o in todo if not o.exists()]

    def one(job) -> bool:
        src, dst = job
        r = call(json.loads(src.read_text()))
        rec, problem = parse_doc(r.get("text") or "")
        _write_private(dst, {**r, "parse_ok": rec is not None, "problem": problem})
        return rec is not None

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        ok = list(pool.map(one, todo))
    return {"called": len(ok), "parse_ok": sum(ok)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("in_dir", type=Path)
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--endpoint", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--doc-max-tokens", type=int, default=4096)
    a = ap.parse_args()
    fmt = {"type": "json_schema", "json_schema": {"name": "doc", "schema": doc_json_schema()}}
    print(json.dumps(run(a.in_dir, a.out_dir, lambda m: chat(a.endpoint, a.model, m, response_format=fmt,
                                                            max_tokens=a.doc_max_tokens, temperature=0.0),
                         a.concurrency)))


if __name__ == "__main__":
    main()
