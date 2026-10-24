from __future__ import annotations

import json

import pytest

from gst_recon.eval.__main__ import main
from gst_recon.eval.cases import load_cases
from gst_recon.eval.guard import EvalDataError, refuse_eval_path


def _run(world, model, name, *extra):
    out = world["tmp"] / "runs" / "eval" / name
    rc = main(["run", "--endpoint", world["stub"].url, "--model", model, "--cases", *map(str, world["dirs"].values()),
               "--out", str(out), "--truth-dir", str(world["truth"]), "--concurrency", "4", "--retries", "0", *extra])
    return rc, out, json.loads((out / "aggregate.json").read_text())


def test_perfect_model_scores_one_and_writes_all_artifacts(world):
    rc, out, agg = _run(world, "perfect", "perfect", "--gpu-hour-usd", "2.0", "--api-in-per-mtok", "3", "--api-out-per-mtok", "15")
    assert rc == 0 and agg["n_cases"] == 6 and agg["n_errors"] == 0
    o = agg["overall"]
    for k in ("schema_valid", "extraction_f1", "match_accuracy", "itc_invoice", "composite"):
        assert o[k]["mean"] == pytest.approx(1.0), k
    assert o["itc_abs_err_rs"]["mean"] == 0
    assert agg["context_source"] == "truth"
    assert o["composite"]["ci_lo"] == pytest.approx(1.0)
    assert set(agg["breakdowns"]["split"]) == {"test_iid", "test_ood"}
    assert set(agg["breakdowns"]["ocr_bucket"]) == {"full", "partial"}
    assert (out / "cases").is_dir() and len(list((out / "cases").glob("*.json"))) == 6
    assert (out / "table.md").exists() and (out / "DO_NOT_TRAIN").exists()
    rec = json.loads(next((out / "cases").glob("*.json")).read_text())
    assert rec["parsed"] is not None and rec["prompt_tokens"] == 1000 and rec["latency_s"] > 0
    # cost: api = (1000*3 + 200*15)/1e6 * 1000 = 6.0 per 1k cases
    assert agg["cost_per_1000_cases"]["api_usd"] == pytest.approx(6.0)
    assert agg["cost_per_1000_cases"]["gpu_usd"] > 0 and agg["throughput"]["req_per_s"] > 0


def test_constrained_flag_sends_json_schema_response_format(world):
    _run(world, "perfect", "c", "--constrained")
    body = world["stub"].requests[-1]
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["name"] == "recon"
    assert body["response_format"]["json_schema"]["schema"]["properties"]["itc_totals"]
    assert "JSON Schema" not in body["messages"][0]["content"]


def test_unconstrained_has_no_response_format_and_schema_in_prompt(world):
    _run(world, "perfect", "u")
    body = world["stub"].requests[-1]
    assert "response_format" not in body
    assert "JSON Schema" in body["messages"][0]["content"]


def test_noisy_model_scores_below_one_with_rupee_error(world):
    _, _, agg = _run(world, "noisy", "noisy")
    o = agg["overall"]
    assert o["itc_abs_err_rs"]["mean"] == pytest.approx(1000.0)
    assert o["extraction_f1"]["mean"] < 1.0 and o["composite"]["mean"] < 1.0
    assert o["itc_total_exact"]["mean"] == 0.0 and o["schema_valid"]["mean"] == 1.0


def test_garbage_and_failed_requests_score_zero(world):
    _, _, agg = _run(world, "garbage", "g")
    assert agg["overall"]["composite"]["mean"] == 0 and agg["overall"]["parse_ok"]["mean"] == 0
    assert agg["overall"]["itc_abs_err_rs"]["mean"] > 0  # claims zero ITC, so error = the true eligible total
    _, _, agg = _run(world, "fail500", "f")
    assert agg["n_errors"] == 6 and agg["overall"]["composite"]["mean"] == 0


def test_fenced_json_is_parsed(world):
    _, _, agg = _run(world, "fenced", "fe")
    assert agg["overall"]["composite"]["mean"] == pytest.approx(1.0)


def test_resume_skips_cached_cases(world):
    _run(world, "perfect", "r")
    n = len(world["stub"].requests)
    _, out, agg = _run(world, "perfect", "r")
    assert len(world["stub"].requests) == n and agg["n_cases"] == 6
    assert json.loads((out / "run_stats.json").read_text())["n_requests"] == 6


def test_n_per_dir_samples_and_context_proxy_without_truth(world):
    cases = load_cases(list(world["dirs"].values()), n_per_dir=2, seed=1)
    assert len(cases) == 4 and {c.split for c in cases} == {"test_iid", "test_ood"}
    assert all(c.truth is None for c in cases)
    out = world["tmp"] / "runs" / "eval" / "p"
    main(["run", "--endpoint", world["stub"].url, "--model", "perfect", "--cases", str(world["dirs"]["test_iid"]),
          "--out", str(out), "--truth-dir", str(world["tmp"] / "none")])
    assert json.loads((out / "aggregate.json").read_text())["context_source"].startswith("proxy")


def test_guard_refuses_eval_outputs(world, tmp_path):
    with pytest.raises(EvalDataError):
        refuse_eval_path("runs/eval/frontier/cases/x.json")
    _, out, _ = _run(world, "perfect", "gd")
    with pytest.raises(EvalDataError):
        refuse_eval_path(out / "cases")
    d = tmp_path / "elsewhere"
    d.mkdir()
    assert refuse_eval_path(d) == d


def test_max_tokens_is_clipped_to_the_server_context_instead_of_failing(world):
    _, _, agg = _run(world, "ctx", "ctx")
    assert agg["n_errors"] == 0 and agg["overall"]["composite"]["mean"] == pytest.approx(1.0)
    assert {r["max_tokens"] for r in world["stub"].requests} == {32768, 8992}


def test_context_overflow_is_counted_separately(world, monkeypatch):
    from gst_recon.eval import client

    assert client.clip_max_tokens("The input (37032 tokens) is longer than the model's context length (16384 tokens).") is None
    assert client.clip_max_tokens("maximum context length of 16384 tokens. You requested a total of 17858 tokens: "
                                  "9666 tokens from the input messages and 8192") == 16384 - 9666 - 8


def test_completion_cap_error_is_clipped():
    from gst_recon.eval import client

    assert client.clip_max_tokens("max_completion_tokens is too large: 32768.This model supports at most 16384 completion tokens.") == 16384


def test_max_tokens_factor_caps_per_case_budget(world):
    _run(world, "perfect", "f", "--max-tokens-factor", "1.5")
    assert {r["max_tokens"] for r in world["stub"].requests} == {2500}
    _run(world, "perfect", "f2", "--max-tokens-factor", "1.5", "--max-tokens", "2000", "--no-resume")
    assert {r["max_tokens"] for r in world["stub"].requests[-6:]} == {2000}
