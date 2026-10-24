"""Real-world sanity split: truth builds, engine agrees with the hand-checked law, target scores 1.0."""

from pathlib import Path

import pytest

from gst_recon.rewards import eval_metrics, score
from realworld.build import PHOTO_SUBSET, SOURCES, photo_map
from realworld.truth import build_all, load_specs


@pytest.fixture(scope="module")
def built():
    return build_all()


def test_engine_agrees_with_hand_expectations_and_rates(built):
    cases, problems = built
    assert problems == []
    assert 10 <= len(cases) <= 15


def test_truth_target_scores_one(built):
    for c in built[0]:
        raw = c.expected.model_dump_json()
        assert score(raw, c.expected)["composite"] == pytest.approx(1.0)
        m = eval_metrics(raw, c)
        assert m["composite"] == pytest.approx(1.0) and m["itc_invoice"] == 1.0 and m["itc_abs_err_rs"] == 0


def test_discrepancy_coverage(built):
    tags = {t for c in built[0] for t in c.anomalies}
    assert {"missing_in_2b", "amount_mismatch", "period_mismatch", "gstin_mismatch", "duplicate", "unpaid_180d",
            "RCM_ELIGIBLE", "CREDIT_NOTE_REVERSAL", "BLOCKED_FOOD_BEVERAGE", "BLOCKED_WORKS_CONTRACT"} <= tags


def test_every_format_has_provenance_and_is_photographed():
    used = {d["format"] for s in load_specs() for d in s["docs"]}
    assert used == set(SOURCES)
    fmt = {f"{s['id']}_{d['id']}": d["format"] for s in load_specs() for d in s["docs"]}
    assert {fmt[k] for k in PHOTO_SUBSET} == used


def test_photo_map_by_name_and_by_order(tmp_path: Path):
    named = tmp_path / "named"
    named.mkdir()
    (named / "rw01_D02.jpg").write_bytes(b"x")
    (named / "notes.txt").write_text("ignored")
    assert list(photo_map(named)) == ["rw01_D02"]
    ordered = tmp_path / "ordered"
    ordered.mkdir()
    for i in range(len(PHOTO_SUBSET)):
        (ordered / f"IMG_{1000 + i}.JPG").write_bytes(b"x")
    assert [p[0].name for p in photo_map(ordered).values()][:2] == ["IMG_1000.JPG", "IMG_1001.JPG"]
    (ordered / "IMG_2000.JPG").write_bytes(b"x")
    with pytest.raises(SystemExit):
        photo_map(ordered)
