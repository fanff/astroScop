#!/bin/bash
set -euo pipefail

APP_DIR="/home/fanf/astroScop/backapp"
DEPLOY_DIR="$APP_DIR/deploy"
VENV_DIR="$APP_DIR/.venv"
REQ_FILE="$DEPLOY_DIR/requirements.generated.txt"

echo "==> Installing apt packages (system / camera stack)"
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3-venv \
  python3-opencv \
  python3-pil \
  python3-numpy \
  python3-picamera2

echo "==> Ensuring Pi requirements export"
if [[ -f "$REQ_FILE" ]]; then
  echo "Using existing $REQ_FILE"
elif command -v uv >/dev/null 2>&1; then
  echo "uv found; exporting from lock"
  (cd "$APP_DIR" && uv export --frozen --no-dev --no-hashes -o "$REQ_FILE")
else
  echo "ERROR: missing $REQ_FILE and uv is not installed."
  echo "On a host with uv, run: backapp/deploy/export_pi_requirements.sh"
  echo "Then sync deploy/requirements.generated.txt to the Pi and re-run this script."
  exit 1
fi

echo "==> Creating venv at $VENV_DIR (system-site-packages for picamera2/numpy/cv2/PIL)"
python3 -m venv --system-site-packages "$VENV_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r "$REQ_FILE"
deactivate

echo "==> Installing systemd units"
sudo cp "$DEPLOY_DIR/astroscop-rootserver.service" /etc/systemd/system/
sudo cp "$DEPLOY_DIR/astroscop-camera.service" /etc/systemd/system/
sudo cp "$DEPLOY_DIR/astroscop-motor.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable \
  astroscop-rootserver.service \
  astroscop-camera.service \
  astroscop-motor.service
sudo systemctl restart astroscop-rootserver.service
sleep 1
sudo systemctl restart astroscop-camera.service
sudo systemctl restart astroscop-motor.service

echo "==> Status"
systemctl --no-pager --full status astroscop-rootserver.service || true
systemctl --no-pager --full status astroscop-camera.service || true
systemctl --no-pager --full status astroscop-motor.service || true

echo "==> Done"
