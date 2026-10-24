"""AlignTune plugin: registers our schema-gated `grpo` reward as `gst_recon_grpo`.

AlignTune resolves a config entry `rewards: [{type: gst_recon_grpo}]` through
RewardRegistry, instantiates the class with a RewardConfig, and calls
`compute(text, reference=...)` once per completion, with `reference` taken from
the dataset column of that name (the truth ReconOutput JSON, see build.grpo_row).
"""

from __future__ import annotations

import json
from functools import lru_cache

from gst_recon.rewards import score

NAME = "gst_recon_grpo"


@lru_cache(maxsize=1024)
def _truth(reference: str) -> dict:
    return json.loads(reference)  # score() never mutates it


def grpo_reward(text: str, reference: str | dict | None = None, **_: object) -> float:
    """Total: a missing or unparseable reference scores 0 instead of crashing the rollout."""
    if not reference:
        return 0.0
    try:
        truth = _truth(reference) if isinstance(reference, str) else reference
    except ValueError:
        return 0.0
    return score(text, truth)["grpo"]


def register() -> str:
    """Register with AlignTune's reward registry (idempotent); returns the reward name."""
    from aligntune.rewards.core import RewardConfig, RewardFunction, RewardType
    from aligntune.rewards.registry import RewardRegistry

    class GstReconGrpoReward(RewardFunction):
        def compute(self, text: str, reference: str | None = None, **kwargs) -> float:
            return grpo_reward(text, reference)

    # RewardType has no CUSTOM member; the type is only metadata for a custom reward
    RewardRegistry.register_custom_reward(NAME, GstReconGrpoReward,
                                          RewardConfig(reward_type=RewardType.INSTRUCTION_FOLLOWING, weight=1.0))
    return NAME
