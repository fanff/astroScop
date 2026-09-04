"""
Preview-only tracking locator (circle + cardinal ticks).

Position is a normalized point on the physical IMX477 (4056×3040). Each
frame's ScalerCrop maps that point into the emitted JPEG; if the crop
excludes the point the glyph is clamped to the nearest visible edge so
the full mark stays on-screen.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence, Tuple

from PIL import Image, ImageDraw

# Native HQ sensor; ScalerCrop metadata is in this space even when binned.
FULL_SENSOR_WH: Tuple[int, int] = (4056, 3040)

# Preview glyph: fraction of the shorter emitted side, with pixel floors.
# Stroke is half the original width so the mark stays readable, not fat.
RADIUS_FRAC = 0.06
TICK_FRAC_OF_RADIUS = 0.65
STROKE_FRAC_OF_RADIUS = 0.07
RADIUS_MIN_PX = 8
TICK_MIN_PX = 5
STROKE_MIN_PX = 1
UNDERSTROKE_PAD_PX = 1
SIZE_DEFAULT = 1.0
SIZE_MIN = 0.15
SIZE_MAX = 3.0

LOCATOR_RED = (220, 40, 36)
LOCATOR_UNDER = (0, 0, 0)


def clamp01(v: Any) -> float:
    try:
        n = float(v)
    except (TypeError, ValueError):
        return 0.5
    if n != n:  # NaN
        return 0.5
    return min(1.0, max(0.0, n))


def parse_scaler_crop(
    crop: Optional[Sequence[Any]],
    full_wh: Tuple[int, int] = FULL_SENSOR_WH,
) -> Tuple[int, int, int, int]:
    """Return (x, y, w, h) in full-sensor pixels; fall back to whole sensor."""
    fw, fh = int(full_wh[0]), int(full_wh[1])
    if crop is None:
        return (0, 0, fw, fh)
    try:
        x, y, w, h = (int(crop[0]), int(crop[1]), int(crop[2]), int(crop[3]))
    except (TypeError, ValueError, IndexError):
        return (0, 0, fw, fh)
    if w < 1 or h < 1:
        return (0, 0, fw, fh)
    return (x, y, w, h)


def locator_preview_xy(
    nx: float,
    ny: float,
    preview_wh: Tuple[int, int],
    scaler_crop: Optional[Sequence[Any]] = None,
    full_wh: Tuple[int, int] = FULL_SENSOR_WH,
) -> Tuple[float, float]:
    """
    Map a full-sensor normalized point into preview pixels.

    Out-of-crop points are clamped to the crop rectangle (image edges)
    before glyph-margin clamping.
    """
    fw, fh = int(full_wh[0]), int(full_wh[1])
    cx, cy, cw, ch = parse_scaler_crop(scaler_crop, full_wh)
    sx = clamp01(nx) * fw
    sy = clamp01(ny) * fh
    rel_x = (sx - cx) / float(cw)
    rel_y = (sy - cy) / float(ch)
    rel_x = min(1.0, max(0.0, rel_x))
    rel_y = min(1.0, max(0.0, rel_y))
    pw, ph = int(preview_wh[0]), int(preview_wh[1])
    px = rel_x * (pw - 1) if pw > 1 else 0.0
    py = rel_y * (ph - 1) if ph > 1 else 0.0
    return px, py


def clamp_locator_size(v: Any) -> float:
    try:
        n = float(v)
    except (TypeError, ValueError):
        return SIZE_DEFAULT
    if n != n:
        return SIZE_DEFAULT
    return min(SIZE_MAX, max(SIZE_MIN, n))


def locator_glyph_metrics(preview_wh: Tuple[int, int], size: float = SIZE_DEFAULT) -> dict:
    """Radius / tick / stroke from the shorter preview side, scaled by ``size``."""
    pw, ph = int(preview_wh[0]), int(preview_wh[1])
    short = max(1, min(pw, ph))
    scale = clamp_locator_size(size)
    radius = max(2, int(round(short * RADIUS_FRAC * scale)))
    tick_len = max(2, int(round(radius * TICK_FRAC_OF_RADIUS)))
    stroke = max(STROKE_MIN_PX, int(round(radius * STROKE_FRAC_OF_RADIUS)))
    under = stroke + UNDERSTROKE_PAD_PX
    half = radius + tick_len + under
    return {
        "radius": radius,
        "tick_len": tick_len,
        "stroke": stroke,
        "under": under,
        "half": half,
        "size": scale,
    }


def clamp_locator_center(
    xy: Tuple[float, float],
    preview_wh: Tuple[int, int],
    half: int,
) -> Tuple[float, float]:
    """Keep the full glyph (circle + ticks + stroke) inside the image."""
    pw, ph = int(preview_wh[0]), int(preview_wh[1])
    x, y = float(xy[0]), float(xy[1])
    margin = float(half)
    if pw <= 2 * margin:
        x = (pw - 1) / 2.0 if pw > 0 else 0.0
    else:
        x = min(pw - 1 - margin, max(margin, x))
    if ph <= 2 * margin:
        y = (ph - 1) / 2.0 if ph > 0 else 0.0
    else:
        y = min(ph - 1 - margin, max(margin, y))
    return x, y


def locator_draw_xy(
    nx: float,
    ny: float,
    preview_wh: Tuple[int, int],
    scaler_crop: Optional[Sequence[Any]] = None,
    full_wh: Tuple[int, int] = FULL_SENSOR_WH,
    size: float = SIZE_DEFAULT,
) -> Tuple[float, float, dict]:
    """Preview-pixel center after crop mapping and glyph-edge clamp."""
    metrics = locator_glyph_metrics(preview_wh, size=size)
    raw = locator_preview_xy(nx, ny, preview_wh, scaler_crop, full_wh)
    cx, cy = clamp_locator_center(raw, preview_wh, metrics["half"])
    return cx, cy, metrics


def draw_locator(
    image: Image.Image,
    nx: float,
    ny: float,
    scaler_crop: Optional[Sequence[Any]] = None,
    size: float = SIZE_DEFAULT,
) -> Image.Image:
    """
    Draw circle + top/bottom/left/right ticks onto ``image`` (in place).

    Returns the same image. Caller should copy if the source must stay clean.
    """
    if image.mode != "RGB":
        rgb = image.convert("RGB")
        image.paste(rgb)
    pw, ph = image.size
    cx, cy, m = locator_draw_xy(nx, ny, (pw, ph), scaler_crop, size=size)
    draw = ImageDraw.Draw(image)
    r = float(m["radius"])
    t = float(m["tick_len"])
    layers = ((LOCATOR_UNDER, int(m["under"])), (LOCATOR_RED, int(m["stroke"])))
    for color, width in layers:
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=width)
        draw.line((cx, cy - r - t, cx, cy - r), fill=color, width=width)
        draw.line((cx, cy + r, cx, cy + r + t), fill=color, width=width)
        draw.line((cx - r - t, cy, cx - r, cy), fill=color, width=width)
        draw.line((cx + r, cy, cx + r + t, cy), fill=color, width=width)
    return image


def apply_locator_overlay(image: Image.Image, locator: Optional[dict] = None) -> Image.Image:
    """
    Return ``image`` unchanged when disabled; otherwise a copy with the locator.

    ``locator`` keys: enabled, x, y, size, scaler_crop.
    """
    loc = locator or {}
    if not loc.get("enabled"):
        return image
    painted = image.copy()
    draw_locator(
        painted,
        loc.get("x", 0.5),
        loc.get("y", 0.5),
        scaler_crop=loc.get("scaler_crop"),
        size=loc.get("size", SIZE_DEFAULT),
    )
    return painted
