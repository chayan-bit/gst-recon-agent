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
    if "dryrun" not in path.name:  # the GPU training configs
        assert args["max_seq_length"] >= 10240 and extras["gradient_checkpointing"] is True
    assert not set(args) & set(extras)


def test_step_line_format():
    assert step_line(3, 40, {"loss": 0.81234, "learning_rate": 1e-4}) == "step 3/40 loss 0.8123"
    assert step_line(5, 300, {"loss": 0.1, "reward": 0.4567}) == "step 5/300 loss 0.1000 reward 0.4567"
    assert step_line(7, 40, {"train_runtime": 10.0}) is None


def test_grpo_refuses_anything_but_sglang_rollouts(monkeypatch, tmp_path):
    import importlib.util

    from gst_recon.train.__main__ import require_sglang_rollout

    ok = {"rollout_backend": "sglang", "sglang_sync_dir": "runs/sync"}
    for bad in ({}, {**ok, "rollout_backend": "hf"}, {**ok, "sglang_sync_dir": "/dev/shm/x"}, {**ok, "sglang_sync_dir": ""}):
        monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
        with pytest.raises(SystemExit):
            require_sglang_rollout(bad)
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)  # stock AlignTune: silent HF fallback
    with pytest.raises(SystemExit, match="no SGLang rollout"):
        require_sglang_rollout(ok)
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    monkeypatch.chdir(tmp_path)
    assert require_sglang_rollout(ok)["sglang_sync_dir"] == str(tmp_path.resolve() / "runs/sync")


def test_every_grpo_config_uses_sglang_rollouts():
    pytest.importorskip("yaml")
    grpo = [p for p in CONFIGS if load_config(str(p))[0]["algo"] == "grpo"]
    assert grpo and all(load_config(str(p))[1]["rollout_backend"] == "sglang" for p in grpo)
