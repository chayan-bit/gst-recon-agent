"""Shortcut audit regression: no surface feature predicts an anomaly flag, and the
s.17(5) outcome cannot be read off the item description alone."""

from gst_recon.sim import audit


def test_no_spurious_feature_flag_correlation():
    rows = audit.spurious(audit.gen("train", 600, 7))
    assert not [r for r in rows if r["spurious"]]


def test_baselines_below_rules_engine_and_context_matters():
    train = audit.gen("train", 300, 7)
    tests = {s: audit.gen(s, 60, 8) for s in ("test_iid", "test_ood")}
    table = audit.evaluate(train, tests)
    for split in tests:
        assert table[(split, "rules_engine")]["composite"] > 0.9999
        assert table[(split, "context_blind")]["itc_invoice"] < 0.9  # profile + remarks are needed
        for name in ("majority", "no_anomaly", "keyword"):
            assert table[(split, name)]["composite"] < 0.9
            assert table[(split, name)]["grpo"] < (0.5 if name == "keyword" else 0.35)
        assert table[(split, "rules_engine")]["grpo"] > 0.9999
