#!/bin/bash
# Run on the Pi (ssh piscope). Installs nginx and publishes the compiled Vue UI on :80.
set -euo pipefail

SRC="${1:-/tmp/wasp-ui}"
WWW_ROOT="/var/www/astroscop"
SITE_NAME="astroscop-ui"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NGINX_CONF="${2:-$SCRIPT_DIR/nginx-astroscop-ui.conf}"

if [[ ! -d "$SRC" ]] || [[ ! -f "$SRC/index.html" ]]; then
  echo "ERROR: compiled UI not found at $SRC (missing index.html)"
  echo "Usage: $0 [dist-dir] [nginx-conf]"
  exit 1
fi
if [[ ! -f "$NGINX_CONF" ]]; then
  echo "ERROR: nginx config not found: $NGINX_CONF"
  exit 1
fi

echo "==> Installing nginx"
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y nginx

echo "==> Publishing UI to $WWW_ROOT"
sudo rm -rf "$WWW_ROOT"
sudo mkdir -p "$WWW_ROOT"
sudo cp -a "$SRC/." "$WWW_ROOT/"
sudo chown -R www-data:www-data "$WWW_ROOT"

echo "==> Installing nginx site $SITE_NAME"
sudo cp "$NGINX_CONF" "/etc/nginx/sites-available/${SITE_NAME}"
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sfn "/etc/nginx/sites-available/${SITE_NAME}" "/etc/nginx/sites-enabled/${SITE_NAME}"
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx

echo "==> Listening on :80"
ss -tlnp | grep ':80' || true
echo "==> Done. Open http://$(hostname)/  (WebSocket hub remains ws://$(hostname):8765)"
