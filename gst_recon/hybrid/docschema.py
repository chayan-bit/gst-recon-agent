"""Per-document model output: one document's extraction plus the judgment calls the rules engine needs.

The judgments are exactly the two truth-only facts `sim.rules.line_block_reason` consumes per line and
that no arithmetic can produce: what kind of supply the line is (`itc_category`, read from a free-text
description that may be OCR-mangled, abbreviated or trade slang) and what the buyer uses it for
(`purpose`, read from the buyer profile header and the invoice remarks). Everything else (the s.17(5)
exceptions such as the 250-employee canteen threshold, 2B and register matching, the 180-day rule,
rupee splits) is applied by code.
"""

from __future__ import annotations

from datetime import date

from pydantic import Field

from gst_recon.hybrid.inputs import parse_date
from gst_recon.schema import (
    DocType,
    ExtractionRecord,
    ItcCategory,
    LineItemOut,
    LinePurpose,
    TruthInvoice,
    TruthLineItem,
    _inline,
    _Strict,
)

# ItcCategory.PERSONAL_USE / GIFT are legacy categories the simulator no longer emits (personal use and
# gifts are purposes), so the model chooses among the remaining five.
MODEL_CATEGORIES = [c.value for c in ItcCategory if c not in (ItcCategory.PERSONAL_USE, ItcCategory.GIFT)]


class DocLine(_Strict):
    description: str
    hsn: str
    taxable_value: float
    rate: float
    igst: float
    cgst: float
    sgst: float
    cess: float
    itc_category: ItcCategory = Field(description="kind of supply for s.17(5)")
    purpose: LinePurpose = Field(description="what the buyer uses it for, from the buyer profile and remarks")


class DocRecord(_Strict):
    """What the model returns for ONE document (doc_id is assigned by code from the section header)."""

    doc_type: DocType
    supplier_gstin: str
    supplier_name: str
    invoice_no: str
    invoice_date: str = Field(description="YYYY-MM-DD")
    place_of_supply: str = Field(description="2-digit GST state code")
    reverse_charge: bool
    original_invoice_no: str = Field(description="credit notes only, else empty string")
    line_items: list[DocLine]
    taxable_value: float
    igst: float
    cgst: float
    sgst: float
    cess: float
    total: float


def doc_json_schema() -> dict:
    """Flattened JSON Schema for grammar-constrained decoding (same treatment as schema.output_json_schema).
    Every field is required and the category enum drops the two legacy values."""
    raw = DocRecord.model_json_schema()
    out = _inline(raw, raw.get("$defs", {}))
    line = out["properties"]["line_items"]["items"]
    line["properties"]["itc_category"]["enum"] = MODEL_CATEGORIES
    for node in (out, line):
        node["required"] = list(node["properties"])
    return out


HEADS = ("igst", "cgst", "sgst", "cess")


def to_extraction(doc_id: str, rec: DocRecord) -> ExtractionRecord:
    return ExtractionRecord(doc_id=doc_id, **rec.model_dump(exclude={"line_items"}), line_items=[
        LineItemOut(**li.model_dump(exclude={"itc_category", "purpose"})) for li in rec.line_items])


def invoice_date(rec: DocRecord, fallback: date) -> tuple[date, bool]:
    """(date, ok). A date the model got unreadable falls back to `fallback` and is reported in the trace."""
    try:
        return parse_date(rec.invoice_date), True
    except (ValueError, KeyError):
        return fallback, False


def to_truth_invoice(doc_id: str, rec: DocRecord, *, buyer_gstin: str, buyer_name: str, when: date) -> TruthInvoice:
    """The rules engine's input type, filled from the model's record. Quantity, unit and price are not used by
    any rule and are not extracted."""
    lines = [TruthLineItem(description=li.description, hsn=li.hsn, quantity=0, unit="", unit_price=0,
                           taxable_value=li.taxable_value, rate=li.rate, **{h: getattr(li, h) for h in HEADS},
                           category=li.itc_category, purpose=li.purpose) for li in rec.line_items]
    return TruthInvoice(doc_id=doc_id, doc_type=rec.doc_type, supplier_gstin=rec.supplier_gstin.strip().upper(),
                        supplier_name=rec.supplier_name, supplier_address="", buyer_gstin=buyer_gstin, buyer_name=buyer_name,
                        invoice_no=rec.invoice_no.strip(), invoice_date=when, place_of_supply=rec.place_of_supply,
                        reverse_charge=rec.reverse_charge, original_invoice_no=rec.original_invoice_no.strip() or None,
                        line_items=lines, taxable_value=rec.taxable_value, **{h: getattr(rec, h) for h in HEADS},
                        total=rec.total)
