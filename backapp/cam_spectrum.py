"""
Fast RGB spectrum stats for live telescope preview frames.

Designed for display-sized uint8 RGB (already downscaled for WS).
256 bins per channel matches full 8-bit precision of that stream.
"""

from __future__ import annotations

from typing import List, Tuple

import numpy as np
from pydantic import BaseModel, ConfigDict


class SpectrumStats(BaseModel):
    """Science-grade RGB spectrum on an 8-bit display/preview frame."""

    model_config = ConfigDict(extra="forbid")

    bins: int = 256
    mean_r: float
    mean_g: float
    mean_b: float
    min_r: int
    min_g: int
    min_b: int
    max_r: int
    max_g: int
    max_b: int
    std_r: float
    std_g: float
    std_b: float
    hist_r: List[int]
    hist_g: List[int]
    hist_b: List[int]
    pixels: int
    shape: Tuple[int, int, int]


def compute_rgb_spectrum(rgb: np.ndarray, bins: int = 256) -> SpectrumStats:
    """
    Compute per-channel moments + histograms on an HxWx3 uint8 RGB array.

    Raises ValueError if the array is not HxWx3 or bins is out of range.
    """
    if rgb is None or rgb.ndim != 3 or rgb.shape[2] < 3:
        raise ValueError(f"expected HxWx3 RGB array, got shape={getattr(rgb, 'shape', None)}")
    if bins < 2 or bins > 256:
        raise ValueError("bins must be in [2, 256] for uint8 RGB")

    arr = np.ascontiguousarray(rgb[:, :, :3])
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)

    # (3, N) view for one pass over channels
    flat = arr.reshape(-1, 3)
    means = flat.mean(axis=0)
    mins = flat.min(axis=0)
    maxs = flat.max(axis=0)
    stds = flat.std(axis=0)

    hr = np.bincount(flat[:, 0], minlength=256).astype(np.int64)
    hg = np.bincount(flat[:, 1], minlength=256).astype(np.int64)
    hb = np.bincount(flat[:, 2], minlength=256).astype(np.int64)
    if bins != 256:
        hr = _rebin_hist(hr, bins)
        hg = _rebin_hist(hg, bins)
        hb = _rebin_hist(hb, bins)

    return SpectrumStats(
        bins=bins,
        mean_r=float(means[0]),
        mean_g=float(means[1]),
        mean_b=float(means[2]),
        min_r=int(mins[0]),
        min_g=int(mins[1]),
        min_b=int(mins[2]),
        max_r=int(maxs[0]),
        max_g=int(maxs[1]),
        max_b=int(maxs[2]),
        std_r=float(stds[0]),
        std_g=float(stds[1]),
        std_b=float(stds[2]),
        hist_r=hr.tolist(),
        hist_g=hg.tolist(),
        hist_b=hb.tolist(),
        pixels=int(flat.shape[0]),
        shape=(int(arr.shape[0]), int(arr.shape[1]), 3),
    )


def _rebin_hist(hist256: np.ndarray, bins: int) -> np.ndarray:
    out = np.zeros(bins, dtype=np.int64)
    edges = np.linspace(0, 256, bins + 1).astype(np.int64)
    for i in range(bins):
        out[i] = int(hist256[edges[i] : edges[i + 1]].sum())
    return out
