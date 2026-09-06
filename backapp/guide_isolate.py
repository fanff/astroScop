"""Star isolation on a small native RGB tile.

Lock-anchored first-moment centroid (numpy only, no OpenCV).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

LUMA_WR, LUMA_WG, LUMA_WB = 0.3, 0.6, 0.1
ANNULUS_PX = 3
GATE_K = 3.0
GATE_FLOOR = 1.0
WINDOW_HALF = 7
SEARCH_HALF = 16
MIN_GATED = 1
MAX_GATED_FRAC = 0.40
MIN_SNR = 5.0
SAT_PEAK = 250.0
EDGE_RING = 1
STACK_N = 5


@dataclass(frozen=True)
class IsolateResult:
    ok: bool
    u: float
    v: float
    snr: float
    n_gated: int
    reason: str = ""


class CentroidEma:
    """3-frame EMA of (u, v). Deadband is a later controller concern."""

    def __init__(self, n: int = 3) -> None:
        self.n = max(1, int(n))
        self.alpha = 1.0 / float(self.n)
        self.u: float | None = None
        self.v: float | None = None

    def reset(self) -> None:
        self.u = None
        self.v = None

    def update(self, u: float, v: float) -> tuple[float, float]:
        if self.u is None or self.v is None:
            self.u = float(u)
            self.v = float(v)
            return self.u, self.v
        a = self.alpha
        self.u = (1.0 - a) * self.u + a * float(u)
        self.v = (1.0 - a) * self.v + a * float(v)
        return self.u, self.v


class TileStack:
    """Short unaligned RGB stack. Median knocks down high-gain spikes before isolate."""

    def __init__(self, n: int = STACK_N, method: str = "median") -> None:
        self.n = max(1, int(n))
        self.method = "mean" if method == "mean" else "median"
        self._frames: list[np.ndarray] = []

    def reset(self) -> None:
        self._frames.clear()

    @property
    def count(self) -> int:
        return len(self._frames)

    def push(self, rgb: np.ndarray) -> np.ndarray:
        arr = np.asarray(rgb, dtype=np.float32)
        if arr.ndim != 3 or arr.shape[2] < 3:
            raise ValueError("rgb tile must be HxWx3")
        if self._frames and arr.shape != self._frames[0].shape:
            self._frames.clear()
        self._frames.append(arr)
        if len(self._frames) > self.n:
            del self._frames[0]
        if len(self._frames) == 1:
            return arr
        stacked = np.stack(self._frames, axis=0)
        if self.method == "mean":
            return stacked.mean(axis=0)
        return np.median(stacked, axis=0)


def luminance(rgb: np.ndarray) -> np.ndarray:
    arr = np.asarray(rgb, dtype=np.float64)
    if arr.ndim != 3 or arr.shape[2] < 3:
        raise ValueError("rgb tile must be HxWx3")
    return LUMA_WR * arr[..., 0] + LUMA_WG * arr[..., 1] + LUMA_WB * arr[..., 2]


def _annulus_mask(h: int, w: int, ring: int) -> np.ndarray:
    mask = np.zeros((h, w), dtype=bool)
    r = int(ring)
    mask[:r, :] = True
    mask[-r:, :] = True
    mask[:, :r] = True
    mask[:, -r:] = True
    return mask


def _slice_around(lu: int, lv: int, half: int, w: int, h: int) -> tuple[int, int, int, int]:
    u0 = max(0, lu - int(half))
    u1 = min(w, lu + int(half) + 1)
    v0 = max(0, lv - int(half))
    v1 = min(h, lv + int(half) + 1)
    return u0, u1, v0, v1


def isolate_star(
    rgb_tile: np.ndarray,
    lock_u: float,
    lock_v: float,
    *,
    window_half: int = WINDOW_HALF,
) -> IsolateResult:
    luma = luminance(rgb_tile)
    h, w = luma.shape
    if h < 8 or w < 8:
        return IsolateResult(False, float(lock_u), float(lock_v), 0.0, 0, "tile_too_small")

    annulus = _annulus_mask(h, w, ANNULUS_PX)
    bg_pix = luma[annulus]
    bg = float(np.median(bg_pix))
    sigma = float(np.std(bg_pix))
    if not np.isfinite(sigma) or sigma < 1e-6:
        sigma = 1e-6
    subtracted = luma - bg
    thresh = max(GATE_K * sigma, GATE_FLOOR)
    gated = subtracted > thresh
    n_sky = int(np.count_nonzero(gated & annulus))
    n_sky_pix = int(np.count_nonzero(annulus))
    if n_sky_pix and n_sky > MAX_GATED_FRAC * n_sky_pix:
        return IsolateResult(False, float(lock_u), float(lock_v), 0.0, n_sky, "saturated")

    lu = int(round(float(lock_u)))
    lv = int(round(float(lock_v)))
    half = int(window_half)
    u0, u1, v0, v1 = _slice_around(lu, lv, half, w, h)
    win_gate = gated[v0:v1, u0:u1]
    n_win = int(np.count_nonzero(win_gate))
    if n_win < MIN_GATED:
        su0, su1, sv0, sv1 = _slice_around(lu, lv, SEARCH_HALF, w, h)
        search = subtracted[sv0:sv1, su0:su1]
        if search.size == 0:
            return IsolateResult(False, float(lock_u), float(lock_v), 0.0, n_win, "too_few")
        peak_loc = np.unravel_index(int(np.argmax(search)), search.shape)
        pu = su0 + int(peak_loc[1])
        pv = sv0 + int(peak_loc[0])
        u0, u1, v0, v1 = _slice_around(pu, pv, half, w, h)
        win_gate = gated[v0:v1, u0:u1]
        n_win = int(np.count_nonzero(win_gate))
        if n_win < MIN_GATED:
            return IsolateResult(False, float(lock_u), float(lock_v), 0.0, n_win, "too_few")

    win_sub = subtracted[v0:v1, u0:u1]
    yy, xx = np.indices(win_sub.shape)
    weights = np.where(win_gate, np.clip(win_sub, 0.0, None), 0.0)
    wsum = float(np.sum(weights))
    if wsum <= 0.0:
        return IsolateResult(False, float(lock_u), float(lock_v), 0.0, n_win, "too_few")
    cu = u0 + float(np.sum(weights * xx) / wsum)
    cv = v0 + float(np.sum(weights * yy) / wsum)

    peak_win = float(np.max(win_sub))
    snr = peak_win / sigma
    if snr < MIN_SNR:
        return IsolateResult(False, cu, cv, snr, n_win, "low_snr")

    peak_loc = np.unravel_index(int(np.argmax(win_sub)), win_sub.shape)
    peak_u = u0 + int(peak_loc[1])
    peak_v = v0 + int(peak_loc[0])
    if (
        peak_u < EDGE_RING
        or peak_u >= w - EDGE_RING
        or peak_v < EDGE_RING
        or peak_v >= h - EDGE_RING
    ):
        return IsolateResult(False, cu, cv, snr, n_win, "edge_exit")

    return IsolateResult(True, cu, cv, snr, n_win, "")


def synthetic_star_rgb(
    h: int,
    w: int,
    u: float,
    v: float,
    *,
    sigma: float = 2.5,
    peak: float = 90.0,
    bg: float = 18.0,
    rng: np.random.Generator | None = None,
    read_sigma: float = 2.0,
) -> np.ndarray:
    """uint8 HxWx3 Gaussian star for tests and the Pi isolate bench."""
    yy, xx = np.mgrid[0:h, 0:w]
    g = peak * np.exp(-((xx - u) ** 2 + (yy - v) ** 2) / (2.0 * sigma**2))
    img = bg + g
    if rng is not None:
        img = rng.poisson(np.clip(img, 0.0, None)).astype(np.float64)
        img = img + rng.normal(0.0, read_sigma, img.shape)
    rgb = np.clip(np.round(img), 0, 255).astype(np.uint8)
    return np.stack([rgb, rgb, rgb], axis=-1)
