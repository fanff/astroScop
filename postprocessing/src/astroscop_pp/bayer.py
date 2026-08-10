"""Bayer format helpers: pattern mapping and stride-pad crop."""

from __future__ import annotations

from typing import Any

import numpy as np

# libcamera / V4L2 fourcc-style prefixes → Siril BAYERPAT
_FORMAT_TO_BAYERPAT: dict[str, str] = {
    "SBGGR": "BGGR",
    "SRGGB": "RGGB",
    "SGRBG": "GRBG",
    "SGBRG": "GBRG",
}


def bayerpat_from_format(raw_format: str | None) -> str:
    """Map ``raw.format`` (e.g. ``SBGGR12``) to a 4-letter Siril ``BAYERPAT``."""
    if not raw_format:
        raise ValueError("raw.format is missing; cannot determine Bayer pattern")
    key = str(raw_format).strip().upper()
    for prefix, pattern in _FORMAT_TO_BAYERPAT.items():
        if key.startswith(prefix):
            return pattern
    raise ValueError(f"unsupported raw.format for Bayer mapping: {raw_format!r}")


def configured_size_wh(meta: dict[str, Any]) -> tuple[int, int]:
    """
    Return ``(width, height)`` from metadata.

    Prefer ``raw.configured_size`` ``[W, H]``; fall back to ``array_shape`` as
    ``[H, W]`` when configured size is absent.
    """
    raw = meta.get("raw") or {}
    cfg = raw.get("configured_size")
    if cfg is not None and len(cfg) == 2:
        width, height = int(cfg[0]), int(cfg[1])
        if width <= 0 or height <= 0:
            raise ValueError(f"invalid configured_size: {cfg!r}")
        return width, height

    shape = meta.get("array_shape") or raw.get("array_shape")
    if shape is not None and len(shape) == 2:
        height, width = int(shape[0]), int(shape[1])
        if width <= 0 or height <= 0:
            raise ValueError(f"invalid array_shape: {shape!r}")
        return width, height

    raise ValueError("metadata lacks raw.configured_size and array_shape")


def crop_to_configured(array_u16: np.ndarray, meta: dict[str, Any]) -> np.ndarray:
    """
    Crop a stride-padded Bayer plane to ``configured_size``.

    Input must be 2-D ``uint16`` with shape ``(H_pad, W_pad)``.
    Output is a contiguous ``(height, width)`` view/copy suitable for FITS.
    """
    if array_u16.ndim != 2:
        raise ValueError(f"expected 2-D Bayer array, got shape {array_u16.shape}")
    if array_u16.dtype != np.uint16:
        raise ValueError(f"expected uint16 Bayer array, got dtype {array_u16.dtype}")

    width, height = configured_size_wh(meta)
    h_pad, w_pad = array_u16.shape
    if h_pad < height or w_pad < width:
        raise ValueError(
            f"array shape {(h_pad, w_pad)} smaller than configured_size "
            f"(W={width}, H={height})"
        )

    cropped = array_u16[:height, :width]
    return np.ascontiguousarray(cropped)
