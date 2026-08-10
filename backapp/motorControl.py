"""ASC + DEC motor worker: UI ctlparams → Pico 2 W USB serial → motorInfo telemetry.

Replaces the legacy Arduino binary-protocol worker. Connects to rootserver at
ws://localhost:8765/motor and drives firm/pico2w/main.py over USB CDC.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
from typing import Optional

from jobutils import Jobstate, clientConnection, formatstr, infiniteRetry
from pico_motor import PicoMotorClient, resolve_pico_port
from asc_rates import (
    ASC_STEPS_PER_DEGREE,
    sidereal_speed_cmd,
)

# Open-loop degrees from empirical sidereal lock (see asc_rates.py).
DEFAULT_STEP_BY_DEGREE = ASC_STEPS_PER_DEGREE
TELEMETRY_PERIOD_S = 0.2

log = logging.getLogger("motor")


class AxisTracker:
    """Open-loop position from commanded step rate for one axis."""

    def __init__(self, step_by_degree: float = DEFAULT_STEP_BY_DEGREE):
        self.step_by_degree = float(step_by_degree)
        self.absolute_step = 0.0
        self._last_t = time.monotonic()
        self.cmd_dir = 0
        self.cmd_step_us = 0
        self.enabled = False

    def set_command(self, dir_bit: int, step_us: int, enabled: bool) -> None:
        self.integrate()
        self.cmd_dir = int(dir_bit)
        self.cmd_step_us = int(step_us) if enabled else 0
        self.enabled = bool(enabled) and self.cmd_step_us > 0

    def stop(self) -> None:
        self.integrate()
        self.cmd_step_us = 0
        self.enabled = False

    def zero(self) -> None:
        self.integrate()
        self.absolute_step = 0.0

    def integrate(self) -> None:
        now = time.monotonic()
        dt = now - self._last_t
        self._last_t = now
        if not self.enabled or self.cmd_step_us <= 0 or dt <= 0:
            return
        rate = 1_000_000.0 / float(self.cmd_step_us)
        signed = rate if self.cmd_dir == 0 else -rate
        self.absolute_step += signed * dt


class MountTracker:
    def __init__(self, step_by_degree: float = DEFAULT_STEP_BY_DEGREE):
        self.asc = AxisTracker(step_by_degree)
        self.dec = AxisTracker(step_by_degree)

    def stop_all(self) -> None:
        self.asc.stop()
        self.dec.stop()

    def snapshot(self) -> dict:
        self.asc.integrate()
        self.dec.integrate()
        return {
            "ascStep": int(round(self.asc.absolute_step)),
            "decStep": int(round(self.dec.absolute_step)),
            "newascDeg": float(self.asc.absolute_step) / self.asc.step_by_degree,
            "newdecDeg": float(self.dec.absolute_step) / self.dec.step_by_degree,
            "ascDir": self.asc.cmd_dir,
            "ascStepUs": self.asc.cmd_step_us if self.asc.enabled else 0,
            "ascEn": 1 if self.asc.enabled else 0,
            "decDir": self.dec.cmd_dir,
            "decStepUs": self.dec.cmd_step_us if self.dec.enabled else 0,
            "decEn": 1 if self.dec.enabled else 0,
        }


# Shared across WS + serial loops
pico: Optional[PicoMotorClient] = None
tracker = MountTracker()


async def handle_ctlparams(msg_type: str, msg: dict, state: Jobstate) -> None:
    global pico
    log_h = logging.getLogger("handle_ctlparams")

    if msg_type != "ctlparams":
        return

    key = msg.get("k")
    val = msg.get("v")
    log_h.info("ctlparams %s=%s", key, val)

    if key == "ASC":
        if pico is None:
            log_h.warning("ASC ignored — Pico not open")
            return
        reply = await asyncio.to_thread(pico.set_speed_asc, float(val))
        tracker.asc.set_command(pico.last_dir, pico.last_step_us, pico.enabled)
        log_h.info("ASC set: %s", reply)
        return

    if key == "DEC":
        if pico is None:
            log_h.warning("DEC ignored — Pico not open")
            return
        reply = await asyncio.to_thread(pico.set_speed_dec, float(val))
        tracker.dec.set_command(
            pico.last_dec_dir, pico.last_dec_step_us, pico.dec_enabled
        )
        log_h.info("DEC set: %s", reply)
        return

    if key == "ASC_SIDEREAL":
        if pico is None:
            log_h.warning("ASC_SIDEREAL ignored — Pico not open")
            return
        speed = sidereal_speed_cmd()
        reply = await asyncio.to_thread(pico.set_speed_asc, speed)
        tracker.asc.set_command(pico.last_dir, pico.last_step_us, pico.enabled)
        log_h.info("ASC_SIDEREAL (v=%s): %s", speed, reply)
        return

    if key == "ASC_ZERO":
        tracker.asc.zero()
        log_h.info("ASC_ZERO")
        return

    if key == "DEC_ZERO":
        tracker.dec.zero()
        log_h.info("DEC_ZERO")
        return

    if key in ("ASC_RESET",):
        if pico is not None:
            reply = await asyncio.to_thread(pico.hard_stop_asc)
            tracker.asc.stop()
            log_h.info("ASC_RESET → hard stop: %s", reply)
        return

    if key in ("DEC_RESET",):
        if pico is not None:
            reply = await asyncio.to_thread(pico.hard_stop_dec)
            tracker.dec.stop()
            log_h.info("DEC_RESET → hard stop: %s", reply)
        return

    if key in ("DEC_CURR", "ASC_CURR"):
        log_h.info("ignored (no TMC UART current yet): %s=%s", key, val)
        return

    log_h.info("unknown ctlparams key: %s", key)


@infiniteRetry(rerunTiming=2)
async def motor_ws_job(uri: str, state: Jobstate) -> None:
    await clientConnection(uri, handle_ctlparams, state)


@infiniteRetry(rerunTiming=5)
async def motor_serial_job(port: Optional[str], state: Jobstate) -> None:
    global pico

    resolved = resolve_pico_port(port)
    log.info("opening Pico ASC/DEC on %s", resolved)
    client = PicoMotorClient(resolved)
    try:
        for line in client.drain_boot():
            log.info("boot: %s", line)
        log.info("ping: %s", client.ping())
        log.info("status: %s", client.status())
        pico = client
        tracker.stop_all()

        while True:
            snap = tracker.snapshot()
            await state.send_msg("motorInfo", snap)
            await asyncio.sleep(TELEMETRY_PERIOD_S)
    finally:
        pico = None
        try:
            client.close()
        except Exception:
            pass
        tracker.stop_all()
        log.info("Pico serial closed")


async def main(uri: str, port: Optional[str]) -> None:
    state = Jobstate()
    task_ws = asyncio.create_task(motor_ws_job(uri, state))
    task_serial = asyncio.create_task(motor_serial_job(port, state))
    await task_ws
    await task_serial


def parse_motor_args(argv=None):
    parser = argparse.ArgumentParser(description="ASC+DEC Pico motor worker")
    parser.add_argument(
        "--uri",
        default="ws://localhost:8765/motor",
        help="rootserver motor WebSocket URI",
    )
    parser.add_argument(
        "--port",
        default=None,
        help="serial port (default: Pico vid 2e8a, else /dev/ttyACM0 or COM5)",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=formatstr)
    args = parse_motor_args()
    asyncio.run(main(args.uri, args.port))
