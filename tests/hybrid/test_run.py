"""Hybrid mode through the real eval harness (run_eval): per-document replies cached, raw scored as usual."""

from __future__ import annotations

import json
import shutil

import pytest

from gst_recon.eval.cases import load_cases
from gst_recon.eval.runner import run_eval
from gst_recon.hybrid.heuristic import heuristic_call
from gst_recon.hybrid.run import make_generator, parse_doc
from gst_recon.hybrid.sft import truth_records

from .conftest import ARGS, EXAMPLES, example


@pytest.fixture()
def cases_dir(tmp_path):
    root = tmp_path / "cases"
    for cid in ARGS:
        shutil.copytree(EXAMPLES / cid, root / cid, ignore=shutil.ignore_patterns("images"))
    return root


def _oracle_call():
    """A fake model that answers each document with its true record (looked up by the document block)."""
    answers = {}
    for cid in ARGS:
        prompt, target, case = example(cid)
        from gst_recon.hybrid.inputs import parse_prompt

        recs = truth_records(target, case)
        answers.update({d.block: recs[d.doc_id].model_dump_json() for d in parse_prompt(prompt).docs})
    calls = []

    def call(messages):
        calls.append(1)
        user = messages[-1]["content"]
        text = next(t for b, t in answers.items() if b in user)
        return {"text": text, "prompt_tokens": 10, "completion_tokens": 5, "latency_s": 0.0, "error": None}

    return call, calls


def test_hybrid_run_with_true_records_scores_one_and_caches(cases_dir, tmp_path):
    cases = load_cases([cases_dir])
    call, calls = _oracle_call()
    out = tmp_path / "run"
    agg = run_eval(cases, make_generator(call, out, concurrency=2), out, {"label": "oracle hybrid"}, concurrency=2)
    assert agg["overall"]["itc_invoice"]["mean"] == pytest.approx(1.0)
    assert agg["overall"]["match_accuracy"]["mean"] == pytest.approx(1.0)
    n_docs = len(calls)
    rec = json.loads(next((out / "cases").glob("*.json")).read_text())
    assert rec["doc_raw"] and rec["trace"]["decisions"] and rec["error"] is None
    run_eval(cases, make_generator(call, out, concurrency=2), out, {"label": "oracle hybrid"}, concurrency=2, resume=False)
    assert len(calls) == n_docs  # second pass re-reconciled from the per-document cache


def test_heuristic_floor_runs(cases_dir, tmp_path):
    out = tmp_path / "heur"
    agg = run_eval(load_cases([cases_dir]), make_generator(heuristic_call, out, concurrency=2), out, {"label": "h"}, concurrency=2)
    assert agg["n_errors"] == 0 and 0 < agg["overall"]["match_accuracy"]["mean"] < 1


def test_parse_doc_is_lenient():
    rec, why = parse_doc('```json\n{"invoice_no": "A1", "line_items": [{"itc_category": "spaceship", "taxable_value": 5}]}\n```')
    assert why == "" and rec.invoice_no == "A1" and rec.line_items[0].itc_category.value == "normal"
    assert parse_doc("no json here") == (None, "unparseable")


def test_msgs_runner_writes_private_replies_beside_each_messages_file_and_resumes(tmp_path):
    import importlib.util
    import stat
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("msgs_run", Path(__file__).parents[2] / "scripts" / "hybrid_msgs_run.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for doc in ("inv-01", "inv-02"):
        (tmp_path / "in" / doc).mkdir(parents=True)
        (tmp_path / "in" / doc / "messages.json").write_text('[{"role": "user", "content": "doc"}]')
    calls = []

    def fake(messages):
        calls.append(messages)
        return {"text": '{"invoice_no": "A1", "line_items": []}', "error": None}

    assert mod.run(tmp_path / "in", tmp_path / "out", fake) == {"called": 2, "parse_ok": 2}
    reply = tmp_path / "out" / "inv-01" / "reply.json"
    assert json.loads(reply.read_text())["parse_ok"] is True
    assert stat.S_IMODE(reply.stat().st_mode) == 0o600 and stat.S_IMODE(reply.parent.stat().st_mode) == 0o700
    assert mod.run(tmp_path / "in", tmp_path / "out", fake) == {"called": 0, "parse_ok": 0} and len(calls) == 2
