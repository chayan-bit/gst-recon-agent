"""Per-document SFT dataset for the hybrid mode: one row per document of every SFT-role train case, built by
gst_recon.hybrid.sft (the eval's build_doc_messages prompt, DocRecord target from target.json + truth).

raw: every document as built. curated: the case-level OCR rule applied per document. A line HSN the OCR lost
is blanked (target.json still holds the true code), and a document that lost any other fact is dropped.
Only that document is dropped, not the whole case.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from gst_recon.train import build as b

LOST_HSN = re.compile(r"line(\d+)_hsn")


def curate_doc_rows(rows: list[dict], unrecoverable: tuple[str, ...]) -> tuple[list[dict], int, int]:
    """(kept rows, dropped documents, blanked HSN codes) for one case; rows are returned as new dicts."""
    lost: dict[str, list[str]] = {}
    for f in unrecoverable:
        doc, fact = f.split(":", 1)
        lost.setdefault(doc, []).append(fact)
    kept, dropped, masked = [], 0, 0
    for r in rows:
        hits = [LOST_HSN.fullmatch(f) for f in lost.get(r["doc_id"], [])]
        rec = json.loads(r["messages"][-1]["content"])
        if not all(hits) or any(int(m.group(1)) >= len(rec["line_items"]) for m in hits):
            dropped += 1
            continue
        for m in hits:
            rec["line_items"][int(m.group(1))]["hsn"] = ""
        masked += len(hits)
        reply = {"role": "assistant", "content": json.dumps(rec, ensure_ascii=False, separators=(",", ":"))}
        kept.append({**r, "messages": [*r["messages"][:-1], reply]})
    return kept, dropped, masked


def prompt_completion(row: dict) -> dict:
    """TRL prompt/completion form of a chat row; TRL's SFTTrainer then puts the loss on the completion only."""
    m = row["messages"]
    return {**{k: v for k, v in row.items() if k != "messages"}, "prompt": m[:-1], "completion": m[-1:]}


def _tokens(rows: list[dict], count) -> dict:
    p = [count(r["messages"][0]["content"] + r["messages"][1]["content"])[0] + b.TEMPLATE_OVERHEAD for r in rows]
    t = [count(r["messages"][2]["content"])[0] for r in rows]
    s = [a + c for a, c in zip(p, t)]
    pct = lambda xs: {"p50": b._pct(xs, .5), "p95": b._pct(xs, .95), "p99": b._pct(xs, .99), "max": max(xs, default=0)}
    return {"prompt": pct(p), "target": pct(t), "total": pct(s)}


def build_perdoc(rendered: Path, truth_dirs: list[Path], out: Path, count) -> dict:
    from gst_recon.hybrid.sft import doc_sft_rows_from_dir

    truth = {p.stem: p for d in truth_dirs for p in Path(d).glob("*.json")}
    cases = [c for c in b.load_rendered(rendered) if c.split == "train" and b.role(c.case_id) == "sft"]
    raw, curated, errors, dropped, masked = [], [], {}, 0, 0
    for c in cases:
        try:
            rows = [{**r, "difficulty": c.difficulty, "ocr_build": c.ocr_build}
                    for r in doc_sft_rows_from_dir(Path(c.path), truth[c.case_id])]
        except (KeyError, ValueError) as e:  # no truth file, or target/truth lines disagree: report, never guess
            errors[c.case_id] = f"{type(e).__name__}: {e}"
            continue
        kept, d, m = curate_doc_rows(rows, c.unrecoverable)
        raw += rows
        curated += kept
        dropped, masked = dropped + d, masked + m
    by_diff = lambda rows: dict(Counter(r["difficulty"] for r in rows))
    stats = {"source": str(rendered.resolve()), "cases": len(cases), "case_errors": errors,
             "raw": {"rows": b.write_jsonl(out / "raw" / "sft-perdoc" / "train.jsonl", raw), "by_difficulty": by_diff(raw),
                     "tokens": _tokens(raw, count)},
             "curated": {"rows": b.write_jsonl(out / "curated" / "sft-perdoc" / "train.jsonl", curated),
                         "prompt_completion_rows": b.write_jsonl(out / "curated" / "sft-perdoc-pc" / "train.jsonl",
                                                                 [prompt_completion(r) for r in curated]),
                         "by_difficulty": by_diff(curated), "docs_dropped_ocr": dropped, "hsn_blanked": masked,
                         "tokens": _tokens(curated, count)}}
    (out / "perdoc_stats.json").write_text(json.dumps(stats, indent=1))
    return stats
