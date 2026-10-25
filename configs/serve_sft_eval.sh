#!/usr/bin/env bash
# Post-SFT eval server on the shared H100 host (run there, after `DONE rc=0` in ~/gst-recon/logs/sft_full.log).
# One SGLang server, two models: request model "base" for base Qwen3-4B-Instruct-2507 and "base:sft"
# for base + the SFT LoRA (SGLang's base:adapter syntax), so the eval worker runs base vs SFT on
# one endpoint. Logs: ~/gst-recon/logs/sglang-sft-eval.log. Stop: tmux kill-session -t sft-eval.
#   bash ~/gst-recon/repo/configs/serve_sft_eval.sh
# GPU (95830 MiB, nothing else of ours on it): 0.80 of ~93 GiB free = ~74 GiB static, which is 7.5 GiB
# of weights + ~67 GiB of KV at 144 KiB/token = ~480k tokens (64 concurrent x 7.5k). The ~18 GiB
# outside the fraction holds CUDA graphs, LoRA buffers and activations. Host RAM ~5 GB (one compile thread).
set -euo pipefail
ROOT=$HOME/gst-recon
BASE=${BASE:-$ROOT/hf/hub/models--Qwen--Qwen3-4B-Instruct-2507/snapshots/cdbee75f17c01a7cc42f958dc650907174af0554}
ADAPTER=${ADAPTER:-$ROOT/runs/sft-curated}
PORT=${PORT:-30000}        # the teacher's port, so existing client configuration works unchanged
MEMFRAC=${MEMFRAC:-0.80}
CONTEXT=${CONTEXT:-32768}  # longest built SFT row is ~18k tokens; eval cases come from the same renderer

tmux has-session -t sft-eval 2>/dev/null && { echo "ABORT: tmux session 'sft-eval' already running"; exit 1; }
grep -q "^DONE rc=0" $ROOT/logs/sft_full.log || { echo "ABORT: SFT has not finished cleanly"; exit 1; }
[ -f $ADAPTER/adapter_model.safetensors ] || { echo "ABORT: no adapter in $ADAPTER"; exit 1; }
ss -ltn | grep -q ":$PORT " && { echo "ABORT: port $PORT in use"; exit 1; }
avail=$(free -g | awk '/Mem:/{print $7}'); gpu=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits)
echo "preflight avail=${avail}G gpu_free=${gpu}MiB disk=$(df -h ~ | awk 'END{print $4}') load=$(cut -d' ' -f1 /proc/loadavg)"
[ "$avail" -ge 8 ] || { echo "ABORT: only ${avail} GB host RAM available"; exit 3; }
[ "$gpu" -ge 85000 ] || { echo "ABORT: only ${gpu} MiB GPU free"; exit 3; }

tmux new-session -d -s sft-eval "
  export HF_HOME=$ROOT/hf HF_HUB_OFFLINE=1 TORCHINDUCTOR_COMPILE_THREADS=1 MALLOC_ARENA_MAX=2 CUDA_HOME=/usr/local/cuda-12.9 PATH=$ROOT/venv-sglang/bin:/usr/local/cuda-12.9/bin:\$PATH
  cd $ROOT && exec $ROOT/venv-sglang/bin/python -m sglang.launch_server \
    --model-path $BASE --served-model-name base \
    --enable-lora --lora-paths sft=$ADAPTER --max-lora-rank 32 --lora-target-modules all --max-loras-per-batch 2 \
    --host 127.0.0.1 --port $PORT --mem-fraction-static $MEMFRAC --context-length $CONTEXT \
    --max-running-requests 64 --grammar-backend xgrammar --tp-size 1 >> $ROOT/logs/sglang-sft-eval.log 2>&1"
echo "launched; wait for 'The server is fired up' in $ROOT/logs/sglang-sft-eval.log, then:"
echo "  curl -s 127.0.0.1:$PORT/v1/chat/completions -H 'Content-Type: application/json' -d '{\"model\":\"base:sft\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"max_tokens\":8}'"
echo "  eval: python -m gst_recon.eval run --endpoint http://127.0.0.1:$PORT/v1 --model base:sft   (and --model base)"
