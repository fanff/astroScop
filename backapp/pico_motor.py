"""Pico 2 W ASC + DEC stepper host client (USB serial text protocol).

Protocol: firm/pico2w/README.md
"""

from __future__ import annotations

import time
from typing import Optional, Tuple

import serial
import serial.tools.list_ports

BAUD = 115200
MIN_STEP_US = 50
MAX_STEP_US = 10_000_000
DEFAULT_PORT_WIN = "COM5"
DEFAULT_PORT_LINUX = "/dev/ttyACM0"

# Flip if mount direction is inverted relative to UI positive speed.
DIR_INVERT_ASC = False
DIR_INVERT_DEC = False


class PicoNotFoundError(LookupError):
    """No Raspberry Pi Pico USB CDC device is present."""


def find_pico_ports() -> list[str]:
    """Prefer Raspberry Pi Pico USB CDC (vid 2e8a)."""
    ports = []
    for p in serial.tools.list_ports.comports():
        if p.vid == 0x2E8A:
            ports.append(p.device)
    return ports


def resolve_pico_port_required(preferred: Optional[str] = None) -> str:
    """Return preferred port or first Pico VID match; raise if none."""
    if preferred:
        return preferred
    found = find_pico_ports()
    if found:
        return found[0]
    raise PicoNotFoundError("no Pico USB CDC (vid 2e8a) found")


def resolve_pico_port(preferred: Optional[str] = None) -> str:
    """Return preferred port, else first Pico VID match, else platform default.

    Prefer :func:`resolve_pico_port_required` for the motor worker so a missing
    board does not open a stale ``/dev/ttyACM0`` / ``COM5``.
    """
    try:
        return resolve_pico_port_required(preferred)
    except PicoNotFoundError:
        import sys

        return DEFAULT_PORT_WIN if sys.platform.startswith("win") else DEFAULT_PORT_LINUX


def speed_to_dir_step_us(
    speed: float, *, invert: bool = False
) -> Tuple[int, Optional[int]]:
    """Map signed steps/sec to (dir, step_us).

    speed == 0 → (dir unchanged conceptually, None) meaning stop.
    Positive speed → dir=0 (unless invert).
    """
    speed = float(speed)
    if speed == 0:
        return (0, None)

    dir_bit = 0 if speed > 0 else 1
    if invert:
        dir_bit ^= 1

    step_us = int(round(1_000_000.0 / abs(speed)))
    if step_us < MIN_STEP_US:
        step_us = MIN_STEP_US
    if step_us > MAX_STEP_US:
        step_us = MAX_STEP_US
    return dir_bit, step_us


def parse_status_fields(reply: str) -> dict:
    """Parse a single-axis reply ``ok motor=asc en=1 dir=0 step_us=2000``.

    For dual-axis ``status`` lines, use :func:`parse_dual_status`.
    """
    out = {}
    for token in reply.split():
        if "=" not in token:
            continue
        key, val = token.split("=", 1)
        key = key.lower()
        if key in ("en", "dir", "step_us"):
            try:
                out[key] = int(val)
            except ValueError:
                out[key] = val
        else:
            out[key] = val
    return out


def parse_dual_status(reply: str) -> dict[str, dict]:
    """Parse ``ok asc en=1 dir=0 step_us=2000 dec en=0 dir=0 step_us=0``.

    Also accepts single-motor ``ok motor=asc en=…`` → ``{"asc": {...}}``.
    """
    tokens = reply.split()
    # Single-motor command reply
    if any(t.lower().startswith("motor=") for t in tokens):
        fields = parse_status_fields(reply)
        name = str(fields.get("motor", "asc")).lower()
        axis = {
            k: fields[k] for k in ("en", "dir", "step_us") if k in fields
        }
        return {name: axis}

    axes: dict[str, dict] = {}
    current: Optional[str] = None
    for token in tokens:
        low = token.lower()
        if low in ("asc", "dec"):
            current = low
            axes.setdefault(current, {})
            continue
        if current is None or "=" not in token:
            continue
        key, val = token.split("=", 1)
        key = key.lower()
        if key in ("en", "dir", "step_us"):
            try:
                axes[current][key] = int(val)
            except ValueError:
                axes[current][key] = val
    return axes


class PicoMotorClient:
    def __init__(self, port: str, baud: int = BAUD, timeout: float = 1.0):
        self.port = port
        # Opening USB CDC often resets MicroPython; wait for boot before I/O.
        self.ser = serial.Serial(port, baud, timeout=timeout)
        time.sleep(2.0)
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        self.last_dir = 0
        self.last_step_us = 0
        self.enabled = False
        self.last_dec_dir = 0
        self.last_dec_step_us = 0
        self.dec_enabled = False

    def close(self) -> None:
        try:
            self.cmd("stop")
        except Exception:
            pass
        try:
            self.ser.close()
        except Exception:
            pass
        self.enabled = False
        self.last_step_us = 0
        self.dec_enabled = False
        self.last_dec_step_us = 0

    def cmd(self, line: str) -> str:
        payload = (line.strip() + "\n").encode("ascii")
        self.ser.write(payload)
        self.ser.flush()
        raw = self.ser.readline()
        if not raw:
            raise TimeoutError(f"no reply for: {line!r}")
        text = raw.decode("ascii", errors="replace").strip()
        if text.startswith("err"):
            raise RuntimeError(f"pico error for {line!r}: {text}")
        if not text.startswith("ok"):
            raise RuntimeError(f"unexpected reply for {line!r}: {text}")
        return text

    def drain_boot(self) -> list[str]:
        """Read any pending boot lines without failing if none."""
        lines = []
        old = self.ser.timeout
        self.ser.timeout = 0.2
        try:
            while True:
                line = self.ser.readline()
                if not line:
                    break
                lines.append(line.decode("ascii", errors="replace").strip())
        finally:
            self.ser.timeout = old
        return lines

    def ping(self) -> str:
        return self.cmd("ping")

    def _apply_axis_fields(self, name: str, fields: dict) -> None:
        if name == "asc":
            if "dir" in fields:
                self.last_dir = int(fields["dir"])
            if "step_us" in fields:
                self.last_step_us = int(fields["step_us"])
            if "en" in fields:
                self.enabled = bool(fields["en"])
        elif name == "dec":
            if "dir" in fields:
                self.last_dec_dir = int(fields["dir"])
            if "step_us" in fields:
                self.last_dec_step_us = int(fields["step_us"])
            if "en" in fields:
                self.dec_enabled = bool(fields["en"])

    def status(self) -> str:
        reply = self.cmd("status")
        for name, fields in parse_dual_status(reply).items():
            self._apply_axis_fields(name, fields)
        return reply

    def stop(self) -> str:
        reply = self.cmd("stop")
        self.last_step_us = 0
        self.enabled = False
        self.last_dec_step_us = 0
        self.dec_enabled = False
        return reply

    def hard_stop_asc(self) -> str:
        reply = self.cmd("asc en=0")
        self.last_step_us = 0
        self.enabled = False
        return reply

    def hard_stop_dec(self) -> str:
        reply = self.cmd("dec en=0")
        self.last_dec_step_us = 0
        self.dec_enabled = False
        return reply

    def set_speed_asc(self, speed: float) -> str:
        """Apply ASC signed steps/sec (0 = ramp-stop ASC only)."""
        dir_bit, step_us = speed_to_dir_step_us(speed, invert=DIR_INVERT_ASC)
        if step_us is None:
            reply = self.cmd("asc step_us=0")
            self.last_step_us = 0
            self.enabled = False
            return reply
        reply = self.cmd(f"asc dir={dir_bit} step_us={step_us}")
        self.last_dir = dir_bit
        self.last_step_us = step_us
        self.enabled = True
        return reply

    def set_speed_dec(self, speed: float) -> str:
        """Apply DEC signed steps/sec (0 = ramp-stop DEC only)."""
        dir_bit, step_us = speed_to_dir_step_us(speed, invert=DIR_INVERT_DEC)
        if step_us is None:
            reply = self.cmd("dec step_us=0")
            self.last_dec_step_us = 0
            self.dec_enabled = False
            return reply
        reply = self.cmd(f"dec dir={dir_bit} step_us={step_us}")
        self.last_dec_dir = dir_bit
        self.last_dec_step_us = step_us
        self.dec_enabled = True
        return reply
