#!/usr/bin/env bash
# After physically unplugging/replugging the Pico USB cable on piscope:
#   bash /tmp/flash_and_restart_motor.sh
set -euo pipefail

MAIN_SRC="${1:-/tmp/pico_main.py}"

echo "==> waiting for Pico ACM (unplug/replug if stuck)"
PORT=""
for i in $(seq 1 60); do
  PORT=$(ls /dev/ttyACM* 2>/dev/null | head -1 || true)
  if [ -n "$PORT" ]; then
    echo "found $PORT"
    break
  fi
  sleep 1
done
if [ -z "$PORT" ]; then
  echo "FAIL: no /dev/ttyACM* — physically unplug/replug Pico USB, then rerun"
  exit 1
fi

echo "==> stop motor worker (release serial)"
sudo systemctl stop astroscop-motor.service || true
sleep 1

echo "==> install mpremote if needed"
python3 -c "import mpremote" 2>/dev/null || pip3 install --user mpremote

echo "==> upload main.py to Pico"
python3 -m mpremote connect "$PORT" cp "$MAIN_SRC" :main.py
python3 -m mpremote connect "$PORT" reset
sleep 2

echo "==> protocol smoke"
python3 - <<PY
import time, serial
port = "$PORT"
ser = serial.Serial(port, 115200, timeout=1.5)
time.sleep(2.0)
while True:
    line = ser.readline()
    if not line:
        break
    print("boot:", line.decode("ascii", "replace").strip())
for cmd in (b"ping\n", b"status\n"):
    ser.write(cmd); ser.flush()
    raw = ser.readline()
    print(cmd.strip().decode(), "->", (raw or b"<timeout>").decode("ascii", "replace").strip())
    if not raw:
        raise SystemExit(1)
ser.close()
print("PASS protocol")
PY

echo "==> restart backend services"
sudo systemctl restart astroscop-rootserver.service
sleep 1
sudo systemctl restart astroscop-motor.service
sleep 2
systemctl --no-pager --full status astroscop-rootserver.service astroscop-motor.service || true
journalctl -u astroscop-motor.service -n 20 --no-pager
