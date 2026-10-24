"""Model JSON (possibly still streaming) -> reconciliation table rows, headline, validity and diff vs ground truth.

Pure functions over dicts. A row cell is "ready" only once the model finished that record, so a half-written
record never shows invented zeros (the model omits zero fields, so a missing field is a real zero only when done).
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from gst_recon.rewards.scoring import HEADS, TOL, _eq, _num, _strset, parse_output
from gst_recon.schema import ReconOutput

from .partial import parse_partial

SECTIONS = ("extractions", "matches", "itc", "itc_totals")  # generation order
BUCKETS = ("eligible", "blocked", "deferred")

# code -> (bucket, plain-words reason with the legal section)
REASONS: dict[str, tuple[str, str]] = {
    "ELIGIBLE": ("eligible", "Eligible: all conditions met, Sec 16(2)"),
    "RCM_ELIGIBLE": ("eligible", "Eligible: reverse charge, you paid the tax, Sec 9(3)/9(4)"),
    "CREDIT_NOTE_REVERSAL": ("eligible", "Credit note: reverses earlier credit, Sec 34"),
    "BLOCKED_MOTOR_VEHICLE": ("blocked", "Blocked: motor vehicles, Sec 17(5)(a)"),
    "BLOCKED_FOOD_BEVERAGE": ("blocked", "Blocked: food and beverages, Sec 17(5)(b)(i)"),
    "BLOCKED_CLUB_MEMBERSHIP": ("blocked", "Blocked: club or gym membership, Sec 17(5)(b)(ii)"),
    "BLOCKED_WORKS_CONTRACT": ("blocked", "Blocked: building work for own use, Sec 17(5)(c)(d)"),
    "BLOCKED_PERSONAL_USE": ("blocked", "Blocked: personal use, Sec 17(5)(g)"),
    "BLOCKED_GIFT": ("blocked", "Blocked: gifts, Sec 17(5)(h)"),
    "DEFERRED_NOT_IN_2B": ("deferred", "Deferred: supplier has not reported it in GSTR-2B, Sec 16(2)(aa)"),
    "DEFERRED_PERIOD_MISMATCH": ("deferred", "Deferred: it appears in another month's GSTR-2B, Sec 16(2)(aa)"),
    "DEFERRED_GSTIN_MISMATCH": ("deferred", "Deferred: GSTR-2B lists it under another supplier GSTIN, Sec 16(2)(aa)"),
    "DEFERRED_AMOUNT_MISMATCH": ("deferred", "Deferred: GSTR-2B shows less tax than the invoice, Sec 16(2)(aa)"),
    "DEFERRED_UNPAID_180D": ("deferred", "Deferred: unpaid for over 180 days, Sec 16(2), Rule 37"),
}
FLAGS: dict[str, tuple[str, str]] = {  # flag -> (label, severity)
    "missing_in_2b": ("Not in GSTR-2B", "bad"),
    "period_mismatch": ("Other month in 2B", "warn"),
    "gstin_mismatch": ("GSTIN mismatch", "bad"),
    "amount_mismatch": ("Amount mismatch", "bad"),
    "duplicate": ("Duplicate in books", "bad"),
    "unpaid_180d": ("Unpaid over 180 days", "warn"),
}


def _by_id(rows: Any) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in rows if isinstance(rows, list) else []:
        if isinstance(r, dict) and r.get("doc_id") is not None:
            out.setdefault(str(r["doc_id"]).strip().upper(), r)
    return out


def _heads(b: Any) -> dict[str, float]:
    b = b if isinstance(b, dict) else {}
    return {h: _num(b.get(h)) or 0.0 for h in HEADS}


def _sum(b: Any) -> float:
    return round(sum(_heads(b).values()), 2)


def _same(a: Any, b: Any) -> bool:
    ha, hb = _heads(a), _heads(b)
    return all(abs(ha[h] - hb[h]) <= TOL for h in HEADS)


def _reason_items(codes: Any) -> list[dict]:
    items = []
    for c in codes if isinstance(codes, list) else []:
        bucket, text = REASONS.get(str(c), ("eligible", str(c)))
        items.append({"code": str(c), "bucket": bucket, "text": text})
    return items


def _flag_items(flags: Any) -> list[dict]:
    return [{"flag": str(f), "label": FLAGS.get(str(f), (str(f), "warn"))[0], "severity": FLAGS.get(str(f), (str(f), "warn"))[1]}
            for f in flags] if isinstance(flags, list) else []


def _ready(out: dict, section: str, idx: int, n: int, final: bool) -> bool:
    """Record `idx` of `section` is complete: the generation moved to the next section or past that record."""
    later = SECTIONS[SECTIONS.index(section) + 1:]
    return final or idx < n - 1 or any(k in out for k in later)


def _row(doc_id: str, e: dict, m: dict, t: dict, ready: tuple[bool, bool, bool]) -> dict:
    return {
        "doc_id": doc_id, "ready": dict(zip(("extraction", "match", "itc"), ready)),
        "supplier": e.get("supplier_name"), "gstin": e.get("supplier_gstin"), "invoice_no": e.get("invoice_no"),
        "date": e.get("invoice_date"), "doc_type": e.get("doc_type"), "total": _num(e.get("total")),
        "lines": [li.get("description") for li in e.get("line_items") or [] if isinstance(li, dict)],
        "in_books": bool(m.get("register_vouchers")), "in_2b": bool(m.get("gstr2b_doc_no")), "paid": bool(m.get("payment_refs")),
        "vouchers": m.get("register_vouchers") or [], "gstr2b": [m.get("gstr2b_period"), m.get("gstr2b_doc_no")] if m.get("gstr2b_doc_no") else None,
        "payments": m.get("payment_refs") or [], "flags": _flag_items(m.get("flags")),
        **{b: _sum(t.get(b)) for b in BUCKETS}, "heads": {b: _heads(t.get(b)) for b in BUCKETS},
        "reasons": _reason_items(t.get("reasons")), "wrong": {}, "missing": False, "trace": None,
    }


def _diff(row: dict, te: dict, tm: dict, tt: dict) -> dict[str, str]:
    """Cell -> what ground truth says, for every cell the model got wrong (judged only once the record is ready)."""
    wrong: dict[str, str] = {}
    if row["ready"]["extraction"]:
        for cell, key, kind in (("supplier", "supplier_name", "name"), ("invoice_no", "invoice_no", "docno"), ("total", "total", "amt")):
            if not _eq(row[cell], te.get(key), kind):
                wrong[cell] = f"{te.get(key)}"
    if row["ready"]["match"]:
        want = tm.get("flags") or []
        if _strset([f["flag"] for f in row["flags"]]) != _strset(want):
            wrong["flags"] = ", ".join(FLAGS.get(f, (f,))[0] for f in sorted(want)) or "no flags"
        for cell, key in (("in_books", "register_vouchers"), ("in_2b", "gstr2b_doc_no"), ("paid", "payment_refs")):
            if row[cell] != bool(tm.get(key)):
                wrong[cell] = "present" if tm.get(key) else "absent"
    if row["ready"]["itc"]:
        for b in BUCKETS:
            if not _same(row["heads"][b], tt.get(b)):
                wrong[b] = f"{_sum(tt.get(b)):,.2f}"
        if _strset([r["code"] for r in row["reasons"]]) != _strset(tt.get("reasons")):
            wrong["reasons"] = "; ".join(r["text"] for r in _reason_items(tt.get("reasons"))) or "none"
    return wrong


def _totals(totals: Any, rows: list[dict]) -> dict[str, float]:
    if isinstance(totals, dict) and totals:
        return {b: _sum(totals.get(b)) for b in BUCKETS}
    return {b: round(sum(r[b] for r in rows if r["ready"]["itc"]), 2) for b in BUCKETS}


def validity(text: str) -> dict:
    """Is the finished text parseable JSON, and does it satisfy the output schema?"""
    obj = parse_output(text)
    if obj is None:
        return {"json": False, "schema": False, "error": "not valid JSON"}
    try:
        ReconOutput.model_validate(obj)
    except ValidationError as e:
        first = e.errors()[0]
        where = ".".join(str(p) for p in first.get("loc", ())) or "document"
        return {"json": True, "schema": False, "error": f"{first['msg']} at {where}"}
    return {"json": True, "schema": True, "error": None}


def build_view(text: str, truth: dict | None, *, final: bool, traces: dict | None = None) -> dict:
    """The right-hand panel's data for the model text so far. `traces` (doc_id -> any JSON) is shown per row (hybrid mode)."""
    out = (parse_output(text) if final else None) or parse_partial(text) or {}
    secs = {k: _by_id(out.get(k)) for k in SECTIONS[:3]}
    t_secs = {k: _by_id((truth or {}).get(k)) for k in SECTIONS[:3]}
    judge = bool(truth) and final
    ids = list(dict.fromkeys([*secs["extractions"], *secs["matches"], *secs["itc"], *(t_secs["extractions"] if judge else [])]))
    rows = []
    for d in ids:
        ready = tuple(d in secs[k] and _ready(out, k, list(secs[k]).index(d), len(secs[k]), final) for k in SECTIONS[:3])
        row = _row(d, secs["extractions"].get(d, {}), secs["matches"].get(d, {}), secs["itc"].get(d, {}), ready)
        if judge:
            row["wrong"] = _diff(row, t_secs["extractions"].get(d, {}), t_secs["matches"].get(d, {}), t_secs["itc"].get(d, {}))
            row["missing"] = d not in secs["extractions"]
        row["trace"] = (traces or {}).get(d)
        rows.append(row)
    t_tot = (truth or {}).get("itc_totals")
    return {
        "rows": rows, "headline": _totals(out.get("itc_totals"), rows), "headline_final": isinstance(out.get("itc_totals"), dict),
        "truth_headline": {b: _sum(t_tot.get(b)) for b in BUCKETS} if isinstance(t_tot, dict) else None,
        "diff": {"judged": len(t_secs["itc"]), "wrong_cells": sum(len(r["wrong"]) for r in rows),
                 "exact": sum(1 for r in rows if r["ready"]["itc"] and not set(BUCKETS) & r["wrong"].keys())} if judge else None,
        "validity": validity(text) if final else None,
    }
