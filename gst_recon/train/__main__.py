"""CLI.

  python -m gst_recon.train build --rendered data/rendered --out data/train [--teacher URL --teacher-model NAME]
  python -m gst_recon.train run configs/sft.yaml

`build` writes <out>/raw/{sft,grpo}/train.jsonl (no gates), <out>/curated/... (CuratorKIT
gates, manifest.json, rejected.jsonl), <out>/eval/{test_iid,test_ood}.jsonl and <out>/stats.json.
`run` registers the gst_recon_grpo reward with AlignTune and trains from a YAML config.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

from gst_recon.eval.guard import refuse_eval_path
from gst_recon.eval.prompts import SYSTEM_PROMPT
from gst_recon.train import build as b
from gst_recon.train import paraphrase as para


def _rewrite(c: b.Candidate, rewrites: dict, count) -> b.Candidate:
    rw = rewrites.get(c.case_id)
    if not rw:
        return c
    prompt = para.apply(c.prompt, rw)
    return b.with_prompt(c, prompt, count(prompt)[0])


def cmd_build(a: argparse.Namespace) -> dict:
    from gst_recon.render.tokens import count_tokens
    from gst_recon.train import curate as cu

    t0 = time.time()
    limits = {"grpo_max_prompt": a.grpo_max_prompt, "grpo_max_completion": a.grpo_max_completion,
              "sft_max_seq": a.sft_max_seq}
    cands = [b.compact_target(c, count_tokens) for c in b.load_rendered(Path(a.rendered))]
    sys_tokens, method = count_tokens(SYSTEM_PROMPT)
    train = [c for c in cands if c.split == "train"]
    raw_rw, gated_rw, para_rej = {}, {}, []
    para_counts = {"skipped": "--no-paraphrase", "unparaphrased_source": str(Path(a.rendered).resolve())}
    kept_old, kept_info = [], None
    if a.keep_grpo:
        kept_old, kept_source = b.load_grpo_rows(Path(a.keep_grpo), count_tokens)
        kept_info = {"path": str(Path(a.keep_grpo).resolve()), "rows": len(kept_old), "rendered_source": kept_source,
                     "paraphrase": "as built (teacher-paraphrased build, rows unchanged)"}
    if a.teacher:
        gen = cu.teacher(a.teacher, a.teacher_model)
        judge = cu.teacher(a.teacher, a.judge_model or a.teacher_model, temperature=0.0, max_tokens=1024)
        raw_rw, gated_rw, para_rej, para_counts = cu.paraphrase_stage(train, gen, judge, a.workers)
    out = Path(a.out)
    raw = [_rewrite(c, raw_rw, count_tokens) for c in train]
    kept, case_rej, info = cu.gate_cases(kept_old + [_rewrite(c, gated_rw, count_tokens) for c in train])
    stats = {
        "cases": {s: sum(c.split == s for c in cands) for s in ("train", "test_iid", "test_ood")},
        "token_method": method,
        "paraphrase": para_counts,
        "kept_grpo": kept_info,
        "ocr_builds": dict(Counter(c.ocr_build for c in kept_old + train)),
        "raw": b.export(raw, out / "raw", sys_tokens, limits),
        "curated": b.export(kept, out / "curated", sys_tokens, limits) | {
            "case_gates": info["stage_counts"],
            "rejected": dict(Counter(r.rejection_reason for r in case_rej))},
        "eval": b.export_eval(cands, out / "eval"),
        "tokens": b.token_report(cands, sys_tokens, limits),
    }
    cu.write_manifest(out / "curated", info["passed_samples"], para_rej + case_rej,
                      {"TeacherParaphrase": para_counts, **info["stage_counts"]}, t0,
                      {"source": str(refuse_eval_path(Path(a.rendered)).resolve()), "teacher": a.teacher_model if a.teacher else None,
                       "paraphrase": "teacher" if a.teacher else "none (--no-paraphrase)", "kept_grpo": kept_info,
                       "ocr_builds": stats["ocr_builds"], "limits": limits})
    (out / "stats.json").write_text(json.dumps(stats, indent=1))
    print(json.dumps({k: stats[k] for k in ("cases", "paraphrase", "kept_grpo", "raw", "curated", "eval")}, indent=1))
    print(json.dumps(stats["tokens"]["by_difficulty"], indent=1), json.dumps(stats["tokens"]["proposed_max_docs"]))
    return stats


def load_config(path: str) -> tuple[dict, dict]:
    """(AlignTune config, runner extras): the `gst_recon:` section is ours, the rest is AlignTune's."""
    import yaml

    cfg = yaml.safe_load(Path(path).read_text())
    return cfg, cfg.pop("gst_recon", None) or {}


def shadowed_args(cfg: dict) -> dict:
    """YAML values that AlignTune 0.1.28's create_sft_trainer / create_rl_trainer ignore in favour of
    their own parameter defaults (max_seq_length 512, batch_size 4, output_dir ./output, ...): the
    first smoke run trained on 512-token truncations and saved to ./output. Restate them as arguments."""
    m, t, log = cfg.get("model", {}), cfg.get("train", {}), cfg.get("logging", {})
    args = {"max_seq_length": m.get("max_seq_length"), "batch_size": t.get("per_device_batch_size"),
            "num_epochs": t.get("epochs"), "learning_rate": t.get("learning_rate"),
            "max_steps": t.get("max_steps"), "output_dir": log.get("output_dir")}
    return {k: v for k, v in args.items() if v is not None}


def _pin_dataset_num_proc(n: int) -> None:
    """AlignTune 0.1.28 never forwards dataset_num_proc into the TRL SFTConfig, and unsloth's SFT
    trainer then tokenizes with cpu_count + 4 worker processes (39 on rs-epyc)."""
    from aligntune.core.sft import training_args_builder as tab

    build = tab.build_sft_config

    def pinned(*args, **kwargs):
        cfg = build(*args, **kwargs)
        cfg.dataset_num_proc = n
        return cfg

    tab.build_sft_config = pinned  # sft.py imports it at call time, so the module attribute is enough


def step_line(step: int, max_steps: int, logs: dict) -> str | None:
    """One greppable progress line per logged step: `step N/M loss X [reward R]`."""
    if "loss" not in logs:
        return None
    keys = ("reward", "rewards/gst_recon_grpo/mean", "rewards/registry_gst_recon_grpo/mean")
    reward = next((logs[k] for k in keys if k in logs), None)
    return f"step {step}/{max_steps} loss {float(logs['loss']):.4f}" + ("" if reward is None else f" reward {float(reward):.4f}")


SGLANG_ROLLOUT = "aligntune.backends.trl.rl.rollout.sglang_rollout"  # AlignTune fork, feat/sglang-rollout


def require_sglang_rollout(extras: dict) -> dict:
    """GRPO runs only on SGLang rollouts (user decision, no HF fallback). Stock AlignTune 0.1.28 takes
    rollout_backend and silently generates with HF, so refuse unless the fork's rollout is installed.
    Returns the kwargs with the weight-sync dir made absolute (the server resolves it from its own cwd)."""
    import importlib.util

    if extras.get("rollout_backend") != "sglang":
        raise SystemExit("GRPO must set gst_recon.rollout_backend: sglang (see configs/grpo_sglang.yaml)")
    try:
        found = importlib.util.find_spec(SGLANG_ROLLOUT) is not None
    except ModuleNotFoundError:  # a parent package (aligntune itself, or its rollout package) is missing
        found = False
    if not found:
        raise SystemExit(f"installed AlignTune has no SGLang rollout ({SGLANG_ROLLOUT}); install the fork ref")
    sync = Path(extras.get("sglang_sync_dir") or "").resolve()
    if not extras.get("sglang_sync_dir") or str(sync).startswith("/dev/shm"):
        raise SystemExit("set gst_recon.sglang_sync_dir to a disk path (never /dev/shm on shared hosts)")
    return {**extras, "sglang_sync_dir": str(sync)}


def _responses_only(trainer, parts: dict) -> None:
    """Loss on the assistant reply only: unsloth's train_on_responses_only sets prompt labels to -100.
    AlignTune 0.1.28's unsloth SFT flattens messages into one text, so without this ~75% of the
    gradient goes to reproducing the rendered documents."""
    setup = trainer.setup_trainer

    def setup_then_mask():
        setup()
        from unsloth_zoo.dataset_utils import train_on_responses_only

        trainer.trainer = train_on_responses_only(trainer.trainer, num_proc=1, **parts)

    trainer.setup_trainer = setup_then_mask  # train() calls self.setup_trainer(), so the instance attribute wins


def _add_step_log(trainer) -> None:
    from transformers import TrainerCallback

    class StepLog(TrainerCallback):
        def on_log(self, args, state, control, logs=None, **kwargs):
            line = step_line(state.global_step, state.max_steps, logs or {})
            if line:
                print(line, flush=True)

    callbacks = trainer.get_hf_callbacks  # both SFT and GRPO trainers build their HF callbacks from this
    trainer.get_hf_callbacks = lambda: [*callbacks(), StepLog()]


def cmd_run(a: argparse.Namespace) -> None:
    import faulthandler
    import signal

    faulthandler.register(signal.SIGUSR1)  # `kill -USR1 <pid>` prints every thread's stack (memory triage)
    cfg, extras = load_config(a.config)
    if cfg.get("backend") == "unsloth":
        import unsloth  # noqa: F401 - must precede transformers/trl/peft or its patches (incl. memory) are skipped

    from aligntune.core.backend_factory import create_rl_trainer, create_sft_trainer

    responses_only = extras.pop("train_on_responses_only", None)
    if "dataset_num_proc" in extras:
        _pin_dataset_num_proc(extras.pop("dataset_num_proc"))

    from gst_recon.train.reward import register

    register()
    is_sft = cfg.get("algo", "sft").lower() == "sft"
    make = create_sft_trainer if is_sft else create_rl_trainer
    extras = extras if is_sft else require_sglang_rollout(extras)
    trainer = make(config=cfg, **shadowed_args(cfg), **extras)
    # datasets fingerprints every .map() function by dill-pickling its closure. AlignTune 0.1.28's
    # unsloth SFT formatter closes over the trainer, so hashing it copied the whole model into host
    # RAM (42 GB, rs-epyc OOM on 2026-10-24). Hash the trainer by identity instead.
    type(trainer).__getstate__ = lambda self: {"trainer_id": id(self)}
    _add_step_log(trainer)
    if responses_only:
        _responses_only(trainer, responses_only)
    print(json.dumps(trainer.train(), indent=1, default=str))


def cmd_perdoc(a: argparse.Namespace) -> None:
    from gst_recon.render.tokens import count_tokens
    from gst_recon.train.perdoc import build_perdoc

    stats = build_perdoc(Path(a.rendered), [Path(t) for t in a.truth], Path(a.out), count_tokens)
    print(json.dumps(stats, indent=1))


def cmd_merge(a: argparse.Namespace) -> None:
    """Fold a LoRA adapter into its base model on the GPU (GRPO starts from the merged SFT model).
    1 GB shards keep the host-RAM staging of save_pretrained small."""
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    model = AutoModelForCausalLM.from_pretrained(a.base, dtype=torch.bfloat16, device_map="cuda", low_cpu_mem_usage=True)
    PeftModel.from_pretrained(model, a.adapter).merge_and_unload().save_pretrained(a.out, max_shard_size="1GB")
    AutoTokenizer.from_pretrained(a.adapter).save_pretrained(a.out)
    print(f"merged {a.adapter} into {a.base} -> {a.out}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m gst_recon.train")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("build", help="rendered cases -> raw and curated SFT/GRPO datasets")
    p.add_argument("--rendered", required=True)
    p.add_argument("--out", required=True)
    para_mode = p.add_mutually_exclusive_group(required=True)  # paraphrase is never skipped silently
    para_mode.add_argument("--teacher", help="OpenAI-compatible base URL of the SGLang teacher, e.g. http://localhost:30000/v1")
    para_mode.add_argument("--no-paraphrase", action="store_true",
                           help="build --rendered without teacher paraphrase (recorded in stats.json and the manifest)")
    p.add_argument("--keep-grpo", help="a previous build's curated grpo/train.jsonl: rows kept verbatim (their own "
                   "paraphrase), gated and deduplicated together with --rendered, listed first so duplicates drop the new case")
    p.add_argument("--teacher-model", default="teacher", help="served model name (infra/launch_teacher.sh)")
    p.add_argument("--judge-model", help="grounding judge (default: the teacher)")
    p.add_argument("--workers", type=int, default=32)
    p.add_argument("--grpo-max-prompt", type=int, default=b.GRPO_MAX_PROMPT)
    p.add_argument("--grpo-max-completion", type=int, default=b.GRPO_MAX_COMPLETION)
    p.add_argument("--sft-max-seq", type=int, default=b.SFT_MAX_SEQ)
    p.set_defaults(fn=cmd_build)
    r = sub.add_parser("run", help="train with AlignTune from a YAML config")
    r.add_argument("config")
    r.set_defaults(fn=cmd_run)
    d = sub.add_parser("perdoc", help="rendered SFT-role train cases + truth -> per-document SFT rows (hybrid mode)")
    d.add_argument("--rendered", required=True)
    d.add_argument("--truth", nargs="+", required=True, help="directories of truth Case JSON (<case_id>.json)")
    d.add_argument("--out", required=True)
    d.set_defaults(fn=cmd_perdoc)
    m = sub.add_parser("merge", help="fold a LoRA adapter into its base model (GPU)")
    m.add_argument("--base", required=True)
    m.add_argument("--adapter", required=True)
    m.add_argument("--out", required=True)
    m.set_defaults(fn=cmd_merge)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
