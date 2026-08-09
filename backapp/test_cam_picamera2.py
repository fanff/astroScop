#!/usr/bin/env python3
"""
Live HQ camera suite for cam_picamera2 (IMX477).

Imports production helpers — keeps the camera warm across presets.
Run only while astroscop-camera.service is stopped/disabled.

Examples (on piscope, from backapp/):

  python3 test_cam_picamera2.py --suite --out /tmp/hq_cam_suite/run1
  python3 test_cam_picamera2.py --frames 2 --width 640 --height 480
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
from picamera2 import Picamera2

import cam_picamera2 as cam


def parse_cli(argv=None):
    p = argparse.ArgumentParser(description="Live test / suite for cam_picamera2 on IMX477")
    p.add_argument("--suite", action="store_true", help="run full warm multi-preset suite")
    p.add_argument("--frames", type=int, default=2, help="frames for simple mode")
    p.add_argument("--width", type=int, default=640)
    p.add_argument("--height", type=int, default=480)
    p.add_argument("--shutter", type=int, default=None, help="ExposureTime µs")
    p.add_argument("--gain", type=float, default=None, help="AnalogueGain")
    p.add_argument("--iso", type=float, default=None)
    p.add_argument("--expomode", choices=("off", "auto"), default="off")
    p.add_argument("--warmup", type=float, default=0.4)
    p.add_argument("--out", default=None, help="output directory")
    p.add_argument("--crop-frac", type=float, default=0.5, help="ScalerCrop linear fraction for crop preset")
    p.add_argument("--fast-frames", type=int, default=20, help="lucky burst length")
    p.add_argument("--fast-shutter", type=int, default=5000, help="fast burst ExposureTime µs")
    p.add_argument(
        "--long-shutters",
        default="1000000,5000000,10000000,20000000,30000000,45000000,60000000,120000000",
        help="comma-separated long ExposureTime µs values",
    )
    p.add_argument(
        "--long-mode",
        choices=("bin2x2", "full"),
        default="bin2x2",
        help="sensor mode used for long-exposure series",
    )
    p.add_argument("--skip-long", action="store_true", help="skip long-exposure series")
    p.add_argument("--skip-fast", action="store_true", help="skip fast burst")
    p.add_argument("--preview-max", type=int, default=640, help="max preview BMP edge")
    return p.parse_args(argv)


def build_params(width, height, shutter=None, gain=None, iso=None, expomode="off"):
    params = cam.cleanParams(None).copy()
    params["shootresol"] = {
        "name": "live-test",
        "width": int(width),
        "height": int(height),
        "mode": 0,
    }
    params["dispresol"] = dict(params["shootresol"])
    params["expomode"] = expomode
    params["denoise"] = False
    params["brightness"] = 50
    params["contrast"] = 0
    params["saturation"] = 0
    params["sharpness"] = 0
    params["redgain"] = 1.0
    params["bluegain"] = 1.0
    if shutter is not None:
        params["shutterSpeed"] = int(shutter)
    if gain is not None:
        params["analog_gain"] = float(gain)
        params["isovalue"] = 0
    if iso is not None:
        params["isovalue"] = float(iso)
    params["save_format"] = "none"
    return params


def _jsonable(obj):
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return str(obj)


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=_jsonable)


def save_preview_bmp(rgb, path, max_edge=640):
    img = Image.fromarray(rgb)
    w, h = img.size
    scale = min(1.0, float(max_edge) / max(w, h))
    if scale < 1.0:
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.BILINEAR)
    img.save(path, format="BMP")
    return path


def capture_science_frame(picam2, params, out_dir, index, include_raw_attempt, preview_max):
    """
    Capture one science frame: prefer Bayer .npy, else RGB .npy; always BMP preview.

    Uses a single libcamera request for raw+main when possible so long exposures
    are not paid twice.

    Timing keys (seconds):
      acquire_s — one sensor/ISP request (raw and/or rgb)
      save_science_s / save_preview_s — disk write
      processing_s — acquire + save total for this frame
    """
    os.makedirs(out_dir, exist_ok=True)
    meta = {
        "index": index,
        "requested_shutter": params.get("shutterSpeed"),
        "requested_analog_gain": params.get("analog_gain"),
        "capture_path": None,
        "timing": {},
    }
    t_frame0 = time.time()
    science_path = None
    rgb = None
    raw_u16 = None
    raw_info = None

    t1 = time.time()
    if include_raw_attempt:
        try:
            # One request → both streams (critical for long exposures).
            request = picam2.capture_request()
            try:
                raw8 = request.make_array("raw")
                rgb = cam.frame_to_rgb(request.make_array("main"))
                md = request.get_metadata()
            finally:
                request.release()

            arr = np.ascontiguousarray(raw8)
            if arr.dtype == np.uint8:
                if arr.shape[-1] % 2 != 0:
                    raise RuntimeError("raw uint8 buffer width is odd; cannot view as uint16")
                raw_u16 = arr.view(np.uint16)
            elif arr.dtype == np.uint16:
                raw_u16 = arr
            else:
                raw_u16 = arr.astype(np.uint16, copy=False)

            cfg = (picam2.camera_configuration().get("raw") or {})
            raw_info = {
                "format": cfg.get("format"),
                "configured_size": cfg.get("size"),
                "array_shape": list(raw_u16.shape),
                "dtype": str(raw_u16.dtype),
                "mean": float(raw_u16.mean()) if raw_u16.size else None,
                "min": int(raw_u16.min()) if raw_u16.size else None,
                "max": int(raw_u16.max()) if raw_u16.size else None,
            }
            meta["capture_path"] = "bayer"
            meta["timing"]["acquire_s"] = round(time.time() - t1, 4)
            meta["timing"]["single_request"] = True
            # Stash metadata fields normally filled by used_params_from_camera
            colour = md.get("ColourGains", (params.get("redgain", 1.0), params.get("bluegain", 1.0)))
            meta["_md"] = {
                "shutterSpeed": str(md.get("ExposureTime", params.get("shutterSpeed"))),
                "analog_gain": str(md.get("AnalogueGain", params.get("analog_gain"))),
                "digital_gain": str(md.get("DigitalGain", params.get("digital_gain"))),
                "redgain": float(colour[0]),
                "bluegain": float(colour[1]),
                "ScalerCrop": list(md["ScalerCrop"]) if md.get("ScalerCrop") is not None else None,
                "FrameDuration": md.get("FrameDuration"),
            }
        except Exception as exc:
            meta["bayer_error"] = repr(exc)
            logging.getLogger("suite").warning("Bayer+RGB single request failed: %s", exc)
            rgb = None

    if rgb is None:
        t1 = time.time()
        rgb = cam.capture_rgb_frame(picam2)
        meta["timing"]["acquire_rgb_s"] = round(time.time() - t1, 4)
        meta["timing"]["single_request"] = False
        used = cam.used_params_from_camera(picam2, params, rgb.shape)
        meta["used"] = {
            "shutterSpeed": used.get("shutterSpeed"),
            "analog_gain": used.get("analog_gain"),
            "digital_gain": used.get("digital_gain"),
            "redgain": used.get("redgain"),
            "bluegain": used.get("bluegain"),
            "ScalerCrop": used.get("ScalerCrop"),
            "FrameDuration": used.get("FrameDuration"),
        }
    else:
        meta["used"] = meta.pop("_md")

    if meta["capture_path"] == "bayer" and raw_u16 is not None:
        science_path = os.path.join(out_dir, f"frame_{index:03d}_bayer.npy")
        t1 = time.time()
        np.save(science_path, raw_u16)
        meta["timing"]["save_science_s"] = round(time.time() - t1, 4)
        meta["raw"] = raw_info
        meta["science_file"] = science_path
        meta["science_shape"] = list(raw_u16.shape)
        meta["science_dtype"] = str(raw_u16.dtype)
        meta["science_mean"] = float(raw_u16.mean())
        meta["science_filesize_bytes"] = int(os.path.getsize(science_path))

    meta["rgb_shape"] = list(rgb.shape)
    meta["rgb_mean"] = float(rgb.mean())

    if meta["capture_path"] is None:
        science_path = os.path.join(out_dir, f"frame_{index:03d}_rgb.npy")
        t1 = time.time()
        np.save(science_path, rgb)
        meta["timing"]["save_science_s"] = round(time.time() - t1, 4)
        meta["capture_path"] = "rgb_fallback"
        meta["science_file"] = science_path
        meta["science_shape"] = list(rgb.shape)
        meta["science_dtype"] = str(rgb.dtype)
        meta["science_mean"] = float(rgb.mean())
        meta["science_filesize_bytes"] = int(os.path.getsize(science_path))

    preview = os.path.join(out_dir, f"frame_{index:03d}_preview.bmp")
    t1 = time.time()
    save_preview_bmp(rgb, preview, max_edge=preview_max)
    meta["timing"]["save_preview_s"] = round(time.time() - t1, 4)
    meta["preview_bmp"] = preview
    meta["preview_filesize_bytes"] = int(os.path.getsize(preview))

    meta["timing"]["processing_s"] = round(time.time() - t_frame0, 4)
    meta["capture_s"] = meta["timing"]["processing_s"]

    fd = meta["used"].get("FrameDuration")
    if fd is not None:
        meta["timing"]["frame_duration_s"] = round(float(fd) / 1e6, 6)
    req = meta.get("requested_shutter")
    if req:
        meta["timing"]["requested_exposure_s"] = round(float(req) / 1e6, 6)
    got = meta["used"].get("shutterSpeed")
    if got is not None:
        try:
            meta["timing"]["got_exposure_s"] = round(float(got) / 1e6, 6)
        except Exception:
            pass

    write_json(os.path.join(out_dir, f"frame_{index:03d}_meta.json"), meta)
    return meta


def try_configure(picam2, params, sensor_size, include_raw, scaler_crop, warmup, buffer_count=3):
    """Configure with Bayer raw when requested; fall back to RGB-only main stream."""
    log = logging.getLogger("suite")
    last_err = None

    def _go(want_raw):
        started = bool(getattr(picam2, "started", False))
        if started:
            return cam.reconfigure_camera(
                picam2,
                params,
                sensor_size=sensor_size,
                include_raw=want_raw,
                science=True,
                buffer_count=buffer_count,
                scaler_crop=scaler_crop,
                warmup_s=warmup,
            )
        return cam.configure_and_start(
            picam2,
            params,
            sensor_size=sensor_size,
            include_raw=want_raw,
            science=True,
            buffer_count=buffer_count,
            scaler_crop=scaler_crop,
            warmup_s=warmup,
        )

    if include_raw:
        try:
            params, mode, info = _go(True)
            info["raw_enabled"] = True
            return params, mode, info
        except Exception as exc:
            last_err = exc
            log.warning("raw configure failed (%s); falling back to RGB-only", exc)
            try:
                picam2.stop()
            except Exception:
                pass

    params, mode, info = _go(False)
    info["raw_enabled"] = False
    info["raw_fallback_error"] = repr(last_err) if last_err else None
    return params, mode, info


def run_suite(args):
    log = logging.getLogger("suite")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_root = args.out or os.path.join("/tmp/hq_cam_suite", run_id)
    os.makedirs(out_root, exist_ok=True)

    manifest = {
        "run_id": run_id,
        "out": out_root,
        "started": time.time(),
        "presets": [],
        "notes": [
            "Daytime long exposures may saturate; check metadata for exposure stickiness.",
            "Science arrays are .npy (lossless). Previews are BMP (no JPEG).",
        ],
    }

    picam2 = Picamera2()
    include_raw = True
    try:
        probe = cam.probe_camera_capabilities(picam2)
        write_json(os.path.join(out_root, "probe.json"), probe)
        log.info("probe written (%d sensor modes)", len(probe.get("sensor_modes", [])))

        # --- spatial presets ---
        spatial = [
            {
                "name": "full",
                "sensor_size": cam.SENSOR_PRESETS["full"]["size"],
                "main": cam.SENSOR_PRESETS["full"]["size"],
                "shutter": 50000,
                "gain": 1.0,
                "scaler_crop": None,
                "frames": 1,
            },
            {
                "name": "bin2x2",
                "sensor_size": cam.SENSOR_PRESETS["bin2x2"]["size"],
                "main": cam.SENSOR_PRESETS["bin2x2"]["size"],
                "shutter": 50000,
                "gain": 1.0,
                "scaler_crop": None,
                "frames": 1,
            },
            {
                # Closest "small/fast" native mode — NOT true 3x3/4x4 full-FOV binning.
                "name": "bin2x2_crop",
                "sensor_size": cam.SENSOR_PRESETS["bin2x2_crop"]["size"],
                "main": cam.SENSOR_PRESETS["bin2x2_crop"]["size"],
                "shutter": 50000,
                "gain": 1.0,
                "scaler_crop": None,
                "frames": 1,
            },
        ]

        # Crop uses full sensor mode + ScalerCrop
        crop_rect = None
        limits = probe.get("scaler_crop")
        if limits is not None:
            _lo, hi, _default = limits
            crop_rect = cam.center_scaler_crop(hi, frac=args.crop_frac)
            spatial.append(
                {
                    "name": "crop",
                    "sensor_size": cam.SENSOR_PRESETS["full"]["size"],
                    "main": (min(2028, crop_rect[2]), min(1520, crop_rect[3])),
                    "shutter": 50000,
                    "gain": 1.0,
                    "scaler_crop": crop_rect,
                    "frames": 1,
                }
            )
            manifest["crop_rect"] = list(crop_rect)
        else:
            manifest["crop_skipped"] = "ScalerCrop control unavailable"
            log.warning("ScalerCrop unavailable — crop preset skipped")

        for preset in spatial:
            name = preset["name"]
            dest = os.path.join(out_root, name)
            os.makedirs(dest, exist_ok=True)
            params = build_params(
                preset["main"][0],
                preset["main"][1],
                shutter=preset["shutter"],
                gain=preset["gain"],
            )
            log.info("preset %s sensor=%s main=%s crop=%s", name, preset["sensor_size"], preset["main"], preset["scaler_crop"])
            params, mode, info = try_configure(
                picam2,
                params,
                sensor_size=preset["sensor_size"],
                include_raw=include_raw,
                scaler_crop=preset["scaler_crop"],
                warmup=args.warmup,
            )
            if not info.get("raw_enabled"):
                include_raw = False

            frames_meta = []
            for i in range(preset["frames"]):
                # Re-assert exposure each frame for constant series behaviour
                cam.apply_science_controls(picam2, params)
                if preset["scaler_crop"] is not None:
                    try:
                        cam.set_scaler_crop(picam2, preset["scaler_crop"])
                    except Exception:
                        log.exception("ScalerCrop re-apply failed")
                fm = capture_science_frame(
                    picam2,
                    params,
                    dest,
                    i,
                    include_raw_attempt=bool(info.get("raw_enabled")),
                    preview_max=args.preview_max,
                )
                frames_meta.append(fm)
                log.info(
                    "%s frame %s path=%s mean=%s shutter=%s",
                    name,
                    i,
                    fm.get("capture_path"),
                    fm.get("science_mean"),
                    fm.get("used", {}).get("shutterSpeed"),
                )

            entry = {
                "name": name,
                "config": info,
                "mode_size": None if mode is None else list(mode.get("size", ())),
                "frames": frames_meta,
            }
            write_json(os.path.join(dest, "preset.json"), entry)
            manifest["presets"].append({"name": name, "ok": True, "frames": len(frames_meta), "raw_enabled": info.get("raw_enabled")})

        # --- long exposures ---
        if not args.skip_long:
            long_mode = args.long_mode
            sensor_size = cam.SENSOR_PRESETS[long_mode]["size"]
            shutters = [int(x.strip()) for x in args.long_shutters.split(",") if x.strip()]
            for shutter in shutters:
                name = f"long_{shutter // 1000000}s" if shutter % 1000000 == 0 else f"long_{shutter}us"
                dest = os.path.join(out_root, name)
                os.makedirs(dest, exist_ok=True)
                params = build_params(sensor_size[0], sensor_size[1], shutter=shutter, gain=1.0)
                log.info("long exposure %s shutter=%s", name, shutter)
                params, mode, info = try_configure(
                    picam2,
                    params,
                    sensor_size=sensor_size,
                    include_raw=include_raw,
                    scaler_crop=None,
                    warmup=min(args.warmup, 0.5),
                    buffer_count=2,
                )
                if not info.get("raw_enabled"):
                    include_raw = False
                cam.apply_science_controls(picam2, params)
                fm = capture_science_frame(
                    picam2,
                    params,
                    dest,
                    0,
                    include_raw_attempt=bool(info.get("raw_enabled")),
                    preview_max=args.preview_max,
                )
                write_json(
                    os.path.join(dest, "preset.json"),
                    {"name": name, "config": info, "frames": [fm]},
                )
                manifest["presets"].append(
                    {
                        "name": name,
                        "ok": True,
                        "requested_shutter": shutter,
                        "got_shutter": fm.get("used", {}).get("shutterSpeed"),
                        "raw_enabled": info.get("raw_enabled"),
                    }
                )
                log.info(
                    "%s done requested=%s got=%s mean=%s",
                    name,
                    shutter,
                    fm.get("used", {}).get("shutterSpeed"),
                    fm.get("science_mean"),
                )

        # --- fast / lucky burst (camera stays warm, same config) ---
        if not args.skip_fast:
            name = "fast"
            dest = os.path.join(out_root, name)
            os.makedirs(dest, exist_ok=True)
            sensor_size = cam.SENSOR_PRESETS["bin2x2"]["size"]
            params = build_params(
                sensor_size[0],
                sensor_size[1],
                shutter=args.fast_shutter,
                gain=1.0,
            )
            params, mode, info = try_configure(
                picam2,
                params,
                sensor_size=sensor_size,
                include_raw=include_raw,
                scaler_crop=None,
                warmup=args.warmup,
                buffer_count=6,
            )
            if not info.get("raw_enabled"):
                include_raw = False
            cam.apply_science_controls(picam2, params)

            frames_meta = []
            dts = []
            prev = time.time()
            for i in range(args.fast_frames):
                fm = capture_science_frame(
                    picam2,
                    params,
                    dest,
                    i,
                    include_raw_attempt=bool(info.get("raw_enabled")),
                    preview_max=args.preview_max,
                )
                now = time.time()
                dts.append(now - prev)
                prev = now
                fm["inter_frame_s"] = dts[-1]
                frames_meta.append(fm)

            summary = {
                "name": name,
                "config": info,
                "frames": len(frames_meta),
                "inter_frame_s_mean": float(np.mean(dts)) if dts else None,
                "inter_frame_s_min": float(np.min(dts)) if dts else None,
                "inter_frame_s_max": float(np.max(dts)) if dts else None,
                "approx_fps": (1.0 / float(np.mean(dts))) if dts and np.mean(dts) > 0 else None,
            }
            write_json(os.path.join(dest, "preset.json"), {**summary, "frame_metas": frames_meta})
            manifest["presets"].append({**summary, "ok": True, "raw_enabled": info.get("raw_enabled")})
            log.info(
                "fast burst n=%s mean_dt=%.4fs ~fps=%.2f",
                len(frames_meta),
                summary["inter_frame_s_mean"] or -1,
                summary["approx_fps"] or -1,
            )

    finally:
        cam.close_camera(picam2)
        log.info("camera closed")

    manifest["finished"] = time.time()
    manifest["duration_s"] = round(manifest["finished"] - manifest["started"], 2)
    manifest["raw_enabled_final"] = include_raw
    write_json(os.path.join(out_root, "manifest.json"), manifest)
    log.info("suite done -> %s (%.1fs)", out_root, manifest["duration_s"])
    print(out_root)
    return 0


def run_simple(args):
    log = logging.getLogger("test_cam")
    out = args.out or "/tmp/hq_cam_test"
    os.makedirs(out, exist_ok=True)
    params = build_params(args.width, args.height, args.shutter, args.gain, args.iso, args.expomode)
    picam2 = None
    results = []
    try:
        picam2, params, mode = cam.open_configured_camera(params, science=True, warmup_s=args.warmup)
        mode_size = None if mode is None else mode.get("size")
        log.info("camera open; sensor mode size=%s", mode_size)
        for i in range(args.frames):
            meta = capture_science_frame(picam2, params, out, i, include_raw_attempt=True, preview_max=args.preview_max)
            results.append(meta)
            log.info("frame %s path=%s mean=%s", i, meta.get("capture_path"), meta.get("science_mean"))
    finally:
        cam.close_camera(picam2)
        log.info("camera closed")
    write_json(os.path.join(out, "results.json"), {"params": params, "frames": results})
    return 0 if results else 1


def main(argv=None):
    args = parse_cli(argv)
    logging.basicConfig(level=logging.INFO, format=cam.formatstr)
    if args.suite:
        return run_suite(args)
    return run_simple(args)


if __name__ == "__main__":
    sys.exit(main())
