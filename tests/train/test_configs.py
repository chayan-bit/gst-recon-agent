from pathlib import Path

import pytest

from gst_recon.train.__main__ import load_config, shadowed_args, step_line

CONFIGS = sorted(Path(__file__).resolve().parents[2].joinpath("configs").glob("*.yaml"))


@pytest.mark.parametrize("path", CONFIGS, ids=lambda p: p.name)
def test_configs_restate_values_aligntune_would_shadow(path):
    pytest.importorskip("yaml")
    cfg, extras = load_config(str(path))
    args = shadowed_args(cfg)
    assert args["max_seq_length"] == cfg["model"]["max_seq_length"]
    assert args["batch_size"] == cfg["train"]["per_device_batch_size"]
    assert args["output_dir"] == cfg["logging"]["output_dir"]
    assert extras["dataloader_num_workers"] == 0
    # restated, not AlignTune's 512 default; per-document rows are short, whole cases need >= 10k
    assert args["max_seq_length"] >= (4096 if "perdoc" in path.name else 10240)
    assert extras["gradient_checkpointing"] is True
    assert not set(args) & set(extras)


def test_step_line_format():
    assert step_line(3, 40, {"loss": 0.81234, "learning_rate": 1e-4}) == "step 3/40 loss 0.8123"
    assert step_line(5, 300, {"loss": 0.1, "reward": 0.4567}) == "step 5/300 loss 0.1000 reward 0.4567"
    assert step_line(7, 40, {"train_runtime": 10.0}) is None


def test_grpo_refuses_anything_but_sglang_rollouts(monkeypatch, tmp_path):
    import importlib.util

    from gst_recon.train.__main__ import require_sglang_rollout

    ok = {"rollout_backend": "sglang", "sglang_server_url": "http://127.0.0.1:30001", "sglang_sync_dir": "runs/sync"}
    bad = ({}, {**ok, "rollout_backend": "hf"}, {**ok, "sglang_sync_dir": "/dev/shm/x"}, {**ok, "sglang_sync_dir": ""},
           {**ok, "sglang_server_url": ""})
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    for train in bad:
        with pytest.raises(SystemExit):
            require_sglang_rollout(train)
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)  # stock AlignTune: silent HF fallback
    with pytest.raises(SystemExit, match="no SGLang rollout"):
        require_sglang_rollout(ok)
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    monkeypatch.chdir(tmp_path)
    kwargs = require_sglang_rollout(ok)  # forwarded as kwargs, which override the parsed YAML in create_rl_trainer
    assert kwargs == {**ok, "sglang_sync_dir": str(tmp_path.resolve() / "runs/sync")}


def test_every_grpo_config_uses_sglang_rollouts():
    pytest.importorskip("yaml")
    grpo = [load_config(str(p))[0] for p in CONFIGS if load_config(str(p))[0]["algo"] == "grpo"]
    assert grpo and all(c["train"]["rollout_backend"] == "sglang" and c["backend"] == "trl" for c in grpo)


def test_mask_report_accepts_only_a_masked_prompt_prefix():
    from gst_recon.train.__main__ import mask_report

    assert mask_report([-100, -100, 7, 8]) == "MASK row0: 2 prompt tokens labelled -100, 2 reply tokens trained (4 total)"
    for bad in ([7, 8, 9], [-100, -100], [-100, 7, -100, 8]):
        with pytest.raises(SystemExit):
            mask_report(bad)
