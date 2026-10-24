"""Rollout-server smoke for per-document GRPO, through the AlignTune fork's own SGLang client.

  python -m gst_recon.train.smoke_rollout URL ADAPTER_DIR DATA_JSONL TOKENIZER_DIR

Checks, in order, what the fork's adapter-sync rollout relies on: the server reports enable_lora, a LoRA loads by
name, one grammar-constrained (doc_json_schema) request returns a schema-valid DocRecord, a second adapter version
loads and the first unloads (the fork's sync step), and a GRPO-style group (prefill once, then 8 samples at
temperature 1) comes back with rewards. Exits non-zero on the first failure.
"""

from __future__ import annotations

import json
import os
import shutil
import statistics
import sys
import tempfile
import time

from gst_recon.hybrid.docschema import doc_json_schema
from gst_recon.rewards.doc import parse_doc
from gst_recon.train.reward import doc_grpo_reward


def main(url: str, adapter: str, data: str, tokenizer_dir: str) -> None:
    from aligntune.backends.trl.rl.rollout.sglang_rollout import SGLangClient
    from transformers import AutoTokenizer

    client, tok = SGLangClient(url, timeout=300), AutoTokenizer.from_pretrained(tokenizer_dir)
    info = client.get_server_info()
    assert info.get("enable_lora"), f"server_info has no enable_lora: {sorted(info)[:20]}"
    print("server", info.get("version"), "model", client.get_model_info().get("model_path"))
    row = json.loads(open(data).readline())
    ids = tok.apply_chat_template(row["prompt"], add_generation_prompt=True, tokenize=True)
    ids = ids["input_ids"] if hasattr(ids, "keys") else ids  # transformers 5 returns a BatchEncoding
    params = {"max_new_tokens": 1024, "temperature": 0.0, "stop_token_ids": [tok.eos_token_id],
              "json_schema": json.dumps(doc_json_schema(), separators=(",", ":"))}

    t = time.time()
    client.load_lora_adapter("smoke-v1", os.path.abspath(adapter))  # the server resolves paths from its own cwd
    out = client.generate([ids], params, "smoke-v1")[0]
    text = tok.decode(out["output_ids"], skip_special_tokens=True)
    assert parse_doc(text) is not None, f"constrained output is not a DocRecord: {text[:300]}"
    print(f"v1 greedy: {len(out['output_ids'])} tokens, reward {doc_grpo_reward(text, row['reference']):.3f}, "
          f"{time.time() - t:.1f}s")

    with tempfile.TemporaryDirectory(dir=".") as d:  # the fork writes each version to its own dir, then swaps
        v2 = os.path.abspath(shutil.copytree(adapter, f"{d}/adapter-0"))
        t = time.time()
        client.load_lora_adapter("smoke-v2", v2)
        client.unload_lora_adapter("smoke-v1")
        print(f"sync: loaded smoke-v2, unloaded smoke-v1 in {time.time() - t:.1f}s")
        group = {**params, "temperature": 1.0, "top_p": 1.0}
        client.generate([ids], {**group, "max_new_tokens": 0}, "smoke-v2")  # prefix-cache the prompt once
        t = time.time()
        outs = client.generate([ids] * 8, group, "smoke-v2")
        rewards = [doc_grpo_reward(tok.decode(o["output_ids"], skip_special_tokens=True), row["reference"]) for o in outs]
        print(f"group of 8: {time.time() - t:.1f}s, reward mean {statistics.mean(rewards):.3f} "
              f"std {statistics.pstdev(rewards):.3f}, tokens {[len(o['output_ids']) for o in outs]}")
        client.unload_lora_adapter("smoke-v2")
    print("SMOKE OK")


if __name__ == "__main__":
    main(*sys.argv[1:5])
