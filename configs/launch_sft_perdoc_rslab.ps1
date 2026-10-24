# Per-document SFT on rs-lab (Windows, RTX A6000): preflight, then configs/sft_perdoc_trl.yaml under a Job
# Object memory cap. Runs as a scheduled task so it survives the ssh session:
#   schtasks /Create /TN gst-sft-perdoc /SC ONCE /ST 23:59 /F /TR "powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\user\gst-train\repo\configs\launch_sft_perdoc_rslab.ps1"
#   schtasks /Run /TN gst-sft-perdoc
# Log (ASCII, tail over ssh): C:\Users\user\gst-train\logs\sft_perdoc.log
$T = "C:\Users\user\gst-train"; $Repo = "$T\repo"; $Log = "$T\logs\sft_perdoc.log"
New-Item -ItemType Directory -Force "$T\logs" | Out-Null
function Log($m) { Add-Content -Path $Log -Encoding ascii -Value "$(Get-Date -Format HH:mm:ss) $m" }
function Die($m) { Log "ABORT: $m"; exit 3 }

# preflight. WDDM hides per-process GPU memory, so a foreign job shows up as total use above the ~1.2 GB desktop.
$g = (nvidia-smi --query-gpu=memory.free,memory.used,utilization.gpu --format=csv,noheader,nounits).Split(",") | ForEach-Object { [int]$_.Trim() }
Add-Type -AssemblyName Microsoft.VisualBasic
$ram = (New-Object Microsoft.VisualBasic.Devices.ComputerInfo).AvailablePhysicalMemory / 1GB
$disk = [System.IO.DriveInfo]::new("C").AvailableFreeSpace / 1GB
Log ("preflight gpu_free={0}MiB gpu_used={1}MiB gpu_util={2}% ram_avail={3:N0}GB disk_free={4:N0}GB" -f $g[0], $g[1], $g[2], $ram, $disk)
if ($g[0] -lt 30000) { Die "only $($g[0]) MiB GPU free" }
if ($g[1] -gt 6000 -or $g[2] -gt 20) { Die "the GPU is in use by someone else ($($g[1]) MiB, $($g[2])%)" }
if ($ram -lt 64) { Die "only $ram GB RAM available" }
if ($disk -lt 20) { Die "only $disk GB disk free" }
if (Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$T\env\*" }) { Die "a run of ours is already active" }
if (-not (Test-Path "$Repo\data\train\curated\sft-perdoc-pc\train.jsonl")) { Die "no per-document rows" }

$env:HF_HOME = "$T\hf"; $env:HF_HUB_OFFLINE = "1"; $env:HF_DATASETS_OFFLINE = "1"
$env:PYTHONPATH = $Repo; $env:PYTHONIOENCODING = "utf-8"; $env:PYTHONUNBUFFERED = "1"
$env:TOKENIZERS_PARALLELISM = "false"; $env:GST_MEM_CAP_GB = "64"  # host commit cap via Job Object (480 GB box, shared)
Set-Location $Repo
cmd /c "`"$T\env\python.exe`" -m gst_recon.train run configs\sft_perdoc_trl.yaml >> `"$Log`" 2>&1"
$rc = $LASTEXITCODE
if ($rc -eq 0) { Remove-Item -Recurse -Force "$Repo\runs\sft-perdoc\checkpoint-*" -ErrorAction SilentlyContinue }
Log "DONE rc=$rc"
