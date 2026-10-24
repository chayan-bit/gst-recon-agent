"""Trivial regex extractor: the "code half alone" floor for hybrid mode (no model at all).

It reads header facts with regexes (GSTIN, number, date, totals), puts the whole invoice on one line,
and judges nothing (every line normal / business use). Whatever the reconciler then scores is what code
achieves without a model.
"""

from __future__ import annotations

import re

from gst_recon.hybrid.docschema import DocLine, DocRecord
from gst_recon.hybrid.inputs import parse_date
from gst_recon.schema import DocType, ItcCategory, LinePurpose

_OCR = str.maketrans({"O": "0", "I": "1", "S": "5", "B": "8", "Z": "2"})
_GSTIN = re.compile(r"\b([0-9O]{2}[A-Z0-9]{10}[0-9A-Z][Z2][0-9A-Z])\b")
_NO = re.compile(r"(?:Invoice|Inv|Bill|Credit Note|CN|C\.N\.)\s*(?:No\.?|#|no)\s*[:.]?\s*([A-Z0-9][\w/.-]*)", re.I)
_DATE = re.compile(r"\b(\d{1,2}[-/. ](?:[A-Za-z]{3}|\d{1,2})[-/. ]\d{2,4})\b")
_AMT = r"[:\s]*(?:Rs\.?|INR)?\s*(-?[\d,]+\.\d{2})"


def _gstin(raw: str) -> str:
    return raw[:2].translate(_OCR) + raw[2:]


def _amount(text: str, labels: str) -> float:
    found = re.findall(rf"(?:{labels})[^\n\d-]*?{_AMT}", text, re.I)
    return float(found[-1].replace(",", "")) if found else 0.0


def heuristic_record(text: str, buyer_gstin: str) -> DocRecord:
    gstins = [_gstin(g) for g in _GSTIN.findall(text.upper())]
    supplier = next((g for g in gstins if g != buyer_gstin), gstins[0] if gstins else "")
    no = _NO.search(text)
    when = ""
    for d in _DATE.findall(text):
        try:
            when = parse_date(d).isoformat()
            break
        except (ValueError, KeyError):
            continue
    heads = {h: _amount(text, h) for h in ("igst", "cgst", "sgst", "cess")}
    taxable = _amount(text, "taxable value|taxable amt|taxable amount|assessable value|sub ?total")
    total = _amount(text, "grand total|total amount|invoice total|net amount|amount payable to supplier|total")
    rcm = re.search(r"reverse\s*charge[^\n]{0,3}\s*[:\-]?\s*(yes|y)\b", text, re.I) is not None
    line = DocLine(description="", hsn="", taxable_value=taxable, rate=0.0, **heads,
                   itc_category=ItcCategory.NORMAL, purpose=LinePurpose.BUSINESS)
    return DocRecord(doc_type=DocType.CREDIT_NOTE if re.search(r"credit\s*note", text, re.I) else DocType.INVOICE,
                     supplier_gstin=supplier, supplier_name="", invoice_no=no.group(1) if no else "", invoice_date=when,
                     place_of_supply=buyer_gstin[:2], reverse_charge=rcm, original_invoice_no="", line_items=[line],
                     taxable_value=taxable, **heads, total=total)


def heuristic_call(messages: list[dict]) -> dict:
    """Drop-in for a model call in hybrid mode: reads the header and document from the user message."""
    user = messages[-1]["content"]
    m = re.search(r"^Buyer GSTIN: (\S+)", user, re.M)
    body = user.split("\n--- ", 1)[-1]
    rec = heuristic_record(body, m.group(1) if m else "")
    return {"text": rec.model_dump_json(), "prompt_tokens": 0, "completion_tokens": 0, "latency_s": 0.0, "error": None,
            "finish_reason": "stop"}
