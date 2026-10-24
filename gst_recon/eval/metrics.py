"""Per-case component metrics. Primary metrics are the components; `composite` is secondary.

Scoring is delegated to `gst_recon.rewards.score` (shared with GRPO); this module adds what the
reward does not report: rupee error of the claimed ITC and accuracy on context-dependent documents.
"""

from __future__ import annotations

from typing import Any

from gst_recon.eval.cases import EvalCase
from gst_recon.rewards import parse_output, score
from gst_recon.schema import DocType, ItcCategory, LinePurpose

HEADS = ("igst", "cgst", "sgst", "cess")
BUCKETS = ("eligible", "blocked", "deferred")
TOL = 1.0  # rupees, same tolerance as the rewards


def _f(x: Any) -> float:
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) and x == x else 0.0


def _rows(obj: dict | None, key: str) -> dict[str, dict]:
    val = obj.get(key) if isinstance(obj, dict) else None
    rows = [r for r in val if isinstance(r, dict)] if isinstance(val, list) else []
    return {str(r.get("doc_id", "")).strip().upper(): r for r in reversed(rows)}  # first occurrence wins


def _bucket(row: dict | None, name: str) -> dict:
    v = row.get(name) if isinstance(row, dict) else None
    return v if isinstance(v, dict) else {}


def _blocked_reasons(row: dict | None) -> set[str]:
    rs = row.get("reasons") if isinstance(row, dict) else None
    return {str(r).upper() for r in rs if str(r).startswith("BLOCKED_")} if isinstance(rs, list) else set()


def context_docs(case: EvalCase) -> tuple[list[str], str]:
    """(doc_ids whose s.17(5) outcome depends on buyer context or remarks, source).
    With the truth Case: invoices with a line whose category is not normal or purpose is not business.
    Without it (proxy): documents whose true reasons include a BLOCKED_ code."""
    if case.truth is not None:
        ids = [i.doc_id.upper() for i in case.truth.inputs.invoices if i.doc_type == DocType.INVOICE and any(
            li.category != ItcCategory.NORMAL or li.purpose != LinePurpose.BUSINESS for li in i.line_items)]
        return ids, "truth"
    return [d for d, r in _rows(case.target, "itc").items() if _blocked_reasons(r)], "proxy"


def _context_ok(p: dict | None, t: dict) -> bool:
    if p is None:
        return False
    same = all(abs(_f(_bucket(p, "blocked").get(h)) - _f(_bucket(t, "blocked").get(h))) <= TOL for h in HEADS)
    return same and _blocked_reasons(p) == _blocked_reasons(t)


def _total_buckets(pred: dict | None, rows: dict[str, dict]) -> dict[str, dict[str, float]]:
    """Claimed totals: the model's itc_totals if present, else the sum of its per-document rows."""
    tot = pred.get("itc_totals") if isinstance(pred, dict) else None
    if isinstance(tot, dict) and all(isinstance(tot.get(b), dict) for b in BUCKETS):
        return {b: {h: _f(tot[b].get(h)) for h in HEADS} for b in BUCKETS}
    return {b: {h: sum(_f(_bucket(r, b).get(h)) for r in rows.values()) for h in HEADS} for b in BUCKETS}


def case_metrics(raw: str, case: EvalCase) -> dict[str, Any]:
    """All metrics for one raw model output. Unparseable output scores 0 and claims zero ITC."""
    pred = parse_output(raw)
    s = score(raw, case.target)
    p_itc, t_itc = _rows(pred, "itc"), _rows(case.target, "itc")
    p_tot, t_tot = _total_buckets(pred, p_itc), _total_buckets(case.target, t_itc)
    ctx, source = context_docs(case)
    return {
        "parse_ok": float(pred is not None),
        "schema_valid": s["schema_valid"], "extraction_f1": s["extraction_f1"], "arithmetic": s["arithmetic"],
        "match_accuracy": s["match_accuracy"], "itc_invoice": s["itc_invoice"], "itc_reasons": s["itc_reasons"],
        "itc_total_exact": s["itc_total"], "composite": s["composite"], "grpo": s["grpo"],
        "context_n": len([d for d in ctx if d in t_itc]),
        "context_ok": sum(_context_ok(p_itc.get(d), t_itc[d]) for d in ctx if d in t_itc),
        "context_source": source,
        # rupees: eligible claim error over 4 heads; and all 12 total fields
        "itc_abs_err_rs": round(sum(abs(p_tot["eligible"][h] - t_tot["eligible"][h]) for h in HEADS), 2),
        "itc_all_abs_err_rs": round(sum(abs(p_tot[b][h] - t_tot[b][h]) for b in BUCKETS for h in HEADS), 2),
    }
