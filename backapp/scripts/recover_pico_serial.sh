#!/usr/bin/env bash
set -euo pipefail

echo "==> stop motor worker"
sudo systemctl stop astroscop-motor.service || true
sleep 1
fuser /dev/ttyACM0 2>/dev/null || true

echo "==> usb devices"
lsusb -d 2e8a: || true
ls -l /dev/ttyACM* 2>/dev/null || echo "no ttyACM yet"

for d in /sys/bus/usb/devices/*; do
  if [ -f "$d/idVendor" ] && grep -qi 2e8a "$d/idVendor"; then
    echo "pico sysfs: $d"
    echo 0 | sudo tee "$d/authorized" >/dev/null
    sleep 1
    echo 1 | sudo tee "$d/authorized" >/dev/null
  fi
done

echo "==> wait for ttyACM"
PORT=""
for i in $(seq 1 30); do
  PORT=$(ls /dev/ttyACM* 2>/dev/null | head -1 || true)
  if [ -n "$PORT" ]; then
    ls -l "$PORT"
    break
  fi
  sleep 0.5
done

if [ -z "$PORT" ]; then
  echo "FAIL: no /dev/ttyACM after USB reauth — try unplug/replug Pico USB"
  exit 1
fi

echo "PORT=$PORT"
python3 - "$PORT" <<'PY'
import sys
import time
import serial

port = sys.argv[1]
print("open", port)
ser = serial.Serial(port, 115200, timeout=1.0)
time.sleep(2.5)
boot = b""
while True:
    chunk = ser.read(200)
    if not chunk:
        break
    boot += chunk
print("boot:", boot.decode("ascii", "replace"))

for cmd in (b"ping\n", b"status\n"):
    ser.reset_input_buffer()
    ser.write(cmd)
    ser.flush()
    raw = ser.readline()
    print(cmd.strip().decode(), "->", raw.decode("ascii", "replace").strip() if raw else "<timeout>")

ser.write(b"\x03\x03")
time.sleep(0.4)
ser.write(b"\r\n")
time.sleep(0.4)
print("repl:", ser.read(300).decode("ascii", "replace"))
ser.write(b"import os; print(os.listdir())\r\n")
time.sleep(0.6)
print("files:", ser.read(400).decode("ascii", "replace"))
ser.close()
PY
