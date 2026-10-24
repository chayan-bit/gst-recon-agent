#!/usr/bin/env bash
# GRPO on rs-epyc (configs/grpo_sglang.yaml): start the SGLang rollout server (base snapshot + LoRA slots),
# wait for health, then the trainer under run_guarded (CAP_GB=8, abort below 12 GB available).
# Rollouts are unconstrained (no JSON-schema grammar), capped at max_completion_length 4096; the reward expands
# the compact output form (tests/train/test_reward_plugin_compact.py).
# The runner stops at 3 h wall clock after saving (gst_recon.max_hours); an outer timeout of 3 h 15 m is the
# backstop. Adapters are saved every 50 steps (save_total_limit 2) to ~/gst-recon/runs/grpo-sglang.
#   tmux new-session -d -s grpo 'bash ~/gst-recon/repo/configs/launch_grpo.sh'
# configs/launch_grpo_small.sh and launch_grpo_perdoc{,_small}.sh reuse this with their config, data, initial
# adapter and server size (env overrides below).
# Logs: ~/gst-recon/logs/grpo.log (`step N/M loss X reward Y`, and the s/step of the first 5 steps),
#       ~/gst-recon/logs/sglang-rollout.log.
set -u
ROOT=$HOME/gst-recon; REPO=$ROOT/repo; LOG=$ROOT/logs/grpo.log
BASE=$ROOT/hf/hub/models--Qwen--Qwen3-4B-Instruct-2507/snapshots/cdbee75f17c01a7cc42f958dc650907174af0554
ALIGN_PY=$ROOT/venv-align/bin/python    # AlignTune fork at ALIGN_REF, installed with:
# uv pip install --python $ALIGN_PY --no-deps "aligntune @ git+https://github.com/chayan-bit/aligntune@$ALIGN_REF"
ALIGN_REF=5e987f3c89a144d7f96da6cdf6d90d95ef35b47d  # ef217fc + unique per-run adapter names (restart-safe)
SGLANG_PY=$ROOT/venv-sglang/bin/python  # sglang 0.5.10.post1
CONFIG=${CONFIG:-configs/grpo_sglang.yaml}
PORT=30001; MEMFRAC=${MEMFRAC:-0.45}     # PORT must match the config's sglang_server_url
GPU_MIN_MIB=${GPU_MIN_MIB:-85000}        # free GPU needed before the server starts
TRAINER_MIN_MIB=${TRAINER_MIN_MIB:-26000}  # free GPU needed after it is up (the trainer's share)
MAX_RUNNING=${MAX_RUNNING:-32}; SERVER_EXTRA=${SERVER_EXTRA:-}; CONTEXT=${CONTEXT:-10240}
DATA=${DATA:-data/train/curated/grpo-merged}
INIT_ADAPTER=${INIT_ADAPTER:-runs/sft-curated}  # the config's gst_recon.init_adapter
INIT_FROM=${INIT_FROM:-}  # optional: link INIT_ADAPTER to this adapter dir after its SHA256SUMS verify
OUT=$(awk '/^  output_dir:/{print $2}' "$HOME/gst-recon/repo/$CONFIG")
cd "$REPO" || exit 1
export HF_HOME=$ROOT/hf
[ -e runs ] || ln -s "$ROOT/runs" runs
log() { echo "$(date +%T) $*" | tee -a "$LOG"; }
die() { log "ABORT: $*"; exit 3; }

# preflight: the eval server stopped, nothing of ours on the GPU, headroom, the fork, the initial adapter
if [ -n "$INIT_FROM" ]; then
  [ -f "$INIT_FROM/SHA256SUMS" ] && (cd "$INIT_FROM" && sha256sum -c --quiet SHA256SUMS) || die "adapter $INIT_FROM fails SHA256SUMS"
  ln -sfn "$INIT_FROM" "$INIT_ADAPTER"
fi
[ -f "$INIT_ADAPTER/adapter_model.safetensors" ] || die "no initial adapter in $INIT_ADAPTER"
grep -q "init_adapter: $INIT_ADAPTER" "$CONFIG" || die "$CONFIG does not start from $INIT_ADAPTER"
[ -s "$DATA/train.jsonl" ] || die "no $DATA/train.jsonl"
tmux has-session -t sglang-rollout 2>/dev/null && die "tmux session sglang-rollout already exists"
pgrep -u "$USER" -f "[s]glang.launch_server" >/dev/null && die "an SGLang server of ours is still running (eval?)"
pgrep -u "$USER" -f "[g]st_recon.train run" >/dev/null && die "a training run of ours is still running"
ss -ltn | grep -q ":$PORT " && die "port $PORT in use"
grep -q "sglang_server_url: http://127.0.0.1:$PORT" "$CONFIG" || die "config does not point at port $PORT"
"$ALIGN_PY" -c "import importlib.util as u; assert u.find_spec('aligntune.backends.trl.rl.rollout.sglang_rollout')" 2>/dev/null \
  || die "AlignTune in $ALIGN_PY has no SGLang rollout"
grep -q "\"commit_id\":\"$ALIGN_REF\"" "$ROOT"/venv-align/lib/python3.11/site-packages/aligntune-*.dist-info/direct_url.json \
  || die "AlignTune in venv-align is not the fork at $ALIGN_REF"
avail=$(free -g | awk '/Mem:/{print $7}'); gpu=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits)
disk=$(df -BG --output=avail ~ | tail -1 | tr -dc 0-9)
log "preflight config=$CONFIG memfrac=$MEMFRAC avail=${avail}G gpu_free=${gpu}MiB disk=${disk}G load=$(cut -d' ' -f1 /proc/loadavg) init=$(readlink -f "$INIT_ADAPTER") rows=$(wc -l < "$DATA/train.jsonl")"
nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader | tee -a "$LOG"
[ "$gpu" -ge "$GPU_MIN_MIB" ] || die "only ${gpu} MiB GPU free, need $GPU_MIN_MIB (server + trainer)"
[ "$avail" -ge 12 ] || die "only ${avail} GB host RAM available"
[ "$disk" -ge 8 ] || die "only ${disk} GB disk (5 GB floor + 2 checkpoints + adapter sync)"

# 1. rollout server in its own tmux session (outside the trainer's process group and time box)
tmux new-session -d -s sglang-rollout "cd $REPO && HF_HOME=$ROOT/hf HF_HUB_OFFLINE=1 TORCHINDUCTOR_COMPILE_THREADS=1 MALLOC_ARENA_MAX=2 \
  exec $SGLANG_PY -m sglang.launch_server --model-path $BASE --host 127.0.0.1 --port $PORT --mem-fraction-static $MEMFRAC \
  --enable-lora --max-lora-rank 32 --lora-target-modules q_proj k_proj v_proj o_proj gate_proj up_proj down_proj \
  --context-length $CONTEXT --max-running-requests $MAX_RUNNING --cuda-graph-max-bs $MAX_RUNNING --skip-tokenizer-init --sleep-on-idle $SERVER_EXTRA \
  >> $ROOT/logs/sglang-rollout.log 2>&1"
for _ in $(seq 90); do curl -sf "127.0.0.1:$PORT/health" >/dev/null && break; sleep 10; done
curl -sf "127.0.0.1:$PORT/health" >/dev/null || { tmux kill-session -t sglang-rollout; die "rollout server not healthy after 15 min"; }
log "rollout server up: $(nvidia-smi --query-gpu=memory.used --format=csv,noheader) used"
left=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits)
[ "$left" -ge "$TRAINER_MIN_MIB" ] || { tmux kill-session -t sglang-rollout; die "only ${left} MiB GPU left for the trainer, need $TRAINER_MIN_MIB"; }

# 2. first-5-steps timing, printed once into the log
( t0=$(date +%s); until grep -q "^step 5/" "$LOG" 2>/dev/null; do sleep 30; pgrep -u "$USER" -f "[g]st_recon.train run" >/dev/null || exit; done
  log "first 5 steps: $(( ($(date +%s) - t0) / 5 )) s/step incl. model load (see step lines for the steady rate)" ) &

# 3. GRPO under the host-RAM watchdog; timeout signals its whole process group (run_guarded, trainer, children)
# UNSLOTH_RETURN_LOGITS: AlignTune's vendored unsloth patches transformers even on the trl backend and would
# return empty logits (seen in the rs-lab per-document SFT); TRL needs real ones for the completion log-probs.
timeout -s TERM 195m env PYTHON="$ALIGN_PY" MODEL="$BASE" UNSLOTH_RETURN_LOGITS=1 CAP_GB=8 DUMP_GB=6 MIN_AVAIL_GB=12 \
  bash configs/run_guarded.sh "$CONFIG" >> "$LOG" 2>&1
rc=$?

# 4. cleanup: stop the server and drop the adapter sync dir; checkpoints stay
tmux kill-session -t sglang-rollout
rm -rf "$ROOT/runs/grpo-sync"
log "DONE rc=$rc$([ $rc = 124 ] && echo ' (outer timeout)') checkpoints: $(cd "$OUT" 2>/dev/null && echo checkpoint-*)"
