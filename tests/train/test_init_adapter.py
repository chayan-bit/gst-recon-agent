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
