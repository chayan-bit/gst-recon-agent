"""Verifiable rewards: score a model output against the ground-truth ReconOutput.

All functions are pure, fast and total: garbage input scores 0, never raises.
Model outputs are handled as plain dicts with defensive accessors so a
schema-invalid but parseable output still earns partial credit.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from gst_recon.schema import ReconOutput

HEADS = ("igst", "cgst", "sgst", "cess")
BUCKETS = ("eligible", "blocked", "deferred")
TOL = 1.0  # rupees, for consistency and ITC checks

WEIGHTS = {
    "schema_valid": 0.10,
    "extraction_f1": 0.25,
    "arithmetic": 0.10,
    "match_accuracy": 0.20,
    "itc_invoice": 0.20,
    "itc_reasons": 0.05,
    "itc_total": 0.10,
}

HEADER_FIELDS = {
    "doc_type": "str", "supplier_gstin": "gstin", "supplier_name": "name", "invoice_no": "docno",
    "invoice_date": "date", "place_of_supply": "pos", "reverse_charge": "bool",
    "original_invoice_no": "docno", "taxable_value": "amt", "igst": "amt", "cgst": "amt", "sgst": "amt",
    "cess": "amt", "total": "amt",
}
LINE_FIELDS = {"hsn": "docno", "taxable_value": "amt", "rate": "amt", "igst": "amt", "cgst": "amt",
               "sgst": "amt", "cess": "amt"}

# ---------------------------------------------------------------- parsing


def parse_output(raw: Any) -> dict | None:
    """Accept a ReconOutput, dict or raw model text; return a dict or None."""
    if isinstance(raw, ReconOutput):
        return raw.model_dump(mode="json")
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    for candidate in (text, text[text.find("{"): text.rfind("}") + 1]):
        try:
            obj = json.loads(candidate)
        except (ValueError, TypeError):
            continue
        if isinstance(obj, dict):
            return obj
    return None


def _list(obj: Any, key: str) -> list[dict]:
    val = obj.get(key) if isinstance(obj, dict) else None
    return [x for x in val if isinstance(x, dict)] if isinstance(val, list) else []


def _num(x: Any) -> float | None:
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return float(x) if x == x and abs(x) != float("inf") else None
    if isinstance(x, str):
        try:
            return float(x.replace(",", "").replace("₹", "").strip())
        except ValueError:
            return None
    return None


_DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%d-%b-%Y", "%d %b %Y", "%Y/%m/%d")


def _norm(value: Any, kind: str) -> Any:
    if kind == "amt":
        n = _num(value)
        return None if n is None else round(n + 0.0, 2)
    if kind == "bool":
        if isinstance(value, bool):
            return value
        return {"true": True, "yes": True, "y": True, "false": False, "no": False, "n": False}.get(str(value).strip().lower())
    s = "" if value is None else str(value).strip()
    if kind == "date":
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(s, fmt).date().isoformat()
            except ValueError:
                pass
        return s
    if kind == "gstin":
        return s.upper().replace(" ", "")
    if kind == "docno":
        return re.sub(r"\s+", "", s).upper()
    if kind == "pos":
        m = re.match(r"\d+", s)
        return f"{int(m.group()):02d}" if m else s
    if kind == "name":
        return " ".join(re.sub(r"[^\w\s&]", " ", s.casefold()).split())
    return s.lower()


def _eq(a: Any, b: Any, kind: str) -> bool:
    na, nb = _norm(a, kind), _norm(b, kind)
    if kind == "amt":
        return na is not None and nb is not None and abs(na - nb) < 0.005
    return na is not None and na == nb


def _by_doc(rows: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in rows:
        out.setdefault(str(r.get("doc_id", "")).strip().upper(), r)
    return out


# ---------------------------------------------------------------- components


def schema_valid(raw: Any) -> float:
    obj = parse_output(raw)
    if obj is None:
        return 0.0
    try:
        ReconOutput.model_validate(obj)
    except (ValidationError, TypeError, ValueError):
        return 0.0
    return 1.0


def _line_tp(pred_lines: list[dict], true_lines: list[dict]) -> int:
    """Greedy one-to-one line alignment maximising matched fields."""
    unused = list(range(len(pred_lines)))
    tp = 0
    for t in true_lines:
        if not unused:
            break
        scores = [(sum(_eq(pred_lines[i].get(f), t.get(f), k) for f, k in LINE_FIELDS.items()), -i) for i in unused]
        best, neg_i = max(scores)
        tp += best
        unused.remove(-neg_i)
    return tp


def extraction_f1(pred: dict | None, truth: dict) -> float:
    """Field-level F1 over header fields and line-item fields, paired by doc_id."""
    p_docs, t_docs = _by_doc(_list(pred, "extractions")), _by_doc(_list(truth, "extractions"))
    n_line = len(LINE_FIELDS)
    p_total = sum(len(HEADER_FIELDS) + n_line * len(_list(d, "line_items")) for d in p_docs.values())
    t_total = sum(len(HEADER_FIELDS) + n_line * len(_list(d, "line_items")) for d in t_docs.values())
    tp = 0
    for doc_id, t in t_docs.items():
        p = p_docs.get(doc_id)
        if p is None:
            continue
        tp += sum(_eq(p.get(f), t.get(f), k) for f, k in HEADER_FIELDS.items())
        tp += _line_tp(_list(p, "line_items"), _list(t, "line_items"))
    if tp == 0:
        return 0.0
    precision, recall = tp / p_total, tp / t_total
    return 2 * precision * recall / (precision + recall)


def _close(a: Any, b: Any) -> bool:
    na, nb = _num(a), _num(b)
    return na is not None and nb is not None and abs(na - nb) <= TOL


def _line_checks(line: dict) -> list[bool]:
    tv, rate = _num(line.get("taxable_value")), _num(line.get("rate"))
    if tv is None or rate is None:
        return [False]
    igst, cgst, sgst = (_num(line.get(h)) or 0.0 for h in ("igst", "cgst", "sgst"))
    if igst and (cgst or sgst):
        return [False]
    if igst:
        return [abs(igst - tv * rate / 100) <= TOL]
    return [abs(cgst - sgst) <= 0.01 and abs(cgst + sgst - tv * rate / 100) <= TOL]


def _doc_checks(doc: dict) -> list[bool]:
    lines = _list(doc, "line_items")
    checks = [c for line in lines for c in _line_checks(line)]
    for f in ("taxable_value", *HEADS):
        checks.append(_close(sum(_num(l.get(f)) or 0.0 for l in lines), doc.get(f)))
    vals = [_num(doc.get(f)) for f in ("taxable_value", *HEADS)]
    if None in vals:
        checks.append(False)
    else:
        rcm = _norm(doc.get("reverse_charge"), "bool") is True
        checks.append(_close(vals[0] + (0 if rcm else sum(vals[1:])), doc.get("total")))
    return checks


def arithmetic_consistency(pred: dict | None) -> float:
    """Internal consistency of the model's own output (no ground truth needed):
    line tax = taxable x rate with a valid CGST/SGST vs IGST split, header =
    sum of lines, total = taxable + tax (taxable only under reverse charge),
    ITC buckets add up to the extracted tax (negated for credit notes), and
    itc_totals = sum of per-document ITC."""
    docs = _by_doc(_list(pred, "extractions"))
    checks = [c for d in docs.values() for c in _doc_checks(d)]
    itc = _list(pred, "itc")
    for row in itc:
        doc = docs.get(str(row.get("doc_id", "")).strip().upper())
        if doc is None:
            checks.append(False)
            continue
        sign = -1.0 if str(doc.get("doc_type")) == "credit_note" else 1.0
        for h in HEADS:
            got = sum(_num(_bucket(row, b).get(h)) or 0.0 for b in BUCKETS)
            checks.append(_close(got, sign * (_num(doc.get(h)) or 0.0)))
    totals = pred.get("itc_totals") if isinstance(pred, dict) else None
    if itc and isinstance(totals, dict):
        for b in BUCKETS:
            for h in HEADS:
                s = sum(_num(_bucket(r, b).get(h)) or 0.0 for r in itc)
                checks.append(_close(s, _bucket(totals, b).get(h)))
    return sum(checks) / len(checks) if checks else 0.0


def _bucket(obj: dict, b: str) -> dict:
    v = obj.get(b)
    return v if isinstance(v, dict) else {}


def _strset(x: Any) -> frozenset[str]:
    return frozenset(str(v).strip().upper() for v in x) if isinstance(x, list) else frozenset({"<invalid>"})


def match_accuracy(pred: dict | None, truth: dict) -> float:
    """Mean over documents of 4 sub-checks: register vouchers, GSTR-2B entry,
    payment refs, flag set. Spurious predicted doc_ids count as misses."""
    p_rows, t_rows = _by_doc(_list(pred, "matches")), _by_doc(_list(truth, "matches"))
    ids = set(t_rows) | set(p_rows)
    if not ids:
        return 0.0
    score = 0.0
    for doc_id in t_rows:
        p, t = p_rows.get(doc_id), t_rows[doc_id]
        if p is None:
            continue
        twob_ok = all(_eq(p.get(f), t.get(f), "docno") for f in ("gstr2b_period", "gstr2b_ctin", "gstr2b_doc_no"))
        score += (
            (_strset(p.get("register_vouchers")) == _strset(t.get("register_vouchers")))
            + twob_ok
            + (_strset(p.get("payment_refs")) == _strset(t.get("payment_refs")))
            + (_strset(p.get("flags")) == _strset(t.get("flags")))
        ) / 4
    return score / len(ids)


def _itc_close(p: dict, t: dict) -> bool:
    return all(_close(_bucket(p, b).get(h), _bucket(t, b).get(h)) for b in BUCKETS for h in HEADS)


def itc_scores(pred: dict | None, truth: dict) -> dict[str, float]:
    """itc_invoice: share of documents whose 12 ITC amounts (3 buckets x 4
    heads) are all within Rs 1; itc_reasons: share with the exact reason set;
    itc_total: 1 if all 12 itc_totals are within Rs 1 of the truth."""
    p_rows, t_rows = _by_doc(_list(pred, "itc")), _by_doc(_list(truth, "itc"))
    ids = set(t_rows) | set(p_rows)
    per_inv = reasons = 0
    for doc_id, t in t_rows.items():
        p = p_rows.get(doc_id)
        if p is None:
            continue
        per_inv += _itc_close(p, t)
        reasons += _strset(p.get("reasons")) == _strset(t.get("reasons"))
    p_tot = pred.get("itc_totals") if isinstance(pred, dict) else None
    total_ok = isinstance(p_tot, dict) and _itc_close(p_tot, truth.get("itc_totals") or {})
    n = len(ids) or 1
    return {"itc_invoice": per_inv / n if ids else 0.0, "itc_reasons": reasons / n if ids else 0.0,
            "itc_total": float(total_ok)}


# ---------------------------------------------------------------- composite


def score(raw: Any, truth: ReconOutput | dict) -> dict[str, float]:
    """All component rewards plus the weighted `composite`, each in [0, 1]."""
    zero = {k: 0.0 for k in WEIGHTS} | {"composite": 0.0}
    try:
        t = truth.model_dump(mode="json") if isinstance(truth, ReconOutput) else truth
        pred = parse_output(raw)
        if pred is None:
            return zero
        out = {
            "schema_valid": schema_valid(pred),
            "extraction_f1": extraction_f1(pred, t),
            "arithmetic": arithmetic_consistency(pred),
            "match_accuracy": match_accuracy(pred, t),
            **itc_scores(pred, t),
        }
    except Exception:  # noqa: BLE001 - a reward must never crash a GRPO rollout
        return zero
    out["composite"] = sum(WEIGHTS[k] * out[k] for k in WEIGHTS)
    return out
