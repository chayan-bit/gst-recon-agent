import json
import shutil

import pytest

from gst_recon.eval.guard import EvalDataError, mark_eval_dir
from gst_recon.eval.prompts import SYSTEM_PROMPT
from gst_recon.train import build as b

LIMITS = {"grpo_max_prompt": b.GRPO_MAX_PROMPT, "grpo_max_completion": b.GRPO_MAX_COMPLETION,
          "sft_max_seq": b.SFT_MAX_SEQ}


def test_refuses_eval_outputs(tmp_path, rendered):
    """Frontier/eval outputs can never become training data: runs/eval/, a DO_NOT_TRAIN marker
    anywhere above, or a case dir symlinked into either."""
    ev = tmp_path / "runs" / "eval" / "frontier"
    ev.mkdir(parents=True)
    with pytest.raises(EvalDataError):
        b.load_rendered(ev)
    marked = tmp_path / "elsewhere" / "run1"
    mark_eval_dir(marked)
    with pytest.raises(EvalDataError):
        b.load_rendered(marked)
    links = tmp_path / "rendered_links"
    links.mkdir()
    case = next(p for p in rendered.iterdir() if p.is_dir())
    shutil.copytree(case, marked / case.name)
    (links / case.name).symlink_to(marked / case.name)
    with pytest.raises(EvalDataError):
        b.load_rendered(links)
    assert b.load_rendered(rendered)  # ordinary rendered data still loads


def test_roles_are_deterministic_and_disjoint():
    ids = [f"easy-1-{i:05d}" for i in range(200)]
    roles = [b.role(i) for i in ids]
    assert roles == [b.role(i) for i in ids]
    assert 0.6 < roles.count("sft") / len(ids) < 0.8


def test_export_rows_and_filters(rendered, tmp_path):
    cands = b.load_rendered(rendered)
    assert {c.split for c in cands} == {"train", "test_iid"}
    counts = b.export(cands, tmp_path, 300, LIMITS)
    assert counts["sft"]["pool"] + counts["grpo"]["pool"] == 13  # train only
    assert counts["sft"]["too_long"] + counts["grpo"]["too_long"] == 1
    by_id = {c.case_id: c for c in cands}
    for line in (tmp_path / "sft" / "train.jsonl").read_text().splitlines():
        row = json.loads(line)
        assert [m["role"] for m in row["messages"]] == ["system", "user", "assistant"]
        assert row["messages"][0]["content"] == SYSTEM_PROMPT
        assert row["messages"][2]["content"] == by_id[row["case_id"]].target
        assert b.role(row["case_id"]) == "sft"
    for line in (tmp_path / "grpo" / "train.jsonl").read_text().splitlines():
        row = json.loads(line)
        assert json.loads(row["reference"]) == json.loads(by_id[row["case_id"]].target)
        assert [m["role"] for m in row["prompt"]] == ["system", "user"] and b.role(row["case_id"]) == "grpo"
    assert b.export_eval(cands, tmp_path / "eval") == {"test_iid": 1}


def test_token_report_proposes_max_docs(rendered):
    rep = b.token_report(b.load_rendered(rendered), 300, LIMITS)
    assert rep["by_difficulty"]["easy"]["n"] == 14
    assert rep["proposed_max_docs"]["grpo"] >= 4 and rep["system_prompt_tokens"] == 300
