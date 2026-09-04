# Sync backapp to the Pi and run install_on_pi.sh (venv + systemd).
# Default SSH host: piscope. Override with ASTROSCOP_PI_HOST.
$ErrorActionPreference = "Stop"
$PiHost = if ($env:ASTROSCOP_PI_HOST) { $env:ASTROSCOP_PI_HOST } else { "piscope" }
$Root = Split-Path -Parent $PSScriptRoot
$RemoteApp = "/home/fanf/astroScop/backapp"
$ReqFile = Join-Path $PSScriptRoot "requirements.generated.txt"

if (-not (Test-Path $ReqFile)) {
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        Write-Host "==> Exporting Pi requirements"
        bash (Join-Path $PSScriptRoot "export_pi_requirements.sh")
        if ($LASTEXITCODE -ne 0) { throw "export_pi_requirements.sh failed" }
    } else {
        throw "missing requirements.generated.txt; run backapp/deploy/export_pi_requirements.sh on a host with uv"
    }
}

Write-Host "==> Packing $Root"
$tar = Join-Path $env:TEMP "astroscop-backapp.tar"
if (Test-Path $tar) { Remove-Item $tar }
tar -C $Root --exclude=.venv --exclude=__pycache__ --exclude=.pytest_cache --exclude=savedimgs --exclude=*.pyc -cf $tar .
if ($LASTEXITCODE -ne 0) { throw "local backapp tar failed" }

Write-Host "==> Uploading to $PiHost"
scp $tar "${PiHost}:/tmp/astroscop-backapp.tar"
if ($LASTEXITCODE -ne 0) { throw "scp backapp failed" }

$extract = "rm -rf '$RemoteApp' && mkdir -p '$RemoteApp' && tar -C '$RemoteApp' -xf /tmp/astroscop-backapp.tar && rm -f /tmp/astroscop-backapp.tar"
ssh $PiHost "$extract"
if ($LASTEXITCODE -ne 0) { throw "remote extract failed" }

Write-Host "==> Installing on $PiHost"
$install = "chmod +x '$RemoteApp/deploy/install_on_pi.sh' && '$RemoteApp/deploy/install_on_pi.sh'"
ssh $PiHost "$install"
if ($LASTEXITCODE -ne 0) { throw "remote install failed" }

Write-Host "==> Backend on ${PiHost}: ws://${PiHost}:8765"
