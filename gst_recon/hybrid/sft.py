"""Training-data hook for per-document SFT: a built case -> one chat row per document.

Target per document = that document's extraction from target.json (so OCR-lost fields stay blanked
exactly as the case-level SFT target has them) plus the two per-line judgments, which only the truth
Case JSON carries (target.json has per-document ITC, not per-line category and purpose).

This module reads truth by design, so the reconciler never imports it (tests/hybrid/test_anticheat.py).
"""

from __future__ import annotations

import json
from pathlib import Path

from gst_recon.eval.guard import refuse_eval_path
from gst_recon.eval.prompts import build_doc_messages
from gst_recon.hybrid.docschema import DocLine, DocRecord
from gst_recon.hybrid.inputs import parse_header, split_docs, split_sections
from gst_recon.rewards import expand
from gst_recon.schema import Case, ExtractionRecord


def truth_records(target: dict, case: Case) -> dict[str, DocRecord]:
    """doc_id -> DocRecord: target.json extraction + truth category and purpose per line (lines align by index;
    the rendered document lists them in truth order)."""
    truth = {i.doc_id: i for i in case.inputs.invoices}
    out: dict[str, DocRecord] = {}
    for raw in expand(target)["extractions"]:
        ex = ExtractionRecord.model_validate(raw)
        inv = truth[ex.doc_id]
        if len(inv.line_items) != len(ex.line_items):
            raise ValueError(f"{case.case_id}/{ex.doc_id}: target has {len(ex.line_items)} lines, truth {len(inv.line_items)}")
        lines = [DocLine(**li.model_dump(), itc_category=t.category, purpose=t.purpose)
                 for li, t in zip(ex.line_items, inv.line_items)]
        out[ex.doc_id] = DocRecord(**ex.model_dump(exclude={"doc_id", "line_items"}), line_items=lines)
    return out


def doc_sft_rows(prompt: str, target: dict, case: Case) -> list[dict]:
    """One {"case_id", "doc_id", "messages"} row per document; assistant content is the DocRecord JSON."""
    sec = split_sections(prompt)
    header = parse_header(sec["CASE"]).text
    recs = truth_records(target, case)
    return [{"case_id": case.case_id, "doc_id": d.doc_id,
             "messages": build_doc_messages(header, d.block) + [
                 {"role": "assistant", "content": recs[d.doc_id].model_dump_json()}]}
            for d in split_docs(sec["INVOICES"])]


def doc_sft_rows_from_dir(case_dir: Path, truth_path: Path) -> list[dict]:
    """Same, from <case_dir>/{prompt.txt,target.json} and the truth Case JSON; refuses evaluation output."""
    case_dir, truth_path = refuse_eval_path(case_dir), refuse_eval_path(truth_path)
    return doc_sft_rows((case_dir / "prompt.txt").read_text(), json.loads((case_dir / "target.json").read_text()),
                        Case.model_validate_json(truth_path.read_text()))
