#!/usr/bin/env bash
# Plan B: per-document GRPO on kratos' RTX 5070 Ti (configs/grpo_perdoc_kratos.yaml; the memory budget is there).
# QLoRA trainer + an FP8 SGLang rollout server on one 16 GB GPU. gst-hybrid's own SGLang server (port 30400,
# ~13.7 GB) must be stopped by gst-hybrid first: this script never touches it, it only waits for a free GPU.
#   bash ~/gst-recon-train/configs/launch_grpo_perdoc_kratos.sh setup    # once: builds .venv-grpo (network)
#   PERDOC_ADAPTER=... bash ~/gst-recon-train/configs/launch_grpo_perdoc_kratos.sh smoke   # server + rollout smoke only
#   PERDOC_ADAPTER=~/gst-recon-hybrid/adapters/perdoc-v2 \
#     tmux new-session -d -s grpo 'bash ~/gst-recon-train/configs/launch_grpo_perdoc_kratos.sh'
# STOP_AT (default 00:30, local time): the trainer saves and stops 15 min before it; everything is killed 1-2 min before.
# Both processes run under ~/bin/heavy-run (KRATOS_GPU=1: heavy.slice, MemoryMax 18G shared, no swap).
# Logs: ~/gst-recon-train/logs/grpo-perdoc-kratos.log, ~/gst-recon-train/logs/sglang-rollout-kratos.log.
set -u
ROOT=$HOME/gst-recon-train; LOG=$ROOT/logs/grpo-perdoc-kratos.log; CONFIG=configs/grpo_perdoc_kratos.yaml
HF=$HOME/gst-recon-hybrid/hf
BASE=$HF/hub/models--Qwen--Qwen3-4B-Instruct-2507/snapshots/cdbee75f17c01a7cc42f958dc650907174af0554
SGL=$HOME/sglang-rl/venv-sglang  # sglang 0.5.22 (the fork's adapter sync was tested on 0.5.10)
CU=$SGL/lib/python3.12/site-packages/nvidia/cu13
PY=$ROOT/.venv-grpo/bin/python
ALIGN_REF=5e987f3c89a144d7f96da6cdf6d90d95ef35b47d
PORT=30001; MEMFRAC=0.45; KV_TOKENS=12288
MODE=${1:-run}; STOP_AT=${STOP_AT:-00:30}
DATA=data/train/curated/grpo-perdoc; INIT=runs/grpo-perdoc-init
cd "$ROOT" || exit 1
mkdir -p logs
log() { echo "$(date +%T) $*" | tee -a "$LOG"; }
die() { log "ABORT: $*"; exit 3; }

if [ "$MODE" = setup ]; then  # torch cu128 for sm_120; the rest pinned to the rs-lab env that trains with this runner
  UV=$HOME/.local/bin/uv
  [ -x "$PY" ] || "$UV" venv --python 3.12 .venv-grpo || exit 1
  "$UV" pip install --python "$PY" torch==2.9.0 --index-url https://download.pytorch.org/whl/cu128 || exit 1
  "$UV" pip install --python "$PY" transformers==5.20.2 trl==1.7.1 peft==0.21.2 accelerate==1.15.0 datasets==5.1.0 \
    "bitsandbytes>=0.48" safetensors tensorboard evaluate pydantic pyyaml sentencepiece scikit-learn scipy pandas \
    rich psutil jsonschema lxml sqlglot msgspec immutables numpy pypdf python-docx || exit 1
  "$UV" pip install --python "$PY" --no-deps "aligntune @ git+https://github.com/chayan-bit/aligntune@$ALIGN_REF" || exit 1
  PYTHONPATH=$ROOT "$PY" -c "import torch, bitsandbytes, peft, trl; from aligntune.core.backend_factory import create_rl_trainer; \
import gst_recon.train.__main__; print('ok torch', torch.__version__, 'cuda', torch.version.cuda, 'bnb', bitsandbytes.__version__)"
  exit $?
fi

# preflight: adapter, data, envs, the GPU free of everyone (gst-hybrid stopped), host headroom
: "${PERDOC_ADAPTER:?set PERDOC_ADAPTER to the per-document adapter dir (v2 if it is not worse than v1, else v1)}"
(cd "$PERDOC_ADAPTER" && sha256sum -c --quiet SHA256SUMS) || die "adapter $PERDOC_ADAPTER fails SHA256SUMS"
ln -sfn "$PERDOC_ADAPTER" "$INIT"
[ -s "$DATA/train.jsonl" ] || die "no $DATA/train.jsonl"
[ -x "$PY" ] || die "no $PY: run '$0 setup' first"
grep -q "\"commit_id\":\"$ALIGN_REF\"" "$ROOT"/.venv-grpo/lib/python3.12/site-packages/aligntune-*.dist-info/direct_url.json \
  || die "AlignTune in .venv-grpo is not the fork at $ALIGN_REF"
tmux has-session -t sglang-rollout 2>/dev/null && die "tmux session sglang-rollout already exists"
pgrep -u "$USER" -f "[g]st_recon.train run" >/dev/null && die "a training run of ours is still running"
ss -ltn | grep -q ":$PORT " && die "port $PORT in use"
avail=$(free -g | awk '/Mem:/{print $7}'); gpu=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits)
disk=$(df -BG --output=avail ~ | tail -1 | tr -dc 0-9)
log "preflight avail=${avail}G gpu_free=${gpu}MiB disk=${disk}G load=$(cut -d' ' -f1 /proc/loadavg) cpus=$(nproc) init=$(readlink -f $INIT) rows=$(wc -l < $DATA/train.jsonl)"
nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader | tee -a "$LOG"
[ "$gpu" -ge 15000 ] || die "only ${gpu} MiB GPU free: the plan needs the whole card (is gst-hybrid's server still up?)"
[ "$avail" -ge 12 ] || die "only ${avail} GB host RAM available"
[ "$disk" -ge 8 ] || die "only ${disk} GB disk"
if [ "$MODE" = smoke ]; then left=1800; else
  end=$(date -d "$STOP_AT" +%s); [ "$end" -gt "$(date +%s)" ] || end=$((end + 86400))
  left=$((end - $(date +%s))); [ "$left" -gt 1800 ] || die "under 30 min to $STOP_AT"
fi

# 1. FP8 rollout server, KV capped, flags as gst-hybrid runs SGLang on this card
tmux new-session -d -s sglang-rollout -c "$ROOT" "KRATOS_GPU=1 KRATOS_GPU_MIN_FREE_MIB=15000 KRATOS_HEAVY_TIMEOUT=$((left - 60))s ~/bin/heavy-run env \
  HF_HOME=$HF HF_HUB_OFFLINE=1 TORCHINDUCTOR_COMPILE_THREADS=1 MALLOC_ARENA_MAX=2 CUDA_HOME=$CU PATH=$CU/bin:$SGL/bin:/usr/bin:/bin \
  python -m sglang.launch_server --model-path $BASE --quantization fp8 --host 127.0.0.1 --port $PORT \
  --mem-fraction-static $MEMFRAC --max-total-tokens $KV_TOKENS --enable-lora --max-lora-rank 32 --max-loras-per-batch 2 \
  --lora-target-modules q_proj k_proj v_proj o_proj gate_proj up_proj down_proj --context-length 6144 \
  --max-running-requests 8 --cuda-graph-max-bs 8 --grammar-backend xgrammar --attention-backend triton \
  --sampling-backend pytorch --skip-tokenizer-init >> $ROOT/logs/sglang-rollout-kratos.log 2>&1"
for _ in $(seq 90); do curl -sf "127.0.0.1:$PORT/health" >/dev/null && break; sleep 10; done
curl -sf "127.0.0.1:$PORT/health" >/dev/null || { tmux kill-session -t sglang-rollout; die "rollout server not healthy after 15 min"; }
gfree=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits)
log "rollout server up: $(nvidia-smi --query-gpu=memory.used --format=csv,noheader) used, ${gfree} MiB left"
[ "$gfree" -ge 6500 ] || { tmux kill-session -t sglang-rollout; die "only ${gfree} MiB left for the ~5.8 GiB trainer"; }

if [ "$MODE" = smoke ]; then  # the fork's client against this server: LoRA load, constrained request, sync, group
  HF_HOME=$HF HF_HUB_OFFLINE=1 PYTHONPATH=$ROOT timeout 15m "$PY" -m gst_recon.train.smoke_rollout \
    "http://127.0.0.1:$PORT" "$INIT/" "$DATA/train.jsonl" "$BASE" 2>&1 | grep -v WARNING | tee -a "$LOG"
  rc=${PIPESTATUS[0]}
  tmux kill-session -t sglang-rollout
  log "SMOKE rc=$rc"; exit "$rc"
fi

# 2. QLoRA trainer under the host-RAM watchdog until STOP_AT: saves and stops 15 min before, killed 2 min before
left=$((end - $(date +%s)))
hours=$(awk -v s="$left" 'BEGIN { printf "%.3f", (s - 900) / 3600 }')
log "trainer until $STOP_AT: save-then-stop after ${hours} h, hard stop in $(( (left - 120) / 60 )) min"
timeout -s TERM $((left - 120)) env KRATOS_GPU=1 KRATOS_GPU_MIN_FREE_MIB=6000 KRATOS_HEAVY_TIMEOUT=$((left - 60))s ~/bin/heavy-run env \
  HF_HOME=$HF PYTHONPATH=$ROOT PYTHON=$PY MODEL=$BASE UNSLOTH_RETURN_LOGITS=1 GST_MAX_HOURS=$hours CAP_GB=10 DUMP_GB=8 \
  MIN_AVAIL_GB=12 bash configs/run_guarded.sh "$CONFIG" >> "$LOG" 2>&1
rc=$?

# 3. cleanup: stop our server and drop the adapter sync dir; checkpoints stay
tmux kill-session -t sglang-rollout
rm -rf "$ROOT/runs/grpo-sync"
log "DONE rc=$rc$([ $rc = 124 ] && echo ' (outer timeout)') checkpoints: $(cd runs/grpo-perdoc-kratos 2>/dev/null && echo checkpoint-*)"
