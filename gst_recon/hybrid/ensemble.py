"""Field-wise ensemble of per-document replies (combiner rule pre-registered in reports/hybrid.md, 69a8e7b).

Identity fields take the value at least two of the three members emit (compared as the scorer compares them;
an empty value is a vote), else "", so reconciler v3's identity fill can act. Every other field comes from
student-perdoc-sft v1, the dev-validated member.
"""

from __future__ import annotations

from gst_recon.hybrid.docschema import DocRecord
from gst_recon.hybrid.inputs import parse_date
from gst_recon.rewards.doc import norm

IDENTITY = ("supplier_gstin", "invoice_no", "invoice_date", "original_invoice_no")


def _key(field: str, value: str) -> str:
    if field == "invoice_date" and value.strip():
        try:
            return parse_date(value).isoformat()
        except (ValueError, KeyError):
            pass
    return norm(value)


def _vote(field: str, recs: list[DocRecord], confirm: DocRecord | None) -> str:
    keys = [_key(field, getattr(r, field)) for r in recs]
    for r, k in zip(recs, keys):
        if keys.count(k) >= 2:
            return getattr(r, field) if k else ""
    c = _key(field, getattr(confirm, field)) if confirm is not None else ""
    return next((getattr(r, field) for r, k in zip(recs, keys) if c and k == c), "")


def ensemble(v1: DocRecord | None, pd3a: DocRecord | None, pd3: DocRecord | None,
             confirm: DocRecord | None = None) -> DocRecord | None:
    """None when no member parsed. Members are passed in tie-break order (v1, pd3a, pd3). `confirm` (variant B,
    pd3g287) breaks a no-majority identity field when its non-blank value equals one of the members' values."""
    recs = [r for r in (v1, pd3a, pd3) if r is not None]
    if not recs:
        return None
    base = recs[0]  # v1, else pd3a ("the value the other two agree on, else pd3a's" is always pd3a's), else pd3
    return base.model_copy(update={f: _vote(f, recs, confirm) for f in IDENTITY})
