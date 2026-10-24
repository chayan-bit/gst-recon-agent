import hashlib
import random

import pytest

from gst_recon.render.context import build_context
from gst_recon.render.holdout import OOD_DATE_FORMATS, OOD_LAYOUTS
from gst_recon.render.layouts import ALL_LAYOUT_IDS, LAYOUTS, choose_layout
from gst_recon.render.textdocs import render_text
from gst_recon.render.verify import Index, check_doc, doc_facts


def _ctx(case, inv, layout, split="train"):
    return build_context(case, inv, layout, random.Random(1), random.Random(2), split)


def test_there_are_at_least_eight_distinct_paper_layouts():
    assert len(LAYOUTS) >= 8 and len({l.template for l in LAYOUTS.values()}) == len(LAYOUTS)


@pytest.mark.parametrize("layout_id", sorted(LAYOUTS))
def test_every_layout_renders_with_all_key_facts(weasy, case, layout_id):
    from gst_recon.render.pdf import html_to_pdf, render_html, render_pages

    inv = next(i for i in case.inputs.invoices if i.line_items)
    ctx = _ctx(case, inv, layout_id)
    html = render_html(LAYOUTS[layout_id], ctx)
    for fact in (inv.invoice_no, inv.supplier_gstin, inv.buyer_gstin, ctx["date"], ctx["total"], ctx["words"]):
        assert fact.replace("&", "&amp;") in html or fact in html
    assert html_to_pdf(html).startswith(b"%PDF")
    pages = render_pages(LAYOUTS[layout_id], ctx)
    assert pages and all(p.width > 100 and p.height > 100 for p in pages)


def test_credit_note_shows_original_invoice(weasy, case):
    cn = next((i for i in case.inputs.invoices if i.original_invoice_no), None)
    if cn is None:
        pytest.skip("no credit note in this case")
    from gst_recon.render.pdf import render_html

    assert cn.original_invoice_no in render_html(LAYOUTS["credit_note"], _ctx(case, cn, "credit_note"))


@pytest.mark.parametrize("kind", ["email_text", "whatsapp_text"])
def test_text_documents_carry_every_fact(case, kind):
    for inv in case.inputs.invoices:
        ctx = _ctx(case, inv, "tally_tax_invoice")
        text = render_text(ctx, kind, random.Random(3))
        r = check_doc(inv.doc_id, doc_facts(inv, ctx["date"]), text, Index.of(""))
        assert not r.missing_in_ocr, (kind, inv.doc_id, r.missing_in_ocr)


def test_train_never_uses_held_out_choices_and_ood_does(case):
    inv = case.inputs.invoices[0]
    seen_train, seen_ood, dates_ood = set(), set(), set()
    for i in range(300):
        seen_train.add(choose_layout(random.Random(i), inv, "train"))
        seen_ood.add(choose_layout(random.Random(i), inv, "test_ood"))
        assert _ctx_fmt(case, inv, i, "train") not in OOD_DATE_FORMATS
        dates_ood.add(_ctx_fmt(case, inv, i, "test_ood"))
    assert not seen_train & set(OOD_LAYOUTS)
    assert set(OOD_LAYOUTS) & seen_ood
    assert set(OOD_DATE_FORMATS) & dates_ood


def _ctx_fmt(case, inv, i, split):
    return build_context(case, inv, "tally_tax_invoice", random.Random(i), random.Random(i), split)["fmt"].date_fmt


def test_layout_choice_is_deterministic_per_supplier(case):
    inv = case.inputs.invoices[0]
    assert choose_layout(random.Random("a"), inv) == choose_layout(random.Random("a"), inv)
    assert set(ALL_LAYOUT_IDS) >= set(LAYOUTS)


def test_degradation_is_deterministic_and_changes_pixels(weasy, case):
    from gst_recon.render.degrade import degrade
    from gst_recon.render.pdf import render_pages

    inv = case.inputs.invoices[0]
    page = render_pages(LAYOUTS["tally_tax_invoice"], _ctx(case, inv, "tally_tax_invoice"))[0]
    md5 = lambda im: hashlib.md5(im.tobytes()).hexdigest()  # noqa: E731
    for level in ("easy", "medium", "hard"):
        a, plan_a = degrade(page, level, random.Random(9))
        b, plan_b = degrade(page, level, random.Random(9))
        assert md5(a) == md5(b) and plan_a == plan_b
        assert md5(a) != md5(page)


def test_render_case_is_deterministic_by_seed(weasy, has_tesseract, tiny_case, tmp_path):
    case = tiny_case
    from gst_recon.render.pipeline import render_case

    ocr = has_tesseract
    m1 = render_case(case, tmp_path / "a", ocr=ocr)
    m2 = render_case(case, tmp_path / "b", ocr=ocr)
    for name in ("prompt.txt", "target.json"):
        assert (tmp_path / "a" / case.case_id / name).read_bytes() == (tmp_path / "b" / case.case_id / name).read_bytes()
    for m in (m1, m2):
        m["timing_s"] = None
    assert m1 == m2
    meta = m1
    assert meta["split"] == "train" and {"ocr_recall", "unrecoverable", "documents", "prompt_tokens"} <= set(meta)
    assert not list((tmp_path / "a").glob(".*.tmp")) and not (tmp_path / "a" / case.case_id / "images").exists()


def test_output_is_target_of_the_truth_and_has_all_sections(weasy, tiny_case, tmp_path):
    case = tiny_case
    import json

    from gst_recon.render.pipeline import render_case

    render_case(case, tmp_path, ocr=False, keep_images=True)
    d = tmp_path / case.case_id
    prompt = (d / "prompt.txt").read_text()
    for marker in ("=== CASE ===", "=== INVOICES ===", "=== PURCHASE REGISTER", "=== GSTR-2B period", "=== BANK STATEMENT", "=== END ==="):
        assert marker in prompt
    assert json.loads((d / "target.json").read_text()) == json.loads(case.expected.model_dump_json())
    assert any((d / "images").glob("*.png")) or all("text" in x["delivery"] for x in json.loads((d / "meta.json").read_text())["documents"])


def _needs_field(model, name):
    if name not in model.model_fields:
        pytest.skip(f"schema has no {name} yet")


@pytest.mark.parametrize("layout_id", sorted(LAYOUTS))
def test_remarks_line_is_printed_on_every_layout(weasy, case, layout_id):
    from gst_recon.render.pdf import render_html
    from gst_recon.schema import TruthInvoice

    _needs_field(TruthInvoice, "remarks")
    inv = case.inputs.invoices[0].model_copy(update={"remarks": "For director residence use"})
    assert "For director residence use" in render_html(LAYOUTS[layout_id], _ctx(case, inv, layout_id))
    for kind in ("email_text", "whatsapp_text"):
        assert "for director residence use" in render_text(_ctx(case, inv, "tally_tax_invoice"), kind, random.Random(1)).lower()


def test_buyer_profile_is_rendered_in_the_case_header(case):
    from gst_recon.render.prompt import _header
    from gst_recon.schema import CaseInputs

    _needs_field(CaseInputs, "buyer_profile")
    from gst_recon.schema import BuyerProfile

    prof = BuyerProfile(profile="hotel", description="Business hotel with restaurant and banquets.", employees=140)
    c2 = case.model_copy(update={"inputs": case.inputs.model_copy(update={"buyer_profile": prof})})
    header = _header(c2)
    assert "Buyer line of business: hotel - Business hotel with restaurant and banquets." in header
    assert "Buyer employees: 140" in header
