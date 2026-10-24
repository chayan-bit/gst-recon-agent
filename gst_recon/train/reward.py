"""AlignTune plugin: registers our schema-gated `grpo` reward as `gst_recon_grpo`, and the per-document
reward (gst_recon.rewards.doc) as `gst_recon_doc_grpo`.

AlignTune resolves a config entry `rewards: [{type: gst_recon_grpo}]` through
RewardRegistry, instantiates the class with a RewardConfig, and calls
`compute(text, reference=...)` once per completion, with `reference` taken from
the dataset column of that name (the truth ReconOutput JSON, see build.grpo_row).
"""

from __future__ import annotations

import json
from functools import lru_cache

from gst_recon.rewards import score
from gst_recon.rewards.doc import doc_reward

NAME = "gst_recon_grpo"
DOC_NAME = "gst_recon_doc_grpo"


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


def doc_grpo_reward(text: str, reference: str | dict | None = None, **_: object) -> float:
    """`reference` = JSON {"truth": DocRecord, "doc_text": the document block}; missing or malformed scores 0."""
    try:
        ref = _truth(reference) if isinstance(reference, str) else reference
        return doc_reward(text, ref["truth"], ref["doc_text"])
    except (ValueError, KeyError, TypeError):
        return 0.0


def register() -> str:
    """Register both rewards with AlignTune's reward registry (idempotent); returns the case-level name."""
    from aligntune.rewards.core import RewardConfig, RewardFunction, RewardType
    from aligntune.rewards.registry import RewardRegistry

    class GstReconGrpoReward(RewardFunction):
        def compute(self, text: str, reference: str | None = None, **kwargs) -> float:
            return grpo_reward(text, reference)

    class GstReconDocGrpoReward(RewardFunction):
        def compute(self, text: str, reference: str | None = None, **kwargs) -> float:
            return doc_grpo_reward(text, reference)

    # RewardType has no CUSTOM member; the type is only metadata for a custom reward
    for name, cls in ((NAME, GstReconGrpoReward), (DOC_NAME, GstReconDocGrpoReward)):
        RewardRegistry.register_custom_reward(name, cls, RewardConfig(reward_type=RewardType.INSTRUCTION_FOLLOWING, weight=1.0))
    return NAME
