from datetime import date

from gst_recon.schema import DocType, ItcCategory as C, MatchFlag as F, ReasonCode as R
from gst_recon.sim.rules import Link, reconcile
from tests.builders import (
    PERIOD, SUP_LOCAL, SUP_LOCAL_ALT, SUP_OTHER, inputs, invoice, line, pay, reg_row, twob,
)

LATE = date(2025, 1, 31)  # > 180 days after June 2024 invoices


def heads(obj):
    return (obj.igst, obj.cgst, obj.sgst, obj.cess)


def run(inv, register=None, gstr2b=None, bank=(), as_of=date(2024, 7, 15), link=None, extra=()):
    register = [reg_row(inv, "PUR/1")] if register is None else register
    gstr2b = [twob(PERIOD, [(inv, inv.supplier_gstin, 1.0)])] if gstr2b is None else gstr2b
    link = link or Link(("PUR/1",), (PERIOD, inv.supplier_gstin, inv.invoice_no), tuple(t.ref_no for t in bank))
    out = reconcile(inputs([inv, *extra], register, gstr2b, bank, as_of), {inv.doc_id: link})
    return out.matches[0], out.itc[0], out


def test_clean_intra_state_invoice_fully_eligible():
    inv = invoice("D01", [line(10000, 18)])
    m, d, _ = run(inv)
    assert m.flags == []
    assert heads(d.eligible) == (0, 900, 900, 0) and d.reasons == [R.ELIGIBLE]
    assert heads(d.blocked) == heads(d.deferred) == (0, 0, 0, 0)


def test_inter_state_igst_eligible():
    inv = invoice("D01", [line(10000, 12, intra=False)], gstin=SUP_OTHER)
    _, d, _ = run(inv)
    assert heads(d.eligible) == (1200, 0, 0, 0)


def test_motor_vehicle_blocked_including_cess():
    inv = invoice("D01", [line(1_500_000, 28, cess_rate=22, category=C.MOTOR_VEHICLE, hsn="8703")])
    _, d, _ = run(inv)
    assert heads(d.blocked) == (0, 210000, 210000, 330000)
    assert heads(d.eligible) == (0, 0, 0, 0) and d.reasons == [R.BLOCKED_MOTOR_VEHICLE]


def test_mixed_invoice_blocks_only_the_blocked_line():
    inv = invoice("D01", [line(10000, 5, category=C.FOOD_BEVERAGE), line(2000, 18)])
    _, d, _ = run(inv)
    assert heads(d.blocked) == (0, 250, 250, 0)
    assert heads(d.eligible) == (0, 180, 180, 0)
    assert d.reasons == [R.ELIGIBLE, R.BLOCKED_FOOD_BEVERAGE]


def test_each_blocked_category_has_its_reason():
    expected = {C.CLUB_MEMBERSHIP: R.BLOCKED_CLUB_MEMBERSHIP, C.WORKS_CONTRACT: R.BLOCKED_WORKS_CONTRACT,
                C.PERSONAL_USE: R.BLOCKED_PERSONAL_USE, C.GIFT: R.BLOCKED_GIFT}
    for cat_, reason in expected.items():
        _, d, _ = run(invoice("D01", [line(1000, 18, category=cat_)]))
        assert d.reasons == [reason] and d.blocked.cgst == 90


def test_missing_in_2b_defers_everything():
    inv = invoice("D01", [line(10000, 18)])
    m, d, _ = run(inv, gstr2b=[twob(PERIOD, [])], link=Link(("PUR/1",), None, ()))
    assert m.flags == [F.MISSING_IN_2B] and m.gstr2b_period == ""
    assert heads(d.deferred) == (0, 900, 900, 0) and d.reasons == [R.DEFERRED_NOT_IN_2B]


def test_blocked_invoice_missing_in_2b_stays_blocked_not_deferred():
    inv = invoice("D01", [line(10000, 18, category=C.GIFT)])
    _, d, _ = run(inv, gstr2b=[twob(PERIOD, [])], link=Link(("PUR/1",), None, ()))
    assert heads(d.blocked) == (0, 900, 900, 0) and heads(d.deferred) == (0, 0, 0, 0)
    assert d.reasons == [R.BLOCKED_GIFT]


def test_period_mismatch_defers():
    inv = invoice("D01", [line(10000, 18)])
    later = "072024"
    m, d, _ = run(inv, gstr2b=[twob(PERIOD, []), twob(later, [(inv, SUP_LOCAL, 1.0)])],
                  link=Link(("PUR/1",), (later, SUP_LOCAL, "INV-1"), ()))
    assert m.flags == [F.PERIOD_MISMATCH] and m.gstr2b_period == later
    assert d.reasons == [R.DEFERRED_PERIOD_MISMATCH] and d.deferred.cgst == 900


def test_2b_under_other_gstin_flags_and_defers():
    inv = invoice("D01", [line(10000, 18)])
    m, d, _ = run(inv, gstr2b=[twob(PERIOD, [(inv, SUP_LOCAL_ALT, 1.0)])],
                  link=Link(("PUR/1",), (PERIOD, SUP_LOCAL_ALT, "INV-1"), ()))
    assert m.flags == [F.GSTIN_MISMATCH] and m.gstr2b_ctin == SUP_LOCAL_ALT
    assert d.reasons == [R.DEFERRED_GSTIN_MISMATCH] and d.eligible.cgst == 0


def test_2b_lower_amount_caps_credit_and_defers_shortfall():
    inv = invoice("D01", [line(10000, 18)])
    m, d, _ = run(inv, gstr2b=[twob(PERIOD, [(inv, SUP_LOCAL, 0.9)])])
    assert m.flags == [F.AMOUNT_MISMATCH]
    assert heads(d.eligible) == (0, 810, 810, 0) and heads(d.deferred) == (0, 90, 90, 0)
    assert d.reasons == [R.ELIGIBLE, R.DEFERRED_AMOUNT_MISMATCH]


def test_2b_higher_amount_still_capped_at_invoice():
    inv = invoice("D01", [line(10000, 18)])
    m, d, _ = run(inv, gstr2b=[twob(PERIOD, [(inv, SUP_LOCAL, 1.25)])])
    assert m.flags == [F.AMOUNT_MISMATCH]
    assert heads(d.eligible) == (0, 900, 900, 0) and d.reasons == [R.ELIGIBLE]


def test_rcm_eligible_even_when_missing_in_2b_and_unpaid():
    inv = invoice("D01", [line(20000, 5, hsn="996791")], rcm=True)
    assert inv.total == 20000  # tax not payable to supplier
    m, d, _ = run(inv, gstr2b=[twob(PERIOD, [])], as_of=LATE, link=Link(("PUR/1",), None, ()))
    assert m.flags == [F.MISSING_IN_2B]  # no unpaid_180d for RCM (r.37(1))
    assert heads(d.eligible) == (0, 500, 500, 0) and d.reasons == [R.RCM_ELIGIBLE]


def test_unpaid_after_180_days_defers_proportionately():
    inv = invoice("D01", [line(10000, 18)])  # total 11800
    m, d, _ = run(inv, bank=[pay("UTR1", 5900)], as_of=LATE)
    assert m.flags == [F.UNPAID_180D] and m.payment_refs == ["UTR1"]
    assert heads(d.eligible) == (0, 450, 450, 0) and heads(d.deferred) == (0, 450, 450, 0)
    assert d.reasons == [R.ELIGIBLE, R.DEFERRED_UNPAID_180D]


def test_fully_unpaid_after_180_days_defers_all():
    inv = invoice("D01", [line(10000, 18)])
    _, d, _ = run(inv, as_of=LATE)
    assert d.eligible.cgst == 0 and d.deferred.cgst == 900 and d.reasons == [R.DEFERRED_UNPAID_180D]


def test_unpaid_within_180_days_is_fine():
    inv = invoice("D01", [line(10000, 18)])
    m, d, _ = run(inv, as_of=date(2024, 12, 7))  # day 180 exactly
    assert m.flags == [] and d.eligible.cgst == 900


def test_credit_note_counts_towards_payment_for_180_days():
    inv = invoice("D01", [line(10000, 18)])
    cn = invoice("D02", [line(1000, 18)], no="CN-1", doc_type=DocType.CREDIT_NOTE, original="INV-1")
    m, d, _ = run(inv, bank=[pay("UTR1", 11800 - 1180)], as_of=LATE, extra=[cn])
    assert m.flags == [] and d.eligible.cgst == 900


def test_credit_note_reverses_credit():
    inv = invoice("D01", [line(10000, 18)])
    cn = invoice("D02", [line(1000, 18)], no="CN-1", doc_type=DocType.CREDIT_NOTE, original="INV-1")
    out = reconcile(inputs([inv, cn], [reg_row(inv, "PUR/1"), reg_row(cn, "DN/1", voucher_type="Debit Note")],
                           [twob(PERIOD, [(inv, SUP_LOCAL, 1.0), (cn, SUP_LOCAL, 1.0)])]),
                    {"D01": Link(("PUR/1",), (PERIOD, SUP_LOCAL, "INV-1")),
                     "D02": Link(("DN/1",), (PERIOD, SUP_LOCAL, "CN-1"))})
    d = out.itc[1]
    assert heads(d.eligible) == (0, -90, -90, 0) and d.reasons == [R.CREDIT_NOTE_REVERSAL]
    assert out.matches[1].flags == []
    assert heads(out.itc_totals.eligible) == (0, 810, 810, 0)


def test_duplicate_register_entry_flagged_credit_counted_once():
    inv = invoice("D01", [line(10000, 18)])
    m, d, _ = run(inv, register=[reg_row(inv, "PUR/1"), reg_row(inv, "PUR/2")],
                  link=Link(("PUR/1", "PUR/2"), (PERIOD, SUP_LOCAL, "INV-1")))
    assert m.flags == [F.DUPLICATE] and m.register_vouchers == ["PUR/1", "PUR/2"]
    assert d.eligible.cgst == 900


def test_register_typos_flag_but_do_not_change_credit():
    inv = invoice("D01", [line(10000, 18)])
    m, d, _ = run(inv, register=[reg_row(inv, "PUR/1", party_gstin=SUP_LOCAL[:5] + "X" + SUP_LOCAL[6:],
                                         taxable_value=1000.0, total=2800.0)])
    assert m.flags == [F.GSTIN_MISMATCH, F.AMOUNT_MISMATCH] and d.eligible.cgst == 900


def test_rounding_differences_within_one_rupee_are_ignored():
    inv = invoice("D01", [line(10000, 18)])
    m, _, _ = run(inv, register=[reg_row(inv, "PUR/1", total=inv.total + 0.6)])
    assert m.flags == []


def test_nil_rated_invoice_reason_is_eligible_with_zero_amounts():
    _, d, _ = run(invoice("D01", [line(5000, 0, hsn="4901")]))
    assert d.reasons == [R.ELIGIBLE] and heads(d.eligible) == (0, 0, 0, 0)


def test_extraction_mirrors_invoice():
    inv = invoice("D01", [line(10000, 18)])
    _, _, out = run(inv)
    e = out.extractions[0]
    assert e.invoice_date == "2024-06-10" and e.original_invoice_no == "" and e.total == 11800
