from pathlib import Path

import pytest

from gst_recon.train.__main__ import load_config, shadowed_args

CONFIGS = sorted(Path(__file__).resolve().parents[2].joinpath("configs").glob("*.yaml"))


@pytest.mark.parametrize("path", CONFIGS, ids=lambda p: p.name)
def test_configs_restate_values_aligntune_would_shadow(path):
    pytest.importorskip("yaml")
    cfg, extras = load_config(str(path))
    args = shadowed_args(cfg)
    assert args["max_seq_length"] == cfg["model"]["max_seq_length"] >= 10240
    assert args["batch_size"] == cfg["train"]["per_device_batch_size"]
    assert args["output_dir"] == cfg["logging"]["output_dir"]
    assert extras["gradient_checkpointing"] is True and extras["dataloader_num_workers"] == 0
    assert not set(args) & set(extras)
