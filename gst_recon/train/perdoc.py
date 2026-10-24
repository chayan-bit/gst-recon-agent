"""Per-document SFT dataset for the hybrid mode: one row per document of every SFT-role train case, built by
gst_recon.hybrid.sft (the eval's build_doc_messages prompt, DocRecord target from target.json + truth).

raw: every document as built. curated: the case-level OCR rule applied per document. A line HSN the OCR lost
is blanked (target.json still holds the true code), and a document that lost any other fact is dropped.
Only that document is dropped, not the whole case.

GRPO rows (build_perdoc_grpo) come from GRPO-role cases with the same rule, except that a lost identity field
keeps the document: the per-document reward gives "" full credit when the page does not show the value.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from gst_recon.train import build as b

LOST_HSN = re.compile(r"line(\d+)_hsn")


def curate_doc_rows(rows: list[dict], unrecoverable: tuple[str, ...],
                    keep_facts: frozenset[str] = frozenset()) -> tuple[list[dict], int, int]:
    """(kept rows, dropped documents, blanked HSN codes) for one case; rows are returned as new dicts.
    A lost fact in `keep_facts` neither drops the document nor changes its target."""
    lost: dict[str, list[str]] = {}
    for f in unrecoverable:
        doc, fact = f.split(":", 1)
        lost.setdefault(doc, []).append(fact)
    kept, dropped, masked = [], 0, 0
    for r in rows:
        hits = [LOST_HSN.fullmatch(f) for f in lost.get(r["doc_id"], []) if f not in keep_facts]
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


# gst-hybrid's reconciler dev set: never trained on
DEV_SET_PREFIXES = ("grpo-easy-201-", "grpo-medium-201-", "grpo-hard-201-")
IDENTITY_FACTS = frozenset({"supplier_gstin", "invoice_no", "invoice_date"})


def grpo_doc_row(row: dict) -> dict:
    """GRPO form of a per-document row: the prompt messages, and the reference the reward reads (truth DocRecord
    plus the document block alone, without the case header, for the abstention check)."""
    m, doc_id = row["messages"], row["doc_id"]
    user = m[1]["content"]
    ref = {"truth": json.loads(m[-1]["content"]), "doc_text": user[user.index(f"--- {doc_id} |"):]}
    return {**{k: v for k, v in row.items() if k != "messages"}, "prompt": m[:-1],
            "reference": json.dumps(ref, ensure_ascii=False, separators=(",", ":"))}


def build_perdoc_grpo(rendered: Path, truth_dirs: list[Path], out: Path, count, max_completion: int) -> dict:
    """GRPO-role train cases outside the dev set -> per-document GRPO rows in <out>/curated/grpo-perdoc."""
    from gst_recon.hybrid.sft import doc_sft_rows_from_dir
    from gst_recon.rewards.doc import IDENTITY, visible

    truth = {p.stem: p for d in truth_dirs for p in Path(d).glob("*.json")}
    cases = [c for c in b.load_rendered(rendered) if c.split == "train" and b.role(c.case_id) == "grpo"
             and not c.case_id.startswith(DEV_SET_PREFIXES)]
    rows, errors, dropped, masked, too_long = [], {}, 0, 0, 0
    for c in cases:
        try:
            built = [{**r, "difficulty": c.difficulty, "ocr_build": c.ocr_build}
                     for r in doc_sft_rows_from_dir(Path(c.path), truth[c.case_id])]
        except (KeyError, ValueError) as e:  # no truth file, or target/truth lines disagree: report, never guess
            errors[c.case_id] = f"{type(e).__name__}: {e}"
            continue
        kept, d, m = curate_doc_rows(built, c.unrecoverable, IDENTITY_FACTS)
        fit = [r for r in kept if count(r["messages"][-1]["content"])[0] <= max_completion]
        rows += fit
        dropped, masked, too_long = dropped + d, masked + m, too_long + len(kept) - len(fit)
    assert not any(r["case_id"].startswith(DEV_SET_PREFIXES) for r in rows)
    grpo = [grpo_doc_row(r) for r in rows]
    refs = [json.loads(r["reference"]) for r in grpo]
    hidden = Counter(f for ref in refs for f in IDENTITY if not visible(f, ref["truth"][f], ref["doc_text"]))
    stats = {"source": str(rendered.resolve()), "cases": len(cases), "case_errors": errors,
             "excluded_prefixes": list(DEV_SET_PREFIXES), "docs_dropped_ocr": dropped, "hsn_blanked": masked,
             "docs_over_max_completion": too_long, "max_completion": max_completion,
             "identity_not_on_page": dict(hidden),  # rows where abstaining ("") is the rewarded answer
             "rows": b.write_jsonl(out / "curated" / "grpo-perdoc" / "train.jsonl", grpo),
             "by_difficulty": dict(Counter(r["difficulty"] for r in rows)), "tokens": _tokens(rows, count)}
    (out / "perdoc_grpo_stats.json").write_text(json.dumps(stats, indent=1))
    return stats


def is_hard_grpo_row(row: dict) -> bool:
    """A medium/hard document that either hides an identity field from the page (abstention is the answer) or has
    more than one line item: the rows where 16 samples of the per-document policy still disagree."""
    from gst_recon.rewards.doc import IDENTITY, visible

    ref = json.loads(row["reference"])
    truth, page = ref["truth"], ref["doc_text"]
    hidden = any(truth.get(f) and not visible(f, truth[f], page) for f in IDENTITY)
    return row["difficulty"] in ("medium", "hard") and (hidden or len(truth["line_items"]) > 1)
