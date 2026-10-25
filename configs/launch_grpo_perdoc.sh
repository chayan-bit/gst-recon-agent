#!/usr/bin/env bash
# Per-document GRPO on the shared H100 host (configs/grpo_perdoc.yaml) through configs/launch_grpo.sh, from a per-document SFT
# adapter that must carry a SHA256SUMS (the bf16 copies do). Needs >= 60 GB GPU free; else launch_grpo_perdoc_small.sh.
#   PERDOC_ADAPTER=~/gst-recon/adapters/perdoc-v2 tmux new-session -d -s grpo 'bash ~/gst-recon/repo/configs/launch_grpo_perdoc.sh'
# The data (data/train/curated/grpo-perdoc) and the adapter are copied from the 16 GB host first.
set -u
: "${PERDOC_ADAPTER:?set PERDOC_ADAPTER to the per-document adapter dir (v2 if it is not worse than v1, else v1)}"
CONFIG=configs/grpo_perdoc.yaml DATA=data/train/curated/grpo-perdoc INIT_ADAPTER=runs/grpo-perdoc-init \
  INIT_FROM="$PERDOC_ADAPTER" CONTEXT=6144 MEMFRAC=0.30 MAX_RUNNING=64 GPU_MIN_MIB=60000 TRAINER_MIN_MIB=26000 \
  exec bash "$(dirname "$0")/launch_grpo.sh"
