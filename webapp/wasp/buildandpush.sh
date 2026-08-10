#!/usr/bin/env bash
set -euo pipefail
npm run build
rsync -azv dist/* scope:/var/www/html/
