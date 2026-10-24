"""CLI: python -m gst_recon.render --truth data/truth --out data/rendered --workers 8

Renders every truth case JSON into <out>/<case_id>/{prompt.txt,target.json,meta.json}.
Resumable (finished cases are skipped), memory-light (forked workers share the
imported libraries; each worker recycles after --recycle cases). Images are kept
only for the first --keep-images cases. `--stats-only` summarises an existing --out.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import statistics
import sys
import time
from pathlib import Path

from gst_recon.render.holdout import SPLITS


def _render_one(job: tuple[str, str, str | None, bool, bool]) -> dict:
    path, out, split, keep, ocr = job
    from gst_recon.render.pipeline import render_case
    from gst_recon.schema import Case

    t0 = time.perf_counter()
    case = Case.model_validate_json(Path(path).read_text())
    try:
        meta = render_case(case, Path(out), split=split, keep_images=keep, ocr=ocr)
    except Exception as e:  # keep the batch going; the failure is reported at the end
        return {"case_id": case.case_id, "error": f"{type(e).__name__}: {e}"}
    meta["wall_s"] = time.perf_counter() - t0
    return {k: meta[k] for k in ("case_id", "difficulty", "split", "ocr_recall", "ocr_recall_scanned", "has_unrecoverable",
                                 "prompt_tokens", "target_tokens", "fits_context", "token_method", "wall_s")}


def _init_worker(max_gb: float) -> None:
    """Cap each worker's private memory so a runaway effect fails one case instead of the host."""
    if max_gb > 0:
        try:
            import resource

            lim = int(max_gb * 2**30)
            resource.setrlimit(resource.RLIMIT_DATA, (lim, lim))  # RLIMIT_AS breaks rust/openblas thread pools
        except (ImportError, ValueError, OSError):
            pass  # not enforceable on this platform (macOS)


def _warm() -> None:
    """Import the pure-python/numpy libraries once, before forking workers (shared copy-on-write pages).

    Not warmed on purpose: WeasyPrint (pango/glib) and the tokenizers thread pool; initialising them
    before fork deadlocked the children, so each worker loads them itself.
    """
    from gst_recon.render import context, degrade, ocr, pipeline  # noqa: F401
    import augraphy  # noqa: F401
    import cv2

    cv2.setNumThreads(1)


def _pct(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))]


def stats(rows: list[dict]) -> str:
    out = []
    for diff in ("easy", "medium", "hard"):
        r = [x for x in rows if x.get("difficulty") == diff]
        if not r:
            continue
        rec = [x["ocr_recall"] for x in r]
        sc = [x["ocr_recall_scanned"] for x in r if x.get("ocr_recall_scanned") is not None]
        tok = [x["prompt_tokens"] for x in r]
        out.append(
            f"{diff:7s} n={len(r):4d}  ocr_recall mean={statistics.mean(rec):.3f} p10={_pct(rec, .1):.3f} "
            f"p50={_pct(rec, .5):.3f} (scanned docs only: mean={statistics.mean(sc) if sc else float('nan'):.3f})  "
            f"cases_with_lost_facts={sum(x['has_unrecoverable'] for x in r) / len(r):.1%}  "
            f"prompt_tokens p50={_pct(tok, .5)} p90={_pct(tok, .9)} max={max(tok)}  "
            f"fit_32k={sum(x['fits_context'] for x in r) / len(r):.1%}")
    return "\n".join(out) or "no rendered cases"


def _collect(out: Path) -> list[dict]:
    rows = []
    for p in sorted(out.glob("*/meta.json")):
        m = json.loads(p.read_text())
        rows.append({k: m.get(k) for k in ("case_id", "difficulty", "split", "ocr_recall", "ocr_recall_scanned",
                                           "has_unrecoverable", "prompt_tokens", "target_tokens", "fits_context")})
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m gst_recon.render", description=__doc__.split("\n\n")[0])
    ap.add_argument("--truth", type=Path, default=Path("data/truth"))
    ap.add_argument("--out", type=Path, default=Path("data/rendered"))
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    ap.add_argument("--split", choices=SPLITS, default=None, help="override the case's own split")
    ap.add_argument("--limit", type=int, default=None, help="render only the first N truth files")
    ap.add_argument("--keep-images", type=int, default=0, metavar="N", help="keep degraded PNGs for the first N cases")
    ap.add_argument("--no-ocr", action="store_true", help="skip OCR (debug only; prompts then lack scanned text)")
    ap.add_argument("--force", action="store_true", help="re-render finished cases")
    ap.add_argument("--recycle", type=int, default=25, help="cases per worker process before it is replaced (memory cap)")
    ap.add_argument("--max-mem-gb", type=float, default=6.0, help="per-worker private-memory cap (Linux), 0 = off")
    ap.add_argument("--stats-only", action="store_true")
    a = ap.parse_args(argv)
    for var, val in (("TOKENIZERS_PARALLELISM", "false"), ("RAYON_NUM_THREADS", "1"), ("OMP_NUM_THREADS", "1"),
                     ("OPENBLAS_NUM_THREADS", "1"), ("MALLOC_ARENA_MAX", "2")):
        os.environ.setdefault(var, val)  # one thread per worker: parallelism comes from --workers

    if a.stats_only:
        print(stats(_collect(a.out)))
        return 0
    files = sorted(a.truth.glob("*.json"))[: a.limit]
    if not files:
        print(f"no truth cases in {a.truth}", file=sys.stderr)
        return 1
    a.out.mkdir(parents=True, exist_ok=True)
    jobs = [(str(f), str(a.out), a.split, i < a.keep_images, not a.no_ocr) for i, f in enumerate(files)
            if a.force or not (a.out / f.stem / "meta.json").exists()]
    print(f"{len(files)} truth cases, {len(jobs)} to render, {a.workers} workers", flush=True)
    _warm()
    t0, rows, errors = time.perf_counter(), [], []
    with mp.get_context("fork").Pool(a.workers, maxtasksperchild=a.recycle, initializer=_init_worker, initargs=(a.max_mem_gb,)) as pool:
        for n, r in enumerate(pool.imap_unordered(_render_one, jobs), 1):
            (errors if "error" in r else rows).append(r)
            if n % 10 == 0 or n == len(jobs):
                dt = time.perf_counter() - t0
                print(f"[{n}/{len(jobs)}] {n / dt * 60:.1f} cases/min overall, {len(errors)} errors", flush=True)
    dt = time.perf_counter() - t0
    if rows:
        busy = sum(r["wall_s"] for r in rows)
        print(f"done: {len(rows)} cases in {dt:.0f}s wall; {len(rows) / dt * 60:.2f} cases/min total, "
              f"{len(rows) / busy * 60:.2f} cases/min/worker (busy time)")
        print(stats(_collect(a.out)))
    for e in errors:
        print(f"FAILED {e['case_id']}: {e['error']}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
