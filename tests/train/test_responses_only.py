"""Response-only loss on a real built SFT row: prompt tokens are labelled -100, the reply is not.

Needs unsloth_zoo, the Qwen3 tokenizer and a built row, so it runs where training runs (rs-epyc
venv-align, HF_HOME with the model) and skips elsewhere. Row: $GST_SFT_ROWS or
data/train/curated/sft/train.jsonl.
"""

import json
import os
from pathlib import Path

import pytest

from gst_recon.train.__main__ import load_config

ROOT = Path(__file__).resolve().parents[2]
ROWS = Path(os.environ.get("GST_SFT_ROWS", ROOT / "data/train/curated/sft/train.jsonl"))
MODEL = os.environ.get("GST_SFT_TOKENIZER", "Qwen/Qwen3-4B-Instruct-2507")


def test_prompt_is_masked_and_reply_is_trained():
    dataset_utils = pytest.importorskip("unsloth_zoo.dataset_utils")
    transformers = pytest.importorskip("transformers")
    if not ROWS.exists():
        pytest.skip(f"no built rows at {ROWS}")
    try:
        tok = transformers.AutoTokenizer.from_pretrained(MODEL)
    except OSError:
        pytest.skip(f"tokenizer {MODEL} not available offline")
    parts = load_config(str(ROOT / "configs/sft.yaml"))[1]["train_on_responses_only"]
    messages = json.loads(ROWS.read_text().splitlines()[0])["messages"]
    ids = tok(tok.apply_chat_template(messages, tokenize=False), add_special_tokens=False)["input_ids"]

    mask = dataset_utils.train_on_responses_only(None, tokenizer=tok, return_function=True, num_proc=1, **parts)
    labels = mask({"input_ids": [ids]})["labels"][0]

    reply = tok(messages[-1]["content"], add_special_tokens=False)["input_ids"]
    start = len(tok(tok.apply_chat_template(messages[:-1], tokenize=False, add_generation_prompt=True),
                    add_special_tokens=False)["input_ids"])  # first token of the assistant reply
    assert ids[start:start + len(reply)] == reply
    assert all(x == -100 for x in labels[:start])  # system prompt + rendered documents: no loss
    assert labels[start:start + len(reply)] == reply  # the target JSON: full loss
    assert start > 3 * len(reply)  # the prompt dominates the sequence, which is why masking matters
