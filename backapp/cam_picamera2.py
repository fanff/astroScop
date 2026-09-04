"""
Pi HQ camera worker using picamera2 (libcamera).

Typed settings live in ``cam_settings.CameraSettings``. Inbound WS ``params``
are validated once; slow fields reconfigure the sensor, fast fields use a
single ``set_controls`` (including ScalerCrop). Canonical gain is continuous
``analog_gain`` only — ISO is never applied.

Agent-facing contract (rootserver + UI): docs/camera-settings-contract.md

WebSocket message types: ``params`` (inbound), ``srcimage`` / ``camTiming``
(outbound) on the camera path used by rootserver and the UI.
"""

import asyncio
import concurrent
import datetime
import json
import logging
import sys
import time

import numpy as np
import websockets
from PIL import Image
from picamera2 import Picamera2

import imgutils
from jobutils import formatstr, makeMessage, MsgBuff, parse_args
from cam_settings import (
    CameraSettings,
    default_settings,
    diff_settings,
    from_legacy_dict,
    preview_wh_from_frame,
)
from cam_locator import apply_locator_overlay
from cam_spectrum import compute_rgb_spectrum
from cam_storage import ScienceStorageClient
from cam_stream_recovery import (
    STREAM_BOOT_GRACE_S,
    STREAM_MAX_SOFT_FAILURES,
    CameraStreamError,
    CameraStreamHangError,
    capture_timeout_s,
    should_exit_after_failures,
    stream_retry_backoff_s,
)
from cam_timing_rates import CaptureClock, compute_timing_rates

continue_loop = True
pending_settings = None  # CameraSettings | None — queued from WS
current_settings = None  # CameraSettings | None — live on the camera

# Unicam can "start" then never deliver frames (capture_request hangs). Soft
# failures reopen in-process; hangs exit so systemd Restart=always recovers.
# Constants / helpers: cam_stream_recovery.py

# Preview handoff only (depth 1). Science Bayer never goes through this buffer.
PREVIEW_BUFF = MsgBuff(1)
IMGBUFF = PREVIEW_BUFF  # back-compat alias

server_connection = None
server_overwhelmed = False

# Dedicated pools: capture scheduling must not share workers with emit packing.
_CAPTURE_POOL = concurrent.futures.ThreadPoolExecutor(
    max_workers=1, thread_name_prefix="cam-capture"
)
_EMIT_POOL = concurrent.futures.ThreadPoolExecutor(
    max_workers=1, thread_name_prefix="cam-emit"
)

# Bayer persistence in a separate process (GIL-free vs camera loop).
SCIENCE_STORAGE = ScienceStorageClient()  # auto ring: ~60% RAM / Bayer slot size

# Wall-clock capture cadence (independent of preview emit throttle).
CAPTURE_CLOCK = CaptureClock()

# Cached Picamera2.sensor_modes (expensive property) keyed by camera instance id.
_SENSOR_MODES_CACHE = {}

defaultconfig = {
    "shutterSpeed": 150000,
    "isovalue": 0,  # unused; kept for legacy dict shape only
    "redgain": 1.0,
    "bluegain": 1.0,
    "digital_gain": 1.0,
    "analog_gain": 1.0,
    "expomode": "off",
    "shootresol": {"name": "default", "width": 640, "height": 480, "mode": 0},
    "dispresol": {"name": "default", "width": 640, "height": 480, "mode": 0},
    "denoise": False,
    "capture_format": "rgb",
    "exposure_compensation": 0,
    "brightness": 50,
    "saturation": 0,
    "contrast": 0,
    "sharpness": 0,
    "save_format": "none",
    "save_section": "test",
    "save_subsection": "",
    "cameraZoom": 0,
    "crop": (0, 0, 1, 1),
}

mandatoryKeys = set(defaultconfig.keys())


def cleanParams(params):
    """Fill missing legacy dict keys (suite / bridge only). Prefer CameraSettings."""
    if params is None:
        return defaultconfig.copy()
    for k in mandatoryKeys:
        if k not in params:
            params[k] = defaultconfig[k]
    return params


def get_sensor_modes(picam2):
    """Return sensor_modes list, caching per Picamera2 instance."""
    key = id(picam2)
    modes = _SENSOR_MODES_CACHE.get(key)
    if modes is None:
        modes = list(picam2.sensor_modes)
        _SENSOR_MODES_CACHE[key] = modes
    return modes


def clear_sensor_modes_cache(picam2=None):
    """Drop cached modes for one camera or all."""
    if picam2 is None:
        _SENSOR_MODES_CACHE.clear()
    else:
        _SENSOR_MODES_CACHE.pop(id(picam2), None)


# Named IMX477 presets used by science / suite code.
# Native hardware modes only — there is no full-FOV 3x3 or 4x4 bin on IMX477.
SENSOR_PRESETS = {
    "full": {
        "size": (4056, 3040),
        "description": "full sensor readout (no binning)",
        "binning": "1x1",
        "fov": "full",
    },
    "full_2160": {
        "size": (4056, 2160),
        "description": "full-width 16:9 crop (no binning)",
        "binning": "1x1",
        "fov": "crop_16_9",
    },
    "bin2x2": {
        "size": (2028, 1520),
        "description": "native 2x2 binning, full FOV",
        "binning": "2x2",
        "fov": "full",
    },
    "bin2x2_1080": {
        "size": (2028, 1080),
        "description": "2x2 binned + 16:9 vertical crop",
        "binning": "2x2",
        "fov": "crop_16_9",
    },
    # Driver comments sometimes say "4x4"; register binning is 2x2 on a central
    # 2664x1980 window → 1332x990. Not full-FOV 3x3/4x4.
    "bin2x2_crop": {
        "size": (1332, 990),
        "description": "2x2 binning of center crop (~2664x1980 → 1332x990), high fps",
        "binning": "2x2",
        "fov": "center_crop",
    },
}

# Prefer unpacked 12-bit Bayer for science; packed formats are a last resort.
PREFERRED_RAW_FORMATS = ("SBGGR12", "SRGGB12", "SBGGR10", "SRGGB10")


def pick_sensor_mode(picam2, width, height):
    """Pick the closest sensor mode size that can cover the requested resolution."""
    modes = get_sensor_modes(picam2)
    best = None
    best_score = None
    for mode in modes:
        sw, sh = mode["size"]
        if sw < width or sh < height:
            continue
        score = (sw * sh) + abs(sw - width) + abs(sh - height)
        if best_score is None or score < best_score:
            best = mode
            best_score = score
    if best is None and modes:
        # Fall back to smallest available mode
        best = min(modes, key=lambda m: m["size"][0] * m["size"][1])
    return best


def select_sensor_mode(picam2, size=None, prefer_bit_depth=12):
    """
    Select an exact sensor mode by size when possible.

    Prefer matching bit_depth (default 12). Falls back to pick_sensor_mode.
    """
    if size is None:
        return pick_sensor_mode(picam2, 640, 480)

    width, height = int(size[0]), int(size[1])
    modes = get_sensor_modes(picam2)
    exact = [m for m in modes if tuple(m["size"]) == (width, height)]
    if not exact:
        return pick_sensor_mode(picam2, width, height)

    def _bit_depth(mode):
        return int(mode.get("bit_depth") or 0)

    preferred = [m for m in exact if _bit_depth(m) == prefer_bit_depth]
    pool = preferred or exact

    def _format_rank(mode):
        fmt = str(mode.get("format") or mode.get("unpacked") or "")
        for i, name in enumerate(PREFERRED_RAW_FORMATS):
            if name in fmt:
                return i
        # Prefer unpacked (no CSI2P) when possible
        if "CSI2P" in fmt:
            return 100
        return 50

    pool = sorted(pool, key=_format_rank)
    return pool[0]


def mode_raw_format(mode, prefer_unpacked=True):
    """Choose a raw stream format string for a sensor mode dict."""
    if mode is None:
        return None
    unpacked = mode.get("unpacked")
    packed = mode.get("format")
    if prefer_unpacked and unpacked:
        return str(unpacked)
    if packed:
        # Try to strip CSI2P packing hint when requesting unpacked
        fmt = str(packed)
        if prefer_unpacked and fmt.endswith("_CSI2P"):
            return fmt[: -len("_CSI2P")]
        return fmt
    return None


def build_still_config(
    picam2,
    width,
    height,
    buffer_count=4,
    sensor_size=None,
    include_raw=True,
    raw_format=None,
    prefer_bit_depth=12,
    queue=True,
):
    """
    Create a still configuration for the requested main stream size.

    If sensor_size is set, select that IMX477 mode explicitly (full / bin2x2 / …).
    """
    if sensor_size is not None:
        mode = select_sensor_mode(picam2, size=sensor_size, prefer_bit_depth=prefer_bit_depth)
    else:
        mode = pick_sensor_mode(picam2, width, height)

    config_kwargs = {
        "main": {"size": (int(width), int(height)), "format": "RGB888"},
        "buffer_count": int(buffer_count),
        "queue": queue,
    }
    if include_raw and mode is not None:
        raw_cfg = {"size": mode["size"]}
        fmt = raw_format or mode_raw_format(mode, prefer_unpacked=True)
        if fmt:
            raw_cfg["format"] = fmt
        config_kwargs["raw"] = raw_cfg
    return picam2.create_still_configuration(**config_kwargs), mode


def frame_to_rgb(frame):
    """Convert a picamera2 main-stream array to RGB for PIL / wasp."""
    if frame.ndim == 3 and frame.shape[2] >= 3:
        # picamera2 RGB888 frames are often BGR-ordered in practice
        return frame[:, :, ::-1].copy()
    return frame


def decode_raw_u16(raw8, picam2=None, stream="raw"):
    """
    Convert a raw stream array to contiguous uint16 Bayer + info dict.

    Does not demosaic. ``picam2`` is optional (used for format/size metadata).
    """
    cfg = {}
    if picam2 is not None:
        cfg = picam2.camera_configuration().get(stream) or {}
    fmt = cfg.get("format")
    size = cfg.get("size")
    arr = np.ascontiguousarray(raw8)
    if arr.dtype == np.uint8:
        if arr.shape[-1] % 2 != 0:
            raise RuntimeError("raw uint8 buffer width is odd; cannot view as uint16")
        u16 = arr.view(np.uint16)
    elif arr.dtype == np.uint16:
        u16 = arr
    else:
        u16 = arr.astype(np.uint16, copy=False)
    u16 = np.ascontiguousarray(u16)
    info = {
        "format": fmt,
        "configured_size": size,
        "array_shape": list(u16.shape),
        "dtype": str(u16.dtype),
        "mean": float(u16.mean()) if u16.size else None,
        "min": int(u16.min()) if u16.size else None,
        "max": int(u16.max()) if u16.size else None,
    }
    return u16, info


async def capture_with_timeout(fn, *args, timeout_s):
    """Run a blocking capture in ``_CAPTURE_POOL`` with an asyncio timeout."""
    loop = asyncio.get_running_loop()
    return await asyncio.wait_for(
        loop.run_in_executor(_CAPTURE_POOL, fn, *args),
        timeout=timeout_s,
    )


def capture_rgb_frame(picam2, stream="main"):
    """Capture one frame from the camera and return an RGB numpy array."""
    return frame_to_rgb(picam2.capture_array(stream))


def capture_rgb_with_metadata(picam2, stream="main"):
    """
    Capture one RGB frame and its metadata from a single completed request.

    Prefer this over capture_array + capture_metadata (two round-trips).
    """
    request = picam2.capture_request()
    try:
        arr = request.make_array(stream)
        md = request.get_metadata()
    finally:
        request.release()
    return frame_to_rgb(arr), md


def capture_bayer_rgb_with_metadata(picam2):
    """
    Single libcamera request → Bayer uint16 + RGB main + metadata.

    Prefer this for the live worker so exposure is paid once.
    Raises if the raw stream is unavailable.
    """
    request = picam2.capture_request()
    try:
        raw8 = request.make_array("raw")
        rgb = frame_to_rgb(request.make_array("main"))
        md = request.get_metadata()
    finally:
        request.release()
    u16, info = decode_raw_u16(raw8, picam2=picam2)
    return u16, info, rgb, md


def capture_raw_frame(picam2, stream="raw"):
    """
    Capture one Bayer frame as uint16 without demosaicing.

    Returns (array_u16, info_dict). Raises if the raw stream is unavailable.
    """
    raw8 = picam2.capture_array(stream)
    return decode_raw_u16(raw8, picam2=picam2, stream=stream)


def pack_preview_emit(rgb, preview_div, locator=None):
    """
    Aspect-preserving downsample → spectrum → optional locator → JPEG.

    Spectrum is computed on the clean resized RGB. The locator is burned
    into the JPEG only (Bayer science is never touched).
    ``locator`` is optional ``{enabled, x, y, scaler_crop}``.
    Returns (jpeg_b64, spectrum_dict_or_None).
    """
    h, w = int(rgb.shape[0]), int(rgb.shape[1])
    dw, dh = preview_wh_from_frame((w, h), preview_div)
    image = Image.fromarray(rgb)
    if (dw, dh) != (w, h):
        image_display = imgutils.resizeImage(image, (dw, dh))
    else:
        image_display = image
    disp_arr = np.asarray(image_display)
    spectrum = None
    try:
        spectrum = compute_rgb_spectrum(disp_arr).model_dump()
    except Exception:
        logging.getLogger("packPreview").exception("spectrum failed")
    try:
        image_display = apply_locator_overlay(image_display, locator)
    except Exception:
        logging.getLogger("packPreview").exception("locator draw failed")
    data = imgutils.pilimTobase64Jpg(image_display)
    return data, spectrum


def sync_science_storage(settings, bayer_shape=None):
    """Apply runtime save switch; optionally size the shm ring for Bayer shape."""
    active = settings.science_save_active()
    SCIENCE_STORAGE.set_enabled(active)
    if active and bayer_shape is not None:
        SCIENCE_STORAGE.ensure_capacity(tuple(bayer_shape))


def publish_science_frame(bayer_u16, raw_info, used, settings):
    """Non-blocking Bayer publish to the storage process (pointer via shm)."""
    if not settings.science_save_active():
        return False
    if not settings.include_raw:
        logging.getLogger("scienceSave").warning(
            "save_enabled but include_raw=false; skipping publish"
        )
        return False
    SCIENCE_STORAGE.ensure_capacity(bayer_u16.shape)
    meta = {
        "triggerDate": used.get("triggerDate"),
        "triggerDateStr": used.get("triggerDateStr"),
        "shutter_us": used.get("shutter_us"),
        "analog_gain": used.get("analog_gain"),
        "colour_gain_r": used.get("colour_gain_r"),
        "colour_gain_b": used.get("colour_gain_b"),
        "sensor_preset": used.get("sensor_preset"),
        "ScalerCrop": used.get("ScalerCrop"),
        "FrameDuration": used.get("FrameDuration"),
        "SensorTimestamp": used.get("SensorTimestamp"),
        "raw": raw_info,
        "settings": settings.to_wire_dict(),
    }
    return SCIENCE_STORAGE.publish(
        bayer_u16,
        meta,
        save_root=settings.save_root,
        save_section=settings.save_section,
        save_subsection=settings.save_subsection,
    )


def scaler_crop_limits(picam2):
    """Return (min, max, default) ScalerCrop rectangles if available."""
    controls = picam2.camera_controls or {}
    if "ScalerCrop" not in controls:
        return None
    return controls["ScalerCrop"]


def center_scaler_crop(full_rect, frac=0.5):
    """
    Build a centered ScalerCrop rectangle covering `frac` of full width/height.

    full_rect is (x, y, w, h). frac=0.5 => half linear size (25% area).
    """
    x, y, w, h = [int(v) for v in full_rect]
    frac = max(0.05, min(float(frac), 1.0))
    cw = max(2, int(round(w * frac)) & ~1)
    ch = max(2, int(round(h * frac)) & ~1)
    cx = x + (w - cw) // 2
    cy = y + (h - ch) // 2
    return (cx, cy, cw, ch)


def clamp_scaler_crop(picam2, rect):
    """Clamp (x, y, w, h) into ScalerCrop limits with even width/height."""
    limits = scaler_crop_limits(picam2)
    if limits is None:
        raise RuntimeError("ScalerCrop control not available")
    _lo, hi, _default = limits
    x, y, w, h = [int(v) for v in rect]
    max_x, max_y, max_w, max_h = [int(v) for v in hi]
    x = max(max_x, min(x, max_x + max_w - 2))
    y = max(max_y, min(y, max_y + max_h - 2))
    w = max(2, min(w, max_x + max_w - x))
    h = max(2, min(h, max_y + max_h - y))
    w -= w % 2
    h -= h % 2
    return (x, y, w, h), hi


def set_scaler_crop(picam2, rect):
    """Apply ScalerCrop (x, y, w, h) in sensor coordinates. Returns applied rect."""
    log = logging.getLogger("scalerCrop")
    applied, hi = clamp_scaler_crop(picam2, rect)
    picam2.set_controls({"ScalerCrop": applied})
    log.info("ScalerCrop applied %s (limit max %s)", applied, hi)
    return applied


def _noise_reduction_minimal():
    try:
        from libcamera import controls as libcontrols

        return libcontrols.draft.NoiseReductionModeEnum.Minimal
    except Exception:
        try:
            from libcamera import controls as libcontrols

            return libcontrols.NoiseReductionModeEnum.Minimal
        except Exception:
            return 0


def controls_from_settings(picam2, settings, include_scaler_crop=True):
    """
    Build libcamera controls from CameraSettings (no ISO / legacy UI keys).

    Always manual AE/AWB off with neutral tone mapping suitable for science
    capture. ``settings.science_neutral`` is retained for API compatibility.
    """
    if not isinstance(settings, CameraSettings):
        raise TypeError("settings must be CameraSettings")

    log = logging.getLogger("setParams")
    shutter = int(settings.shutter_us)
    analog_gain = float(settings.analog_gain)
    _ = settings.science_neutral  # reserved; worker path is always manual/neutral

    controls = {
        "AeEnable": False,
        "AwbEnable": False,
        "ExposureTime": shutter,
        "AnalogueGain": max(analog_gain, 0.1),
        "ColourGains": (float(settings.colour_gain_r), float(settings.colour_gain_b)),
        "Brightness": 0.0,
        "Contrast": 1.0,
        "Saturation": 1.0,
        "Sharpness": 1.0,
    }

    if "NoiseReductionMode" in (picam2.camera_controls or {}):
        controls["NoiseReductionMode"] = _noise_reduction_minimal()

    if "FrameDurationLimits" in (picam2.camera_controls or {}):
        lo, hi, _ = picam2.camera_controls["FrameDurationLimits"]
        need = int(shutter * 1.05) if shutter > 0 else int(lo)
        controls["FrameDurationLimits"] = (int(lo), max(int(hi), need))
        if shutter > 0 and shutter < int(lo):
            log.warning(
                "shutter_us=%s below FrameDurationLimits min=%s for this mode; expect clamp",
                shutter,
                lo,
            )

    if include_scaler_crop and settings.scaler_crop is not None:
        try:
            applied, _hi = clamp_scaler_crop(picam2, settings.scaler_crop)
            controls["ScalerCrop"] = applied
        except RuntimeError:
            log.warning("ScalerCrop requested but not available")

    return controls


def apply_controls(picam2, params, science=False):
    """
    Apply exposure / colour controls from a legacy params dict.

    ISO / isovalue are ignored — use analog_gain only.
    Prefer ``apply_settings_fast`` / ``controls_from_settings`` for new code.
    """
    log = logging.getLogger("setParams")
    controls = {}

    shutter = int(params.get("shutterSpeed", 0) or 0)
    analog_gain = float(params.get("analog_gain", 1.0) or 1.0)
    if params.get("isovalue") not in (None, 0, "0"):
        log.warning(
            "isovalue=%s ignored (canonical gain is analog_gain=%s)",
            params.get("isovalue"),
            analog_gain,
        )

    if science:
        params = dict(params)
        params["expomode"] = "off"
        params["brightness"] = 50
        params["contrast"] = 0
        params["saturation"] = 0
        params["sharpness"] = 0

    expomode = params.get("expomode", "off")
    if expomode == "off" or science:
        controls["AeEnable"] = False
        if shutter > 0:
            controls["ExposureTime"] = shutter
        controls["AnalogueGain"] = max(analog_gain, 0.1)
    else:
        controls["AeEnable"] = True

    controls["AwbEnable"] = False
    controls["ColourGains"] = (
        float(params.get("redgain", 1.0)),
        float(params.get("bluegain", 1.0)),
    )

    # picamera2 Brightness is typically around -1..1; UI uses 0..100 centered at 50
    controls["Brightness"] = (float(params.get("brightness", 50)) - 50.0) / 50.0
    controls["Contrast"] = 1.0 + float(params.get("contrast", 0)) / 100.0
    controls["Saturation"] = 1.0 + float(params.get("saturation", 0)) / 100.0
    controls["Sharpness"] = 1.0 + float(params.get("sharpness", 0)) / 16.0

    if science or not params.get("denoise", False):
        if "NoiseReductionMode" in (picam2.camera_controls or {}):
            controls["NoiseReductionMode"] = _noise_reduction_minimal()

    # Allow long exposures (FrameDurationLimits are in microseconds).
    # Note: the lower bound is a hard sensor/mode floor (e.g. ~85 ms on full
    # 4056x3040). Requested ExposureTime below that floor will be clamped.
    if "FrameDurationLimits" in (picam2.camera_controls or {}):
        lo, hi, _ = picam2.camera_controls["FrameDurationLimits"]
        need = int(shutter * 1.05) if shutter > 0 else int(lo)
        controls["FrameDurationLimits"] = (int(lo), max(int(hi), need))
        if shutter > 0 and shutter < int(lo):
            log.warning(
                "shutter_us=%s below FrameDurationLimits min=%s for this mode; expect clamp",
                shutter,
                lo,
            )

    try:
        picam2.set_controls(controls)
        log.info("applied controls %s", controls)
    except Exception:
        log.exception("failed applying controls %s", controls)
    return controls


def apply_science_controls(picam2, params):
    """Force manual, constant processing suitable for telescope signal capture."""
    return apply_controls(picam2, params, science=True)


def probe_camera_capabilities(picam2):
    """Snapshot of modes / controls useful for suite probe.json."""
    modes = []
    for m in get_sensor_modes(picam2):
        modes.append(
            {
                "size": list(m.get("size", ())),
                "format": str(m.get("format")),
                "unpacked": str(m.get("unpacked")) if m.get("unpacked") is not None else None,
                "bit_depth": m.get("bit_depth"),
                "fps": m.get("fps"),
                "crop_limits": list(m["crop_limits"]) if m.get("crop_limits") is not None else None,
            }
        )
    controls = {}
    for name, lim in (picam2.camera_controls or {}).items():
        try:
            controls[name] = [lim[0], lim[1], lim[2]]
        except Exception:
            controls[name] = str(lim)
    props = {}
    for key in ("Model", "UnitCellSize", "PixelArraySize", "PixelArrayActiveAreas"):
        if key in (picam2.camera_properties or {}):
            props[key] = picam2.camera_properties[key]
    return {
        "properties": props,
        "sensor_modes": modes,
        "controls": controls,
        "scaler_crop": scaler_crop_limits(picam2),
    }


def configure_and_start(
    picam2,
    params,
    sensor_size=None,
    include_raw=True,
    raw_format=None,
    science=True,
    buffer_count=4,
    scaler_crop=None,
    warmup_s=0.3,
):
    """
    Configure + start an already-created Picamera2 (warm reconfigure friendly).

    Returns (params, mode, config_info).
    """
    params = cleanParams(params)
    shootresol = params["shootresol"]
    width = int(shootresol["width"])
    height = int(shootresol["height"])

    config, mode = build_still_config(
        picam2,
        width,
        height,
        buffer_count=buffer_count,
        sensor_size=sensor_size,
        include_raw=include_raw,
        raw_format=raw_format,
    )
    picam2.configure(config)
    if science:
        apply_science_controls(picam2, params)
    else:
        apply_controls(picam2, params)
    picam2.start()
    if scaler_crop is not None:
        # Crop after start so the control is live.
        set_scaler_crop(picam2, scaler_crop)
    if warmup_s > 0:
        time.sleep(warmup_s)

    cam_cfg = picam2.camera_configuration()
    config_info = {
        "main": cam_cfg.get("main"),
        "raw": cam_cfg.get("raw"),
        "sensor": cam_cfg.get("sensor"),
        "mode_size": None if mode is None else list(mode.get("size", ())),
        "mode_format": None if mode is None else str(mode.get("format")),
        "include_raw": include_raw,
        "scaler_crop_requested": scaler_crop,
    }
    return params, mode, config_info


def open_configured_camera(
    params,
    sensor_size=None,
    include_raw=True,
    raw_format=None,
    science=False,
    buffer_count=4,
    scaler_crop=None,
    warmup_s=0.0,
):
    """
    Open, configure, and start Picamera2 from cleaned worker params.

    Caller must stop/close the returned instance.
    Returns (picam2, params, mode) — same tuple as before for worker compat.
    """
    params = cleanParams(params)
    picam2 = Picamera2()
    try:
        params, mode, _info = configure_and_start(
            picam2,
            params,
            sensor_size=sensor_size,
            include_raw=include_raw,
            raw_format=raw_format,
            science=science,
            buffer_count=buffer_count,
            scaler_crop=scaler_crop,
            warmup_s=warmup_s,
        )
    except Exception:
        try:
            picam2.close()
        except Exception:
            pass
        raise
    return picam2, params, mode


def reconfigure_camera(
    picam2,
    params,
    sensor_size=None,
    include_raw=True,
    raw_format=None,
    science=True,
    buffer_count=4,
    scaler_crop=None,
    warmup_s=0.3,
):
    """Stop + reconfigure + start without destroying the Picamera2 instance."""
    log = logging.getLogger("reconfigure")
    try:
        picam2.stop()
    except Exception:
        log.exception("stop before reconfigure failed")
    return configure_and_start(
        picam2,
        params,
        sensor_size=sensor_size,
        include_raw=include_raw,
        raw_format=raw_format,
        science=science,
        buffer_count=buffer_count,
        scaler_crop=scaler_crop,
        warmup_s=warmup_s,
    )


def close_camera(picam2):
    """Best-effort stop + close."""
    if picam2 is None:
        return
    try:
        picam2.stop()
    except Exception:
        pass
    try:
        picam2.close()
    except Exception:
        pass
    clear_sensor_modes_cache(picam2)


def _legacy_bundle_from_settings(settings):
    """Shared legacy dict + sensor size for configure / reconfigure."""
    if not isinstance(settings, CameraSettings):
        raise TypeError("settings must be CameraSettings")
    sensor_size = SENSOR_PRESETS[settings.sensor_preset]["size"]
    mw, mh = settings.resolved_main_size(SENSOR_PRESETS)
    legacy = settings.to_legacy_worker_dict(SENSOR_PRESETS)
    legacy["shootresol"] = {
        "name": settings.sensor_preset,
        "width": mw,
        "height": mh,
        "mode": 0,
    }
    return legacy, sensor_size


def apply_settings_fast(picam2, settings):
    """
    Fast path: one set_controls (exposure, gain, colour, optional ScalerCrop).
    Camera stays streaming.
    """
    log = logging.getLogger("setParams")
    controls = controls_from_settings(picam2, settings, include_scaler_crop=True)
    try:
        picam2.set_controls(controls)
        log.info("applied fast controls %s", controls)
    except Exception:
        log.exception("failed applying fast controls %s", controls)
    return controls


def apply_settings_slow(picam2, settings, warmup_s=0.3, buffer_count=4):
    """Slow path: stop → configure sensor mode / main size / raw → start."""
    legacy, sensor_size = _legacy_bundle_from_settings(settings)
    params, mode, info = reconfigure_camera(
        picam2,
        legacy,
        sensor_size=sensor_size,
        include_raw=settings.include_raw,
        science=settings.science_neutral,
        buffer_count=buffer_count,
        scaler_crop=settings.scaler_crop,
        warmup_s=warmup_s,
    )
    return params, mode, info


def open_from_settings(settings, warmup_s=0.3, buffer_count=4):
    """Create Picamera2 and apply slow configure from CameraSettings."""
    legacy, sensor_size = _legacy_bundle_from_settings(settings)
    picam2 = Picamera2()
    try:
        params, mode, info = configure_and_start(
            picam2,
            legacy,
            sensor_size=sensor_size,
            include_raw=settings.include_raw,
            science=settings.science_neutral,
            buffer_count=buffer_count,
            scaler_crop=settings.scaler_crop,
            warmup_s=warmup_s,
        )
    except Exception:
        close_camera(picam2)
        raise
    return picam2, params, mode, info


def used_params_from_settings(picam2, settings, frame_shape, metadata=None):
    """Build clean used-params dict from CameraSettings + live metadata."""
    md = metadata if metadata is not None else picam2.capture_metadata()
    colour = md.get(
        "ColourGains",
        (settings.colour_gain_r, settings.colour_gain_b),
    )
    h, w = frame_shape[0], frame_shape[1]
    emit_w, emit_h = preview_wh_from_frame((w, h), settings.preview_div)
    return {
        "triggerDate": time.time(),
        "triggerDateStr": str(datetime.datetime.utcnow()),
        "settings": settings.to_wire_dict(),
        "shutter_us": int(md.get("ExposureTime", settings.shutter_us)),
        "requested_shutter_us": settings.shutter_us,
        "analog_gain": float(md.get("AnalogueGain", settings.analog_gain)),
        "requested_analog_gain": settings.analog_gain,
        "digital_gain": float(md.get("DigitalGain", 1.0)) if md.get("DigitalGain") is not None else None,
        "colour_gain_r": float(colour[0]),
        "colour_gain_b": float(colour[1]),
        "sensor_preset": settings.sensor_preset,
        "frame_width": w,
        "frame_height": h,
        "ScalerCrop": list(md["ScalerCrop"]) if md.get("ScalerCrop") is not None else None,
        "FrameDuration": md.get("FrameDuration"),
        "SensorTimestamp": md.get("SensorTimestamp"),
        # Temporary legacy aliases for rootserver overlay until UI catches up
        "shutterSpeed": str(md.get("ExposureTime", settings.shutter_us)),
        "redgain": float(colour[0]),
        "bluegain": float(colour[1]),
        "shootresol": {"name": str(frame_shape), "width": w, "height": h},
        "preview_div": int(settings.preview_div),
        "dispresol": {
            "width": emit_w,
            "height": emit_h,
        },
        "save_format": settings.save_format,
        "save_section": settings.save_section,
        "save_subsection": settings.save_subsection,
        "save_enabled": settings.science_save_active(),
        "save_root": settings.save_root,
    }


def used_params_from_camera(picam2, params, frame_shape, metadata=None):
    """Legacy used-params builder for suite tests still on dict params."""
    md = metadata if metadata is not None else picam2.capture_metadata()
    colour = md.get("ColourGains", (params.get("redgain", 1.0), params.get("bluegain", 1.0)))
    h, w = frame_shape[0], frame_shape[1]
    used = {
        "triggerDate": time.time(),
        "triggerDateStr": str(datetime.datetime.utcnow()),
        "shutterSpeed": str(md.get("ExposureTime", params.get("shutterSpeed"))),
        "requested_shutterSpeed": params.get("shutterSpeed"),
        "isovalue": 0,
        "redgain": float(colour[0]),
        "bluegain": float(colour[1]),
        "expomode": params.get("expomode"),
        "shootresol": {"name": str(frame_shape), "width": w, "height": h},
        "exposure_compensation": params.get("exposure_compensation", 0),
        "brightness": params.get("brightness"),
        "saturation": params.get("saturation"),
        "contrast": params.get("contrast"),
        "sensor_mode": params.get("shootresol", {}).get("mode", 0),
        "sharpness": params.get("sharpness"),
        "video_denoise": params.get("denoise"),
        "analog_gain": str(md.get("AnalogueGain", params.get("analog_gain"))),
        "requested_analog_gain": params.get("analog_gain"),
        "digital_gain": str(md.get("DigitalGain", params.get("digital_gain"))),
        "ScalerCrop": list(md["ScalerCrop"]) if md.get("ScalerCrop") is not None else None,
        "FrameDuration": md.get("FrameDuration"),
        "SensorTimestamp": md.get("SensorTimestamp"),
    }
    p = params.copy()
    p.update(used)
    return p


async def open_camera(settings):
    """Acquire frames until a slow settings change forces reconfigure."""
    global continue_loop
    global pending_settings
    global current_settings
    log = logging.getLogger("openCam")

    if not isinstance(settings, CameraSettings):
        settings = from_legacy_dict(settings, SENSOR_PRESETS)

    mw, mh = settings.resolved_main_size(SENSOR_PRESETS)
    log.info(
        "OpeningCamera preset=%s main=%sx%s shutter=%s gain=%s save=%s root=%s",
        settings.sensor_preset,
        mw,
        mh,
        settings.shutter_us,
        settings.analog_gain,
        settings.science_save_active(),
        settings.save_root,
    )

    picam2, _legacy, mode, _info = open_from_settings(settings, warmup_s=0.3)
    current_settings = settings
    sync_science_storage(settings)
    if mode is not None:
        log.info("using sensor mode size %s", mode["size"])
    want_raw = bool(settings.include_raw)

    async def capture_one(timeout_s):
        """One timed capture; hang → CameraStreamHangError (do not reuse pool)."""
        nonlocal want_raw
        if want_raw:
            try:
                return await capture_with_timeout(
                    capture_bayer_rgb_with_metadata,
                    picam2,
                    timeout_s=timeout_s,
                )
            except asyncio.TimeoutError as e:
                raise CameraStreamHangError(
                    f"bayer+rgb capture hung after {timeout_s:.1f}s"
                ) from e
            except Exception:
                log.exception("bayer+rgb capture failed; falling back to RGB-only")
                try:
                    rgb, md = await capture_with_timeout(
                        capture_rgb_with_metadata,
                        picam2,
                        timeout_s=timeout_s,
                    )
                except asyncio.TimeoutError as e:
                    raise CameraStreamHangError(
                        f"rgb capture hung after {timeout_s:.1f}s"
                    ) from e
                return None, None, rgb, md
        try:
            rgb, md = await capture_with_timeout(
                capture_rgb_with_metadata,
                picam2,
                timeout_s=timeout_s,
            )
        except asyncio.TimeoutError as e:
            raise CameraStreamHangError(
                f"rgb capture hung after {timeout_s:.1f}s"
            ) from e
        return None, None, rgb, md

    def emit_frame(bayer_u16, raw_info, rgb, md):
        used = used_params_from_settings(
            picam2, current_settings, rgb.shape, metadata=md
        )
        CAPTURE_CLOCK.note_capture(time.monotonic())
        if bayer_u16 is not None:
            publish_science_frame(bayer_u16, raw_info, used, current_settings)
        PREVIEW_BUFF.stack((rgb, used, used["triggerDate"]))

    try:
        await asyncio.sleep(0.05)

        timeout_s = capture_timeout_s(current_settings.shutter_us)
        log.info("probing first frame timeout_s=%.1f", timeout_s)
        try:
            bayer_u16, raw_info, rgb, md = await capture_one(timeout_s)
        except CameraStreamHangError:
            raise
        except Exception as e:
            raise CameraStreamError(f"first-frame probe failed: {e}") from e
        emit_frame(bayer_u16, raw_info, rgb, md)
        log.info("first frame ok")

        while continue_loop:
            if pending_settings is not None:
                new_s = pending_settings
                pending_settings = None
                d = diff_settings(current_settings, new_s)
                log.info("settings diff %s", d.model_dump())
                if d.slow_changed:
                    current_settings = new_s
                    continue_loop = False
                    break
                if d.fast_changed or d.output_changed:
                    if d.fast_changed:
                        apply_settings_fast(picam2, new_s)
                    current_settings = new_s
                    sync_science_storage(current_settings)
                    want_raw = bool(current_settings.include_raw)

            timeout_s = capture_timeout_s(current_settings.shutter_us)
            bayer_u16, raw_info, rgb, md = await capture_one(timeout_s)
            emit_frame(bayer_u16, raw_info, rgb, md)
            await asyncio.sleep(0)
    finally:
        close_camera(picam2)


# Back-compat alias for scripts that still import openCamera
openCamera = open_camera


async def camera_loop():
    global continue_loop
    global pending_settings
    global current_settings
    await asyncio.sleep(STREAM_BOOT_GRACE_S)
    log = logging.getLogger("cameraLoop")
    consecutive_failures = 0

    while True:
        try:
            if pending_settings is not None:
                settings = pending_settings
                pending_settings = None
            elif current_settings is not None:
                settings = current_settings
            else:
                settings = default_settings()
            continue_loop = True
            current_settings = settings
            await open_camera(settings)
            consecutive_failures = 0
            log.info("camera closed")
        except CameraStreamHangError:
            log.exception(
                "Unicam/capture hung; exiting for systemd restart"
            )
            sys.exit(1)
        except Exception:
            consecutive_failures += 1
            log.exception(
                "whooops failure=%s/%s",
                consecutive_failures,
                STREAM_MAX_SOFT_FAILURES,
            )
            if should_exit_after_failures(consecutive_failures):
                log.error(
                    "too many consecutive stream failures; exiting for systemd restart"
                )
                sys.exit(1)
            await asyncio.sleep(stream_retry_backoff_s(consecutive_failures))


cameraLoop = camera_loop


async def ws_client(uri):
    global server_connection
    global server_overwhelmed
    global pending_settings

    log = logging.getLogger("wsclient")
    while True:
        try:
            async with websockets.connect(
                uri,
                ping_interval=3,
                ping_timeout=3,
                close_timeout=3,
                max_size=32 * 1024 * 1024,
            ) as websocket:
                log.info("Connected to server")
                server_connection = websocket
                while True:
                    data = await websocket.recv()
                    msg = json.loads(data)
                    if msg["msgtype"] == "params":
                        try:
                            pending_settings = from_legacy_dict(
                                msg["data"], SENSOR_PRESETS
                            )
                            log.info(
                                "queued settings preset=%s shutter=%s gain=%s",
                                pending_settings.sensor_preset,
                                pending_settings.shutter_us,
                                pending_settings.analog_gain,
                            )
                        except Exception:
                            log.exception("invalid params ignored")
                    elif msg["msgtype"] == "serverOverwhelmed":
                        server_overwhelmed = msg["data"]
                    else:
                        log.warning("received type %s", msg["msgtype"])
        except websockets.exceptions.ConnectionClosed:
            server_connection = None
        except concurrent.futures._base.CancelledError:
            log.info("quit due to cancelled Error")
            return
        except Exception as e:
            log.exception("websocket disconnected %s", str(e))
            server_connection = None

        log.info("reconnecting websocket in 1")
        await asyncio.sleep(1)


wsclient = ws_client


async def bg_job():
    global server_connection
    global server_overwhelmed
    global current_settings
    log = logging.getLogger("imgForwd")
    sleepdur = 0.05
    lastTimingSend = 0.0
    lastEmit = 0.0
    skipped = 0
    emitted = 0
    prev_capture_count = 0
    prev_published = 0
    prev_written = 0
    prev_rate_mono = time.monotonic()

    while True:
        try:
            if len(PREVIEW_BUFF.content) > 0:
                a, params, triggerDate = PREVIEW_BUFF.pop()

                max_fps = 8.0
                if current_settings is not None:
                    max_fps = float(current_settings.max_emit_fps)
                min_period = 1.0 / max_fps if max_fps > 0 else 0.125
                now = time.time()
                if now - lastEmit < min_period:
                    skipped += 1
                    await asyncio.sleep(0.001)
                    continue

                if not server_overwhelmed:
                    if server_connection:
                        try:
                            preview_div = 2
                            locator = None
                            if current_settings is not None:
                                preview_div = int(current_settings.preview_div)
                                locator = {
                                    "enabled": bool(current_settings.locator_enabled),
                                    "x": float(current_settings.locator_x),
                                    "y": float(current_settings.locator_y),
                                    "size": float(current_settings.locator_size),
                                    "scaler_crop": params.get("ScalerCrop"),
                                }
                            loop = asyncio.get_running_loop()
                            data, spectrum = await loop.run_in_executor(
                                _EMIT_POOL,
                                pack_preview_emit,
                                a,
                                preview_div,
                                locator,
                            )
                            msg = {
                                "usedParams": params,
                                "msgtype": "srcimage",
                                "imageData": data,
                            }
                            if spectrum is not None:
                                msg["spectrum"] = spectrum
                            await server_connection.send(json.dumps(msg))
                            lastEmit = time.time()
                            emitted += 1
                            await asyncio.sleep(0)
                        except websockets.exceptions.ConnectionClosed as e:
                            server_connection = None
                            log.error("disconnected with server %s", e)
                        except Exception:
                            log.exception("err sending to server")
                    else:
                        await asyncio.sleep(0.05)
                else:
                    skipped += 1
                    await asyncio.sleep(0.001)
            else:
                await asyncio.sleep(sleepdur)

            if time.time() > lastTimingSend + 3:
                now_mono = time.monotonic()
                lastTimingSend = time.time()
                st = SCIENCE_STORAGE.poll_stats()
                save_enabled = (
                    current_settings.science_save_active()
                    if current_settings
                    else False
                )
                capture_count, frame_time_ms = CAPTURE_CLOCK.snapshot()
                dt_s = max(1e-3, now_mono - prev_rate_mono)
                rates = compute_timing_rates(
                    dt_s=dt_s,
                    capture_delta=max(0, capture_count - prev_capture_count),
                    frame_time_ms=frame_time_ms,
                    published_delta=max(0, int(st.published) - prev_published),
                    written_delta=max(0, int(st.written) - prev_written),
                    emitted=emitted,
                    science_pending=int(st.pending),
                    science_slots=int(st.n_slots or SCIENCE_STORAGE.n_slots),
                    save_enabled=save_enabled,
                )
                prev_capture_count = capture_count
                prev_published = int(st.published)
                prev_written = int(st.written)
                prev_rate_mono = now_mono
                timingData = {
                    # Preview path only (depth-1). NOT the science save queue.
                    "imgbuffcount": len(PREVIEW_BUFF.content),
                    # Legacy name: science ring slots in flight (pending disk write).
                    "tosavecount": int(st.pending),
                    "science_published": st.published,
                    "science_dropped": st.dropped,
                    "science_written": st.written,
                    "science_errors": st.errors,
                    "science_pending": int(st.pending),
                    "science_slots": int(st.n_slots or SCIENCE_STORAGE.n_slots),
                    "save_enabled": save_enabled,
                    "save_root": (
                        current_settings.save_root if current_settings else None
                    ),
                    "emitted": emitted,
                    "skipped": skipped,
                    "max_emit_fps": (
                        current_settings.max_emit_fps if current_settings else 8.0
                    ),
                    "capture_fps": round(rates.capture_fps, 3),
                    "frame_time_ms": round(rates.frame_time_ms, 2),
                    "science_publish_fps": round(rates.science_publish_fps, 3),
                    "science_write_fps": round(rates.science_write_fps, 3),
                    "emit_fps": round(rates.emit_fps, 3),
                    "queue_fill_eta_s": (
                        None
                        if rates.queue_fill_eta_s is None
                        else round(rates.queue_fill_eta_s, 2)
                    ),
                }
                log.info("some info %s ", timingData)
                if server_connection:
                    await server_connection.send(
                        makeMessage("camTiming", timingData, jdump=True)
                    )
                emitted = 0
                skipped = 0
        except concurrent.futures._base.CancelledError:
            log.info("quit due to cancelledError")
            return
        except Exception:
            log.exception("error")


bgjob = bg_job


async def main(args):
    uri = "ws://localhost:8765/camera" if args.uri is None else args.uri
    try:
        await asyncio.gather(
            ws_client(uri),
            camera_loop(),
            bg_job(),
        )
    finally:
        SCIENCE_STORAGE.shutdown()
        _CAPTURE_POOL.shutdown(wait=False)
        _EMIT_POOL.shutdown(wait=False)


if __name__ == "__main__":
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format=formatstr)
    asyncio.run(main(args))
