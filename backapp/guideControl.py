#!/usr/bin/env python3
"""Guide worker: shm tiles (or --feed) → isolate → geom → PI.

Connects to the hub at /guide. With --emit-trims, GUIDE_D* go to the mixer
(still ignored until GUIDE_ENABLE). JPEG off unless --jpeg or guide_show_crop.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import sys
import time

from jobutils import Jobstate, clientConnection, formatstr, infiniteRetry
from guide_geom import cos_eff_and_pole_gate
from guide_handoff import SLOT_NAME, GuideTile, GuideTileSlot
from guide_isolate import synthetic_star_rgb
from guide_process import GuideConfig, GuideEngine, ProcessResult, config_from_settings
from guide_trace import GuideTraceBuffer
from ws_messages import (
    CTL_GUIDE_DASC,
    CTL_GUIDE_DDEC,
    CTL_GUIDE_DISABLE,
    CTL_GUIDE_ENABLE,
    CTL_GUIDE_TRACE_DUMP,
)

log = logging.getLogger("guideControl")

SHM_STALE_S = 1.0


def _drop_slot(slot: GuideTileSlot | None) -> None:
    if slot is None:
        return
    try:
        slot.close(unlink=False)
    except Exception:
        log.warning("guide shm close failed", exc_info=True)


def _try_attach() -> GuideTileSlot | None:
    try:
        slot = GuideTileSlot.attach(SLOT_NAME)
        log.info("attached shm %s", SLOT_NAME)
        return slot
    except FileNotFoundError:
        return None
    except Exception:
        log.warning("guide shm attach failed", exc_info=True)
        return None


def _synthetic_tile(seq: int, size: int = 64) -> GuideTile:
    lock = size / 2.0
    u = lock + 0.4 * ((seq % 7) - 3)
    v = lock + 0.3 * ((seq % 5) - 2)
    rgb = synthetic_star_rgb(size, size, u, v, sigma=2.8, peak=90.0)
    return GuideTile(rgb=rgb, origin_u=0, origin_v=0, lock_u=lock, lock_v=lock, t=time.time())


def _log_sample(sample, jpeg_len: int, every_s: float, last: list) -> None:
    now = time.monotonic()
    if now - last[0] < every_s:
        return
    last[0] = now
    cos_eff, pole = cos_eff_and_pole_gate(sample.dec_deg)
    log.info(
        "ok=%s reason=%s n=%s δ=%.2f f_mm=%.1f bin=%s cos_eff=%.3f pole=%s "
        "e_asc=%.2f\" e_dec=%.2f\" e_px=%.2f/%.2f e_asc_st=%.3f e_dec_st=%.3f "
        "dAsc=%.3f dDec=%.3f snr=%.1f jpeg=%s",
        sample.ok,
        getattr(sample, "reason", "") or "-",
        getattr(sample, "n_gated", 0),
        sample.dec_deg,
        sample.focal_mm,
        sample.bin,
        cos_eff,
        pole,
        sample.e_asc_arcsec,
        sample.e_dec_arcsec,
        getattr(sample, "e_asc_px", 0.0),
        getattr(sample, "e_dec_px", 0.0),
        sample.e_asc_steps,
        sample.e_dec_steps,
        sample.dAsc,
        sample.dDec,
        sample.snr,
        jpeg_len,
    )


def _sample_payload(sample, jpeg_bytes: bytes | None = None) -> dict:
    data = sample.model_dump()
    data.pop("msgtype", None)
    if jpeg_bytes:
        data["jpeg"] = base64.b64encode(jpeg_bytes).decode("ascii")
    return data


async def _send_ctl(state: Jobstate, key: str, val: float) -> None:
    if not state.is_connected():
        return
    try:
        await state.sc.send(json.dumps({"msgtype": "ctlparams", "k": key, "v": val}))
    except Exception:
        log.warning("ctlparams %s send failed", key, exc_info=True)
        state.sc = None


def _trace(state: Jobstate) -> GuideTraceBuffer:
    buf = getattr(state, "trace", None)
    if buf is None:
        buf = GuideTraceBuffer()
        state.trace = buf
    return buf


async def _send_trace_dump(state: Jobstate) -> None:
    buf = _trace(state)
    buf.prune(time.time())
    await state.send_msg("guideTrace", buf.to_payload())


def run_loop(
    engine: GuideEngine,
    *,
    feed: str,
    hz: float,
    jpeg: bool,
    emit_trims: bool,
    duration_s: float | None = None,
) -> dict:
    """Offline loop (benches / --no-hub). Does not talk to the hub."""
    period = 1.0 / max(float(hz), 0.1)
    slot = None
    if feed == "shm":
        while True:
            slot = _try_attach()
            if slot is not None:
                break
            log.info("waiting for guide tile slot %s", SLOT_NAME)
            time.sleep(1.0)
            if duration_s is not None:
                break

    seq = 0
    last_shm_seq = 0
    processed = 0
    skipped = 0
    generated = 0
    t_end = None if duration_s is None else time.monotonic() + float(duration_s)
    last_log = [0.0]
    t0 = time.monotonic()
    while True:
        loop_t0 = time.monotonic()
        if t_end is not None and loop_t0 >= t_end:
            break
        tile = None
        this_seq = None
        if feed == "synthetic":
            seq += 1
            generated += 1
            tile = _synthetic_tile(seq)
            this_seq = seq
        elif slot is not None:
            got = slot.read()
            if got is not None:
                token = int(got.t * 1e9)
                if token != last_shm_seq:
                    last_shm_seq = token
                    generated += 1
                    tile = got
                    this_seq = token
        if tile is None:
            time.sleep(min(0.05, period))
            continue
        want_jpeg = jpeg or bool(engine.cfg.show_crop)
        r: ProcessResult = engine.process_tile(tile, seq=this_seq, jpeg=want_jpeg)
        if r.skipped:
            skipped += 1
        else:
            processed += 1
            _log_sample(r.sample, len(r.jpeg or b""), 1.0, last_log)
            if emit_trims:
                log.warning("emit_trims with --no-hub; not sending dAsc=%s", r.sample.dAsc)
        elapsed = time.monotonic() - loop_t0
        sleep = period - elapsed
        if sleep > 0:
            time.sleep(sleep)
        else:
            skipped += 1
    return {
        "processed": processed,
        "skipped": skipped,
        "generated": generated,
        "elapsed_s": time.monotonic() - t0,
    }


async def handle_hub(msg_type: str, msg: dict, state: Jobstate) -> None:
    if msg_type == "ctlparams":
        key = msg.get("k")
        if key == CTL_GUIDE_TRACE_DUMP:
            await _send_trace_dump(state)
            return
        if key in (CTL_GUIDE_ENABLE, CTL_GUIDE_DISABLE):
            state.engine.reset()
            log.info("PI reset (%s)", key)
        return
    if msg_type != "params":
        return
    raw = msg.get("data") or {}
    prev = bool(getattr(state, "track_enabled", False))
    track_on = bool(raw.get("track_enabled"))
    if prev and not track_on:
        state.engine.reset()
        log.info("PI reset (track_enabled off)")
    state.track_enabled = track_on
    cfg = config_from_settings(raw)
    state.engine.apply_config(cfg)
    log.info(
        "guide cfg f_mm=%s dec=%s theta=%s flips=%s/%s show_crop=%s "
        "stack_n=%s kp=%s ki=%s preset=%s track=%s",
        cfg.f_mm,
        cfg.dec_deg,
        cfg.theta_deg,
        cfg.flip_asc,
        cfg.flip_dec,
        cfg.show_crop,
        cfg.stack_n,
        cfg.kp,
        cfg.ki,
        cfg.preset,
        track_on,
    )


@infiniteRetry(0.01)
async def hub_loop(uri: str, state: Jobstate) -> None:
    await clientConnection(uri, handle_hub, state)


async def tile_loop(
    state: Jobstate,
    *,
    feed: str,
    hz: float,
    jpeg: bool,
    emit_trims: bool,
    duration_s: float | None,
) -> dict:
    engine: GuideEngine = state.engine
    period = 1.0 / max(float(hz), 0.1)
    slot = None
    seq = 0
    last_shm_seq = 0
    processed = 0
    skipped = 0
    generated = 0
    stale_since: float | None = None
    t_end = None if duration_s is None else time.monotonic() + float(duration_s)
    last_log = [0.0]
    t0 = time.monotonic()
    while True:
        loop_t0 = time.monotonic()
        if t_end is not None and loop_t0 >= t_end:
            break
        tile = None
        this_seq = None
        if feed == "synthetic":
            seq += 1
            generated += 1
            tile = _synthetic_tile(seq)
            this_seq = seq
        else:
            if slot is None:
                slot = _try_attach()
                last_shm_seq = 0
                stale_since = None
                if slot is None:
                    log.info("waiting for guide tile slot %s", SLOT_NAME)
                    await asyncio.sleep(1.0)
                    if duration_s is not None:
                        break
                    continue
            try:
                got = slot.read()
            except Exception:
                log.warning("guide shm read failed; reattaching", exc_info=True)
                _drop_slot(slot)
                slot = None
                await asyncio.sleep(0.05)
                continue
            if got is not None:
                token = int(got.t * 1e9)
                if token != last_shm_seq:
                    last_shm_seq = token
                    generated += 1
                    tile = got
                    this_seq = token
                    stale_since = None
            track_on = bool(getattr(state, "track_enabled", False))
            if tile is None and track_on:
                if stale_since is None:
                    stale_since = loop_t0
                elif loop_t0 - stale_since >= SHM_STALE_S:
                    log.warning("guide shm stale for %.1fs; reattaching", SHM_STALE_S)
                    _drop_slot(slot)
                    slot = None
                    stale_since = None
                    continue
            elif tile is None:
                stale_since = None
        if tile is None:
            await asyncio.sleep(min(0.05, period))
            continue
        want_jpeg = jpeg or bool(engine.cfg.show_crop)
        r: ProcessResult = engine.process_tile(tile, seq=this_seq, jpeg=want_jpeg)
        if r.skipped:
            skipped += 1
        else:
            processed += 1
            _log_sample(r.sample, len(r.jpeg or b""), 1.0, last_log)
            trace = _trace(state)
            trace.append(r.sample)
            trace.maybe_flush()
            if state.is_connected() and not r.skipped:
                await state.send_msg(
                    "guideInfo", _sample_payload(r.sample, r.jpeg)
                )
                if emit_trims:
                    await _send_ctl(state, CTL_GUIDE_DASC, float(r.sample.dAsc))
                    await _send_ctl(state, CTL_GUIDE_DDEC, float(r.sample.dDec))
        elapsed = time.monotonic() - loop_t0
        sleep = period - elapsed
        if sleep > 0:
            await asyncio.sleep(sleep)
        else:
            skipped += 1
    return {
        "processed": processed,
        "skipped": skipped,
        "generated": generated,
        "elapsed_s": time.monotonic() - t0,
    }


async def amain(args) -> int:
    cfg = GuideConfig(f_mm=args.f_mm, dec_deg=args.dec_deg)
    state = Jobstate()
    state.engine = GuideEngine(cfg)
    state.trace = GuideTraceBuffer()
    if args.emit_trims:
        log.warning("emit-trims ON — mixer applies GUIDE_D* only after GUIDE_ENABLE")
    hub_task = asyncio.create_task(hub_loop(args.uri, state))
    try:
        stats = await tile_loop(
            state,
            feed=args.feed,
            hz=args.hz,
            jpeg=bool(args.jpeg),
            emit_trims=bool(args.emit_trims),
            duration_s=args.duration,
        )
        log.info("loop stats %s", stats)
        return 0
    finally:
        hub_task.cancel()
        try:
            await hub_task
        except asyncio.CancelledError:
            pass


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--feed", choices=("shm", "synthetic"), default="shm")
    ap.add_argument("--hz", type=float, default=5.0)
    ap.add_argument("--jpeg", action="store_true")
    ap.add_argument("--emit-trims", action="store_true", default=False)
    ap.add_argument("--f-mm", type=float, default=18.0)
    ap.add_argument("--dec-deg", type=float, default=0.0)
    ap.add_argument("--duration", type=float, default=None)
    ap.add_argument("--uri", default="ws://127.0.0.1:8765/guide")
    ap.add_argument("--no-hub", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format=formatstr)

    use_hub = not args.no_hub
    if args.duration is not None and not args.emit_trims:
        use_hub = False

    if not use_hub:
        cfg = GuideConfig(f_mm=args.f_mm, dec_deg=args.dec_deg)
        engine = GuideEngine(cfg)
        stats = run_loop(
            engine,
            feed=args.feed,
            hz=args.hz,
            jpeg=bool(args.jpeg),
            emit_trims=bool(args.emit_trims),
            duration_s=args.duration,
        )
        log.info("loop stats %s", stats)
        return 0

    return asyncio.run(amain(args))


if __name__ == "__main__":
    sys.exit(main())
