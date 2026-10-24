import copy
import json

import pytest

from gst_recon.rewards import (
    arithmetic_consistency,
    extraction_f1,
    itc_scores,
    match_accuracy,
    parse_output,
    schema_valid,
    score,
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


# ---------------------------------------------------------------- GRPO variant


def _all_clean(truth: dict) -> dict:
    """Trivial baseline: true extraction and links, no flags, everything eligible."""
    out = copy.deepcopy(truth)
    for m in out["matches"]:
        m["flags"] = []
    for row in out["itc"]:
        for h in ("igst", "cgst", "sgst", "cess"):
            row["eligible"][h] = round(sum(row[b][h] for b in ("eligible", "blocked", "deferred")), 2)
            row["blocked"][h] = row["deferred"][h] = 0.0
        row["reasons"] = ["CREDIT_NOTE_REVERSAL"] if "CREDIT_NOTE_REVERSAL" in row["reasons"] else ["ELIGIBLE"]
    return out


def test_grpo_is_one_for_truth_and_gated_on_schema(truth):
    assert score(json.dumps(truth), truth)["grpo"] == pytest.approx(1.0)
    broken = copy.deepcopy(truth)
    broken["itc_totals"] = "n/a"  # parseable JSON, schema-invalid
    s = score(broken, truth)
    assert s["schema_valid"] == 0.0 and s["grpo"] == 0.0 and s["composite"] > 0.5


def test_grpo_gives_trivial_all_clean_little_credit(truth):
    s = score(_all_clean(truth), truth)
    assert s["composite"] > 0.7 and s["grpo"] < 0.4, s


def test_grpo_keeps_partial_credit(truth):
    pred = copy.deepcopy(truth)
    flagged = next(m for m in pred["matches"] if m["flags"])
    flagged["flags"] = []
    s = score(pred, truth)
    assert 0.8 < s["grpo"] < 1.0 and 0 < s["flag_f1"] < 1


def test_eval_metrics_components():
    from gst_recon.rewards import eval_metrics
    case = generate_case(5, "hard", 0)
    perfect = eval_metrics(case.expected.model_dump(mode="json"), case)
    assert perfect["itc_abs_err_rs"] == 0 and perfect["context_doc_acc"] in (1.0, None) and perfect["grpo"] == 1.0
    garbage = eval_metrics("not json", case)
    assert garbage["field_f1"] == 0 and garbage["grpo"] == 0 and garbage["itc_abs_err_rs"] > 0


def test_compact_output_scores_identically_to_full(truth):
    from gst_recon.rewards import compact, expand

    small = compact(truth)
    assert expand(small) == truth and len(json.dumps(small)) < 0.85 * len(json.dumps(truth))
    full, comp = score(json.dumps(truth), truth), score(json.dumps(small), truth)
    assert comp == full and score(json.dumps(small), small) == full  # compact prediction and/or compact reference
    pred = copy.deepcopy(truth)
    next(m for m in pred["matches"] if m["flags"])["flags"] = []
    assert score(compact(pred), truth) == score(pred, truth)  # partial credit unchanged too
    assert schema_valid({"extractions": [], "matches": []}) == 0.0  # a missing top-level key stays invalid
