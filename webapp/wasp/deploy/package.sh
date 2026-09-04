#!/usr/bin/env bash
# Build the production Vue bundle into webapp/wasp/dist.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v npm >/dev/null 2>&1; then
  echo "ERROR: npm is required to package the UI"
  exit 1
fi

echo "==> npm ci"
if ! npm ci; then
  echo "==> npm ci failed; falling back to npm install"
  npm install
fi
echo "==> npm run build"
npm run build

if [[ ! -f "$ROOT/dist/index.html" ]]; then
  echo "ERROR: build did not produce dist/index.html"
  exit 1
fi

echo "==> Packaged $ROOT/dist"
