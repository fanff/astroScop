# Run HQ camera suite on piscope and pull results locally.
#
# Usage (from repo root or backapp/):
#   powershell -File backapp/scripts/run_hq_cam_tests.ps1
#   powershell -File backapp/scripts/run_hq_cam_tests.ps1 -SkipLong
#   powershell -File backapp/scripts/run_hq_cam_tests.ps1 -FastFrames 10 -SkipLong

param(
    [string]$HostAlias = "piscope",
    [string]$RemoteApp = "/home/fanf/astroScop/backapp",
    [switch]$SkipLong,
    [switch]$SkipFast,
    [int]$FastFrames = 20,
    [int]$FastShutter = 5000,
    [double]$CropFrac = 0.5,
    [string]$LongMode = "bin2x2",
    [string]$LongShutters = "1000000,5000000,10000000,20000000,30000000,45000000,60000000,120000000"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackappDir = Resolve-Path (Join-Path $ScriptDir "..")
$LocalOutRoot = Join-Path $BackappDir "cam_test_out"
New-Item -ItemType Directory -Force -Path $LocalOutRoot | Out-Null

$RunId = Get-Date -Format "yyyyMMddTHHmmss"
$RemoteOut = "/tmp/hq_cam_suite/$RunId"
$LocalOut = Join-Path $LocalOutRoot $RunId

Write-Host "==> Checking camera service is inactive on $HostAlias"
$svc = ssh -o BatchMode=yes -o ConnectTimeout=10 $HostAlias "systemctl is-active astroscop-camera.service 2>/dev/null; systemctl is-enabled astroscop-camera.service 2>/dev/null"
Write-Host $svc
if ($svc -match "(?m)^active") {
    Write-Error "astroscop-camera.service is active. Run: ssh $HostAlias 'sudo systemctl disable --now astroscop-camera.service'"
}

Write-Host "==> Syncing cam_picamera2.py + test_cam_picamera2.py"
scp -o BatchMode=yes `
    (Join-Path $BackappDir "cam_picamera2.py") `
    (Join-Path $BackappDir "test_cam_picamera2.py") `
    "${HostAlias}:${RemoteApp}/"

$extra = @()
if ($SkipLong) { $extra += "--skip-long" }
if ($SkipFast) { $extra += "--skip-fast" }
$extraArgs = ($extra -join " ")

$remoteCmd = "cd $RemoteApp && python3 test_cam_picamera2.py --suite --out $RemoteOut --fast-frames $FastFrames --fast-shutter $FastShutter --crop-frac $CropFrac --long-mode $LongMode --long-shutters $LongShutters $extraArgs"

Write-Host "==> Running suite on Pi"
Write-Host $remoteCmd
ssh -o BatchMode=yes -o ConnectTimeout=10 $HostAlias $remoteCmd
if ($LASTEXITCODE -ne 0) {
    Write-Error "Remote suite failed with exit code $LASTEXITCODE"
}

Write-Host "==> Pulling results to $LocalOut"
New-Item -ItemType Directory -Force -Path $LocalOut | Out-Null
scp -o BatchMode=yes -r "${HostAlias}:${RemoteOut}/*" "$LocalOut/"

$manifest = Join-Path $LocalOut "manifest.json"
if (Test-Path $manifest) {
    Write-Host "==> manifest.json"
    Get-Content $manifest -Raw
} else {
    Write-Warning "manifest.json missing under $LocalOut"
}

Write-Host "==> Done. Local results: $LocalOut"
Write-Host "==> Generating capability report"
python (Join-Path $ScriptDir "generate_hq_capability_report.py") $LocalOut
Write-Output $LocalOut
