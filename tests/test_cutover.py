"""GST 2.0 rate cutover (22 Sep 2025): rates follow the supply/invoice date."""

from datetime import date

import pytest

from gst_recon.schema import DocType
from gst_recon.sim import catalog as cat
from gst_recon.sim.__main__ import main
from gst_recon.sim.world import DEFAULT_PERIODS, fy_label, generate_case, period_range

BEFORE, ON = date(2025, 9, 21), date(2025, 9, 22)
PRODUCTS = {p.description: p for p in cat.GOODS + cat.SERVICES + cat.RCM + cat.BLOCKED}


def by_hsn(hsn):
    return next(p for p in PRODUCTS.values() if p.hsn == hsn)


@pytest.mark.parametrize("hsn,before,after", [
    ("2523", (28, 0), (18, 0)),    # cement
    ("8415", (28, 0), (18, 0)),    # air conditioners
    ("3004", (12, 0), (5, 0)),     # medicaments
    ("8703", (28, 22), (40, 0)),   # SUV: 40% slab, compensation cess Nil
    ("2202", (28, 12), (40, 0)),   # aerated waters
    ("999723", (18, 0), (5, 0)),   # fitness centre (group 99972)
    ("996311", (12, 0), (5, 0)),   # hotel <= Rs 7500
    ("8471", (18, 0), (18, 0)),    # unchanged
])
def test_rate_on_switches_exactly_at_cutover(hsn, before, after):
    p = by_hsn(hsn)
    assert cat.rate_on(p, BEFORE) == before
    assert cat.rate_on(p, ON) == after


def test_unverified_post_rate_excludes_product_after_cutover():
    p = cat.Product("x", "0000", 18, "Nos", (1, 2), (1, 1))  # post_rate defaults to unverified
    assert cat.rate_on(p, BEFORE) == (18, 0) and cat.rate_on(p, ON) is None


def test_every_catalog_product_has_a_verified_post_rate():
    missing = [p.description for p in PRODUCTS.values() if p.post_rate is None]
    assert missing == []  # if one is added unverified, it is simply not generated after the cutover


def _check_case_rates(c):
    invs = c.inputs.invoices
    originals = {(i.supplier_gstin, i.invoice_no): i for i in invs if i.doc_type == DocType.INVOICE}
    for inv in invs:
        for li in inv.line_items:
            if inv.doc_type == DocType.CREDIT_NOTE:
                orig = originals[(inv.supplier_gstin, inv.original_invoice_no)]
                assert li.rate == orig.line_items[0].rate  # credit note keeps the original supply's rate
                continue
            rate, cess = cat.rate_on(PRODUCTS[li.description], inv.invoice_date)
            assert li.rate == rate
            assert li.cess == pytest.approx(round(li.taxable_value * cess / 100, 2), abs=0.011)


def test_straddling_period_uses_rate_on_invoice_date():
    seen = set()
    for i in range(60):
        c = generate_case(7, "hard", i, periods=[(2025, 9)])
        _check_case_rates(c)
        seen |= {(inv.invoice_date >= ON, li.rate) for inv in c.inputs.invoices for li in inv.line_items
                 if inv.doc_type == DocType.INVOICE}
    assert (False, 28) in seen and (True, 40) in seen and (True, 28) not in seen


def test_credit_note_after_cutover_keeps_pre_cutover_rate():
    hits = 0
    for i in range(300):
        c = generate_case(3, "hard", i, periods=[(2025, 9)])
        for cn in c.inputs.invoices:
            if cn.doc_type == DocType.CREDIT_NOTE and cn.invoice_date >= ON:
                orig = next(x for x in c.inputs.invoices if x.invoice_no == cn.original_invoice_no
                            and x.supplier_gstin == cn.supplier_gstin)
                if orig.invoice_date < ON and orig.line_items[0].rate != cat.rate_on(PRODUCTS[orig.line_items[0].description], ON)[0]:
                    hits += 1
                    assert cn.line_items[0].rate == orig.line_items[0].rate
    assert hits > 0


def test_pre_cutover_invoices_keep_old_rate_when_recon_and_2b_are_after():
    found = 0
    for i in range(40):
        c = generate_case(8, "hard", i, periods=[(2025, 8)])
        _check_case_rates(c)
        if c.inputs.as_of_date >= ON:
            found += 1
            assert all(li.rate != 40 for inv in c.inputs.invoices for li in inv.line_items)
            assert any(g.data.gendt.endswith("2025") for g in c.inputs.gstr2b)
    assert found > 0


def test_post_cutover_period_has_no_old_slabs():
    for i in range(20):
        c = generate_case(9, "hard", i, periods=[(2026, 3)])
        assert all(li.rate in (0, 5, 18, 40) and li.cess == 0 for inv in c.inputs.invoices for li in inv.line_items)


def test_default_periods_span_april_2024_to_september_2026():
    assert DEFAULT_PERIODS[0] == (2024, 4) and DEFAULT_PERIODS[-1] == (2026, 9) and len(DEFAULT_PERIODS) == 30
    assert period_range((2025, 11), (2026, 2)) == [(2025, 11), (2025, 12), (2026, 1), (2026, 2)]
    with pytest.raises(ValueError):
        period_range((2026, 2), (2025, 11))


def test_fy_label():
    assert fy_label(date(2025, 3, 31)) == "24-25" and fy_label(date(2025, 4, 1)) == "25-26"


def test_cli_period_range(tmp_path):
    from gst_recon.schema import Case
    main(["generate", "--n-cases", "4", "--seed", "1", "--difficulty", "easy", "--out", str(tmp_path),
          "--period-from", "2025-10", "--period-to", "2025-12"])
    for f in tmp_path.glob("*.json"):
        assert Case.model_validate_json(f.read_text()).inputs.period in ("102025", "112025", "122025")


def test_cli_rejects_bad_period(tmp_path):
    with pytest.raises(SystemExit):
        main(["generate", "--n-cases", "1", "--out", str(tmp_path), "--period-from", "2025-13"])
