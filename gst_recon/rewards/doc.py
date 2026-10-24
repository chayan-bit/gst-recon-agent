"""Per-document GRPO reward: one DocRecord against the truth DocRecord, with abstention credit.

Weighted field match. The identity fields (supplier GSTIN, invoice number, invoice date) and the two per-line
judgments (itc_category, purpose) weigh most, the line amounts less, everything else least.

Abstention: a truth identity value the document's OCR text does not show (both normalised, with the usual OCR
look-alikes such as O/0 folded) cannot be read off the page, so "" earns full credit there and any value other
than the truth earns a penalty. A value the page shows only with look-alike errors counts as shown: reading
"O7ABC..." as "07ABC..." is expected, not abstaining. An invented GSTIN or
invoice number silently breaks GSTR-2B linking; an empty one is visible to the reconciler.

Schema-invalid output scores 0 and every valid output scores at least VALID_FLOOR, so breaking the format never
beats a bad answer. Pure, deterministic and total: it never raises.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from gst_recon.hybrid.docschema import DocRecord
from gst_recon.hybrid.inputs import parse_date
from gst_recon.render.fmt import DATE_FORMATS, fmt_date
from gst_recon.render.holdout import OOD_DATE_FORMATS

IDENTITY = ("supplier_gstin", "invoice_no", "invoice_date")
LINE_AMOUNTS = ("taxable_value", "rate", "igst", "cgst", "sgst", "cess")
DOC_OTHER = ("doc_type", "supplier_name", "place_of_supply", "reverse_charge", "original_invoice_no",
             "taxable_value", "igst", "cgst", "sgst", "cess", "total")
WEIGHTS = {"supplier_gstin": 3.0, "invoice_no": 3.0, "invoice_date": 3.0, "itc_category": 3.0, "purpose": 3.0,
           "line_amounts": 1.5, "other": 1.0}
INVENTED = -1.0  # an identity value the page does not show, other than the truth
VALID_FLOOR = 0.1
TOL = 1.0  # rupees
_LOWEST = sum(WEIGHTS[f] for f in IDENTITY) * INVENTED / sum(WEIGHTS.values())  # every identity field invented


_LOOKALIKE = str.maketrans("$OILSB", "501158")  # "$" is how Tesseract most often reads a degraded "S"


def norm(s: Any) -> str:
    return re.sub(r"[^0-9A-Z]", "", str(s).upper())


def _fold(s: Any) -> str:
    return norm(str(s).upper().translate(_LOOKALIKE))


def parse_doc(text: str) -> DocRecord | None:
    """The completion as a DocRecord (a ```json fence or text around the object is tolerated), else None."""
    if not isinstance(text, str):
        return None
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    for candidate in (text, text[text.find("{"): text.rfind("}") + 1]):
        try:
            return DocRecord.model_validate(json.loads(candidate))
        except (ValueError, TypeError, ValidationError):
            continue
    return None


def _same(field: str, a: str, b: str) -> bool:
    if field == "invoice_date":
        try:
            return parse_date(a) == parse_date(b)
        except (ValueError, KeyError):
            return False
    return norm(a) == norm(b) != ""


def visible(field: str, value: str, doc_text: str) -> bool:
    """Whether the page shows the truth value: look-alike-folded substring, in any date style the renderer uses."""
    page = _fold(doc_text)
    if field != "invoice_date":
        return _fold(value) in page
    try:
        d = parse_date(value)
    except (ValueError, KeyError):
        return False
    return any(_fold(fmt_date(d, f)) in page for f in {*DATE_FORMATS, *OOD_DATE_FORMATS, "YYYY-MM-DD"})


def identity_score(field: str, pred: str, truth: str, doc_text: str) -> float:
    if _same(field, pred, truth) or (not truth.strip() and not pred.strip()):
        return 1.0
    if visible(field, truth, doc_text):
        return 0.0
    return 1.0 if not pred.strip() else INVENTED


def _eq(a: Any, b: Any, tol: float) -> bool:
    if isinstance(a, bool) or isinstance(b, bool) or isinstance(a, str) or isinstance(b, str):
        return norm(a) == norm(b) if isinstance(a, str) and isinstance(b, str) else a == b
    return abs(float(a) - float(b)) <= tol


def _lines(pred: DocRecord, truth: DocRecord, fields: tuple[str, ...]) -> float:
    """Mean match over lines aligned by index; missing or extra lines count as misses."""
    n = max(len(pred.line_items), len(truth.line_items))
    if n == 0:
        return 1.0
    hits = sum(_eq(getattr(p, f), getattr(t, f), 0.01 if f == "rate" else TOL)
               for p, t in zip(pred.line_items, truth.line_items) for f in fields)
    return hits / (n * len(fields))


def doc_components(pred: DocRecord, truth: DocRecord, doc_text: str) -> dict[str, float]:
    out = {f: identity_score(f, getattr(pred, f), getattr(truth, f), doc_text) for f in IDENTITY}
    out["itc_category"] = _lines(pred, truth, ("itc_category",))
    out["purpose"] = _lines(pred, truth, ("purpose",))
    out["line_amounts"] = _lines(pred, truth, LINE_AMOUNTS)
    n_lines = max(len(pred.line_items), len(truth.line_items))
    doc_hits = sum(_eq(getattr(pred, f), getattr(truth, f), TOL) for f in DOC_OTHER)
    out["other"] = (doc_hits + _lines(pred, truth, ("hsn",)) * n_lines) / (len(DOC_OTHER) + n_lines)
    return out


def doc_reward(text: str, truth: dict | DocRecord, doc_text: str) -> float:
    """0 for schema-invalid output; else VALID_FLOOR..1, linear in the weighted field score."""
    pred = parse_doc(text)
    if pred is None:
        return 0.0
    try:
        truth = truth if isinstance(truth, DocRecord) else DocRecord.model_validate(truth)
    except ValidationError:
        return 0.0
    comp = doc_components(pred, truth, doc_text)
    weighted = sum(WEIGHTS[k] * v for k, v in comp.items()) / sum(WEIGHTS.values())
    return VALID_FLOOR + (1 - VALID_FLOOR) * (weighted - _LOWEST) / (1 - _LOWEST)
