"""Cross-source fill of identity fields the document does not show (accountant practice: when the scan is
illegible, the books' entry for that supplier with the same amounts identifies the invoice).

A field is unread when the model left it empty or unparseable, or (FILL_UNSUPPORTED) when the value it gave
is not printed in the document's own text: an invoice number not within 1 edit of any stretch of the text,
a date in none of the usual printed forms. An unread invoice number or date is filled only when exactly one
GSTR-2B entry of the same GSTIN matches every amount (the supplier's own filing); failing that, an unread
date (never a number: the buyer's books can mistype it) comes from exactly one such register voucher.
Otherwise the model's value stands. Every fill goes to the trace.
"""

from __future__ import annotations

import re
from datetime import date

from gst_recon.hybrid.docschema import HEADS, DocRecord
from gst_recon.hybrid.inputs import parse_date
from gst_recon.hybrid.linker import lev
from gst_recon.schema import DocType, Gstr2b, PurchaseRegisterRow
from gst_recon.sim.rules import AMOUNT_TOLERANCE

FILL_UNSUPPORTED = True
_MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")


def _norm(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def no_supported(value: str, text: str) -> bool:
    v, t = _norm(value), _norm(text)
    if len(v) < 3:
        return False
    if v in t:
        return True
    return any(lev(v, t[i:i + n]) <= 1 for n in (len(v) - 1, len(v), len(v) + 1) for i in range(max(0, len(t) - n + 1)))


def date_forms(d: date) -> set[str]:
    m = _MONTHS[d.month - 1]
    raw = {f"{d.day:02d}{d.month:02d}{d.year}", f"{d.day:02d}{d.month:02d}{d.year % 100:02d}", d.isoformat(),
           f"{d.day}{m}{d.year}", f"{d.day:02d}{m}{d.year}", f"{d.day:02d}{m}{d.year % 100:02d}", f"{m}{d.day}{d.year}",
           f"{d.day}{d.month}{d.year}"}
    return {_norm(x) for x in raw}


def date_supported(value: str, text: str) -> bool:
    try:
        d = parse_date(value)
    except (ValueError, KeyError):
        return False
    t = _norm(text)
    return any(f in t for f in date_forms(d))


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= AMOUNT_TOLERANCE


def _book_ids(rec: DocRecord, register: list[PurchaseRegisterRow], gstr2b: list[Gstr2b]) -> set[tuple[str, str]]:
    """(invoice no, ISO date) of every book entry of this GSTIN whose amounts all equal the record's."""
    g = rec.supplier_gstin.strip().upper()
    note = rec.doc_type == DocType.CREDIT_NOTE
    twob = set()
    for r in gstr2b:
        docs = [(s.ctin, d, False) for s in r.data.docdata.b2b for d in s.inv] + [(s.ctin, d, True) for s in r.data.docdata.cdnr for d in s.nt]
        for ctin, d, is_note in docs:
            heads = {h: sum(getattr(it, h) for it in d.items) for h in HEADS}
            if (is_note == note and lev(ctin, g) <= 2 and _close(sum(it.txval for it in d.items), rec.taxable_value)
                    and all(_close(heads[h], getattr(rec, h)) for h in HEADS) and _close(d.val, rec.total)):
                day, mon, year = d.dt.split("-")
                twob.add((d.ntnum if is_note else d.inum, f"{year}-{mon}-{day}"))
    if twob:
        return twob
    return {("", r.supplier_invoice_date.isoformat()) for r in register  # the buyer's books may mistype a number: dates only
            if (r.voucher_type.lower() == "debit note") == note and lev(r.party_gstin.upper(), g) <= 2
            and _close(r.taxable_value, rec.taxable_value) and all(_close(getattr(r, h), getattr(rec, h)) for h in HEADS)
            and _close(r.total, rec.total)}


def fill_identity(rec: DocRecord, text: str, register: list[PurchaseRegisterRow], gstr2b: list[Gstr2b]) -> tuple[DocRecord, list[str]]:
    unread = []
    if not rec.invoice_no.strip() or (FILL_UNSUPPORTED and not no_supported(rec.invoice_no, text)):
        unread.append("invoice_no")
    if not _parses(rec.invoice_date) or (FILL_UNSUPPORTED and not date_supported(rec.invoice_date, text)):
        unread.append("invoice_date")
    if not unread or not rec.supplier_gstin.strip():
        return rec, []
    ids = _book_ids(rec, register, gstr2b)
    if len(ids) != 1:
        return rec, []
    no, when = next(iter(ids))
    upd = {k: v for k, v in (("invoice_no", no), ("invoice_date", when)) if k in unread and v and getattr(rec, k) != v}
    return (rec.model_copy(update=upd), [f"{k} {getattr(rec, k)!r} not shown by the document -> {v!r} from the one book entry "
                                         f"of this GSTIN with the same amounts" for k, v in upd.items()]) if upd else (rec, [])


def _parses(value: str) -> bool:
    try:
        parse_date(value)
        return True
    except (ValueError, KeyError):
        return False
