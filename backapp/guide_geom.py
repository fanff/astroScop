"""Guide geometry: pixel error → on-sky arcsec and motor step-error.

Pure stdlib math. No camera, no PID. Phase B of the autoguide evolution.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from asc_rates import ASC_STEPS_PER_DEGREE

IMX477_PIXEL_PITCH_UM = 1.55
# arcsec/px = 206.265 * pixel_um / f_mm  (then × bin)
PLATE_SCALE_ARCSEC_FACTOR = 206.265
DEC_FREEZE_DEG = 80.0
COS_FLOOR = abs(math.cos(math.radians(DEC_FREEZE_DEG)))

ASC_ARCSEC_PER_STEP = 3600.0 / ASC_STEPS_PER_DEGREE
# v1: same gear scale as ASC; split after a DEC pulse if needed.
DEC_ARCSEC_PER_STEP = ASC_ARCSEC_PER_STEP

_BIN1_PRESETS = frozenset({"full", "full_2160"})
_BIN2_PRESETS = frozenset({"bin2x2", "bin2x2_1080", "bin2x2_crop"})


@dataclass(frozen=True)
class AxisError:
    e_asc_px: float
    e_dec_px: float
    e_asc_arcsec: float
    e_dec_arcsec: float
    e_asc_steps: float
    e_dec_steps: float
    cos_eff: float
    pole_gate: bool


def plate_scale_arcsec_per_px(f_mm: float, bin: int) -> float:
    """Capture-RGB plate scale in arcsec per pixel (after the current preset bin)."""
    _check_f_mm(f_mm)
    _check_bin(bin)
    return PLATE_SCALE_ARCSEC_FACTOR * IMX477_PIXEL_PITCH_UM / float(f_mm) * int(bin)


plate_scale = plate_scale_arcsec_per_px


def bin_factor_for_preset(preset: str) -> int:
    name = str(preset)
    if name in _BIN1_PRESETS:
        return 1
    if name in _BIN2_PRESETS:
        return 2
    raise ValueError(f"unknown sensor preset for bin factor: {preset!r}")


def cos_eff_and_pole_gate(dec_deg: float) -> tuple[float, bool]:
    pole_gate = abs(float(dec_deg)) > DEC_FREEZE_DEG
    cos_eff = max(abs(math.cos(math.radians(float(dec_deg)))), COS_FLOOR)
    return cos_eff, pole_gate


def rotate_pixel_error(
    e_u: float,
    e_v: float,
    theta_deg: float = 0.0,
    flip_asc: bool = False,
    flip_dec: bool = False,
) -> tuple[float, float]:
    """ROI pixel error → mount axes in pixels. θ = 0: ASC+ = +u, DEC+ = +v."""
    th = math.radians(float(theta_deg))
    c = math.cos(th)
    s = math.sin(th)
    e_asc_px = c * float(e_u) + s * float(e_v)
    e_dec_px = -s * float(e_u) + c * float(e_v)
    if flip_asc:
        e_asc_px = -e_asc_px
    if flip_dec:
        e_dec_px = -e_dec_px
    return e_asc_px, e_dec_px


def _unrotate_pixel_error(
    e_asc_px: float,
    e_dec_px: float,
    theta_deg: float = 0.0,
    flip_asc: bool = False,
    flip_dec: bool = False,
) -> tuple[float, float]:
    if flip_asc:
        e_asc_px = -e_asc_px
    if flip_dec:
        e_dec_px = -e_dec_px
    th = math.radians(float(theta_deg))
    c = math.cos(th)
    s = math.sin(th)
    e_u = c * e_asc_px - s * e_dec_px
    e_v = s * e_asc_px + c * e_dec_px
    return e_u, e_v


def pixels_to_axis_steps(
    e_u: float,
    e_v: float,
    *,
    f_mm: float,
    bin: int,
    dec_deg: float,
    theta_deg: float = 0.0,
    flip_asc: bool = False,
    flip_dec: bool = False,
) -> AxisError:
    s = plate_scale_arcsec_per_px(f_mm, bin)
    e_asc_px, e_dec_px = rotate_pixel_error(
        e_u, e_v, theta_deg=theta_deg, flip_asc=flip_asc, flip_dec=flip_dec
    )
    e_asc_arcsec = e_asc_px * s
    e_dec_arcsec = e_dec_px * s
    cos_eff, pole_gate = cos_eff_and_pole_gate(dec_deg)
    e_asc_steps = e_asc_arcsec / (ASC_ARCSEC_PER_STEP * cos_eff)
    e_dec_steps = e_dec_arcsec / DEC_ARCSEC_PER_STEP
    return AxisError(
        e_asc_px=e_asc_px,
        e_dec_px=e_dec_px,
        e_asc_arcsec=e_asc_arcsec,
        e_dec_arcsec=e_dec_arcsec,
        e_asc_steps=e_asc_steps,
        e_dec_steps=e_dec_steps,
        cos_eff=cos_eff,
        pole_gate=pole_gate,
    )


def axis_steps_to_pixels(
    e_asc_steps: float,
    e_dec_steps: float,
    *,
    f_mm: float,
    bin: int,
    dec_deg: float,
    theta_deg: float = 0.0,
    flip_asc: bool = False,
    flip_dec: bool = False,
) -> tuple[float, float]:
    """Inverse of pixels_to_axis_steps (same geometry kwargs)."""
    s = plate_scale_arcsec_per_px(f_mm, bin)
    cos_eff, _ = cos_eff_and_pole_gate(dec_deg)
    e_asc_px = float(e_asc_steps) * ASC_ARCSEC_PER_STEP * cos_eff / s
    e_dec_px = float(e_dec_steps) * DEC_ARCSEC_PER_STEP / s
    return _unrotate_pixel_error(
        e_asc_px,
        e_dec_px,
        theta_deg=theta_deg,
        flip_asc=flip_asc,
        flip_dec=flip_dec,
    )


def _check_f_mm(f_mm: float) -> None:
    if not math.isfinite(float(f_mm)) or float(f_mm) <= 0.0:
        raise ValueError(f"guide_focal_mm must be > 0, got {f_mm!r}")


def _check_bin(bin: int) -> None:
    if int(bin) not in (1, 2):
        raise ValueError(f"bin must be 1 or 2, got {bin!r}")
