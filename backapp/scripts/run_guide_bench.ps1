# Push guide benches to piscope, run, pull results.
#
# SSH / paths (same family as run_cam_settings_bench.ps1):
#   Host alias:  piscope          (ssh piscope)
#   Remote user: fanf
#   Remote app:  /home/fanf/astroScop/backapp
#
# Phase B geom and Phase C isolate are CPU-only. Do NOT stop astroscop-camera.
# Phase D crop MUST run with astroscop-camera.service inactive (exclusive IMX477).
param(
    [string]$HostAlias = "piscope",
    [string]$RemoteApp = "/home/fanf/astroScop/backapp",
    [ValidateSet("geom", "isolate", "crop", "worker")]
    [string]$Stage = "geom",
    [int]$Iters = 0,
    [int]$Frames = 40
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackappDir = Resolve-Path (Join-Path $ScriptDir "..")
$DocsDir = Join-Path $BackappDir "docs"
$LocalOutRoot = Join-Path $BackappDir "cam_test_out"
New-Item -ItemType Directory -Force -Path $LocalOutRoot | Out-Null

$RunId = Get-Date -Format "yyyyMMddTHHmmss"
$RemoteOut = "/tmp/guide_bench/$Stage/$RunId"
$LocalOut = Join-Path $LocalOutRoot "guide_${Stage}_$RunId"

Write-Host "==> Checking ssh $HostAlias"
ssh -o BatchMode=yes -o ConnectTimeout=10 $HostAlias "echo ok" | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Cannot ssh $HostAlias (BatchMode). Fix the host alias first."
}

if ($Stage -eq "geom") {
    if ($Iters -le 0) { $Iters = 10000 }
    Write-Host "==> Sync guide_geom modules (camera service stays running)"
    scp -o BatchMode=yes `
        (Join-Path $BackappDir "guide_geom.py") `
        (Join-Path $BackappDir "asc_rates.py") `
        (Join-Path $BackappDir "test_guide_geom_bench.py") `
        "${HostAlias}:${RemoteApp}/"
    $remoteCmd = "mkdir -p $RemoteOut && cd $RemoteApp && python3 test_guide_geom_bench.py --out $RemoteOut --iters $Iters"
    $expectJson = "geom_bench.json"
} elseif ($Stage -eq "isolate") {
    if ($Iters -le 0) { $Iters = 400 }
    Write-Host "==> Sync guide_isolate modules (camera service stays running)"
    scp -o BatchMode=yes `
        (Join-Path $BackappDir "guide_isolate.py") `
        (Join-Path $BackappDir "test_guide_isolate_bench.py") `
        "${HostAlias}:${RemoteApp}/"
    $remoteCmd = "mkdir -p $RemoteOut && cd $RemoteApp && python3 test_guide_isolate_bench.py --out $RemoteOut --iters $Iters"
    $expectJson = "isolate_bench.json"
} elseif ($Stage -eq "crop") {
    Write-Host "==> Checking camera service inactive"
    $svc = ssh -o BatchMode=yes -o ConnectTimeout=10 $HostAlias "systemctl is-active astroscop-camera.service 2>/dev/null"
    if ($svc -match "(?m)^active") {
        Write-Error "Stop camera service first: sudo systemctl disable --now astroscop-camera.service"
    }
    Write-Host "==> Sync crop handoff modules (exclusive camera)"
    scp -o BatchMode=yes `
        (Join-Path $BackappDir "guide_handoff.py") `
        (Join-Path $BackappDir "guide_roi.py") `
        (Join-Path $BackappDir "cam_locator.py") `
        (Join-Path $BackappDir "cam_settings.py") `
        (Join-Path $BackappDir "cam_picamera2.py") `
        (Join-Path $BackappDir "cam_spectrum.py") `
        (Join-Path $BackappDir "imgutils.py") `
        (Join-Path $BackappDir "test_guide_crop_bench.py") `
        "${HostAlias}:${RemoteApp}/"
    $remoteCmd = "mkdir -p $RemoteOut && cd $RemoteApp && python3 test_guide_crop_bench.py --out $RemoteOut --frames $Frames"
    $expectJson = "crop_bench.json"
} elseif ($Stage -eq "worker") {
    Write-Host "==> Sync guide worker modules (camera service stays running)"
    scp -o BatchMode=yes `
        (Join-Path $BackappDir "guide_pid.py") `
        (Join-Path $BackappDir "guide_process.py") `
        (Join-Path $BackappDir "guideControl.py") `
        (Join-Path $BackappDir "guide_geom.py") `
        (Join-Path $BackappDir "guide_isolate.py") `
        (Join-Path $BackappDir "guide_handoff.py") `
        (Join-Path $BackappDir "guide_roi.py") `
        (Join-Path $BackappDir "guide_mixer.py") `
        (Join-Path $BackappDir "asc_rates.py") `
        (Join-Path $BackappDir "cam_locator.py") `
        (Join-Path $BackappDir "ws_messages.py") `
        (Join-Path $BackappDir "cam_settings.py") `
        (Join-Path $BackappDir "cam_spectrum.py") `
        (Join-Path $BackappDir "test_guide_worker_bench.py") `
        "${HostAlias}:${RemoteApp}/"
    $remoteCmd = "mkdir -p $RemoteOut && cd $RemoteApp && python3 test_guide_worker_bench.py --out $RemoteOut"
    $expectJson = "worker_bench.json"
} else {
    Write-Error "Unknown stage $Stage"
}

Write-Host "==> Running bench"
Write-Host $remoteCmd
ssh -o BatchMode=yes -o ConnectTimeout=10 $HostAlias $remoteCmd
$benchExit = $LASTEXITCODE

Write-Host "==> Pull $RemoteOut -> $LocalOut"
New-Item -ItemType Directory -Force -Path $LocalOut | Out-Null
scp -o BatchMode=yes -r "${HostAlias}:${RemoteOut}/*" "$LocalOut/"

$jsonPath = Join-Path $LocalOut $expectJson
if (-not (Test-Path $jsonPath)) {
    Write-Error "No $expectJson pulled from Pi"
}

python (Join-Path $ScriptDir "generate_guide_bench_report.py") $LocalOut $DocsDir
Write-Output $LocalOut
if ($benchExit -ne 0) {
    Write-Error "Bench exited with code $benchExit"
}
