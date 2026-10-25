#!/bin/bash
# Run `python -m gst_recon.train run CONFIG` on a shared GPU host with a host-RAM cap.
#   PYTHON=~/gst-recon/venv-align/bin/python MODEL=/path/to/local/snapshot bash configs/run_guarded.sh configs/sft.yaml
# the shared H100 host has no user systemd manager (systemd-run --user fails) and ulimit -v / prlimit --as break CUDA
# init (it reserves tens of GB of address space), so a 1 s watchdog is the cap: it SIGKILLs the run when
# the process tree's anonymous+shmem PSS passes CAP_GB (default 12), after a SIGUSR1 stack dump at
# DUMP_GB (default 8). It refuses to start below MIN_AVAIL_GB (default 20) of available host RAM, and with
# ABORT_AVAIL_GB set it SIGKILLs the run once the host's available RAM stays below that for 60 s (others' load).
set -u
CFG=${1:?usage: run_guarded.sh CONFIG}
PY=${PYTHON:-python}
CAP_KB=$(( ${CAP_GB:-12} * 1024 * 1024 )); DUMP_KB=$(( ${DUMP_GB:-8} * 1024 * 1024 ))
avail=$(free -g | awk '/Mem:/{print $7}')
[ "$avail" -ge "${MIN_AVAIL_GB:-20}" ] || { echo "ABORT: only ${avail} GB host RAM available"; exit 3; }
if [ -n "${MODEL:-}" ]; then  # local snapshot instead of the hub id (offline hosts, no unsloth remapping)
  R=$(mktemp --suffix=.yaml); sed "s#^\(  name_or_path:\).*#\1 $MODEL#" "$CFG" > "$R"; CFG=$R
fi
export HF_HUB_OFFLINE=${HF_HUB_OFFLINE:-1} HF_DATASETS_OFFLINE=${HF_DATASETS_OFFLINE:-1} TOKENIZERS_PARALLELISM=false \
  OMP_NUM_THREADS=4 TORCHINDUCTOR_COMPILE_THREADS=1 HF_DEACTIVATE_ASYNC_LOAD=1 MALLOC_ARENA_MAX=2 PYTHONUNBUFFERED=1
echo "start $(date +%T) avail=${avail}G config=$CFG"; nvidia-smi --query-gpu=memory.used,memory.free --format=csv,noheader; df -h . | tail -1
"$PY" -m gst_recon.train run "$CFG" &
PID=$!
procs() { echo $PID $(pgrep -P $PID) $(for c in $(pgrep -P $PID); do pgrep -P $c; done); }
# proportional set size: forked workers share copy-on-write pages that plain RSS counts once per process
pss() { local t=0 r; for p in $(procs); do r=$(awk '/^Pss_Anon|^Pss_Shmem/{s+=$2} END{print s+0}' /proc/$p/smaps_rollup 2>/dev/null); t=$((t + ${r:-0})); done; echo $t; }
peak=0; gpeak=0; dumped=0; n=0; low=0
while kill -0 $PID 2>/dev/null; do
  r=$(pss); [ "$r" -gt "$peak" ] && peak=$r
  if [ "$r" -gt "$DUMP_KB" ] && [ $dumped = 0 ]; then echo "WATCHDOG $(date +%T) pss=$((r/1024))M: stack dump"; kill -USR1 $PID; dumped=1; fi
  if [ "$r" -gt "$CAP_KB" ]; then echo "WATCHDOG $(date +%T) pss=$((r/1024))M over cap: SIGKILL"; kill -9 $(procs); break; fi
  if [ -n "${ABORT_AVAIL_GB:-}" ]; then
    a=$(free -m | awk '/Mem:/{print $7}'); if [ "$a" -lt $((ABORT_AVAIL_GB * 1024)) ]; then low=$((low + 1)); else low=0; fi
    if [ "$low" -ge 60 ]; then echo "WATCHDOG $(date +%T) host avail ${a}M under ${ABORT_AVAIL_GB}G for 60 s: SIGKILL"; kill -9 $(procs); break; fi
  fi
  if [ $((n % 10)) = 0 ]; then
    g=$(nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader,nounits | awk -F', ' -v p=$PID '$1==p{print $2}'); g=${g:-0}; [ "$g" -gt "$gpeak" ] && gpeak=$g
    echo "MEM $(date +%T) pss=$((r/1024))M peak=$((peak/1024))M gpu=${g}M peak_gpu=${gpeak}M avail=$(free -m | awk '/Mem:/{print $7}')M disk=$(df -BM --output=avail . | tail -1)"
  fi
  n=$((n+1)); sleep 1
done
wait $PID; rc=$?
echo "EXIT $rc peak_pss=$((peak/1024))M peak_gpu=${gpeak}M $(date +%T)"
exit $rc
