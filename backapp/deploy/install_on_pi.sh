#!/bin/bash
set -euo pipefail

APP_DIR="/home/fanf/astroScop/backapp"
DEPLOY_DIR="$APP_DIR/deploy"

echo "==> Installing apt packages"
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3-websockets \
  python3-opencv \
  python3-pil \
  python3-numpy \
  python3-psutil \
  python3-serial \
  python3-picamera2 \
  python3-pydantic

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
