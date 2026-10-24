#!/usr/bin/env bash
# Launch the teacher on rs-epyc (run there). Idempotent: refuses if the tmux session exists.
# Usage: bash ~/gst-recon/launch_teacher.sh   (logs: ~/gst-recon/logs/sglang-teacher.log)
set -euo pipefail
ROOT=$HOME/gst-recon
MODEL=${MODEL:-Qwen/Qwen3-30B-A3B-Instruct-2507-FP8}
PORT=${PORT:-30000}
MEMFRAC=${MEMFRAC:-0.62}   # 0.62 * 95.8 GB = ~59 GB static (weights 31 GB + KV pool)
tmux has-session -t teacher 2>/dev/null && { echo "tmux session 'teacher' already running"; exit 1; }
tmux new-session -d -s teacher "
  export HF_HOME=$ROOT/hf HF_HUB_OFFLINE=1 CUDA_HOME=/usr/local/cuda-12.9 PATH=$ROOT/venv-sglang/bin:/usr/local/cuda-12.9/bin:\$PATH
  cd $ROOT && exec $ROOT/venv-sglang/bin/python -m sglang.launch_server \
    --model-path $MODEL --served-model-name teacher \
    --host 127.0.0.1 --port $PORT --mem-fraction-static $MEMFRAC \
    --context-length 16384 --max-running-requests 128 --grammar-backend xgrammar \
    --tp-size 1 >> $ROOT/logs/sglang-teacher.log 2>&1"
echo "launched; tail -f $ROOT/logs/sglang-teacher.log"
