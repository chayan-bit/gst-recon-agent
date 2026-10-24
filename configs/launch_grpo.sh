#!/usr/bin/env bash
# GRPO on rs-epyc (configs/grpo_sglang.yaml): start the SGLang rollout server (base snapshot + LoRA slots),
# wait for health, then the trainer under run_guarded (CAP_GB=8, abort below 8 GB available).
# The runner stops at 3 h wall clock after saving (gst_recon.max_hours); an outer timeout of 3 h 15 m is the
# backstop. Adapters are saved every 50 steps (save_total_limit 2) to ~/gst-recon/runs/grpo-sglang.
#   tmux new-session -d -s grpo 'bash ~/gst-recon/repo/configs/launch_grpo.sh'
# Logs: ~/gst-recon/logs/grpo.log (`step N/M loss X reward Y`, and the s/step of the first 5 steps),
#       ~/gst-recon/logs/sglang-rollout.log.
set -u
ROOT=$HOME/gst-recon; REPO=$ROOT/repo; LOG=$ROOT/logs/grpo.log
BASE=$ROOT/hf/hub/models--Qwen--Qwen3-4B-Instruct-2507/snapshots/cdbee75f17c01a7cc42f958dc650907174af0554
ALIGN_PY=$ROOT/venv-align/bin/python    # AlignTune fork ef217fc (installed 2026-10-24)
SGLANG_PY=$ROOT/venv-sglang/bin/python  # sglang 0.5.10.post1
PORT=30001; MEMFRAC=0.45                # must match configs/grpo_sglang.yaml (sglang_server_url, budget)
cd "$REPO" || exit 1
export HF_HOME=$ROOT/hf
[ -e runs ] || ln -s "$ROOT/runs" runs
log() { echo "$(date +%T) $*" | tee -a "$LOG"; }
die() { log "ABORT: $*"; exit 3; }

# preflight: the eval server stopped, nothing of ours on the GPU, headroom, the fork, the SFT adapter
[ -f runs/sft-curated/adapter_model.safetensors ] || die "no SFT adapter in runs/sft-curated"
[ -s data/train/curated/grpo-merged/train.jsonl ] || die "no data/train/curated/grpo-merged/train.jsonl"
tmux has-session -t sglang-rollout 2>/dev/null && die "tmux session sglang-rollout already exists"
pgrep -u "$USER" -f "[s]glang.launch_server" >/dev/null && die "an SGLang server of ours is still running (eval?)"
pgrep -u "$USER" -f "[g]st_recon.train run" >/dev/null && die "a training run of ours is still running"
ss -ltn | grep -q ":$PORT " && die "port $PORT in use"
grep -q "sglang_server_url: http://127.0.0.1:$PORT" configs/grpo_sglang.yaml || die "config does not point at port $PORT"
"$ALIGN_PY" -c "import importlib.util as u; assert u.find_spec('aligntune.backends.trl.rl.rollout.sglang_rollout')" 2>/dev/null \
  || die "AlignTune in $ALIGN_PY has no SGLang rollout"
avail=$(free -g | awk '/Mem:/{print $7}'); gpu=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits)
disk=$(df -BG --output=avail ~ | tail -1 | tr -dc 0-9)
log "preflight avail=${avail}G gpu_free=${gpu}MiB disk=${disk}G load=$(cut -d' ' -f1 /proc/loadavg) rows=$(wc -l < data/train/curated/grpo-merged/train.jsonl)"
nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader | tee -a "$LOG"
[ "$gpu" -ge 85000 ] || die "only ${gpu} MiB GPU free (plan: ~45 GiB server + ~25 GiB trainer)"
[ "$avail" -ge 8 ] || die "only ${avail} GB host RAM available"
[ "$disk" -ge 8 ] || die "only ${disk} GB disk (5 GB floor + 2 checkpoints + adapter sync)"

# 1. rollout server in its own tmux session (outside the trainer's process group and time box)
tmux new-session -d -s sglang-rollout "cd $REPO && HF_HOME=$ROOT/hf HF_HUB_OFFLINE=1 TORCHINDUCTOR_COMPILE_THREADS=1 MALLOC_ARENA_MAX=2 \
  exec $SGLANG_PY -m sglang.launch_server --model-path $BASE --host 127.0.0.1 --port $PORT --mem-fraction-static $MEMFRAC \
  --enable-lora --max-lora-rank 32 --lora-target-modules q_proj k_proj v_proj o_proj gate_proj up_proj down_proj \
  --context-length 10240 --max-running-requests 32 --cuda-graph-max-bs 32 --skip-tokenizer-init --sleep-on-idle \
  >> $ROOT/logs/sglang-rollout.log 2>&1"
for _ in $(seq 90); do curl -sf "127.0.0.1:$PORT/health" >/dev/null && break; sleep 10; done
curl -sf "127.0.0.1:$PORT/health" >/dev/null || { tmux kill-session -t sglang-rollout; die "rollout server not healthy after 15 min"; }
log "rollout server up: $(nvidia-smi --query-gpu=memory.used --format=csv,noheader) used"

# 2. first-5-steps timing, printed once into the log
( t0=$(date +%s); until grep -q "^step 5/" "$LOG" 2>/dev/null; do sleep 30; pgrep -u "$USER" -f "[g]st_recon.train run" >/dev/null || exit; done
  log "first 5 steps: $(( ($(date +%s) - t0) / 5 )) s/step incl. model load (see step lines for the steady rate)" ) &

# 3. GRPO under the host-RAM watchdog; timeout signals its whole process group (run_guarded, trainer, children)
timeout -s TERM 195m env PYTHON="$ALIGN_PY" MODEL="$BASE" CAP_GB=8 DUMP_GB=6 MIN_AVAIL_GB=8 \
  bash configs/run_guarded.sh configs/grpo_sglang.yaml >> "$LOG" 2>&1
rc=$?

# 4. cleanup: stop the server and drop the adapter sync dir; checkpoints stay
tmux kill-session -t sglang-rollout
rm -rf "$ROOT/runs/grpo-sync"
log "DONE rc=$rc$([ $rc = 124 ] && echo ' (outer timeout)') checkpoints: $(cd runs/grpo-sglang 2>/dev/null && echo checkpoint-*)"
