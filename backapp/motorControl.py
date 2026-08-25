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
from pico_motor import (
    PicoMotorClient,
    PicoNotFoundError,
    resolve_pico_port_required,
)
from asc_rates import (
    ASC_STEPS_PER_DEGREE,
    sidereal_speed_cmd,
)

# Open-loop degrees from empirical sidereal lock (see asc_rates.py).
DEFAULT_STEP_BY_DEGREE = ASC_STEPS_PER_DEGREE
TELEMETRY_PERIOD_S = 0.2
SEARCH_PERIOD_S = 0.5
PING_PERIOD_S = 5.0

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
ui_armed = False
link_error: Optional[str] = None
force_rescan: Optional[asyncio.Event] = None
serial_lock: Optional[asyncio.Lock] = None


def _request_rescan() -> None:
    if force_rescan is not None:
        force_rescan.set()


def motor_info_payload(*, link: Optional[str] = None) -> dict:
    """Build motorInfo including explicit Pico link status for the UI."""
    snap = tracker.snapshot()
    connected = pico is not None
    if link is None:
        if connected:
            link = "connected"
        elif link_error:
            link = "error"
        else:
            link = "searching"
    snap.update(
        {
            "connected": connected,
            "port": pico.port if pico is not None else None,
            "link": link,
            "error": link_error,
            "armed": ui_armed,
        }
    )
    return snap


async def emit_motor_info(state: Jobstate, *, link: Optional[str] = None) -> None:
    await state.send_msg("motorInfo", motor_info_payload(link=link))


async def _serial_call(fn, *args):
    """Run blocking Pico I/O under the shared lock (WS + telemetry share one port)."""
    if serial_lock is None:
        return await asyncio.to_thread(fn, *args)
    async with serial_lock:
        return await asyncio.to_thread(fn, *args)


def _open_pico_client(resolved: str) -> PicoMotorClient:
    """Blocking open + boot drain + ping/status (run in a thread)."""
    client = PicoMotorClient(resolved)
    try:
        for line in client.drain_boot():
            log.info("boot: %s", line)
        log.info("ping: %s", client.ping())
        log.info("status: %s", client.status())
        return client
    except Exception:
        try:
            client.close()
        except Exception:
            pass
        raise


async def _close_pico() -> None:
    global pico, link_error
    client = pico
    pico = None
    if client is None:
        return
    try:
        await _serial_call(client.close)
    except Exception:
        pass
    tracker.stop_all()
    log.info("Pico serial closed")


async def handle_ctlparams(msg_type: str, msg: dict, state: Jobstate) -> None:
    global pico, ui_armed, link_error
    log_h = logging.getLogger("handle_ctlparams")

    if msg_type != "ctlparams":
        return

    key = msg.get("k")
    val = msg.get("v")
    log_h.info("ctlparams %s=%s", key, val)

    if key == "MOTOR_ARM":
        ui_armed = True
        if pico is not None:
            try:
                await _serial_call(pico.ping)
                link_error = None
                log_h.info("MOTOR_ARM — Pico healthy on %s", pico.port)
                await emit_motor_info(state, link="connected")
                return
            except Exception as e:
                link_error = str(e)
                log_h.warning("MOTOR_ARM — ping failed, rescanning: %s", e)
                await _close_pico()
                _request_rescan()
                await emit_motor_info(state, link="error")
                return
        log_h.info("MOTOR_ARM — no Pico yet, requesting scan")
        _request_rescan()
        await emit_motor_info(state, link="searching")
        return

    if key == "MOTOR_DISARM":
        ui_armed = False
        log_h.info("MOTOR_DISARM")
        await emit_motor_info(state)
        return

    if key == "ASC":
        if pico is None:
            log_h.warning("ASC ignored — Pico not open")
            return
        try:
            reply = await _serial_call(pico.set_speed_asc, float(val))
        except Exception as e:
            link_error = str(e)
            log_h.warning("ASC serial error: %s", e)
            await _close_pico()
            _request_rescan()
            await emit_motor_info(state, link="error")
            return
        tracker.asc.set_command(pico.last_dir, pico.last_step_us, pico.enabled)
        log_h.info("ASC set: %s", reply)
        await emit_motor_info(state, link="connected")
        return

    if key == "DEC":
        if pico is None:
            log_h.warning("DEC ignored — Pico not open")
            return
        try:
            reply = await _serial_call(pico.set_speed_dec, float(val))
        except Exception as e:
            link_error = str(e)
            log_h.warning("DEC serial error: %s", e)
            await _close_pico()
            _request_rescan()
            await emit_motor_info(state, link="error")
            return
        tracker.dec.set_command(
            pico.last_dec_dir, pico.last_dec_step_us, pico.dec_enabled
        )
        log_h.info("DEC set: %s", reply)
        await emit_motor_info(state, link="connected")
        return

    if key == "ASC_SIDEREAL":
        if pico is None:
            log_h.warning("ASC_SIDEREAL ignored — Pico not open")
            return
        speed = sidereal_speed_cmd()
        try:
            reply = await _serial_call(pico.set_speed_asc, speed)
        except Exception as e:
            link_error = str(e)
            log_h.warning("ASC_SIDEREAL serial error: %s", e)
            await _close_pico()
            _request_rescan()
            await emit_motor_info(state, link="error")
            return
        tracker.asc.set_command(pico.last_dir, pico.last_step_us, pico.enabled)
        log_h.info("ASC_SIDEREAL (v=%s): %s", speed, reply)
        await emit_motor_info(state, link="connected")
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
            try:
                reply = await _serial_call(pico.hard_stop_asc)
                tracker.asc.stop()
                log_h.info("ASC_RESET → hard stop: %s", reply)
                await emit_motor_info(state, link="connected")
            except Exception as e:
                link_error = str(e)
                log_h.warning("ASC_RESET serial error: %s", e)
                await _close_pico()
                _request_rescan()
                await emit_motor_info(state, link="error")
        return

    if key in ("DEC_RESET",):
        if pico is not None:
            try:
                reply = await _serial_call(pico.hard_stop_dec)
                tracker.dec.stop()
                log_h.info("DEC_RESET → hard stop: %s", reply)
                await emit_motor_info(state, link="connected")
            except Exception as e:
                link_error = str(e)
                log_h.warning("DEC_RESET serial error: %s", e)
                await _close_pico()
                _request_rescan()
                await emit_motor_info(state, link="error")
        return

    if key in ("DEC_CURR", "ASC_CURR"):
        log_h.info("ignored (no TMC UART current yet): %s=%s", key, val)
        return

    log_h.info("unknown ctlparams key: %s", key)


@infiniteRetry(rerunTiming=2)
async def motor_ws_job(uri: str, state: Jobstate) -> None:
    await clientConnection(uri, handle_ctlparams, state)


async def _wait_rescan_or_timeout(timeout_s: float) -> None:
    """Sleep until force_rescan or timeout; clear the event if set."""
    if force_rescan is None:
        await asyncio.sleep(timeout_s)
        return
    try:
        await asyncio.wait_for(force_rescan.wait(), timeout=timeout_s)
    except asyncio.TimeoutError:
        return
    finally:
        force_rescan.clear()


async def motor_serial_job(port: Optional[str], state: Jobstate) -> None:
    """Scan / open / telemetry loop — never exits; no systemd restart needed."""
    global pico, link_error

    while True:
        try:
            # --- searching / open ---
            while pico is None:
                try:
                    resolved = resolve_pico_port_required(port)
                except PicoNotFoundError as e:
                    link_error = str(e)
                    await emit_motor_info(state, link="searching")
                    await _wait_rescan_or_timeout(SEARCH_PERIOD_S)
                    continue

                log.info("opening Pico ASC/DEC on %s", resolved)
                try:
                    if serial_lock is None:
                        client = await asyncio.to_thread(_open_pico_client, resolved)
                    else:
                        async with serial_lock:
                            client = await asyncio.to_thread(
                                _open_pico_client, resolved
                            )
                except Exception as e:
                    link_error = str(e)
                    log.warning("open failed on %s: %s", resolved, e)
                    await emit_motor_info(state, link="error")
                    await _wait_rescan_or_timeout(SEARCH_PERIOD_S)
                    continue

                pico = client
                link_error = None
                tracker.stop_all()
                log.info("Pico linked on %s", resolved)
                await emit_motor_info(state, link="connected")

            # --- connected telemetry + health ---
            last_ping = time.monotonic()
            while pico is not None:
                if force_rescan is not None and force_rescan.is_set():
                    force_rescan.clear()
                    log.info("rescan requested — closing Pico link")
                    await _close_pico()
                    break

                now = time.monotonic()
                if now - last_ping >= PING_PERIOD_S:
                    try:
                        await _serial_call(pico.ping)
                        last_ping = now
                        link_error = None
                    except Exception as e:
                        link_error = str(e)
                        log.warning("health ping failed: %s", e)
                        await _close_pico()
                        await emit_motor_info(state, link="error")
                        break

                await emit_motor_info(state, link="connected")
                await asyncio.sleep(TELEMETRY_PERIOD_S)
        except Exception:
            log.exception("motor_serial_job iteration failed; continuing")
            await asyncio.sleep(SEARCH_PERIOD_S)


async def main(uri: str, port: Optional[str]) -> None:
    global force_rescan, serial_lock
    force_rescan = asyncio.Event()
    serial_lock = asyncio.Lock()
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
        help="serial port (default: first Pico vid 2e8a; no ACM0/COM5 fallback)",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=formatstr)
    args = parse_motor_args()
    asyncio.run(main(args.uri, args.port))
