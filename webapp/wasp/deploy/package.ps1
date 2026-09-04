# Build the production Vue bundle into webapp/wasp/dist.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm is required to package the UI"
}

Write-Host "==> npm ci"
npm ci
if ($LASTEXITCODE -ne 0) {
    Write-Host "==> npm ci failed; falling back to npm install"
    npm install
    if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
}

Write-Host "==> npm run build"
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "==> npm run build failed; trying npx vite build"
    npx vite build
    if ($LASTEXITCODE -ne 0) { throw "vite build failed" }
}

if (-not (Test-Path (Join-Path $Root "dist\index.html"))) {
    throw "build did not produce dist/index.html"
}

Write-Host "==> Packaged $(Join-Path $Root 'dist')"
