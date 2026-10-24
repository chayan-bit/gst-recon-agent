"""Code half alone: true per-document records in -> the target out (score identical to the target's own)."""

from __future__ import annotations

import pytest

from gst_recon.hybrid.inputs import parse_prompt
from gst_recon.hybrid.reconcile import reconcile_prompt
from gst_recon.hybrid.sft import truth_records
from gst_recon.rewards import expand, score


def test_parsers_reproduce_register_2b_and_bank(ex):
    prompt, _, case = ex
    p = parse_prompt(prompt)
    assert p.register == case.inputs.purchase_register
    assert p.gstr2b == case.inputs.gstr2b
    assert [t.model_dump(exclude={"narration"}) for t in p.bank] == [t.model_dump(exclude={"narration"}) for t in case.inputs.bank_statement]
    assert (p.header.profile, p.header.period, p.header.as_of) == (case.inputs.buyer_profile, case.inputs.period, case.inputs.as_of_date)
    assert [d.doc_id for d in p.docs] == [i.doc_id for i in case.inputs.invoices]


def test_truth_records_reproduce_target(ex):
    prompt, target, case = ex
    out, trace = reconcile_prompt(prompt, truth_records(target, case))
    assert out.model_dump(mode="json") == expand(target)
    assert score(out, target)["composite"] == pytest.approx(1.0)
    assert set(trace["decisions"]) == {i.doc_id for i in case.inputs.invoices}


def test_missing_record_drops_only_that_document(ex):
    prompt, target, case = ex
    recs = truth_records(target, case)
    gone = sorted(recs)[0]
    out, trace = reconcile_prompt(prompt, {k: v for k, v in recs.items() if k != gone})
    assert trace["missing_records"] == [gone]
    assert gone not in {m.doc_id for m in out.matches} and len(out.itc) == len(recs) - 1


def test_ocr_typos_in_invoice_no_and_gstin_still_link(ex):
    prompt, target, case = ex
    recs = truth_records(target, case)
    good, _ = reconcile_prompt(prompt, recs)
    doc = sorted(recs)[-1]
    r = recs[doc]
    g = r.supplier_gstin
    typo = r.model_copy(update={"invoice_no": r.invoice_no[:-1] + ("X" if r.invoice_no[-1] != "X" else "Y"),
                                "supplier_gstin": g[:5] + ("0" if g[5] != "0" else "1") + g[6:]})
    out, _ = reconcile_prompt(prompt, {**recs, doc: typo})
    links = lambda o: {m.doc_id: (m.register_vouchers, m.gstr2b_doc_no, m.payment_refs) for m in o.matches}  # noqa: E731
    assert links(out)[doc] == links(good)[doc]


def test_repair_fixes_all_heads_filled_and_keeps_true_records(ex):
    from gst_recon.hybrid.repair import repair

    prompt, target, case = ex
    recs = truth_records(target, case)
    assert all(repair(r) == (r, []) for r in recs.values())
    doc = next(d for d, r in recs.items() if not r.reverse_charge and any(li.cgst for li in r.line_items))
    r = recs[doc]
    broken = r.model_copy(update={"line_items": [li.model_copy(update={"igst": li.cgst, "sgst": li.cgst}) for li in r.line_items],
                                  "igst": r.cgst, "total": 1.0})
    fixed, notes = repair(broken)
    assert notes and fixed == r


def test_repair_never_mints_tax_from_a_misread_rate(ex):
    from gst_recon.hybrid.repair import repair

    prompt, target, case = ex
    recs = truth_records(target, case)
    doc = next(d for d, r in recs.items() if r.line_items and r.taxable_value and len({li.rate for li in r.line_items}) == 1)
    r = recs[doc]
    misread = r.model_copy(update={"line_items": [li.model_copy(update={"rate": 137573.6, "cgst": 9e6, "sgst": 9e6, "igst": 0.0})
                                                  for li in r.line_items]})
    fixed, notes = repair(misread)
    assert notes and fixed == r  # the header's standard rate replaces the amount read into the rate cell
    unknown = misread.model_copy(update={"cgst": 1.0, "sgst": 1.0, "igst": 0.0})
    kept, notes = repair(unknown)
    assert all(li.rate == 137573.6 and li.cgst == 9e6 for li in kept.line_items)  # no standard rate fits: kept as read
