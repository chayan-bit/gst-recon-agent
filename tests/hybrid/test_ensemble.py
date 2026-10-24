from __future__ import annotations

from gst_recon.hybrid.docschema import DocRecord
from gst_recon.hybrid.ensemble import ensemble


def rec(**kw) -> DocRecord:
    base = dict(doc_type="invoice", supplier_gstin="29ABCDE1234F1Z5", supplier_name="A", invoice_no="INV-1",
                invoice_date="2026-04-01", place_of_supply="29", reverse_charge=False, original_invoice_no="",
                line_items=[], taxable_value=100.0, igst=0.0, cgst=9.0, sgst=9.0, cess=0.0, total=118.0)
    return DocRecord.model_validate({**base, **kw})


def test_identity_takes_the_two_vote_value_written_as_the_first_member_that_emitted_it():
    out = ensemble(rec(invoice_no="inv 1"), rec(invoice_no="INV-1"), rec(invoice_no="X9"))
    assert out.invoice_no == "inv 1"


def test_identity_abstains_when_all_three_disagree():
    out = ensemble(rec(invoice_no="A1"), rec(invoice_no="B2"), rec(invoice_no="C3"))
    assert out.invoice_no == ""


def test_empty_counts_as_a_vote():
    out = ensemble(rec(supplier_gstin="29ABCDE1234F1Z5"), rec(supplier_gstin=""), rec(supplier_gstin=""))
    assert out.supplier_gstin == ""


def test_dates_in_different_printed_styles_agree():
    out = ensemble(rec(invoice_date="2026-04-07"), rec(invoice_date="07/04/2026"), rec(invoice_date="2026-05-01"))
    assert out.invoice_date == "2026-04-07"


def test_other_fields_come_from_v1():
    out = ensemble(rec(total=118.0, cgst=9.0), rec(total=200.0, cgst=1.0), rec(total=200.0, cgst=1.0))
    assert (out.total, out.cgst) == (118.0, 9.0)


def test_without_v1_the_rest_comes_from_pd3a_and_identity_needs_both_survivors_to_agree():
    out = ensemble(None, rec(total=200.0, invoice_no="A1"), rec(total=300.0, invoice_no="B2"))
    assert out.total == 200.0 and out.invoice_no == ""
    assert ensemble(None, None, rec(invoice_no="B2")).invoice_no == ""


def test_no_parsed_member_gives_none():
    assert ensemble(None, None, None) is None


def test_flat_build_combines_member_files_and_keeps_v1_when_nothing_parses(tmp_path):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("ens", Path(__file__).resolve().parents[2] / "scripts" / "hybrid_ensemble.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    dirs = [tmp_path / n for n in ("v1", "a", "b")]
    for d, no in zip(dirs, ("A1", "A1", "B2")):
        d.mkdir()
        (d / "x.json").write_text(rec(invoice_no=no).model_dump_json())
        (d / "y.json").write_text("not json")
    assert mod.flat(tmp_path / "out", dirs) == 2
    assert DocRecord.model_validate_json((tmp_path / "out" / "x.json").read_text()).invoice_no == "A1"
    assert (tmp_path / "out" / "y.json").read_text() == "not json"
