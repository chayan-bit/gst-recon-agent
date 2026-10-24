"""fmt_version 2: diverse per-supplier invoice-number and date formats for new training data; v1 untouched."""

import random
import re
from collections import defaultdict

import pytest

from gst_recon.render.context import build_context
from gst_recon.render.fmt import DATE_FORMATS_V2, fmt_date
from gst_recon.rewards.doc import visible
from gst_recon.schema import Case, DocType
from gst_recon.sim.suppliers import LEGAL_NO, MAX_NO_LEN
from gst_recon.sim.world import generate_case

CASES = [generate_case(8101, d, i, size="sft", fmt_version=2) for d in ("easy", "medium", "hard") for i in range(15)]


def _shape(no: str) -> str:
    return re.sub(r"\d+", "9", no)


def test_v1_json_has_no_version_field_and_v2_round_trips():
    assert "fmt_version" not in generate_case(9001, "easy", 0, split="test_iid").model_dump_json()
    c = CASES[0]
    assert c.fmt_version == 2 and Case.model_validate_json(c.model_dump_json()).fmt_version == 2
    with pytest.raises(ValueError):
        generate_case(1, "easy", 0, fmt_version=3)


def test_numbers_are_legal_and_one_format_per_supplier():
    shapes = defaultdict(lambda: defaultdict(set))
    for c in CASES:
        for inv in c.inputs.invoices:
            assert len(inv.invoice_no) <= MAX_NO_LEN and LEGAL_NO.fullmatch(inv.invoice_no), inv.invoice_no
            shapes[c.case_id][(inv.supplier_gstin, inv.doc_type)].add(_shape(inv.invoice_no))
    assert all(len(s) == 1 for per_case in shapes.values() for s in per_case.values())
    distinct = {next(iter(s)) for per_case in shapes.values() for s in per_case.values()}
    assert len(distinct) >= 30  # diverse across suppliers


def test_register_and_2b_carry_the_document_number():
    for c in CASES:
        twob = {n.inum for r in c.inputs.gstr2b for s in r.data.docdata.b2b for n in s.inv}
        twob |= {n.ntnum for r in c.inputs.gstr2b for s in r.data.docdata.cdnr for n in s.nt}
        reg = {r.supplier_invoice_no for r in c.inputs.purchase_register}
        typo = {a.split(":")[0] for a in c.anomalies if a.endswith("reg_invoice_no_typo")}
        for inv in c.inputs.invoices:
            if inv.doc_id not in typo:
                assert inv.invoice_no in reg
        assert twob <= {inv.invoice_no for inv in c.inputs.invoices}


@pytest.mark.parametrize("style", DATE_FORMATS_V2)
def test_every_v2_date_style_counts_as_visible(style):
    d = CASES[0].inputs.invoices[0].invoice_date
    assert visible("invoice_date", d.isoformat(), f"Invoice Date : {fmt_date(d, style)} 02:31 PM")


def test_v2_dates_are_per_supplier_and_visible():
    pytest.importorskip("faker")  # render extra
    styles = defaultdict(set)
    for c in CASES[:20]:
        for inv in c.inputs.invoices:
            ctx = build_context(c, inv, "tally_tax_invoice", random.Random(f"{c.case_id}:{inv.supplier_gstin}:style"),
                                random.Random(1), c.split)
            assert visible("invoice_date", inv.invoice_date.isoformat(), ctx["date"])
            assert ctx["date"].startswith(ctx["date_only"])
            styles[(c.case_id, inv.supplier_gstin)].add(ctx["fmt"].date_fmt)
    assert all(len(s) == 1 for s in styles.values())
    assert len({s for v in styles.values() for s in v}) >= 8


def test_credit_notes_use_the_supplier_cn_format():
    cns = [inv.invoice_no for c in CASES for inv in c.inputs.invoices if inv.doc_type == DocType.CREDIT_NOTE]
    assert all(LEGAL_NO.fullmatch(n) for n in cns)
