# Run typed-settings / spectrum / reconfig bench on piscope and pull results.
param(
    [string]$HostAlias = "piscope",
    [string]$RemoteApp = "/home/fanf/astroScop/backapp",
    [int]$Frames = 3,
    [int]$FastIters = 5,
    [int]$SlowIters = 2,
    [int]$EmitBurst = 30
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackappDir = Resolve-Path (Join-Path $ScriptDir "..")
$LocalOutRoot = Join-Path $BackappDir "cam_test_out"
New-Item -ItemType Directory -Force -Path $LocalOutRoot | Out-Null

$RunId = Get-Date -Format "yyyyMMddTHHmmss"
$RemoteOut = "/tmp/cam_settings_bench/$RunId"
$LocalOut = Join-Path $LocalOutRoot "settings_$RunId"

Write-Host "==> Checking camera service inactive"
$svc = ssh -o BatchMode=yes -o ConnectTimeout=10 $HostAlias "systemctl is-active astroscop-camera.service 2>/dev/null"
if ($svc -match "(?m)^active") {
    Write-Error "Stop camera service first: sudo systemctl disable --now astroscop-camera.service"
}

Write-Host "==> Ensure pydantic"
ssh -o BatchMode=yes $HostAlias "dpkg -l python3-pydantic 2>/dev/null | grep -q '^ii' || sudo apt-get install -y python3-pydantic"

Write-Host "==> Sync modules"
scp -o BatchMode=yes `
    (Join-Path $BackappDir "cam_picamera2.py") `
    (Join-Path $BackappDir "cam_settings.py") `
    (Join-Path $BackappDir "cam_spectrum.py") `
    (Join-Path $BackappDir "test_cam_settings_bench.py") `
    "${HostAlias}:${RemoteApp}/"

$remoteCmd = "cd $RemoteApp && python3 test_cam_settings_bench.py --out $RemoteOut --frames $Frames --fast-iters $FastIters --slow-iters $SlowIters --emit-burst $EmitBurst"
Write-Host "==> Running bench"
Write-Host $remoteCmd
ssh -o BatchMode=yes -o ConnectTimeout=10 $HostAlias $remoteCmd
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Bench exited with code $LASTEXITCODE (results may still be useful)"
}

Write-Host "==> Pull $RemoteOut -> $LocalOut"
New-Item -ItemType Directory -Force -Path $LocalOut | Out-Null
scp -o BatchMode=yes -r "${HostAlias}:${RemoteOut}/*" "$LocalOut/"

python (Join-Path $ScriptDir "generate_cam_settings_bench_report.py") $LocalOut
Write-Output $LocalOut
