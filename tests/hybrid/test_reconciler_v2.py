"""Reconciler v2 rules: each one a GST-practice rule, checked on the committed examples' true records."""

from __future__ import annotations

from gst_recon.hybrid.linker import lev
from gst_recon.hybrid.reconcile import reconcile_prompt
from gst_recon.hybrid.repair import repair
from gst_recon.hybrid.sft import truth_records
from gst_recon.schema import ItcCategory, LinePurpose, MatchFlag
from gst_recon.sim.gstin import is_valid_gstin, make_gstin


def _by_doc(out):
    return {m.doc_id: m for m in out.matches}, {t.doc_id: t for t in out.itc}


def _in_2b(out):
    matches, _ = _by_doc(out)
    return sorted(d for d, m in matches.items() if m.gstr2b_doc_no and MatchFlag.GSTIN_MISMATCH not in m.flags)


def test_invented_invoice_no_still_links_to_2b_on_gstin_date_and_amounts(ex):
    prompt, target, case = ex
    recs = truth_records(target, case)
    good, _ = reconcile_prompt(prompt, recs)
    doc = _in_2b(good)[0]
    out, _ = reconcile_prompt(prompt, {**recs, doc: recs[doc].model_copy(update={"invoice_no": "00444"})})
    assert _by_doc(out)[0][doc].gstr2b_doc_no == _by_doc(good)[0][doc].gstr2b_doc_no
    assert _by_doc(out)[1][doc] == _by_doc(good)[1][doc]


def test_gstin_failing_the_check_digit_is_read_from_the_linked_entry(ex):
    prompt, target, case = ex
    recs = truth_records(target, case)
    good, _ = reconcile_prompt(prompt, recs)
    doc = _in_2b(good)[0]
    g = recs[doc].supplier_gstin
    bad = g[:7] + ("8" if g[7] != "8" else "3") + g[8:]
    assert not is_valid_gstin(bad)
    out, trace = reconcile_prompt(prompt, {**recs, doc: recs[doc].model_copy(update={"supplier_gstin": bad})})
    assert doc in trace["gstin_fixes"]
    assert _by_doc(out)[0][doc] == _by_doc(good)[0][doc] and _by_doc(out)[1][doc] == _by_doc(good)[1][doc]
    assert next(e for e in out.extractions if e.doc_id == doc).supplier_gstin == g


def test_a_valid_gstin_of_another_registration_still_flags_gstin_mismatch(ex):
    prompt, target, case = ex
    recs = truth_records(target, case)
    good, _ = reconcile_prompt(prompt, recs)
    doc = _in_2b(good)[0]
    g = recs[doc].supplier_gstin
    other = make_gstin("27" if g[:2] != "27" else "29", g[2:12], g[12])
    out, trace = reconcile_prompt(prompt, {**recs, doc: recs[doc].model_copy(update={"supplier_gstin": other})})
    assert doc not in trace["gstin_fixes"]
    m = _by_doc(out)[0][doc]
    assert not m.gstr2b_doc_no or MatchFlag.GSTIN_MISMATCH in m.flags




def test_a_misread_state_code_alone_is_read_from_the_linked_entry(ex):
    prompt, target, case = ex
    recs = truth_records(target, case)
    good, _ = reconcile_prompt(prompt, recs)
    def misread(g):
        return g[0] + str((int(g[1]) + 1) % 10) + g[2:]

    doc = next(d for d in _in_2b(good) if not is_valid_gstin(misread(recs[d].supplier_gstin)))
    g = recs[doc].supplier_gstin
    bad = misread(g)
    out, trace = reconcile_prompt(prompt, {**recs, doc: recs[doc].model_copy(update={"supplier_gstin": bad})})
    assert doc in trace["gstin_fixes"]
    assert next(e for e in out.extractions if e.doc_id == doc).supplier_gstin == g

def test_a_misread_gstin_is_never_fixed_into_another_state_registration(ex):
    prompt, target, case = ex
    recs = truth_records(target, case)
    good, _ = reconcile_prompt(prompt, recs)
    doc = _in_2b(good)[0]
    g = recs[doc].supplier_gstin
    other = make_gstin(g[0] + ("4" if g[1] != "4" else "7"), g[2:12], g[12])  # same PAN, another state
    bad = other[:14] + next(c for c in "ZYX" if c not in (g[14], other[14]))
    assert not is_valid_gstin(bad) and lev(bad, g) <= 2
    out, trace = reconcile_prompt(prompt, {**recs, doc: recs[doc].model_copy(update={"supplier_gstin": bad})})
    assert doc not in trace["gstin_fixes"]
    assert next(e for e in out.extractions if e.doc_id == doc).supplier_gstin == bad

def test_goods_vehicle_hsn_8704_is_never_blocked_as_a_motor_vehicle(ex):
    prompt, target, case = ex
    recs = truth_records(target, case)
    doc = next(d for d, r in recs.items() if r.line_items and r.line_items[0].itc_category == ItcCategory.NORMAL
               and r.line_items[0].purpose == LinePurpose.BUSINESS)
    r = recs[doc]
    good, _ = reconcile_prompt(prompt, recs)
    truck = r.line_items[0].model_copy(update={"hsn": "8704", "itc_category": ItcCategory.MOTOR_VEHICLE})
    car = truck.model_copy(update={"hsn": "8703"})
    as_truck, trace = reconcile_prompt(prompt, {**recs, doc: r.model_copy(update={"line_items": [truck, *r.line_items[1:]]})})
    as_car, _ = reconcile_prompt(prompt, {**recs, doc: r.model_copy(update={"line_items": [car, *r.line_items[1:]]})})
    assert _by_doc(as_truck)[1][doc] == _by_doc(good)[1][doc] and any("goods vehicle" in n for n in trace["repairs"][doc])
    assert _by_doc(as_car)[1][doc] != _by_doc(good)[1][doc]  # a car (8703) is still blocked


def test_single_line_takes_the_self_consistent_header_over_a_misread_line(ex):
    prompt, target, case = ex
    recs = truth_records(target, case)
    r = next(r for r in recs.values() if len(r.line_items) == 1 and r.taxable_value > 100 and r.line_items[0].rate)
    li = r.line_items[0]
    k = 0.5
    wrong = li.model_copy(update={"taxable_value": round(li.taxable_value * k, 2),
                                  **{h: round(getattr(li, h) * k, 2) for h in ("igst", "cgst", "sgst", "cess")}})
    fixed, notes = repair(r.model_copy(update={"line_items": [wrong]}))
    assert fixed == r and notes


def test_invoice_no_and_date_not_shown_by_the_document_are_filled_from_the_one_matching_book_entry(ex):
    prompt, target, case = ex
    recs = truth_records(target, case)
    good, _ = reconcile_prompt(prompt, recs)
    doc = _in_2b(good)[0]
    r = recs[doc]
    invented = r.model_copy(update={"invoice_no": "ZQ-99817", "invoice_date": "2019-01-07"})
    out, trace = reconcile_prompt(prompt, {**recs, doc: invented})
    assert doc in trace["fills"]
    assert _by_doc(out)[0][doc] == _by_doc(good)[0][doc] and _by_doc(out)[1][doc] == _by_doc(good)[1][doc]
    ex_out = next(e for e in out.extractions if e.doc_id == doc)
    assert (ex_out.invoice_no, ex_out.invoice_date) == (r.invoice_no, r.invoice_date)


def test_a_value_the_document_shows_is_never_replaced(ex):
    prompt, target, case = ex
    out, trace = reconcile_prompt(prompt, truth_records(target, case))
    assert trace["fills"] == {}

