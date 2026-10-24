from __future__ import annotations

import json

from gst_recon.eval.__main__ import main
from gst_recon.eval.stats import paired_delta


def _run(world, model, name, *extra):
    out = world["tmp"] / "runs" / "eval" / name
    main(["run", "--endpoint", world["stub"].url, "--model", model, "--cases", *map(str, world["dirs"].values()),
          "--out", str(out), "--truth-dir", str(world["truth"]), *extra])
    return out


def test_report_table_chart_baselines_and_paired_delta(world):
    _run(world, "noisy", "base")
    _run(world, "perfect", "sft", "--label", "SFT")
    audit = world["tmp"] / "audit.json"
    audit.write_text(json.dumps({"baselines": {
        "test_iid/majority": {"field_f1": 1.0, "match_accuracy": 1.0, "itc_invoice": 0.3, "context_doc_acc": 0.1, "itc_abs_err_rs": 5000.0, "composite": 0.6},
        "test_iid/rules_engine": {"composite": 1.0}}}))
    out = world["tmp"] / "reports" / "results.md"
    rc = main(["report", "--runs", str(world["tmp"] / "runs" / "eval"), "--out", str(out), "--baselines", str(audit),
               "--ref", "base", "--order", "base", "SFT"])
    assert rc == 0
    md = out.read_text()
    assert "| base |" in md and "| SFT |" in md
    assert "baseline: majority" in md and "rules_engine" not in md
    assert "Paired difference vs base" in md and "bootstrap p" in md
    assert out.with_suffix(".png").stat().st_size > 5000
    assert md.index("| base |") < md.index("| SFT |")


def test_report_includes_hybrid_md_next_to_the_output_once(world):
    _run(world, "perfect", "sft", "--label", "SFT")
    out = world["tmp"] / "reports" / "results.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    (out.parent / "hybrid.md").write_text("## Hybrid mode\n\nhybrid rows\n")
    (out.parent / "pipeline.md").write_text("## Pipeline comparison\n\nrows\n")
    (out.parent / "frontier-hybrid.md").write_text("## Frontier per-document models\n\nrows\n")
    for extra in ([], ["--append", str(out.parent / "hybrid.md")]):
        assert main(["report", "--runs", str(world["tmp"] / "runs" / "eval"), "--out", str(out), *extra]) == 0
        assert out.read_text().count("## Hybrid mode") == 1 and out.read_text().count("## Pipeline comparison") == 1
        assert out.read_text().count("## Frontier per-document models") == 1


def test_paired_delta_detects_improvement():
    mk = lambda v: [{"case_id": f"c{i}", "metrics": {"composite": x, "context_ok": 0, "context_n": 0}} for i, x in enumerate(v)]  # noqa: E731
    a, b = mk([0.1, 0.2, 0.15, 0.1, 0.2, 0.1, 0.12, 0.18]), mk([0.9, 0.8, 0.85, 0.9, 0.8, 0.9, 0.88, 0.82])
    d = paired_delta(a, b)
    assert d["delta"] > 0.6 and d["p_value"] < 0.05 and d["ci_lo"] > 0
    assert paired_delta(a, a)["p_value"] > 0.5
