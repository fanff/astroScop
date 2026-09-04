# Package wasp and publish it to the Pi (default host: piscope) on port 80.
$ErrorActionPreference = "Stop"
$PiHost = if ($env:ASTROSCOP_PI_HOST) { $env:ASTROSCOP_PI_HOST } else { "piscope" }
$Root = Split-Path -Parent $PSScriptRoot
$RemoteStaging = "/tmp/wasp-ui"
$RemoteDeploy = "/tmp/wasp-deploy"

Set-Location $Root
if ($env:ASTROSCOP_SKIP_UI_PACKAGE -eq "1") {
    if (-not (Test-Path (Join-Path $Root "dist\index.html"))) {
        throw "ASTROSCOP_SKIP_UI_PACKAGE=1 but dist/index.html is missing"
    }
    Write-Host "==> Skipping UI package (using existing dist/)"
} else {
    & (Join-Path $PSScriptRoot "package.ps1")
}

Write-Host "==> Uploading to $PiHost"
ssh $PiHost "rm -rf '$RemoteStaging' '$RemoteDeploy' && mkdir -p '$RemoteStaging' '$RemoteDeploy'"
if ($LASTEXITCODE -ne 0) { throw "ssh mkdir failed" }

# File-based tar: piping tar through Windows OpenSSH corrupts the archive.
$uiTar = Join-Path $env:TEMP "wasp-ui.tar"
$depTar = Join-Path $env:TEMP "wasp-deploy.tar"
if (Test-Path $uiTar) { Remove-Item $uiTar }
if (Test-Path $depTar) { Remove-Item $depTar }

tar -C (Join-Path $Root "dist") -cf $uiTar .
if ($LASTEXITCODE -ne 0) { throw "local dist tar failed" }
tar -C (Join-Path $Root "deploy") -cf $depTar install_on_pi.sh nginx-astroscop-ui.conf
if ($LASTEXITCODE -ne 0) { throw "local deploy tar failed" }

scp $uiTar "${PiHost}:/tmp/wasp-ui.tar"
if ($LASTEXITCODE -ne 0) { throw "scp dist failed" }
scp $depTar "${PiHost}:/tmp/wasp-deploy.tar"
if ($LASTEXITCODE -ne 0) { throw "scp deploy files failed" }

ssh $PiHost "tar -C '$RemoteStaging' -xf /tmp/wasp-ui.tar && tar -C '$RemoteDeploy' -xf /tmp/wasp-deploy.tar && rm -f /tmp/wasp-ui.tar /tmp/wasp-deploy.tar"
if ($LASTEXITCODE -ne 0) { throw "remote extract failed" }

Write-Host "==> Installing on $PiHost"
ssh $PiHost "chmod +x '$RemoteDeploy/install_on_pi.sh' && '$RemoteDeploy/install_on_pi.sh' '$RemoteStaging' '$RemoteDeploy/nginx-astroscop-ui.conf'"
if ($LASTEXITCODE -ne 0) { throw "remote install failed" }

Write-Host "==> UI should be at http://$PiHost/"
