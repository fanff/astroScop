"""Hardware check: Pico ASC + DEC firmware over USB serial.

Validates the sparse text protocol in firm/pico2w/README.md by moving
ASC then DEC briefly left/right.

Usage (from repo root, 12V on, mpremote/repl closed):

    uv run python backapp/test_pico_motor_firmware_win.py
    uv run python backapp/test_pico_motor_firmware_win.py --port COM5
    uv run python backapp/test_pico_motor_firmware_win.py --port /dev/ttyACM0
    uv run python backapp/test_pico_motor_firmware_win.py --axis dec
"""

from __future__ import annotations

import argparse
import sys
import time

import serial

from pico_motor import PicoMotorClient, resolve_pico_port

STEP_US = 2000  # 500 step/s
BURST_S = 1.5


def run_axis_burst(client: PicoMotorClient, axis: str) -> None:
    print(f"--- {axis.upper()} ---", flush=True)
    print(f"LEFT  (dir=0) {BURST_S}s @ step_us={STEP_US} …", flush=True)
    r = client.cmd(f"{axis} dir=0 step_us={STEP_US}")
    print(" ", r)
    time.sleep(BURST_S)
    print(" ", client.cmd(f"{axis} step_us=0"))
    time.sleep(0.15)  # allow ramp-to-stop

    time.sleep(0.4)

    print(f"RIGHT (dir=1) {BURST_S}s @ step_us={STEP_US} …", flush=True)
    r = client.cmd(f"{axis} dir=1 step_us={STEP_US}")
    print(" ", r)
    time.sleep(BURST_S)
    print(" ", client.cmd(f"{axis} step_us=0"))
    time.sleep(0.15)


def run_motion_test(port: str, axes: list[str]) -> None:
    print(f"opening {port} …")
    client = PicoMotorClient(port)
    try:
        for line in client.drain_boot():
            print("boot:", line)

        print("ping …", end=" ", flush=True)
        r = client.ping()
        print(r)
        assert "pong" in r, r

        print("status …", end=" ", flush=True)
        r = client.status()
        print(r)
        assert "asc" in r and "dec" in r, r

        for axis in axes:
            run_axis_burst(client, axis)

        print("status …", end=" ", flush=True)
        print(client.status())
        print(" ", client.stop())
        print("PASS — protocol ok; motors should have moved for:", ", ".join(axes))
    finally:
        client.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate Pico ASC/DEC firmware over USB serial"
    )
    parser.add_argument(
        "--port",
        default=None,
        help="serial port (default: Pico vid 2e8a, else platform default)",
    )
    parser.add_argument(
        "--axis",
        choices=("asc", "dec", "both"),
        default="both",
        help="which axis to move (default: both)",
    )
    args = parser.parse_args(argv)

    port = resolve_pico_port(args.port)
    if not args.port:
        print(f"using port: {port}")

    axes = ["asc", "dec"] if args.axis == "both" else [args.axis]

    try:
        run_motion_test(port, axes)
    except serial.SerialException as exc:
        print(f"FAIL — serial: {exc}", file=sys.stderr)
        print("Close mpremote/repl and confirm serial port.", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"FAIL — {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
