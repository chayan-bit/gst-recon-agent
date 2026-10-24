import json

import pytest

from gst_recon.sim.world import generate_case
from gst_recon.train.reward import NAME, grpo_reward


@pytest.fixture(scope="module")
def truth():
    return generate_case(4, "medium", 0).expected.model_dump_json()


def test_grpo_reward_plain_function(truth):
    assert grpo_reward(truth, truth) == pytest.approx(1.0)
    assert grpo_reward("```json\n" + truth + "\n```", reference=truth) == pytest.approx(1.0)
    assert grpo_reward("I cannot help", truth) == 0.0
    assert grpo_reward(truth, None) == 0.0 and grpo_reward(truth, "not json") == 0.0
    half = json.loads(truth)
    half["matches"] = []
    assert 0.0 < grpo_reward(json.dumps(half), truth) < 1.0


def test_round_trips_through_aligntune_reward_call(truth):
    """The exact path GRPO takes: registry name -> RewardFunction -> TRL batch wrapper."""
    pytest.importorskip("aligntune")
    from aligntune.core.rl.reward_handler import RewardBridge, call_reward_safely
    from aligntune.rewards.registry import RewardRegistry

    from gst_recon.train.reward import register

    assert register() == NAME and NAME in RewardRegistry.list_rewards()
    fn = RewardRegistry.get_reward_function(NAME, {"type": NAME, "weight": 1.0, "params": {}})
    batch = RewardBridge.wrap_registry_reward(fn, NAME)
    fake = [[{"role": "assistant", "content": truth}], [{"role": "assistant", "content": "{}"}]]
    scores = batch(prompts=["p", "p"], completions=fake, reference=[truth, truth], case_id=["c", "c"])
    assert scores[0] == pytest.approx(1.0) and scores[1] == 0.0
    assert call_reward_safely(fn.compute, truth, answer=truth) == pytest.approx(1.0)  # `answer` alias
