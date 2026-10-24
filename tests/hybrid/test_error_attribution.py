"""scripts/hybrid_error_attribution.py: field-group oracle swaps and the recoverable-from-text check."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from gst_recon.hybrid.docschema import DocRecord

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "hybrid_error_attribution.py"


def _load():
    spec = importlib.util.spec_from_file_location("hybrid_error_attribution", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["hybrid_error_attribution"] = mod
    spec.loader.exec_module(mod)
    return mod


def rec(lines=(("normal", "business"),), **kw) -> DocRecord:
    items = [dict(description="x", hsn="1", taxable_value=100.0, rate=18.0, igst=0.0, cgst=9.0, sgst=9.0, cess=0.0,
                  itc_category=c, purpose=p) for c, p in lines]
    base = dict(doc_type="invoice", supplier_gstin="29ABCDE1234F1Z5", supplier_name="A", invoice_no="INV-1",
                invoice_date="2026-04-01", place_of_supply="29", reverse_charge=False, original_invoice_no="",
                line_items=items, taxable_value=100.0, igst=0.0, cgst=9.0, sgst=9.0, cess=0.0, total=118.0)
    return DocRecord.model_validate({**base, **kw})


def test_each_group_swap_copies_only_its_own_fields():
    mod = _load()
    m = rec(invoice_no="WRONG", total=999.0, reverse_charge=True)
    t = rec()
    assert mod.patch(m, t, ("identity",)).model_dump() == rec(total=999.0, reverse_charge=True).model_dump()
    assert mod.patch(m, t, ("amounts",)).model_dump() == rec(invoice_no="WRONG", reverse_charge=True).model_dump()
    assert mod.patch(m, t, ("judgment",)).model_dump() == rec(invoice_no="WRONG", total=999.0).model_dump()
    assert mod.patch(m, t, ("identity", "amounts", "judgment")) == t


def test_amounts_swap_fixes_a_line_count_misread_but_keeps_the_model_judgment():
    mod = _load()
    m = rec(lines=(("motor_vehicle", "further_supply"),))
    t = rec(lines=(("normal", "business"), ("normal", "business")))
    out = mod.patch(m, t, ("amounts",))
    assert len(out.line_items) == 2
    assert (out.line_items[0].itc_category, out.line_items[0].purpose) == ("motor_vehicle", "further_supply")


def test_recoverable_folds_formats_and_flags_values_the_text_lacks():
    mod = _load()
    text = "GSTIN: 29ABCDE1234FIZ5  Bill No inv/1  Dated 01-Apr-26  Grand Total Rs 1,18,000.40"
    assert mod.recoverable("supplier_gstin", "29ABCDE1234F1Z5", text)  # I/1 look-alike
    assert mod.recoverable("invoice_date", "2026-04-01", text)
    assert mod.recoverable("total", 118000.0, text)
    assert mod.recoverable("cess", 0.0, text)
    assert not mod.recoverable("total", 120000.0, text)
    assert not mod.recoverable("invoice_date", "2026-04-02", text)
    assert not mod.recoverable("supplier_gstin", "07ZZZZZ9999Z1Z9", text)
