"""The realworld split is reported on its own, with CIs, and never leaks into the simulator-comparable aggregates."""

import json

from gst_recon.eval.__main__ import main
from tests.eval.conftest import make_rendered


def test_realworld_is_its_own_table_with_ci_and_stays_out_of_overall(world):
    rw = world["tmp"] / "rendered" / "realworld"
    world["targets"] |= make_rendered(rw, "test_ood", 3, world["truth"], seed=7)  # the simulator has no realworld split: relabel
    for meta in rw.glob("*/meta.json"):
        meta.write_text(json.dumps(json.loads(meta.read_text()) | {"split": "realworld", "difficulty": "realworld"}))
    out = world["tmp"] / "runs" / "eval" / "noisy"
    dirs = [*map(str, world["dirs"].values()), str(rw)]
    assert main(["run", "--endpoint", world["stub"].url, "--model", "noisy", "--cases", *dirs, "--out", str(out),
                 "--truth-dir", str(world["truth"]), "--retries", "0"]) == 0
    agg = json.loads((out / "aggregate.json").read_text())
    assert agg["n_cases"] == 9 and agg["overall"]["n"] == 6
    assert agg["external"]["realworld"]["n"] == 3 and "ci_lo" in agg["external"]["realworld"]["composite"]
    assert "realworld" in agg["breakdowns"]["split"] and "realworld" not in agg["breakdowns"]["difficulty"]
    assert all(not g.startswith("realworld") for g in agg["breakdowns"]["split_difficulty"])
    md_path = world["tmp"] / "reports" / "results.md"
    assert main(["report", "--runs", str(out), "--out", str(md_path)]) == 0
    md = md_path.read_text()
    assert "## realworld" in md and "sanity split of 3 hand-built cases" in md
    sec = md.split("## realworld")[1].split("\n## ")[0]
    assert "[" in sec  # CI brackets in the realworld table
