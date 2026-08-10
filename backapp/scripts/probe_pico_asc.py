#!/usr/bin/env python3
"""Probe Pico ASC serial; optionally soft-interrupt and list files."""
import sys
import time

import serial

port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyACM0"
ser = serial.Serial(port, 115200, timeout=1.5)
time.sleep(2.5)
while True:
    line = ser.readline()
    if not line:
        break
    print("boot:", line.decode("ascii", "replace").strip())

ok = True
for cmd in (b"ping\n", b"status\n"):
    ser.write(cmd)
    ser.flush()
    raw = ser.readline()
    text = (raw or b"<timeout>").decode("ascii", "replace").strip()
    print(cmd.strip().decode(), "->", text)
    if not raw or not text.startswith("ok"):
        ok = False

if not ok:
    print("==> protocol failed; trying REPL")
    ser.write(b"\x03\x03")
    time.sleep(0.3)
    ser.write(b"\r\n")
    time.sleep(0.3)
    print("repl:", repr(ser.read(200)))
    ser.write(b"import os; print(os.listdir())\r\n")
    time.sleep(0.5)
    print("files:", repr(ser.read(400)))

ser.close()
sys.exit(0 if ok else 1)
