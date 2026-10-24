# Run in venv-align. 10-step SFT of Qwen2.5-0.5B-Instruct on the GPU (TRL backend).
import os
os.environ.setdefault("WANDB_MODE", "disabled")
from aligntune.core.backend_factory import create_sft_trainer

trainer = create_sft_trainer(
    model_name="Qwen/Qwen2.5-0.5B-Instruct", dataset_name="tatsu-lab/alpaca", backend="trl",
    output_dir="smoke/sft", num_epochs=1, max_steps=10, batch_size=4, learning_rate=2e-5,
    max_seq_length=512, max_samples=200, report_to="none",
)
trainer.train()
print("SFT DONE")
