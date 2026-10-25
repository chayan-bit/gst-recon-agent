#!/usr/bin/env bash
# Per-document GRPO, hard variant (configs/grpo_perdoc_hard.yaml), on the shared H100 host through configs/launch_grpo.sh:
# 1168 hard documents, 16 generations, completion cap 640, from perdoc-v2 (its SHA256SUMS must verify).
# Saves at 25-step intervals with bf16 snapshots; saves and stops by STOP_AT - 15 min, killed at STOP_AT - 2 min.
#   PERDOC_ADAPTER=~/gst-recon/adapters/perdoc-v2 tmux new-session -d -s grpo 'bash ~/gst-recon/repo-grpo/configs/launch_grpo_perdoc_hard.sh'
# Data (data/train/curated/grpo-perdoc-hard) and adapter are built on / copied from the 16 GB host.
set -u
export REPO=${REPO:-$(cd "$(dirname "$0")/.." && pwd)}  # this checkout (~/gst-recon/repo-grpo), not gst-eval's ~/gst-recon/repo
: "${PERDOC_ADAPTER:?set PERDOC_ADAPTER to the perdoc-v2 adapter dir}"
export ABORT_AVAIL_GB=${ABORT_AVAIL_GB:-4}  # run_guarded kills our run if the shared host stays under 4 GB available for 60 s
CONFIG=${CONFIG:-configs/grpo_perdoc_hard.yaml} DATA=${DATA:-data/train/curated/grpo-perdoc-hard} \
  INIT_ADAPTER=${INIT_ADAPTER:-runs/grpo-perdoc-init} \
  INIT_FROM="$PERDOC_ADAPTER" CONTEXT=2688 MEMFRAC=${MEMFRAC:-0.30} MAX_RUNNING=64 GPU_MIN_MIB=60000 TRAINER_MIN_MIB=26000 \
  MIN_AVAIL=10 STOP_AT=${STOP_AT:-00:30} exec bash "$(dirname "$0")/launch_grpo.sh"
