#!/usr/bin/env python3
"""
On-device benchmark for typed CameraSettings / spectrum / fast+slow apply.

Worst-case focus: full 4056x3040. Run while astroscop-camera.service is stopped.

  python3 test_cam_settings_bench.py --out /tmp/cam_settings_bench/run1
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
from PIL import Image

import cam_picamera2 as cam
from cam_settings import CameraSettings, diff_settings, from_legacy_dict
from cam_spectrum import compute_rgb_spectrum
import imgutils


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def save_preview(rgb, path, max_edge=640):
    img = Image.fromarray(rgb)
    w, h = img.size
    scale = min(1.0, float(max_edge) / max(w, h))
    if scale < 1.0:
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.BILINEAR)
    img.save(path, format="BMP")


def timed(fn, *args, **kwargs):
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    return result, time.perf_counter() - t0


def assert_true(cond, msg, failures):
    if not cond:
        failures.append(msg)
        logging.getLogger("bench").error("FAIL: %s", msg)
    else:
        logging.getLogger("bench").info("PASS: %s", msg)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--frames", type=int, default=3)
    ap.add_argument("--fast-iters", type=int, default=5)
    ap.add_argument("--slow-iters", type=int, default=2)
    ap.add_argument("--emit-burst", type=int, default=40)
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format=cam.formatstr)
    log = logging.getLogger("bench")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.out or os.path.join("/tmp/cam_settings_bench", run_id)
    os.makedirs(out, exist_ok=True)

    failures = []
    results = {
        "run_id": run_id,
        "started": time.time(),
        "cases": {},
        "failures": failures,
    }

    # --- unit: settings ingest ---
    s0 = CameraSettings(sensor_preset="full", shutter_us=50000, analog_gain=1.25)
    legacy_in = {
        "shutterSpeed": 80000,
        "analog_gain": 2.5,
        "redgain": 1.1,
        "bluegain": 0.9,
        "isovalue": 400,  # must be stripped / ignored
        "shootresol": {"name": "bin2x2", "width": 2028, "height": 1520},
    }
    s1 = from_legacy_dict(legacy_in, cam.SENSOR_PRESETS)
    assert_true(s1.analog_gain == 2.5, "legacy ingest uses analog_gain not ISO", failures)
    assert_true(s1.shutter_us == 80000, "legacy shutterSpeed maps to shutter_us", failures)
    assert_true(s1.sensor_preset == "bin2x2", "legacy shootresol maps preset", failures)
    d = diff_settings(s0, s1)
    assert_true(d.slow_changed, "preset change is slow", failures)
    s2 = s1.model_copy(update={"analog_gain": 3.0})
    d2 = diff_settings(s1, s2)
    assert_true(d2.fast_changed and not d2.slow_changed, "gain-only is fast", failures)
    results["cases"]["settings_unit"] = {"ok": len(failures) == 0, "diff_slow": d.model_dump(), "diff_fast": d2.model_dump()}

    # --- live camera ---
    settings_full = CameraSettings(
        sensor_preset="full",
        shutter_us=20000,
        analog_gain=1.0,
        include_raw=False,
        science_neutral=True,
        preview_div=2,
        max_emit_fps=8.0,
    )
    picam2 = None
    try:
        (picam2, _legacy, mode, info), open_s = timed(
            cam.open_from_settings, settings_full, warmup_s=0.4, buffer_count=2
        )
        results["cases"]["open_full"] = {
            "open_s": round(open_s, 4),
            "mode_size": None if mode is None else list(mode.get("size", ())),
            "config": info,
        }
        assert_true(
            mode is not None and tuple(mode["size"]) == (4056, 3040),
            "full preset selects 4056x3040",
            failures,
        )

        # Capture frames
        caps = []
        for i in range(args.frames):
            rgb, dt = timed(cam.capture_rgb_frame, picam2)
            used = cam.used_params_from_settings(picam2, settings_full, rgb.shape)
            caps.append(
                {
                    "i": i,
                    "shape": list(rgb.shape),
                    "capture_s": round(dt, 4),
                    "shutter_us": used.get("shutter_us"),
                    "analog_gain": used.get("analog_gain"),
                }
            )
            if i == 0:
                save_preview(rgb, os.path.join(out, "full_preview.bmp"))
                np.save(os.path.join(out, "full_frame0_rgb.npy"), rgb)
        results["cases"]["capture_full"] = caps
        assert_true(caps[0]["shape"] == [3040, 4056, 3], "full RGB shape", failures)

        # Spectrum full vs display
        rgb0 = np.load(os.path.join(out, "full_frame0_rgb.npy"))
        _, t_full_spec = timed(compute_rgb_spectrum, rgb0)
        disp = np.asarray(
            imgutils.resizeImage(Image.fromarray(rgb0), (640, 480))
        )
        spec_disp, t_disp_spec = timed(compute_rgb_spectrum, disp)
        write_json(os.path.join(out, "spectrum_display.json"), spec_disp.model_dump())
        results["cases"]["spectrum"] = {
            "full_res_s": round(t_full_spec, 4),
            "display_640x480_s": round(t_disp_spec, 4),
            "display_mean_r": spec_disp.mean_r,
            "display_bins": spec_disp.bins,
            "hist_len": len(spec_disp.hist_r),
        }
        assert_true(len(spec_disp.hist_r) == 256, "256-bin hist_r", failures)
        assert_true(t_disp_spec < t_full_spec or t_disp_spec < 0.05, "display spectrum is cheap", failures)

        # Fast apply sweep — stay above full-mode FrameDuration floor (~85 ms)
        fast_timings = []
        for i in range(args.fast_iters):
            gain = 1.0 + 0.15 * i
            shutter = 100000 + 10000 * i
            s_fast = settings_full.model_copy(
                update={"analog_gain": gain, "shutter_us": shutter, "colour_gain_r": 1.0 + 0.02 * i}
            )
            _, dt = timed(cam.apply_settings_fast, picam2, s_fast)
            # Controls apply on subsequent frames; flush a few before asserting.
            for _ in range(3):
                cam.capture_rgb_frame(picam2)
            rgb, _ = timed(cam.capture_rgb_frame, picam2)
            used = cam.used_params_from_settings(picam2, s_fast, rgb.shape)
            err_g = abs(float(used["analog_gain"]) - gain)
            err_s = abs(int(used["shutter_us"]) - shutter)
            fast_timings.append(
                {
                    "apply_s": round(dt, 4),
                    "req_gain": gain,
                    "got_gain": used["analog_gain"],
                    "req_shutter": shutter,
                    "got_shutter": used["shutter_us"],
                    "err_gain": err_g,
                    "err_shutter_us": err_s,
                }
            )
            assert_true(err_g < 0.35, f"fast gain track iter {i} err={err_g}", failures)
            assert_true(err_s < max(1500, 0.05 * shutter), f"fast shutter track iter {i} err={err_s}", failures)
        results["cases"]["apply_fast"] = fast_timings

        # Slow apply toggles
        slow_timings = []
        for i in range(args.slow_iters):
            target = "bin2x2" if i % 2 == 0 else "full"
            s_slow = settings_full.model_copy(
                update={"sensor_preset": target, "shutter_us": 20000, "analog_gain": 1.0}
            )
            (_params, mode2, info2), dt = timed(
                cam.apply_settings_slow, picam2, s_slow, warmup_s=0.25, buffer_count=2
            )
            expect = cam.SENSOR_PRESETS[target]["size"]
            got = tuple(mode2["size"]) if mode2 else None
            slow_timings.append(
                {
                    "apply_s": round(dt, 4),
                    "preset": target,
                    "mode_size": list(got) if got else None,
                }
            )
            assert_true(got == expect, f"slow reconfig to {target}", failures)
        # Return to full for emit bench
        cam.apply_settings_slow(
            picam2,
            settings_full,
            warmup_s=0.25,
            buffer_count=2,
        )
        results["cases"]["apply_slow"] = slow_timings

        # Emit path simulation: resize+spectrum+jpeg with 8fps skip
        max_fps = 8.0
        min_period = 1.0 / max_fps
        last = 0.0
        emitted = 0
        skipped = 0
        emit_dts = []
        t_burst0 = time.perf_counter()
        for i in range(args.emit_burst):
            rgb = cam.capture_rgb_frame(picam2)
            now = time.perf_counter()
            if now - last < min_period:
                skipped += 1
                continue
            t0 = time.perf_counter()
            im = Image.fromarray(rgb)
            disp = imgutils.resizeImage(im, (640, 480))
            compute_rgb_spectrum(np.asarray(disp))
            imgutils.pilimTobase64Jpg(disp)
            emit_dts.append(time.perf_counter() - t0)
            last = time.perf_counter()
            emitted += 1
        burst_s = time.perf_counter() - t_burst0
        emit_fps = emitted / burst_s if burst_s > 0 else 0
        results["cases"]["emit_8fps"] = {
            "burst_frames_attempted_capture": args.emit_burst,
            "emitted": emitted,
            "skipped": skipped,
            "burst_s": round(burst_s, 4),
            "emit_fps": round(emit_fps, 4),
            "mean_process_s": round(float(np.mean(emit_dts)), 4) if emit_dts else None,
            "max_process_s": round(float(np.max(emit_dts)), 4) if emit_dts else None,
        }
        assert_true(emit_fps <= max_fps * 1.15, f"emit fps {emit_fps} <= ~8", failures)
        assert_true(emitted >= 1, "at least one emit", failures)

    except Exception as e:
        log.exception("bench aborted")
        failures.append(f"exception: {e!r}")
    finally:
        cam.close_camera(picam2)
        log.info("camera closed")

    results["finished"] = time.time()
    results["duration_s"] = round(results["finished"] - results["started"], 2)
    results["ok"] = len(failures) == 0
    write_json(os.path.join(out, "manifest.json"), results)
    print(out)
    print("OK" if results["ok"] else "FAIL")
    return 0 if results["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
