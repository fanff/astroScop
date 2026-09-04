#!/usr/bin/env bash
# Back-compat wrapper. Prefer: ./deploy/deploy.sh  or  npm run deploy:pi
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$ROOT/deploy/deploy.sh" "$@"
