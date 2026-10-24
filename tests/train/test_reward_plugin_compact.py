"""GRPO reward on compact text: rollouts are unconstrained (no JSON-schema grammar), the SFT policy writes the
compact form (zero buckets and heads omitted) and the GRPO references are compact; the reward must expand both."""

import json
from pathlib import Path

from gst_recon.rewards import compact, expand
from gst_recon.train.reward import grpo_reward

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "easy-21-00001" / "target.json"


def test_compact_completion_and_reference_score_like_full():
    full = expand(json.loads(EXAMPLE.read_text()))
    small = compact(full)
    assert len(json.dumps(small)) < len(json.dumps(full))
    best = grpo_reward(json.dumps(full), json.dumps(full))
    assert best > 0
    for text in (json.dumps(small), "```json\n" + json.dumps(small) + "\n```"):
        for ref in (json.dumps(full), json.dumps(small)):
            assert grpo_reward(text, ref) == best
