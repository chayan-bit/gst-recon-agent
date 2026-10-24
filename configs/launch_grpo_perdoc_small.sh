#!/usr/bin/env bash
# Small per-document GRPO on a shared H100 (configs/grpo_perdoc_small.yaml): a ~12 GiB rollout server (KV capped at
# 24576 tokens, 16 running requests, 2 LoRA slots) and a ~13 GiB trainer. Needs >= 28 GB GPU free.
#   PERDOC_ADAPTER=~/gst-recon/adapters/perdoc-v2 tmux new-session -d -s grpo 'bash ~/gst-recon/repo/configs/launch_grpo_perdoc_small.sh'
# mem_fraction_static is set from the GPU memory free right now to cover the weights plus the capped KV (11.6 GiB
# with slack), as in launch_grpo_small.sh; --max-total-tokens caps the KV.
set -u
: "${PERDOC_ADAPTER:?set PERDOC_ADAPTER to the per-document adapter dir (v2 if it is not worse than v1, else v1)}"
free_mib=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits)
MEMFRAC=$(awk -v f="$free_mib" 'BEGIN { x = 11.6 * 1024 / f; x = int(x * 100 + 0.999) / 100; print (x > 0.9 ? 0.9 : x) }')
CONFIG=configs/grpo_perdoc_small.yaml DATA=data/train/curated/grpo-perdoc INIT_ADAPTER=runs/grpo-perdoc-init \
  INIT_FROM="$PERDOC_ADAPTER" CONTEXT=6144 MEMFRAC=$MEMFRAC MAX_RUNNING=16 GPU_MIN_MIB=28000 TRAINER_MIN_MIB=13500 \
  SERVER_EXTRA="--max-total-tokens 24576 --max-loras-per-batch 2" \
  exec bash "$(dirname "$0")/launch_grpo.sh"
