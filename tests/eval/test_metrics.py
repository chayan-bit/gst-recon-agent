"""Per-invoice ITC overclaim and underclaim, in rupees."""

import json

import pytest

from gst_recon.eval.cases import EvalCase
from gst_recon.eval.metrics import case_metrics, itc_claim_gaps


def _row(doc: str, eligible: float) -> dict:
    return {"doc_id": doc, "eligible": {"igst": eligible, "cgst": 0, "sgst": 0, "cess": 0}}


def _gaps(pred: dict[str, float], truth: dict[str, float]) -> tuple[float, float]:
    return itc_claim_gaps({d: _row(d, v) for d, v in pred.items()}, {d: _row(d, v) for d, v in truth.items()})


def test_overclaim_and_underclaim_are_per_invoice_and_do_not_net():
    # invoice A claimed 300 too much, invoice B 200 too little: net error 100, but both gaps are real money
    assert _gaps({"A": 1300, "B": 800}, {"A": 1000, "B": 1000}) == (300.0, 200.0)


def test_exact_claim_has_no_gap():
    assert _gaps({"A": 500}, {"A": 500}) == (0.0, 0.0)


def test_invented_invoice_is_overclaim_and_dropped_invoice_is_underclaim():
    assert _gaps({"X": 700}, {"A": 400}) == (700.0, 400.0)


def test_heads_are_summed_within_an_invoice():
    p = {"A": {"doc_id": "A", "eligible": {"igst": 0, "cgst": 90, "sgst": 90, "cess": 0}}}
    t = {"A": {"doc_id": "A", "eligible": {"igst": 180, "cgst": 0, "sgst": 0, "cess": 0}}}
    assert itc_claim_gaps(p, t) == (0.0, 0.0)


def test_unparseable_output_claims_nothing(world):
    case = EvalCase("c", "", world["targets"][next(iter(world["targets"]))], {"split": "test_iid", "difficulty": "easy"}, None)
    m = case_metrics("not json", case)
    assert m["itc_overclaim_rs"] == 0 and m["itc_underclaim_rs"] > 0
    assert m["itc_underclaim_rs"] == pytest.approx(m["itc_abs_err_rs"])


def test_perfect_output_has_zero_gaps(world):
    cid, target = next(iter(world["targets"].items()))
    m = case_metrics(json.dumps(target), EvalCase(cid, "", target, {"split": "test_iid", "difficulty": "easy"}, None))
    assert m["itc_overclaim_rs"] == 0 and m["itc_underclaim_rs"] == 0
