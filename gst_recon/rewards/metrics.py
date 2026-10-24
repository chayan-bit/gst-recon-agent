"""Component-wise eval metrics (the primary eval report; `composite` and `grpo` are secondary).

The output schema has no per-line ITC decision, so context-dependence is scored
per document: an invoice with any line whose s.17(5) outcome depends on the
buyer profile or remarks counts as correct when its blocked amounts (4 heads,
within Rs 1) and its BLOCKED_* reasons both match the truth.
"""

from __future__ import annotations

from typing import Any

from gst_recon.rewards.scoring import HEADS, TOL, _bucket, _by_doc, _list, _num, _strset, parse_output, score
from gst_recon.schema import Case, DocType, ItcCategory, LinePurpose


def _context_docs(case: Case) -> list[str]:
    return [inv.doc_id.upper() for inv in case.inputs.invoices if inv.doc_type == DocType.INVOICE and any(
        li.category != ItcCategory.NORMAL or li.purpose != LinePurpose.BUSINESS for li in inv.line_items)]


def _blocked_ok(p: dict | None, t: dict) -> bool:
    if p is None:
        return False
    same_amounts = all(abs((_num(_bucket(p, "blocked").get(h)) or 0.0) - (_num(_bucket(t, "blocked").get(h)) or 0.0))
                       <= TOL for h in HEADS)
    blocked = {r for r in _strset(p.get("reasons")) if r.startswith("BLOCKED_")}
    return same_amounts and blocked == {r for r in _strset(t.get("reasons")) if r.startswith("BLOCKED_")}


def _eligible_total(rows: list[dict]) -> float:
    return sum(_num(_bucket(r, "eligible").get(h)) or 0.0 for r in rows for h in HEADS)


def eval_metrics(raw: Any, case: Case) -> dict[str, float | None]:
    """field_f1, match_accuracy, itc_invoice (exact, 12 amounts), context_doc_acc
    (None if the case has no context-dependent invoice), itc_abs_err_rs (absolute
    error of total eligible ITC claimed, rupees), plus composite and grpo."""
    truth = case.expected.model_dump(mode="json")
    s = score(raw, truth)
    p_itc, t_itc = _by_doc(_list(parse_output(raw), "itc")), _by_doc(truth["itc"])
    ctx = _context_docs(case)
    return {
        "field_f1": s["extraction_f1"], "match_accuracy": s["match_accuracy"], "itc_invoice": s["itc_invoice"],
        "context_doc_acc": sum(_blocked_ok(p_itc.get(d), t_itc[d]) for d in ctx) / len(ctx) if ctx else None,
        "itc_abs_err_rs": round(abs(_eligible_total(list(p_itc.values())) - _eligible_total(truth["itc"])), 2),
        "composite": s["composite"], "grpo": s["grpo"],
    }
