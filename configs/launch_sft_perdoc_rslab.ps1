# Per-document SFT on rs-lab (Windows, RTX A6000): preflight, then a per-doc config (default
# configs/sft_perdoc_trl.yaml) under a Job Object memory cap. Runs as a scheduled task so it survives ssh. The task
# is interactive-only (no stored password), so its console would open on the shared desktop: keep it hidden.
#   schtasks /Create /TN gst-sft-perdoc /SC ONCE /ST 23:59 /F /TR "powershell -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File D:\gst\gst-train\repo\configs\launch_sft_perdoc_rslab.ps1"
#   schtasks /Run /TN gst-sft-perdoc
# v2 (finish the epoch from v1's adapter): append -Config configs\sft_perdoc_v2_trl.yaml -Name sft_perdoc_v2 -Data sft-perdoc-v2-rest
# Log (ASCII, tail over ssh): D:\gst\gst-train\logs\<Name>.log
param([string]$Config = "configs\sft_perdoc_trl.yaml", [string]$Name = "sft_perdoc", [string]$Data = "sft-perdoc-pc", [switch]$SharedGpu)  # -SharedGpu: run next to a foreign GPU job when >= 40 GB is free
# Everything of ours lives on D: (C: is the shared system drive): code, envs, logs, runs and every cache.
$T = "D:\gst\gst-train"; $Repo = "$T\repo"; $Log = "$T\logs\$Name.log"; $Cache = "D:\gst\cache"
New-Item -ItemType Directory -Force "$T\logs" | Out-Null
function Log($m) { Add-Content -Path $Log -Encoding ascii -Value "$(Get-Date -Format HH:mm:ss) $m" }
function Die($m) { Log "ABORT: $m"; exit 3 }

# preflight. WDDM hides per-process GPU memory, so a foreign job shows up as total use above the ~1.2 GB desktop.
$g = (nvidia-smi --query-gpu=memory.free,memory.used,utilization.gpu --format=csv,noheader,nounits).Split(",") | ForEach-Object { [int]$_.Trim() }
Add-Type -AssemblyName Microsoft.VisualBasic
$ram = (New-Object Microsoft.VisualBasic.Devices.ComputerInfo).AvailablePhysicalMemory / 1GB
$disk = [System.IO.DriveInfo]::new("D").AvailableFreeSpace / 1GB
Log ("preflight gpu_free={0}MiB gpu_used={1}MiB gpu_util={2}% ram_avail={3:N0}GB disk_free={4:N0}GB" -f $g[0], $g[1], $g[2], $ram, $disk)
if ($g[0] -lt $(if ($SharedGpu) { 40000 } else { 30000 })) { Die "only $($g[0]) MiB GPU free" }
if (-not $SharedGpu -and ($g[1] -gt 6000 -or $g[2] -gt 20)) { Die "the GPU is in use by someone else ($($g[1]) MiB, $($g[2])%)" }
if ($ram -lt 64) { Die "only $ram GB RAM available" }
if ($disk -lt 20) { Die "only $disk GB disk free" }
if (Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$T\env\*" }) { Die "a run of ours is already active" }
if (-not (Test-Path "$Repo\data\train\curated\$Data\train.jsonl")) { Die "no per-document rows in $Data" }

$env:HF_HOME = "$Cache\hf"; $env:TRANSFORMERS_CACHE = "$Cache\hf\hub"; $env:HF_HUB_OFFLINE = "1"; $env:HF_DATASETS_OFFLINE = "1"
$env:TORCH_HOME = "$Cache\torch"; $env:PIP_CACHE_DIR = "$Cache\pip"; $env:UV_CACHE_DIR = "$Cache\uv"
$env:CONDA_PKGS_DIRS = "$Cache\conda-pkgs"; $env:XDG_CACHE_HOME = $Cache; $env:GST_TOKENIZER = "$Cache\gst_recon\qwen3-tokenizer.json"
$env:TMP = "D:\gst\tmp"; $env:TEMP = "D:\gst\tmp"; New-Item -ItemType Directory -Force $env:TMP | Out-Null
$env:PYTHONPATH = $Repo; $env:PYTHONIOENCODING = "utf-8"; $env:PYTHONUNBUFFERED = "1"
$env:TOKENIZERS_PARALLELISM = "false"; $env:GST_MEM_CAP_GB = "64"  # host commit cap via Job Object (480 GB box, shared)
# AlignTune's vendored unsloth patches transformers on import, even on the trl backend, and returns empty logits
# (fused loss); TRL's SFTTrainer computes token accuracy from logits, so ask for real ones (~2 GB at 4 x 1.5k).
$env:UNSLOTH_RETURN_LOGITS = "1"
Set-Location $Repo
Log "run $Config"
# rs-lab is someone else's machine: a Ctrl-C or close event from its desktop ends the run, by design.
cmd /c "`"$T\env\python.exe`" -m gst_recon.train run $Config >> `"$Log`" 2>&1"
$rc = $LASTEXITCODE  # checkpoints stay: with the optimizer state they allow a true resume
Log "DONE rc=$rc"
