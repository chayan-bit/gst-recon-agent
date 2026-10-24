import copy
import json

import pytest

from gst_recon.rewards import (
    arithmetic_consistency, extraction_f1, itc_scores, match_accuracy, parse_output, schema_valid, score,
)
from gst_recon.sim.world import generate_case


@pytest.fixture(scope="module")
def truth():
    return generate_case(5, "hard", 0).expected.model_dump(mode="json")


def test_perfect_output_scores_one(truth):
    s = score(json.dumps(truth), truth)
    assert all(v == pytest.approx(1.0) for v in s.values()), s


GARBAGE = [None, "", "   ", "not json", "{", "[]", "[1,2]", 42, 3.5, b"bytes", ["x"], {},
           {"extractions": "x", "matches": 5, "itc": None, "itc_totals": []},
           {"extractions": [1, "a", None, {"line_items": "q"}], "itc": [{"doc_id": None, "eligible": 3}]},
           {"extractions": [{"doc_id": "D01", "total": "NaN", "line_items": [{"rate": "abc"}]}]},
           {"itc_totals": {"eligible": {"igst": float("nan")}}}, "```json\n{oops\n```"]


@pytest.mark.parametrize("garbage", GARBAGE)
def test_garbage_never_raises_and_scores_low(garbage, truth):
    s = score(garbage, truth)
    assert set(s) >= {"composite", "schema_valid"}
    assert s["schema_valid"] == 0.0 and s["composite"] < 0.15


def test_fenced_json_is_parsed(truth):
    assert parse_output("```json\n" + json.dumps(truth) + "\n```") == truth
    assert parse_output("Here you go: " + json.dumps(truth) + " done") == truth


def test_extraction_normalises_dates_gstin_case_amount_strings(truth):
    pred = copy.deepcopy(truth)
    for e in pred["extractions"]:
        y, m, d = e["invoice_date"].split("-")
        e["invoice_date"] = f"{d}/{m}/{y}"
        e["supplier_gstin"] = e["supplier_gstin"].lower()
        e["total"] = f"{e['total']:,.2f}"
        e["place_of_supply"] = str(int(e["place_of_supply"]))
    assert extraction_f1(pred, truth) == pytest.approx(1.0)
    assert schema_valid(pred) == 0.0  # total as string breaks the schema


def test_missing_document_lowers_f1_and_match(truth):
    pred = copy.deepcopy(truth)
    pred["extractions"] = pred["extractions"][1:]
    pred["matches"] = pred["matches"][1:]
    assert 0.8 < extraction_f1(pred, truth) < 1.0
    assert match_accuracy(pred, truth) == pytest.approx(1 - 1 / len(truth["matches"]))


def test_wrong_field_lowers_f1(truth):
    pred = copy.deepcopy(truth)
    pred["extractions"][0]["invoice_no"] = "WRONG"
    assert extraction_f1(pred, truth) < 1.0


def test_spurious_document_lowers_scores(truth):
    pred = copy.deepcopy(truth)
    extra = copy.deepcopy(pred["matches"][0]) | {"doc_id": "D99"}
    pred["matches"].append(extra)
    assert match_accuracy(pred, truth) < 1.0


def test_wrong_flag_costs_quarter_of_that_doc(truth):
    pred = copy.deepcopy(truth)
    pred["matches"][0]["flags"] = ["duplicate"] if pred["matches"][0]["flags"] != ["duplicate"] else []
    n = len(truth["matches"])
    assert match_accuracy(pred, truth) == pytest.approx(1 - 0.25 / n)


def test_itc_tolerance_one_rupee(truth):
    pred = copy.deepcopy(truth)
    pred["itc"][0]["eligible"]["cgst"] += 0.99
    assert itc_scores(pred, truth)["itc_invoice"] == 1.0
    pred["itc"][0]["eligible"]["cgst"] += 1.0
    assert itc_scores(pred, truth)["itc_invoice"] < 1.0


def test_itc_total_checked_from_model_totals(truth):
    pred = copy.deepcopy(truth)
    pred["itc_totals"]["deferred"]["igst"] += 5
    s = itc_scores(pred, truth)
    assert s["itc_total"] == 0.0 and s["itc_invoice"] == 1.0


def test_reason_order_does_not_matter(truth):
    pred = copy.deepcopy(truth)
    for d in pred["itc"]:
        d["reasons"] = list(reversed(d["reasons"]))
    assert itc_scores(pred, truth)["itc_reasons"] == 1.0


def test_arithmetic_flags_inconsistent_output(truth):
    pred = copy.deepcopy(truth)
    assert arithmetic_consistency(pred) == pytest.approx(1.0)
    pred["extractions"][0]["total"] += 100
    pred["extractions"][0]["line_items"][0]["cgst"] += 50
    pred["itc_totals"]["eligible"]["cgst"] += 50
    assert arithmetic_consistency(pred) < 1.0


def test_arithmetic_rejects_igst_with_cgst_on_one_line():
    pred = {"extractions": [{"doc_id": "D01", "doc_type": "invoice", "reverse_charge": False,
                             "taxable_value": 100, "igst": 18, "cgst": 9, "sgst": 9, "cess": 0, "total": 136,
                             "line_items": [{"taxable_value": 100, "rate": 18, "igst": 18, "cgst": 9, "sgst": 9, "cess": 0}]}]}
    assert arithmetic_consistency(pred) < 1.0


def test_composite_is_weighted_and_bounded(truth):
    pred = copy.deepcopy(truth)
    pred["itc"] = []
    s = score(pred, truth)
    assert 0 < s["composite"] < 1
    assert s["itc_invoice"] == 0 and s["schema_valid"] == 1


def test_score_is_fast(truth):
    import time
    raw = json.dumps(truth)
    t = time.perf_counter()
    for _ in range(50):
        score(raw, truth)
    assert (time.perf_counter() - t) / 50 < 0.02
