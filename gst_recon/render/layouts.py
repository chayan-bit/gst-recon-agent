"""Layout registry: which template renders a document and how its line table looks."""

from __future__ import annotations

import random
from dataclasses import dataclass

from gst_recon.render.holdout import OOD_LAYOUT_BOOST, OOD_LAYOUTS
from gst_recon.schema import DocType, TruthInvoice


@dataclass(frozen=True)
class Layout:
    id: str
    template: str  # file under templates/
    table: str  # "full" (per-line tax columns) or "compact" (amount only + tax summary block)
    page: str  # CSS @page size
    dpi: int = 200
    crop: bool = False  # trim blank space below content (receipt-style)


LAYOUTS: dict[str, Layout] = {
    l.id: l
    for l in (
        Layout("tally_tax_invoice", "tally.html.j2", "full", "A4"),
        Layout("small_trader_bill", "trader.html.j2", "compact", "A5 landscape"),
        Layout("thermal_receipt", "thermal.html.j2", "compact", "80mm 700mm", dpi=220, crop=True),
        Layout("service_invoice_sac", "service.html.j2", "full", "A4"),
        Layout("letterhead_stamp", "letterhead.html.j2", "full", "A4"),
        Layout("saas_two_column", "saas.html.j2", "full", "A4"),
        Layout("handwritten_bill", "handwritten.html.j2", "compact", "A5 landscape"),
        Layout("credit_note", "credit_note.html.j2", "full", "A4"),
    )
}
TEXT_LAYOUTS = ("email_text", "whatsapp_text")
ALL_LAYOUT_IDS = (*LAYOUTS, *TEXT_LAYOUTS)

_GOODS_WEIGHTS = {"tally_tax_invoice": 30, "small_trader_bill": 22, "thermal_receipt": 8, "letterhead_stamp": 15,
                  "handwritten_bill": 8, "saas_two_column": 5, "service_invoice_sac": 2}
_SERVICE_WEIGHTS = {"service_invoice_sac": 30, "saas_two_column": 25, "letterhead_stamp": 20,
                    "tally_tax_invoice": 15, "handwritten_bill": 3, "thermal_receipt": 2, "small_trader_bill": 5}
_CREDIT_WEIGHTS = {"credit_note": 60, "tally_tax_invoice": 20, "letterhead_stamp": 20}


def is_service(inv: TruthInvoice) -> bool:
    return all(l.hsn.startswith("99") for l in inv.line_items)


def choose_layout(rng: random.Random, inv: TruthInvoice, split: str = "train") -> str:
    """Pick a layout for the supplier of `inv` (call with a per-supplier rng so a supplier keeps its look)."""
    if inv.doc_type == DocType.CREDIT_NOTE:
        weights = _CREDIT_WEIGHTS
    else:
        weights = dict(_SERVICE_WEIGHTS if is_service(inv) else _GOODS_WEIGHTS)
        if inv.total > 100_000 or len(inv.line_items) > 6:  # a Rs 20 lakh car does not come on a receipt roll
            weights.pop("thermal_receipt", None)
            weights.pop("handwritten_bill", None)
            weights.pop("small_trader_bill", None)
    if split == "test_ood":
        weights = {k: v * (OOD_LAYOUT_BOOST if k in OOD_LAYOUTS else 1) for k, v in weights.items()}
    else:
        weights = {k: v for k, v in weights.items() if k not in OOD_LAYOUTS} or weights
    ids = sorted(weights)
    return rng.choices(ids, weights=[weights[i] for i in ids])[0]
