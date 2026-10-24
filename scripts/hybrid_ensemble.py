"""Build ensemble replies (gst_recon.hybrid.ensemble) from three members' saved per-document replies, offline.

usage:
  python scripts/hybrid_ensemble.py runs OUT_RUN V1_RUN PD3A_RUN PD3_RUN [CONFIRM_RUN]
      writes OUT_RUN/docs/<case>/<doc>.json; then re-run the eval on OUT_RUN with --no-resume (no model calls)
  python scripts/hybrid_ensemble.py flat OUT_DIR V1_DIR PD3A_DIR PD3_DIR [CONFIRM_DIR]
      <dir>/<doc_id>.json raw reply texts (the realinv scorer layout); files are written 0600
A document no member parsed keeps v1's reply, so it fails exactly as v1 did. CONFIRM (variant B) is pd3g287.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gst_recon.hybrid.ensemble import ensemble  # noqa: E402
from gst_recon.rewards.doc import parse_doc  # noqa: E402


def combine(texts: list[str | None]) -> str | None:
    """Ensemble reply text from the members' raw texts (None = missing), or None if no member parsed."""
    e = ensemble(*[parse_doc(t) if t is not None else None for t in texts])  # 3 members, then the optional confirm
    return e.model_dump_json() if e is not None else None


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(text)


def runs(out: Path, members: list[Path]) -> int:
    n = 0
    for v1_doc in sorted((members[0] / "docs").glob("*/*.json")):
        rel = v1_doc.relative_to(members[0] / "docs")
        recs = [json.loads((m / "docs" / rel).read_text()) if (m / "docs" / rel).exists() else None for m in members]
        text = combine([r.get("text") if r and r.get("error") is None else None for r in recs])
        rec = recs[0] if text is None else {"text": text, "finish_reason": "stop", "prompt_tokens": 0,
                                            "completion_tokens": 0, "latency_s": 0.0, "error": None}
        _write(out / "docs" / rel, json.dumps(rec))
        n += 1
    return n


def flat(out: Path, members: list[Path]) -> int:
    n = 0
    for v1_file in sorted(members[0].glob("*.json")):
        texts = [(m / v1_file.name).read_text() if (m / v1_file.name).exists() else None for m in members]
        _write(out / v1_file.name, combine(texts) or texts[0])
        n += 1
    return n


if __name__ == "__main__":
    mode, out, *members = sys.argv[1:]
    print({"runs": runs, "flat": flat}[mode](Path(out), [Path(m) for m in members]), "documents")
