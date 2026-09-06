"""Map a full-sensor lock into a capture-RGB ROI rectangle.

Reuses locator crop space (ScalerCrop is full-sensor even when binned).
Out-of-crop locks are rejected — they are not clamped to the RGB edge.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from cam_locator import FULL_SENSOR_WH, parse_scaler_crop


@dataclass(frozen=True)
class LockRoi:
    ok: bool
    origin_u: int
    origin_v: int
    size_u: int
    size_v: int
    lock_u: float
    lock_v: float
    rgb_u: float
    rgb_v: float
    reason: str = ""


def _inside_crop(sx: float, sy: float, crop: Tuple[int, int, int, int]) -> bool:
    cx, cy, cw, ch = crop
    return (cx <= sx < cx + cw) and (cy <= sy < cy + ch)


def lock_to_rgb_uv(
    track_x: float,
    track_y: float,
    rgb_wh: Tuple[int, int],
    scaler_crop: Optional[Sequence] = None,
    full_wh: Tuple[int, int] = FULL_SENSOR_WH,
) -> Tuple[bool, float, float, str]:
    """Full-sensor fractions → capture-RGB pixels. ok=False if outside the crop."""
    fw, fh = int(full_wh[0]), int(full_wh[1])
    rgb_w, rgb_h = int(rgb_wh[0]), int(rgb_wh[1])
    if rgb_w < 1 or rgb_h < 1:
        return False, 0.0, 0.0, "bad_rgb_size"
    crop = parse_scaler_crop(scaler_crop, full_wh)
    sx = float(track_x) * fw
    sy = float(track_y) * fh
    if not _inside_crop(sx, sy, crop):
        return False, 0.0, 0.0, "outside_crop"
    cx, cy, cw, ch = crop
    rel_x = (sx - cx) / float(cw)
    rel_y = (sy - cy) / float(ch)
    rgb_u = rel_x * (rgb_w - 1) if rgb_w > 1 else 0.0
    rgb_v = rel_y * (rgb_h - 1) if rgb_h > 1 else 0.0
    return True, rgb_u, rgb_v, ""


def _shift_origin(center: float, half: int, length: int) -> Tuple[int, int]:
    size = 2 * int(half)
    if length < 1:
        return 0, 0
    if length < size:
        return 0, length
    origin = int(round(float(center) - half))
    origin = max(0, min(origin, length - size))
    return origin, size


def lock_to_roi(
    track_x: float,
    track_y: float,
    rgb_wh: Tuple[int, int],
    *,
    scaler_crop: Optional[Sequence] = None,
    roi_half: int = 32,
    center_uv: Optional[Tuple[float, float]] = None,
    full_wh: Tuple[int, int] = FULL_SENSOR_WH,
) -> LockRoi:
    """Square ROI in capture RGB around the lock (or last centroid)."""
    half = int(roi_half)
    if half < 4:
        return LockRoi(False, 0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, "bad_roi_half")
    ok, rgb_u, rgb_v, reason = lock_to_rgb_uv(
        track_x, track_y, rgb_wh, scaler_crop=scaler_crop, full_wh=full_wh
    )
    if not ok:
        return LockRoi(False, 0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, reason)
    cu, cv = (float(center_uv[0]), float(center_uv[1])) if center_uv is not None else (rgb_u, rgb_v)
    rgb_w, rgb_h = int(rgb_wh[0]), int(rgb_wh[1])
    origin_u, size_u = _shift_origin(cu, half, rgb_w)
    origin_v, size_v = _shift_origin(cv, half, rgb_h)
    if size_u < 8 or size_v < 8:
        return LockRoi(
            False, origin_u, origin_v, size_u, size_v, 0.0, 0.0, rgb_u, rgb_v, "rgb_too_small"
        )
    lock_u = rgb_u - origin_u
    lock_v = rgb_v - origin_v
    if not (0.0 <= lock_u < size_u and 0.0 <= lock_v < size_v):
        return LockRoi(
            False,
            origin_u,
            origin_v,
            size_u,
            size_v,
            lock_u,
            lock_v,
            rgb_u,
            rgb_v,
            "lock_outside_tile",
        )
    return LockRoi(
        True, origin_u, origin_v, size_u, size_v, lock_u, lock_v, rgb_u, rgb_v, ""
    )
