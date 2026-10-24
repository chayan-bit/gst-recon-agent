from gst_recon.render.fmt import fmt_date
from gst_recon.render.verify import Index, case_recall, check_doc, doc_facts

EMPTY = Index.of("")


def _clean_text(inv, date_fmt="DD-MM-YYYY", num=lambda x: f"{x:,.2f}"):
    parts = [inv.invoice_no, inv.supplier_gstin, fmt_date(inv.invoice_date, date_fmt), num(inv.taxable_value), num(inv.total),
             *[num(getattr(inv, h)) for h in ("igst", "cgst", "sgst", "cess") if getattr(inv, h) > 0],
             inv.original_invoice_no or ""]
    for l in inv.line_items:
        parts += [l.hsn, num(l.taxable_value)]
    return "  ".join(parts)


def test_clean_text_is_fully_recovered(case):
    inv = case.inputs.invoices[0]
    shown = fmt_date(inv.invoice_date, "DD-MM-YYYY")
    r = check_doc(inv.doc_id, doc_facts(inv, shown), _clean_text(inv), EMPTY)
    assert r.found == r.total and not r.lost


def test_ocr_noise_in_separators_and_o0_confusions_is_tolerated(case):
    inv = case.inputs.invoices[0]
    shown = fmt_date(inv.invoice_date, "DD/MM/YY")
    text = _clean_text(inv, "DD/MM/YY", num=lambda x: f"{x:,.2f}".replace(",", ".")  # 1.23.456.00 style swap
                       ).replace(inv.supplier_gstin, inv.supplier_gstin.replace("0", "O"))
    r = check_doc(inv.doc_id, doc_facts(inv, shown), text, EMPTY)
    assert "supplier_gstin" not in r.missing_in_ocr and "total" not in r.missing_in_ocr


def test_destroyed_gstin_is_lost_unless_other_sections_carry_it(case):
    inv = case.inputs.invoices[0]
    shown = fmt_date(inv.invoice_date, "DD-MM-YYYY")
    text = _clean_text(inv).replace(inv.supplier_gstin, "##########")
    lost = check_doc(inv.doc_id, doc_facts(inv, shown), text, EMPTY)
    assert lost.lost == ["supplier_gstin"] and lost.found == lost.total - 1
    elsewhere = check_doc(inv.doc_id, doc_facts(inv, shown), text, Index.of(f"register row {inv.supplier_gstin}"))
    assert elsewhere.lost == [] and elsewhere.missing_in_ocr == ["supplier_gstin"]


def test_hsn_needs_digit_boundaries(case):
    inv = case.inputs.invoices[0]
    shown = fmt_date(inv.invoice_date, "DD-MM-YYYY")
    hsn = inv.line_items[0].hsn
    text = _clean_text(inv).replace(hsn, f"9{hsn}9", 1)
    r = check_doc(inv.doc_id, doc_facts(inv, shown), text, Index.of(hsn))
    assert "line0_hsn" in r.lost  # HSN is never recoverable from the other sections


def test_case_recall_summary(case):
    inv = case.inputs.invoices[0]
    shown = fmt_date(inv.invoice_date, "DD-MM-YYYY")
    good = check_doc("D01", doc_facts(inv, shown), _clean_text(inv), EMPTY)
    bad = check_doc("D02", doc_facts(inv, shown), "nothing readable", EMPTY)
    s = case_recall([good, bad], {"D01", "D02"})
    assert s["has_unrecoverable"] and s["ocr_recall"] == 0.5 and s["doc_recall"] == {"D01": 1.0, "D02": 0.0}
