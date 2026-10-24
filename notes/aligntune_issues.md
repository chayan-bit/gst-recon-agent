# AlignTune 0.1.28 findings and their upstream pull requests

Status of each item (all pull requests are open, none merged, at the time of writing):

| Item | Status |
|---|---|
| 1. Unsloth SFT dataset fingerprint pickles the trainer | AlignTune PR #33 https://github.com/Lexsi-Labs/aligntune/pull/33 |
| 2. Config values replaced by factory defaults | AlignTune PR #34 https://github.com/Lexsi-Labs/aligntune/pull/34 |
| 3. Train keys dropped by the YAML parser | AlignTune PR #35 https://github.com/Lexsi-Labs/aligntune/pull/35 |
| 4. `gradient_checkpointing="unsloth"` offloads activations to host RAM | not a bug, a documented default; no PR |

AlignTune PR #32 https://github.com/Lexsi-Labs/AlignTune/pull/32 is the SGLang rollout backend for GRPO, a feature rather than one of the items below.
Found while training Qwen3-4B-Instruct-2507 with LoRA through `create_sft_trainer(config=...)` with `backend: unsloth` on an H100.
The environment was transformers 5.20.2, trl 1.7.1, datasets 5.1.0, unsloth 2026.7.2, peft 0.21.2 and torch 2.9.1+cu128.
Every reproduction below uses a public model and a 4-row dataset.
The symptoms (the 42.7 GB RSS, the stack trace, 39 tokenizer processes, 512-token truncation, the adapter in ./output) were observed in our runs.
The scripts below were reconstructed from the 0.1.28 source and may need adjusting (attribute paths such as `t.config.train`); the reproductions that were actually run are in the pull requests, for example #33, which reproduces the host-RAM growth as +6.96 GB on a 0.5B model.

Shared setup for the reproductions:

```python
# repro_common.py
import json, os
os.makedirs("toy/sft", exist_ok=True)
with open("toy/sft/train.jsonl", "w") as f:
    for i in range(4):
        f.write(json.dumps({"messages": [{"role": "user", "content": f"say {i}"},
                                         {"role": "assistant", "content": str(i)}]}) + "\n")

BASE = {
    "algo": "sft", "backend": "unsloth",
    "model": {"name_or_path": "Qwen/Qwen2.5-0.5B-Instruct", "precision": "bf16", "max_seq_length": 4096,
              "use_peft": True, "lora_r": 16, "lora_alpha": 32},
    "datasets": [{"name": "toy/sft", "split": "train", "task_type": "sft"}],
    "train": {"max_steps": 2, "per_device_batch_size": 1, "learning_rate": 1e-4, "epochs": 1},
    "logging": {"output_dir": "runs/toy", "loggers": []},
}
```

---

## 1. Unsloth SFT: dataset fingerprinting pickles the whole trainer (and model) into host RAM

Status: AlignTune PR #33.

**Summary.**
`UnslothSFTTrainer.setup_trainer()` formats `messages` with `dataset.map(formatting_prompts_func, batched=True)`.
`formatting_prompts_func` is a closure over `self`, the trainer.
`datasets` fingerprints every `map` transform by dill-pickling the function including its closure (`datasets.fingerprint.update_fingerprint` calls `Hasher.update(transform)`), and this happens whether or not caching is enabled.
Pickling `self` walks into `self.model`, and `datasets.utils._dill._save_torchTensor` copies every parameter to CPU to hash it.
With Qwen3-4B in bf16 already on the GPU, the process reached 42.7 GB of resident host memory within five minutes.
It took a shared 251 GB host into swap and the OOM killer.

**Reproduction.**

```python
import signal, faulthandler, resource
from repro_common import BASE
from aligntune.core.backend_factory import create_sft_trainer

faulthandler.register(signal.SIGUSR1)  # kill -USR1 <pid> while host RSS climbs: the main thread is in dill/_save_torchTensor
trainer = create_sft_trainer(config=BASE)
trainer.train()
print("peak host RSS GB", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6)
```

With `Qwen/Qwen2.5-0.5B-Instruct` the extra host memory is about one model copy, around 1-2 GB.
It scales with model size and was 42 GB for a 4B model.

**Expected.**
Host memory stays near the size of the tokenizer and dataset, because the model lives on the GPU.

**Suggested fix.**
Do not capture `self` in the mapped function.
For example, bind the tokenizer only (`tok = self.tokenizer`, then refer to `tok` in the closure), or pass `new_fingerprint=` explicitly to `dataset.map`.
Our workaround makes the trainer hash by identity: `type(trainer).__getstate__ = lambda self: {"id": id(self)}`.

---

## 2. Config values silently replaced by factory defaults (max_seq_length 512, batch size 4, output_dir ./output)

Status: AlignTune PR #34.

**Summary.**
`create_sft_trainer(config=...)` and `create_rl_trainer(config=...)` parse the YAML or dict into `kwargs`.
Several values are then taken from the factory's own keyword parameters, which keep their defaults: `max_seq_length=512`, `batch_size=4`, `num_epochs=3`, `learning_rate=2e-4`, `output_dir="./output"` and, for RL, `max_steps=-1`.
The parsed values are ignored without any warning.
In our run this meant 512-token truncation of 12k-token examples, a batch size of 4 instead of 1, and the final adapter written to `./output` instead of `logging.output_dir`.
The intermediate checkpoints did go to the configured directory, which makes the problem easy to miss.
Our loss fell to 0.006 because the model memorised the 512-token prefixes.

**Reproduction.**

```python
from repro_common import BASE
from aligntune.core.backend_factory import create_sft_trainer

t = create_sft_trainer(config=BASE)
print(t.config.model.max_seq_length, t.config.train.per_device_batch_size, t.config.logging.output_dir)
# prints: 512 4 ./output        expected: 4096 1 runs/toy
```

**Expected.**
Values from `config` win over factory defaults, and explicit keyword arguments win over both.
The factory parameters could default to `None` so that "not given" can be told apart from "given".

**Workaround.**
Pass them again explicitly: `create_sft_trainer(config=cfg, max_seq_length=..., batch_size=..., num_epochs=..., learning_rate=..., output_dir=...)`.

---

## 3. Train keys dropped by the YAML parser: gradient_checkpointing, optimizer, lr_scheduler, dataloader_num_workers, dataset_num_proc

Status: AlignTune PR #35.

**Summary.**
`aligntune.utils.config_utils.parse_config_to_unified` copies a fixed list of `train:` keys.
`gradient_checkpointing`, `optimizer`, `lr_scheduler`, `dataloader_num_workers`, `mask_truncated_completions` and `dataset_num_proc` are not on that list, so they are dropped silently.
In `create_sft_trainer`, `SFTTrainingConfig(gradient_checkpointing=kwargs.get('gradient_checkpointing', False))` then defaults to False.
`model.gradient_checkpointing: true` is parsed into `use_gradient_checkpointing`, which the unsloth SFT path never reads.
`peft/lora.py` passes `getattr(train_config, 'gradient_checkpointing', "unsloth")` to `FastLanguageModel.get_peft_model`, so it receives False.
**A config that asks for gradient checkpointing trains without it**, and the optimizer falls back to `adamw_torch`.

Separately, `training_args_builder.build_sft_config` never forwards `dataset_num_proc` into `trl.SFTConfig`.
Unsloth's SFT trainer then picks `cpu_count + 4` tokenizer processes, which was 39 on our host.
Each one forks a CUDA-initialised parent.

**Reproduction.**

```python
from repro_common import BASE
from aligntune.core.backend_factory import create_sft_trainer

cfg = {**BASE, "model": {**BASE["model"], "gradient_checkpointing": True},
       "train": {**BASE["train"], "gradient_checkpointing": True, "optimizer": "adamw_8bit",
                 "dataloader_num_workers": 0, "dataset_num_proc": 1}}
t = create_sft_trainer(config=cfg)
print(t.config.train.gradient_checkpointing, t.config.train.optimizer, t.config.train.dataset_num_proc)
# prints: False adamw_torch None    expected: True adamw_8bit 1
t.train()  # log shows "Unsloth: Tokenizing ["text"] (num_proc=<cpu_count+4>)"
```

**Expected.**
Either pass every `train:` key through (unknown keys go to `extra_params`), or reject unknown keys with an error.
The gradient-checkpointing default should match the documented default (True), and `dataset_num_proc` should reach `SFTConfig`.

**Workaround.**
Pass these keys as keyword arguments to `create_sft_trainer` (`gradient_checkpointing=True`, `optimizer=...`).
For `dataset_num_proc`, wrap `build_sft_config` and set `cfg.dataset_num_proc` on the result.

---

## 4. Note: unsloth gradient_checkpointing="unsloth" offloads activations to host RAM

Status: not a bug, a documented default; no PR.

This is less a bug than a missing warning.
When `train.gradient_checkpointing` is absent from the train config object, `peft/lora.py` defaults to `"unsloth"`.
That mode offloads activations to pinned host memory, which cannot be swapped.
It grows with sequence length times layer count.
On shared hosts this is a surprising default.
We suggest defaulting to `True` (standard checkpointing) and documenting `"unsloth"` as an opt-in for single-tenant machines.
