#!/usr/bin/env bash
# GRPO on rs-epyc, time-boxed: merge the SFT adapter, start the SGLang rollout server, run the guarded
# trainer for at most HOURS (default 3), stop the server. Adapters every 50 steps (save_total_limit 2),
# so stopping at any time leaves a result in runs/grpo-curated/checkpoint-*.
#   tmux new-session -d -s grpo 'bash ~/gst-recon/repo/configs/launch_grpo.sh'
#   CAP_GB / DUMP_GB / MIN_AVAIL_GB pass through to run_guarded.sh (host-RAM cap: coordinator decides).
# Logs: ~/gst-recon/logs/grpo.log (`step N/M loss X reward Y`), ~/gst-recon/logs/sglang-rollout.log.
set -u
ROOT=$HOME/gst-recon; REPO=$ROOT/repo; LOG=$ROOT/logs/grpo.log
BASE=${BASE:-$ROOT/hf/hub/models--Qwen--Qwen3-4B-Instruct-2507/snapshots/cdbee75f17c01a7cc42f958dc650907174af0554}
SFT=$ROOT/runs/sft-curated; MERGED=$SFT/merged
ALIGN_PY=${ALIGN_PY:-$ROOT/venv-align/bin/python}     # PENDING: the venv with the rollout worker's AlignTune install ref
SGLANG_PY=${SGLANG_PY:-$ROOT/venv-sglang/bin/python}  # PENDING: sglang 0.5.10.post1 env the rollout worker verified
PORT=30001; MEMFRAC=0.40; HOURS=${HOURS:-3}           # port and mem fraction must match configs/grpo_sglang.yaml
cd "$REPO" || exit 1
log() { echo "$(date +%T) $*" | tee -a "$LOG"; }
die() { log "ABORT: $*"; exit 3; }

# preflight: SFT done, nothing of ours on the GPU, headroom, the fork installed, the config pointing at this server
grep -q "^DONE rc=0" "$ROOT/logs/sft_full.log" || die "SFT has not finished cleanly"
[ -f "$SFT/adapter_model.safetensors" ] || die "no SFT adapter in $SFT"
tmux has-session -t sglang-rollout 2>/dev/null && die "tmux session sglang-rollout already exists"
pgrep -u "$USER" -f "[s]glang.launch_server" >/dev/null && die "an SGLang server of ours is running (teacher or eval?)"
ss -ltn | grep -q ":$PORT " && die "port $PORT in use"
grep -q "sglang_server_url: http://127.0.0.1:$PORT" configs/grpo_sglang.yaml || die "config does not point at port $PORT"
[ -s data/train/curated/grpo-merged/train.jsonl ] || die "no data/train/curated/grpo-merged/train.jsonl"
"$ALIGN_PY" -c "import importlib.util as u; assert u.find_spec('aligntune.backends.trl.rl.rollout.sglang_rollout')" 2>/dev/null \
  || die "AlignTune in $ALIGN_PY has no SGLang rollout (install the fork ref)"
avail=$(free -g | awk '/Mem:/{print $7}'); gpu=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits)
disk=$(df -BG --output=avail ~ | tail -1 | tr -dc 0-9)
log "preflight avail=${avail}G gpu_free=${gpu}MiB disk=${disk}G load=$(cut -d' ' -f1 /proc/loadavg) rows=$(wc -l < data/train/curated/grpo-merged/train.jsonl)"
nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader | tee -a "$LOG"
[ "$gpu" -ge 88000 ] || die "only ${gpu} MiB GPU free (plan: ~41 GiB server + ~35 GiB trainer)"
[ "$disk" -ge 25 ] || die "only ${disk} GB disk (merged 8 + weight-sync file 8 + checkpoints 2 + 5 floor)"

# 1. merged SFT model: the GRPO policy init and the rollout server's model (once)
if [ ! -f "$MERGED/config.json" ]; then
  log "merge $SFT -> $MERGED"
  PYTHON=$ALIGN_PY bash configs/run_guarded.sh merge --base "$BASE" --adapter "$SFT" --out "$MERGED" >> "$LOG" 2>&1 || die "merge failed"
fi

# 2. rollout server in its own tmux session (outside the trainer's process group and its time box)
tmux new-session -d -s sglang-rollout "cd $REPO && HF_HUB_OFFLINE=1 TORCHINDUCTOR_COMPILE_THREADS=1 MALLOC_ARENA_MAX=2 exec $SGLANG_PY \
  -m sglang.launch_server --model-path $MERGED --host 127.0.0.1 --port $PORT --mem-fraction-static $MEMFRAC \
  --context-length 10240 --max-running-requests 32 --cuda-graph-max-bs 32 --skip-tokenizer-init --sleep-on-idle \
  >> $ROOT/logs/sglang-rollout.log 2>&1"
for _ in $(seq 90); do curl -sf "127.0.0.1:$PORT/health" >/dev/null && break; sleep 10; done
curl -sf "127.0.0.1:$PORT/health" >/dev/null || { tmux kill-session -t sglang-rollout; die "rollout server not healthy after 15 min"; }
log "rollout server up: $(nvidia-smi --query-gpu=memory.used --format=csv,noheader) used"

# 3. GRPO; timeout signals its whole process group (run_guarded, trainer and its children); 124 = time box hit
timeout -s TERM "${HOURS}h" env PYTHON="$ALIGN_PY" bash configs/run_guarded.sh configs/grpo_sglang.yaml >> "$LOG" 2>&1
rc=$?

# 4. cleanup: stop the server, drop the 8 GB weight-sync file; checkpoints stay
tmux kill-session -t sglang-rollout
rm -rf runs/grpo-sglang-sync
log "DONE rc=$rc$([ $rc = 124 ] && echo ' (time box)') checkpoints: $(cd runs/grpo-curated 2>/dev/null && echo checkpoint-*)"
