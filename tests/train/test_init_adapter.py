"""GRPO starts from the SFT adapter: its weights land in the trainable LoRA that AlignTune attached."""

import types

import pytest

from gst_recon.train.__main__ import _init_from_adapter


def _peft_model(r: int, seed: int):
    torch = pytest.importorskip("torch")
    peft = pytest.importorskip("peft")
    transformers = pytest.importorskip("transformers")
    torch.manual_seed(seed)
    cfg = transformers.LlamaConfig(vocab_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2,
                                   num_attention_heads=4, num_key_value_heads=2)
    lora = peft.LoraConfig(r=r, lora_alpha=2 * r, target_modules=["q_proj", "v_proj"], init_lora_weights=False)
    return peft.get_peft_model(transformers.LlamaForCausalLM(cfg), lora)


def test_saved_adapter_becomes_the_trainable_lora(tmp_path):
    saved = _peft_model(4, seed=1)
    saved.save_pretrained(tmp_path)
    trainer = types.SimpleNamespace(model=None)
    trainer.setup_model = lambda: setattr(trainer, "model", _peft_model(4, seed=2))  # fresh LoRA, other weights
    _init_from_adapter(trainer, str(tmp_path))
    trainer.setup_model()
    want = {k: v for k, v in saved.state_dict().items() if "lora_" in k}
    got = trainer.model.state_dict()
    assert want and all((got[k] == v).all() for k, v in want.items())
    assert all(p.requires_grad for n, p in trainer.model.named_parameters() if "lora_" in n)


def test_mismatched_lora_is_refused(tmp_path):
    _peft_model(4, seed=1).save_pretrained(tmp_path)
    trainer = types.SimpleNamespace(model=None)
    trainer.setup_model = lambda: setattr(trainer, "model", _peft_model(8, seed=2))
    _init_from_adapter(trainer, str(tmp_path))
    with pytest.raises(SystemExit, match="does not match"):
        trainer.setup_model()


def test_bf16_snapshot_casts_weights_and_writes_checksums_last(tmp_path):
    import hashlib

    torch = pytest.importorskip("torch")
    from safetensors.torch import load_file, save_file

    from gst_recon.train.__main__ import bf16_snapshot

    src = tmp_path / "checkpoint-40"
    src.mkdir()
    save_file({"a.lora_A.weight": torch.randn(4, 8), "step": torch.tensor([3])}, str(src / "adapter_model.safetensors"))
    config = b'{"r": 4}'
    (src / "adapter_config.json").write_bytes(config)

    sha = bf16_snapshot(src, tmp_path / "out" / "step-40")

    out = tmp_path / "out" / "step-40"
    w = load_file(str(out / "adapter_model.safetensors"))
    assert w["a.lora_A.weight"].dtype == torch.bfloat16 and w["step"].dtype == torch.int64
    assert sha == hashlib.sha256((out / "adapter_model.safetensors").read_bytes()).hexdigest()
    lines = (out / "SHA256SUMS").read_text().splitlines()
    assert lines == [f"{sha}  adapter_model.safetensors",
                     f"{hashlib.sha256(config).hexdigest()}  adapter_config.json"]
