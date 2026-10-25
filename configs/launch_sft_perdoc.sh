#!/usr/bin/env bash
# Per-document SFT (configs/sft_perdoc.yaml, ~20-30 min) on the shared H100 host; needs the GPU free (after GRPO).
#   tmux new-session -d -s sft-perdoc 'bash ~/gst-recon/repo/configs/launch_sft_perdoc.sh'
#   CAP_GB / DUMP_GB / MIN_AVAIL_GB pass through to run_guarded.sh.
# Log: ~/gst-recon/logs/sft_perdoc.log (`step N/M loss X`); adapter: ~/gst-recon/runs/sft-perdoc.
set -u
ROOT=$HOME/gst-recon; LOG=$ROOT/logs/sft_perdoc.log; DATA=data/train/curated/sft-perdoc/train.jsonl
cd "$ROOT/repo" || exit 1
die() { echo "ABORT: $*" | tee -a "$LOG"; exit 3; }
[ -s "$DATA" ] || die "no $DATA"
pgrep -u "$USER" -f "[g]st_recon.train run" >/dev/null && die "a training run of ours is still running"
gpu=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits); disk=$(df -BG --output=avail ~ | tail -1 | tr -dc 0-9)
echo "$(date +%T) preflight rows=$(wc -l < "$DATA") avail=$(free -g | awk '/Mem:/{print $7}')G gpu_free=${gpu}MiB disk=${disk}G load=$(cut -d' ' -f1 /proc/loadavg)" | tee -a "$LOG"
[ "$gpu" -ge 60000 ] || die "only ${gpu} MiB GPU free"
[ "$disk" -ge 7 ] || die "only ${disk} GB disk free (5 GB floor + adapter and checkpoint)"
[ -e runs ] || ln -s "$ROOT/runs" runs
HF_HOME=$ROOT/hf PYTHON=$ROOT/venv-align/bin/python \
MODEL=$ROOT/hf/hub/models--Qwen--Qwen3-4B-Instruct-2507/snapshots/cdbee75f17c01a7cc42f958dc650907174af0554 \
  bash configs/run_guarded.sh configs/sft_perdoc.yaml >> "$LOG" 2>&1
rc=$?
# transformers always writes a last-step checkpoint with optimizer state; keep the adapter only (disk)
[ $rc = 0 ] && rm -rf "$ROOT"/runs/sft-perdoc/checkpoint-*
echo "DONE rc=$rc $(date +%T) $(du -sh "$ROOT/runs/sft-perdoc" 2>/dev/null | cut -f1)" >> "$LOG"
