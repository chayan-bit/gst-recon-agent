#!/usr/bin/env bash
# Small GRPO on a shared H100 (configs/grpo_sglang_small.yaml): configs/launch_grpo.sh with a ~14 GiB rollout server
# (KV capped at 40960 tokens, 16 running requests, 2 LoRA slots) and a ~15 GiB trainer. Needs >= 32 GB GPU free.
#   tmux new-session -d -s grpo 'bash ~/gst-recon/repo/configs/launch_grpo_small.sh'
# SGLang 0.5.10.post1 sizes KV as free_after_load - free_before_load * (1 - mem_fraction_static), and
# --max-total-tokens caps it. So mem_fraction_static is set from the GPU memory free right now to cover the
# weights plus the capped KV (13.8 GiB with 0.4 GiB slack); the rest stays free for the trainer.
set -u
free_mib=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits)
MEMFRAC=$(awk -v f="$free_mib" 'BEGIN { x = 13.8 * 1024 / f; x = int(x * 100 + 0.999) / 100; print (x > 0.9 ? 0.9 : x) }')
CONFIG=configs/grpo_sglang_small.yaml MEMFRAC=$MEMFRAC GPU_MIN_MIB=32000 TRAINER_MIN_MIB=15500 MAX_RUNNING=16 \
  SERVER_EXTRA="--max-total-tokens 40960 --max-loras-per-batch 2" \
  exec bash "$(dirname "$0")/launch_grpo.sh"
