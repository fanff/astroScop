#!/usr/bin/env bash
# Sync backapp to the Pi and run install_on_pi.sh (venv + systemd).
# Default SSH host: piscope. Override with ASTROSCOP_PI_HOST.
set -euo pipefail

HOST="${ASTROSCOP_PI_HOST:-piscope}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE_APP="/home/fanf/astroScop/backapp"
REQ_FILE="$ROOT/deploy/requirements.generated.txt"

if [[ ! -f "$REQ_FILE" ]]; then
  if command -v uv >/dev/null 2>&1; then
    echo "==> Exporting Pi requirements"
    "$ROOT/deploy/export_pi_requirements.sh"
  else
    echo "ERROR: missing $REQ_FILE and uv is not installed."
    echo "Run: backapp/deploy/export_pi_requirements.sh"
    exit 1
  fi
fi

echo "==> Syncing $ROOT → ${HOST}:${REMOTE_APP}"
ssh "$HOST" "mkdir -p '$REMOTE_APP'"

EXCLUDES=(
  --exclude '.venv'
  --exclude '__pycache__'
  --exclude '.pytest_cache'
  --exclude 'savedimgs'
  --exclude '*.pyc'
)

if command -v rsync >/dev/null 2>&1; then
  rsync -az --delete "${EXCLUDES[@]}" "$ROOT/" "${HOST}:${REMOTE_APP}/"
else
  ssh "$HOST" "rm -rf '$REMOTE_APP' && mkdir -p '$REMOTE_APP'"
  tar -C "$ROOT" "${EXCLUDES[@]}" -cf - . | ssh "$HOST" "tar -C '$REMOTE_APP' -xf -"
fi

echo "==> Installing on ${HOST}"
ssh "$HOST" "chmod +x '$REMOTE_APP/deploy/install_on_pi.sh' && '$REMOTE_APP/deploy/install_on_pi.sh'"

echo "==> Backend on ${HOST}: ws://$(printf '%s' "$HOST"):8765"
