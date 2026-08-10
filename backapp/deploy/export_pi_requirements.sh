#!/bin/bash
# Host helper: export a frozen requirements file from backapp/uv.lock.
# Copy/sync deploy/requirements.generated.txt to the Pi, then run install_on_pi.sh.
# The Pi does not need uv.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/deploy/requirements.generated.txt"

cd "$ROOT"
uv export --frozen --no-dev --no-hashes -o "$OUT"
echo "Wrote $OUT"
