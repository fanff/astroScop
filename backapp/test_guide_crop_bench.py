#!/usr/bin/env python3
"""Live-camera crop vs off bench (Phase D).

Run on piscope with astroscop-camera.service STOPPED.

Gates (evolution §10):
  extract 64² p95 < 2 ms; 128² p95 < 5 ms
  extract+write extra p95 < 3 ms
  crop-on capture cadence / emit fps within 10% of crop-off

  python3 test_guide_crop_bench.py --out /tmp/guide_crop_bench/run1
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone

import numpy as np

import cam_picamera2 as cam
from cam_settings import CameraSettings
from guide_handoff import GuideTileSlot, extract_guide_tile, unique_slot_name

EXTRACT_GATE = {64: 0.002, 128: 0.005}
HANDOFF_EXTRA_GATE = 0.003
CADENCE_TOL = 0.10


def percentile(sorted_vals, p):
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = k - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def camera_service_active():
    try:
        r = subprocess.run(
            ["systemctl", "is-active", "astroscop-camera.service"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return r.stdout.strip() == "active"
    except Exception:
        return False


def stats(samples):
    s = sorted(samples)
    return {
        "n": len(s),
        "p50_s": percentile(s, 50),
        "p95_s": percentile(s, 95),
        "max_s": s[-1] if s else 0.0,
        "mean_s": float(np.mean(s)) if s else 0.0,
    }


def burst(picam2, n, *, crop_on, roi_half, slot):
    capture = []
    extract = []
    write_s = []
    emit = []
    t0 = time.perf_counter()
    last_emit = -1e9
    emitted = 0
    skipped = 0
    min_period = 1.0 / 8.0
    for i in range(n):
        c0 = time.perf_counter()
        rgb = cam.capture_rgb_frame(picam2)
        capture.append(time.perf_counter() - c0)
        if crop_on:
            e0 = time.perf_counter()
            tile = extract_guide_tile(rgb, 0.5, 0.5, roi_half=roi_half)
            extract.append(time.perf_counter() - e0)
            w0 = time.perf_counter()
            if tile is not None:
                slot.write(tile)
            write_s.append(time.perf_counter() - w0)
        now = time.perf_counter()
        if now - last_emit < min_period:
            skipped += 1
            continue
        p0 = time.perf_counter()
        cam.pack_preview_emit(rgb, 2, None)
        emit.append(time.perf_counter() - p0)
        last_emit = time.perf_counter()
        emitted += 1
    wall = time.perf_counter() - t0
    emit_fps = emitted / wall if wall > 0 else 0.0
    handoff = [a + b for a, b in zip(extract, write_s)] if crop_on else []
    return {
        "capture": stats(capture),
        "extract": stats(extract) if extract else None,
        "write": stats(write_s) if write_s else None,
        "handoff": stats(handoff) if handoff else None,
        "emit": stats(emit) if emit else None,
        "wall_s": wall,
        "emitted": emitted,
        "skipped": skipped,
        "emit_fps": emit_fps,
        "frame_time_ms": (stats(capture)["mean_s"] * 1e3),
        "rgb_shape": list(rgb.shape),
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--frames", type=int, default=40)
    args = ap.parse_args(argv)

    host = platform.node()
    machine = platform.machine()
    on_pi = host.lower() == "piscope" and machine.lower() in ("aarch64", "arm64")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.out or os.path.join("/tmp/guide_crop_bench", run_id)
    os.makedirs(out, exist_ok=True)

    failures = []
    if camera_service_active():
        failures.append("astroscop-camera.service is active; stop it first")
        write_json(
            os.path.join(out, "crop_bench.json"),
            {"pass": False, "host": host, "machine": machine, "failures": failures},
        )
        print("FAIL: stop astroscop-camera.service first")
        return 1

    settings = CameraSettings(
        sensor_preset="bin2x2",
        shutter_us=20000,
        analog_gain=1.0,
        include_raw=False,
        preview_div=2,
        max_emit_fps=8.0,
        track_enabled=False,
    )
    name = unique_slot_name()
    slot = GuideTileSlot.create(name)
    mode = None
    picam2 = None
    cases = {}
    try:
        picam2, _legacy, mode, _info = cam.open_from_settings(
            settings, warmup_s=0.4, buffer_count=2
        )
        off = burst(picam2, args.frames, crop_on=False, roi_half=32, slot=slot)
        cases["crop_off"] = off
        on64 = burst(picam2, args.frames, crop_on=True, roi_half=32, slot=slot)
        cases["crop_on_64"] = on64
        on128 = burst(picam2, args.frames, crop_on=True, roi_half=64, slot=slot)
        cases["crop_on_128"] = on128
    finally:
        if picam2 is not None:
            cam.close_camera(picam2)
        slot.close(unlink=True)

    def gate(cond, msg):
        if not cond:
            failures.append(msg)

    e64 = cases["crop_on_64"]["extract"]["p95_s"]
    e128 = cases["crop_on_128"]["extract"]["p95_s"]
    h64 = cases["crop_on_64"]["handoff"]["p95_s"]
    h128 = cases["crop_on_128"]["handoff"]["p95_s"]
    gate(e64 < EXTRACT_GATE[64], f"64 extract p95 {e64*1e3:.3f} ms >= 2 ms")
    gate(e128 < EXTRACT_GATE[128], f"128 extract p95 {e128*1e3:.3f} ms >= 5 ms")
    gate(h64 < HANDOFF_EXTRA_GATE, f"64 handoff p95 {h64*1e3:.3f} ms >= 3 ms")
    gate(h128 < HANDOFF_EXTRA_GATE, f"128 handoff p95 {h128*1e3:.3f} ms >= 3 ms")

    off_ft = cases["crop_off"]["frame_time_ms"]
    off_fps = cases["crop_off"]["emit_fps"]
    for key in ("crop_on_64", "crop_on_128"):
        ft = cases[key]["frame_time_ms"]
        fps = cases[key]["emit_fps"]
        if off_ft > 0:
            drift = abs(ft - off_ft) / off_ft
            gate(drift <= CADENCE_TOL, f"{key} frame_time drift {drift:.1%} > 10%")
        if off_fps > 0:
            drift_f = abs(fps - off_fps) / off_fps
            gate(drift_f <= CADENCE_TOL, f"{key} emit_fps drift {drift_f:.1%} > 10%")

    timing_ok = not failures
    passed = timing_ok and on_pi
    result = {
        "run_id": run_id,
        "stage": "guide_crop",
        "host": host,
        "machine": machine,
        "on_pi": on_pi,
        "timing_ok": timing_ok,
        "pass": passed,
        "failures": failures,
        "cases": cases,
        "mode": None if mode is None else list(mode.get("size", ())),
    }
    write_json(os.path.join(out, "crop_bench.json"), result)
    verdict = "PASS" if passed else "FAIL"
    print(f"guide_crop bench {verdict}")
    print(f"  host={host} machine={machine}")
    print(f"  extract 64 p95={e64*1e3:.3f} ms  128 p95={e128*1e3:.3f} ms")
    print(f"  handoff 64 p95={h64*1e3:.3f} ms  128 p95={h128*1e3:.3f} ms")
    print(
        f"  frame_time_ms off={off_ft:.2f} on64={cases['crop_on_64']['frame_time_ms']:.2f} "
        f"on128={cases['crop_on_128']['frame_time_ms']:.2f}"
    )
    print(
        f"  emit_fps off={off_fps:.3f} on64={cases['crop_on_64']['emit_fps']:.3f} "
        f"on128={cases['crop_on_128']['emit_fps']:.3f}"
    )
    for f in failures:
        print(f"  FAIL: {f}")
    print(f"  out={out}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
