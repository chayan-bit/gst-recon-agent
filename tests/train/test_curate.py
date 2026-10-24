"""CuratorKIT stage with a fake teacher/judge (no network)."""

import dataclasses
import json

import pytest

pytest.importorskip("curatorkit")
pytest.importorskip("detect_secrets")
from curatorkit.llm.base import BaseLLM, LLMResponse

from gst_recon.train import build as b
from gst_recon.train import curate as cu


class FakeLLM(BaseLLM):
    def __init__(self, reply):
        super().__init__(model="fake", temperature=0.0, max_tokens=64)
        self.reply = reply

    def _call(self, messages, **kwargs):
        return LLMResponse(text=self.reply(messages), model="fake")

    async def _acall(self, messages, **kwargs):
        return self._call(messages)


def rewrite(messages):
    text = messages[-1]["content"]
    if "Remarks" in text and "ACME" in text and messages[0]["role"] == "system":
        return "Dear team, " + text.replace("Grand Total", "Total payable")
    return text


def test_paraphrase_gates(rendered):
    cands = b.load_rendered(rendered)
    lossy = FakeLLM(lambda m: m[-1]["content"].replace("236.00", "236"))
    raw, gated, _, counts = cu.paraphrase_stage(cands, lossy, FakeLLM(lambda m: '{"grounding_score": 0.95}'), 4)
    assert counts["blocks"] == 13 and counts["rewritten"] == 13 and not gated
    assert counts["rejected"] == {"fact_missing": 13}
    good = FakeLLM(rewrite)
    raw, gated, _, counts = cu.paraphrase_stage(cands, good, FakeLLM(lambda m: '{"grounding_score": 0.95}'), 4)
    assert counts["kept"] == 13 and all("Total payable" in g["D01"] for g in gated.values())
    raw, gated, _, counts = cu.paraphrase_stage(cands, good, FakeLLM(lambda m: '{"grounding_score": 0.2}'), 4)
    assert not gated and set(counts["rejected"]) == {"hallucination_contract_failed"} and len(raw) == 13


def test_case_gates_and_manifest(rendered, tmp_path):
    cands = [c for c in b.load_rendered(rendered) if c.split == "train"]
    dup = dataclasses.replace(cands[3], case_id="easy-1-dup")  # same content under another id
    kept, rej, info = cu.gate_cases(cands + [dup])
    reasons = sorted(r.rejection_reason for r in rej)
    assert reasons == ["duplicate_exact", "ocr_unrecoverable"] and len(kept) == len(cands) - 1
    path = cu.write_manifest(tmp_path, info["passed_samples"], rej, info["stage_counts"], 0.0, {"source": "test"})
    m = json.loads(path.read_text())
    assert m["rejected_breakdown"] == {"ocr_unrecoverable": 1, "duplicate_exact": 1}
    assert (tmp_path / "rejected.jsonl").read_text().count("\n") == 2


def test_secrets_gate_keeps_bank_refs_and_catches_keys(rendered):
    c = next(c for c in b.load_rendered(rendered) if c.split == "train" and not c.unrecoverable)
    utr = dataclasses.replace(c, case_id="utr", prompt=c.prompt + "15/05/24,RTGS DR-HDFC0296548-X-HDFCN457645932682,HDFCN457645932682\n")
    fake = "AKIA" + "IOSFODNN7EXAMPLE"  # AWS's documented example key id, split so commit hooks don't flag it
    key = dataclasses.replace(c, case_id="key", prompt=c.prompt + f"aws_secret {fake}\n")
    kept, rej, _ = cu.gate_cases([utr, key])
    assert [k.case_id for k in kept] == ["utr"] and rej[0].rejection_reason.startswith("secret_detected:AWS")
