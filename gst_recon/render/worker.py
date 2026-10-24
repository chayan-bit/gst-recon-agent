"""Pool worker entry points; a real module (not __main__) so spawn-started workers can unpickle them on Windows."""
from __future__ import annotations

import sys
import time
from pathlib import Path

from gst_recon.render.memlimit import apply_memory_cap


def _render_one(job: tuple[str, str, str | None, bool, bool]) -> dict:
    path, out, split, keep, ocr = job
    from gst_recon.render.pipeline import render_case
    from gst_recon.schema import Case

    t0 = time.perf_counter()
    case = Case.model_validate_json(Path(path).read_text(encoding="utf-8"))
    try:
        meta = render_case(case, Path(out), split=split, keep_images=keep, ocr=ocr)
    except Exception as e:  # keep the batch going; the failure is reported at the end
        return {"case_id": case.case_id, "error": f"{type(e).__name__}: {e}"}
    meta["wall_s"] = time.perf_counter() - t0
    return {k: meta[k] for k in ("case_id", "difficulty", "split", "ocr_recall", "ocr_recall_scanned", "has_unrecoverable",
                                 "prompt_tokens", "target_tokens", "fits_context", "token_method", "wall_s")}


def _init_worker(max_gb: float) -> None:
    """Cap each worker's private memory so a runaway effect fails one case instead of the host."""
    if apply_memory_cap(max_gb) == "unsupported":
        print("warning: --max-mem-gb is not enforceable on this platform", file=sys.stderr)
