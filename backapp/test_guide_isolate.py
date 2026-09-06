"""Synthetic-tile tests for star isolation (no camera)."""

import numpy as np

from guide_isolate import SAT_PEAK, CentroidEma, TileStack, isolate_star, luminance


def synthetic_star(
    h,
    w,
    u,
    v,
    *,
    sigma=2.5,
    peak=90.0,
    bg=18.0,
    rng=None,
    read_sigma=2.0,
    extra=None,
):
    yy, xx = np.mgrid[0:h, 0:w]
    g = peak * np.exp(-((xx - u) ** 2 + (yy - v) ** 2) / (2.0 * sigma**2))
    img = bg + g
    if extra is not None:
        img = img + extra
    if rng is not None:
        lam = np.clip(img, 0.0, None)
        img = rng.poisson(lam).astype(np.float64)
        img = img + rng.normal(0.0, read_sigma, img.shape)
    rgb = np.clip(np.round(img), 0, 255).astype(np.uint8)
    return np.stack([rgb, rgb, rgb], axis=-1)


def test_luminance_weights():
    tile = np.zeros((8, 8, 3), dtype=np.uint8)
    tile[..., 0] = 10
    tile[..., 1] = 20
    tile[..., 2] = 30
    y = luminance(tile)
    assert abs(float(y[0, 0]) - (0.3 * 10 + 0.6 * 20 + 0.1 * 30)) < 1e-9


def test_gaussian_psf_centroid_near_lock():
    rng = np.random.default_rng(1)
    u0, v0 = 32.4, 31.1
    tile = synthetic_star(64, 64, u0, v0, sigma=3.0, rng=rng)
    r = isolate_star(tile, 32.0, 32.0)
    assert r.ok, r.reason
    assert abs(r.u - u0) < 0.8
    assert abs(r.v - v0) < 0.8
    assert r.snr >= 5.0


def test_slow_drift_stays_on_primary():
    rng = np.random.default_rng(2)
    lock_u, lock_v = 32.0, 32.0
    for i in range(8):
        u = lock_u + 0.3 * i
        v = lock_v - 0.2 * i
        tile = synthetic_star(64, 64, u, v, sigma=2.5, rng=rng)
        r = isolate_star(tile, lock_u, lock_v)
        assert r.ok, (i, r.reason)
        assert abs(r.u - u) < 1.0
        assert abs(r.v - v) < 1.0


def test_hot_pixel_does_not_steal():
    rng = np.random.default_rng(3)
    extra = np.zeros((64, 64))
    extra[8, 50] = 255.0
    tile = synthetic_star(64, 64, 32.0, 32.0, sigma=3.0, peak=80.0, rng=rng, extra=extra)
    r = isolate_star(tile, 32.0, 32.0)
    assert r.ok, r.reason
    assert abs(r.u - 32.0) < 1.2
    assert abs(r.v - 32.0) < 1.2


def test_dimmer_neighbor_at_edge_does_not_steal():
    rng = np.random.default_rng(4)
    yy, xx = np.mgrid[0:64, 0:64]
    extra = 40.0 * np.exp(-((xx - 58.0) ** 2 + (yy - 6.0) ** 2) / (2.0 * 2.5**2))
    tile = synthetic_star(64, 64, 32.0, 32.0, sigma=3.0, peak=90.0, rng=rng, extra=extra)
    r = isolate_star(tile, 32.0, 32.0)
    assert r.ok, r.reason
    assert abs(r.u - 32.0) < 1.2
    assert abs(r.v - 32.0) < 1.2


def test_low_snr_lost_star():
    rng = np.random.default_rng(5)
    tile = synthetic_star(
        64, 64, 32.0, 32.0, sigma=3.0, peak=2.0, bg=20.0, rng=rng, read_sigma=8.0
    )
    r = isolate_star(tile, 32.0, 32.0)
    assert r.ok is False
    assert r.reason in ("too_few", "low_snr")


def test_blob_on_outer_ring_lost():
    tile = synthetic_star(64, 64, 0.3, 32.0, sigma=1.5, peak=120.0, rng=None, read_sigma=0.0)
    r = isolate_star(tile, 0.3, 32.0)
    assert r.ok is False
    assert r.reason == "edge_exit"


def test_clipped_core_still_ok():
    tile = synthetic_star(
        64, 64, 32.0, 32.0, sigma=2.0, peak=240.0, bg=12.0, rng=None, read_sigma=0.0
    )
    assert float(tile[32, 32, 1]) >= SAT_PEAK
    r = isolate_star(tile, 32.0, 32.0)
    assert r.ok, r.reason
    assert abs(r.u - 32.0) < 1.0
    assert abs(r.v - 32.0) < 1.0


def test_compact_star_one_pixel():
    tile = np.full((64, 64, 3), 16, dtype=np.uint8)
    tile[32, 32] = 200
    r = isolate_star(tile, 32.0, 32.0)
    assert r.ok, r.reason
    assert abs(r.u - 32.0) < 0.6
    assert abs(r.v - 32.0) < 0.6


def test_lock_offset_still_finds_star():
    tile = synthetic_star(64, 64, 46.0, 32.0, sigma=2.0, peak=120.0, rng=None, read_sigma=0.0)
    r = isolate_star(tile, 32.0, 32.0)
    assert r.ok, r.reason
    assert abs(r.u - 46.0) < 1.0


def test_extended_bright_star_not_tile_fill():
    tile = synthetic_star(
        64, 64, 32.0, 32.0, sigma=10.0, peak=160.0, bg=12.0, rng=None, read_sigma=0.0
    )
    r = isolate_star(tile, 32.0, 32.0)
    assert r.ok, r.reason


def test_ema_converges_no_noise():
    ema = CentroidEma(n=3)
    u, v = ema.update(10.0, 20.0)
    assert u == 10.0 and v == 20.0
    u, v = ema.update(13.0, 20.0)
    assert abs(u - 11.0) < 1e-12
    u, v = ema.update(13.0, 20.0)
    assert 11.0 < u < 13.0


def test_tile_stack_median_kills_hot_pixel():
    rng = np.random.default_rng(9)
    stack = TileStack(n=5, method="median")
    last = None
    for i in range(5):
        extra = np.zeros((64, 64))
        extra[10, 10] = 255.0 if i == 2 else 0.0
        tile = synthetic_star(64, 64, 32.0, 32.0, sigma=3.0, peak=80.0, rng=rng, extra=extra)
        last = stack.push(tile)
    assert last is not None
    assert float(last[10, 10].max()) < 80.0
    r = isolate_star(last, 32.0, 32.0)
    assert r.ok, r.reason
    assert abs(r.u - 32.0) < 1.2
    assert abs(r.v - 32.0) < 1.2


def test_tile_stack_reset_and_shape_change():
    stack = TileStack(n=3)
    stack.push(np.zeros((16, 16, 3), dtype=np.uint8))
    stack.push(np.ones((16, 16, 3), dtype=np.uint8))
    assert stack.count == 2
    stack.reset()
    assert stack.count == 0
    stack.push(np.zeros((16, 16, 3), dtype=np.uint8))
    stack.push(np.zeros((32, 32, 3), dtype=np.uint8))
    assert stack.count == 1
