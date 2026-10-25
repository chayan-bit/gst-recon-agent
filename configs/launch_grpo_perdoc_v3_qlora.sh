#!/usr/bin/env bash
# Per-document GRPO v3 hard, QLoRA + FP8 rollout server, on the shared H100 host within 16 GB per job
# (configs/grpo_perdoc_v3_hard_qlora.yaml), through configs/launch_grpo.sh, from the pd3 adapter (SHA256SUMS must verify).
#   PERDOC_ADAPTER=~/gst-recon/adapters/perdoc-v3 STOP_AT=03:30 \
#     tmux new-session -d -s grpo 'bash ~/gst-recon/repo-grpo/configs/launch_grpo_perdoc_v3_qlora.sh'
# SERVER_QUANT= (empty) serves bf16 weights instead (~11.5 GB, still under 16) if FP8 + LoRA fails on sglang 0.5.10.
# Host RAM: start needs 10 GB available; run_guarded kills the run if available RAM stays under 6 GB for 60 s.
set -u
export REPO=${REPO:-$(cd "$(dirname "$0")/.." && pwd)}
: "${PERDOC_ADAPTER:?set PERDOC_ADAPTER to the pd3 adapter dir}"
export GST_GPU_CAP_GB=15 ABORT_AVAIL_GB=6 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
CONFIG=configs/grpo_perdoc_v3_hard_qlora.yaml DATA=data/train/curated/grpo-perdoc-v3-hard INIT_ADAPTER=runs/grpo-perdoc-v3-init \
  INIT_FROM="$PERDOC_ADAPTER" CONTEXT=2688 MEMFRAC=${MEMFRAC:-0.12} MAX_RUNNING=32 \
  SERVER_EXTRA="${SERVER_QUANT---quantization fp8} --max-total-tokens 16384" GPU_MIN_MIB=26000 TRAINER_MIN_MIB=16000 \
  MIN_AVAIL=10 STOP_AT=${STOP_AT:-03:30} exec bash "$(dirname "$0")/launch_grpo.sh"
