"""s.17(5) depends on who buys and why, not on what the item is called."""

import pytest

from gst_recon.schema import BusinessProfile as P
from gst_recon.schema import BuyerProfile, ItcCategory as C, LinePurpose as U, ReasonCode as R
from gst_recon.sim import lexicon as lex
from gst_recon.sim.rules import Link, line_block_reason, reconcile
from gst_recon.sim.world import generate_case
from tests.builders import PERIOD, SUP_LOCAL, inputs, invoice, line, reg_row, twob


def prof(kind, employees=100):
    return BuyerProfile(profile=kind, description="x", employees=employees)


def mk(cat, purpose):
    return line(100000, 18, category=cat).model_copy(update={"purpose": purpose})


@pytest.mark.parametrize("cat,purpose,kind,employees,expected", [
    # s.17(5)(a): the same SUV
    (C.MOTOR_VEHICLE, U.BUSINESS, P.MANUFACTURER, 100, R.BLOCKED_MOTOR_VEHICLE),
    (C.MOTOR_VEHICLE, U.FURTHER_SUPPLY, P.CAR_DEALER, 20, None),              # (A) further supply
    (C.MOTOR_VEHICLE, U.PASSENGER_TRANSPORT, P.PASSENGER_TRANSPORT, 20, None),  # (B)
    (C.MOTOR_VEHICLE, U.DRIVING_TRAINING, P.DRIVING_SCHOOL, 10, None),        # (C)
    # s.17(5)(b)(i): the same food
    (C.FOOD_BEVERAGE, U.BUSINESS, P.IT_SERVICES, 100, R.BLOCKED_FOOD_BEVERAGE),
    (C.FOOD_BEVERAGE, U.STAFF_WELFARE, P.MANUFACTURER, 600, R.BLOCKED_FOOD_BEVERAGE),
    (C.FOOD_BEVERAGE, U.FURTHER_SUPPLY, P.HOTEL, 80, None),                   # composite / same category
    (C.FOOD_BEVERAGE, U.FURTHER_SUPPLY, P.CATERER, 30, None),
    (C.FOOD_BEVERAGE, U.FACTORY_CANTEEN, P.MANUFACTURER, 600, None),          # obliged by law (> 250)
    (C.FOOD_BEVERAGE, U.FACTORY_CANTEEN, P.MANUFACTURER, 250, R.BLOCKED_FOOD_BEVERAGE),  # not obliged
    (C.FOOD_BEVERAGE, U.FACTORY_CANTEEN, P.IT_SERVICES, 900, R.BLOCKED_FOOD_BEVERAGE),   # not a factory
    # s.17(5)(b)(ii): no same-category proviso
    (C.CLUB_MEMBERSHIP, U.BUSINESS, P.GYM_OPERATOR, 20, R.BLOCKED_CLUB_MEMBERSHIP),
    (C.CLUB_MEMBERSHIP, U.STAFF_WELFARE, P.IT_SERVICES, 20, R.BLOCKED_CLUB_MEMBERSHIP),
    # s.17(5)(c)
    (C.WORKS_CONTRACT, U.BUSINESS, P.HOTEL, 20, R.BLOCKED_WORKS_CONTRACT),
    (C.WORKS_CONTRACT, U.FURTHER_SUPPLY, P.CONSTRUCTION_CONTRACTOR, 20, None),
    # s.17(5)(d), (g), (h) on ordinary goods
    (C.NORMAL, U.OWN_CONSTRUCTION, P.MANUFACTURER, 100, R.BLOCKED_WORKS_CONTRACT),
    (C.NORMAL, U.BUSINESS, P.CONSTRUCTION_CONTRACTOR, 100, None),
    (C.NORMAL, U.PERSONAL, P.IT_SERVICES, 100, R.BLOCKED_PERSONAL_USE),
    (C.NORMAL, U.BUSINESS, P.HOTEL, 100, None),
    (C.NORMAL, U.GIFT, P.MANUFACTURER, 100, R.BLOCKED_GIFT),
    (C.NORMAL, U.FURTHER_SUPPLY, P.TRADING_COMPANY, 100, None),
])
def test_line_block_reason_by_context(cat, purpose, kind, employees, expected):
    assert line_block_reason(mk(cat, purpose), prof(kind, employees)) == expected


def test_same_invoice_different_profiles_end_to_end():
    def run(inv, p):
        inp = inputs([inv], [reg_row(inv, "PUR/1")], [twob(PERIOD, [(inv, SUP_LOCAL, 1.0)])]).model_copy(
            update={"buyer_profile": p})
        return reconcile(inp, {"D01": Link(("PUR/1",), (PERIOD, SUP_LOCAL, "INV-1"))}).itc[0]
    food = invoice("D01", [mk(C.FOOD_BEVERAGE, U.FURTHER_SUPPLY)])
    assert run(food, prof(P.HOTEL)).reasons == [R.ELIGIBLE]
    canteen = invoice("D01", [mk(C.FOOD_BEVERAGE, U.FACTORY_CANTEEN)])
    assert run(canteen, prof(P.MANUFACTURER, 300)).reasons == [R.ELIGIBLE]
    assert run(canteen, prof(P.MANUFACTURER, 200)).reasons == [R.BLOCKED_FOOD_BEVERAGE]


def _cases(split="train", n=120):
    return [generate_case(21, d, i, split=split) for d in ("easy", "medium", "hard") for i in range(n // 3)]


def test_purpose_is_always_visible_to_the_model():
    """Remark-only purposes always come with a matching remark; profile-implied
    purposes only occur for the profile that implies them."""
    implied = {U.PASSENGER_TRANSPORT: {P.PASSENGER_TRANSPORT}, U.DRIVING_TRAINING: {P.DRIVING_SCHOOL}}
    for split in ("train", "test_iid", "test_ood"):
        for c in _cases(split, 60):
            kind = c.inputs.buyer_profile.profile
            for inv in c.inputs.invoices:
                if inv.doc_type.value == "credit_note":
                    continue
                for li in inv.line_items:
                    if li.purpose in lex.REMARK_REQUIRED:
                        assert inv.remarks in lex.REMARKS[li.purpose], (inv.remarks, li.purpose)
                    if li.purpose in implied:
                        assert kind in implied[li.purpose]
                    if li.purpose == U.FURTHER_SUPPLY:
                        assert kind in {P.TRADING_COMPANY, P.CAR_DEALER, P.HOTEL, P.CATERER,
                                        P.CONSTRUCTION_CONTRACTOR}


def test_same_concept_gets_both_decisions_across_contexts():
    seen: dict[str, set[bool]] = {}
    for c in _cases("train", 240):
        for inv in c.inputs.invoices:
            for li in inv.line_items:
                blocked = line_block_reason(li, c.inputs.buyer_profile) is not None
                seen.setdefault(li.concept, set()).add(blocked)
    both = {k for k, v in seen.items() if v == {True, False}}
    # at least one concept per context-dependent family flips
    for fam_ids in (("small_car", "suv", "car_servicing"), ("tea", "biscuits", "coffee", "restaurant_meals",
                    "fruit_juice", "packaged_rice", "edible_oil", "sugar", "pulses_loose", "aerated_drinks"),
                    ("wc_building", "wc_interior", "wc_electrical"), ("cement", "tiles", "tmt_bars", "sanitaryware"),
                    ("led_tv", "refrigerator", "washing_machine", "water_heater", "mixer_grinder")):
        assert both & set(fam_ids), fam_ids


def test_neutral_remarks_appear_on_eligible_invoices():
    with_remark = [inv for c in _cases("train", 90) for inv in c.inputs.invoices
                   if inv.remarks in lex.NEUTRAL_REMARKS]
    assert len(with_remark) > 30
