"""ROI mapping tests (no camera)."""

from cam_locator import FULL_SENSOR_WH
from guide_roi import lock_to_rgb_uv, lock_to_roi


def test_center_full_sensor_rgb_sizes():
    for wh in ((4056, 3040), (2028, 1520), (1332, 990)):
        ok, u, v, reason = lock_to_rgb_uv(0.5, 0.5, wh, scaler_crop=None)
        assert ok and reason == ""
        assert abs(u - (wh[0] - 1) / 2.0) < 1e-9
        assert abs(v - (wh[1] - 1) / 2.0) < 1e-9


def test_known_scaler_crop_maps_like_locator():
    crop = [1000, 500, 2000, 1500]
    rgb_wh = (1000, 750)
    cx, cy, cw, ch = crop
    track_x = (cx + cw / 2.0) / FULL_SENSOR_WH[0]
    track_y = (cy + ch / 2.0) / FULL_SENSOR_WH[1]
    ok, u, v, _ = lock_to_rgb_uv(track_x, track_y, rgb_wh, scaler_crop=crop)
    assert ok
    assert abs(u - (rgb_wh[0] - 1) / 2.0) < 1e-6
    assert abs(v - (rgb_wh[1] - 1) / 2.0) < 1e-6


def test_lock_outside_crop_rejected():
    crop = [2000, 1000, 800, 600]
    ok, _, _, reason = lock_to_rgb_uv(0.05, 0.5, (400, 300), scaler_crop=crop)
    assert ok is False
    assert reason == "outside_crop"
    roi = lock_to_roi(0.05, 0.5, (400, 300), scaler_crop=crop, roi_half=32)
    assert roi.ok is False
    assert roi.reason == "outside_crop"


def test_origin_plus_lock_matches_rgb():
    roi = lock_to_roi(0.4, 0.6, (2028, 1520), scaler_crop=None, roi_half=32)
    assert roi.ok
    assert roi.size_u == 64 and roi.size_v == 64
    assert abs((roi.origin_u + roi.lock_u) - roi.rgb_u) < 1e-9
    assert abs((roi.origin_v + roi.lock_v) - roi.rgb_v) < 1e-9
    assert 0.0 <= roi.lock_u < 64
    assert 0.0 <= roi.lock_v < 64


def test_border_shifts_to_keep_full_tile():
    rgb_wh = (200, 200)
    # Near top-left of full sensor → near top-left of RGB when crop is full.
    roi = lock_to_roi(0.002, 0.002, rgb_wh, scaler_crop=None, roi_half=32)
    assert roi.ok
    assert roi.origin_u == 0 and roi.origin_v == 0
    assert roi.size_u == 64 and roi.size_v == 64
    assert 0.0 <= roi.lock_u < 64
    assert 0.0 <= roi.lock_v < 64


def test_center_uv_recenters_tile():
    base = lock_to_roi(0.5, 0.5, (400, 400), roi_half=32)
    moved = lock_to_roi(
        0.5, 0.5, (400, 400), roi_half=32, center_uv=(base.rgb_u + 10.0, base.rgb_v)
    )
    assert moved.ok
    assert moved.origin_u == base.origin_u + 10


def test_bad_roi_half():
    roi = lock_to_roi(0.5, 0.5, (200, 200), roi_half=2)
    assert roi.ok is False
    assert roi.reason == "bad_roi_half"
