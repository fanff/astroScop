#!/usr/bin/env python3
"""Upload a text file to MicroPython via raw REPL (no mpremote)."""
from __future__ import annotations

import sys
import time

import serial

PORT = sys.argv[1]
LOCAL = sys.argv[2]
REMOTE = sys.argv[3] if len(sys.argv) > 3 else "main.py"


def read_until(ser: serial.Serial, token: bytes, timeout: float = 3.0) -> bytes:
    end = time.time() + timeout
    buf = b""
    while time.time() < end:
        chunk = ser.read(64)
        if chunk:
            buf += chunk
            if token in buf:
                return buf
        else:
            time.sleep(0.02)
    raise TimeoutError(f"timeout waiting for {token!r}, got {buf!r}")


def enter_raw_repl(ser: serial.Serial) -> None:
    ser.write(b"\x03\x03")
    time.sleep(0.3)
    ser.reset_input_buffer()
    ser.write(b"\x01")  # Ctrl-A raw REPL
    read_until(ser, b"raw REPL", timeout=3.0)
    # drain prompt
    time.sleep(0.2)
    ser.read(200)


def exec_raw(ser: serial.Serial, code: str) -> bytes:
    data = code.encode("utf-8")
    ser.write(data)
    ser.write(b"\x04")  # Ctrl-D execute
    # response: OK<stdout>\x04<stderr>\x04>
    buf = read_until(ser, b"\x04>", timeout=10.0)
    return buf


def main() -> int:
    with open(LOCAL, "rb") as f:
        content = f.read()
    # ensure LF
    content = content.replace(b"\r\n", b"\n")

    ser = serial.Serial(PORT, 115200, timeout=0.2)
    time.sleep(1.0)
    enter_raw_repl(ser)

    # write file in chunks
    exec_raw(ser, f"f=open({REMOTE!r},'wb')\n")
    chunk_size = 128
    for i in range(0, len(content), chunk_size):
        chunk = content[i : i + chunk_size]
        exec_raw(ser, f"f.write({chunk!r})\n")
    exec_raw(ser, "f.close()\n")
    exec_raw(ser, f"print(open({REMOTE!r}).read(40))\n")

    # soft reset → run main.py
    ser.write(b"\x02")  # Ctrl-B exit raw
    time.sleep(0.2)
    ser.write(b"\x04")  # Ctrl-D soft reset
    time.sleep(2.0)
    boot = ser.read(500)
    print("boot after reset:", boot.decode("ascii", "replace"))
    ser.close()
    print(f"uploaded {LOCAL} -> :{REMOTE} ({len(content)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
