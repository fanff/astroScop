#!/usr/bin/env bash
# Package wasp and publish it to the Pi (default host: piscope) on port 80.
set -euo pipefail

HOST="${ASTROSCOP_PI_HOST:-piscope}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE_STAGING="/tmp/wasp-ui"
REMOTE_DEPLOY="/tmp/wasp-deploy"

cd "$ROOT"
"$ROOT/deploy/package.sh"

echo "==> Uploading to ${HOST}"
ssh "$HOST" "rm -rf '$REMOTE_STAGING' '$REMOTE_DEPLOY' && mkdir -p '$REMOTE_STAGING' '$REMOTE_DEPLOY'"
# Prefer rsync when present; fall back to tar+ssh (Windows OpenSSH).
if command -v rsync >/dev/null 2>&1; then
  rsync -az --delete "$ROOT/dist/" "${HOST}:${REMOTE_STAGING}/"
  rsync -az "$ROOT/deploy/install_on_pi.sh" "$ROOT/deploy/nginx-astroscop-ui.conf" "${HOST}:${REMOTE_DEPLOY}/"
else
  tar -C "$ROOT/dist" -cf - . | ssh "$HOST" "tar -C '$REMOTE_STAGING' -xf -"
  tar -C "$ROOT/deploy" -cf - install_on_pi.sh nginx-astroscop-ui.conf | ssh "$HOST" "tar -C '$REMOTE_DEPLOY' -xf -"
fi

echo "==> Installing on ${HOST}"
ssh "$HOST" "chmod +x '$REMOTE_DEPLOY/install_on_pi.sh' && '$REMOTE_DEPLOY/install_on_pi.sh' '$REMOTE_STAGING' '$REMOTE_DEPLOY/nginx-astroscop-ui.conf'"

echo "==> UI should be at http://${HOST}/"
