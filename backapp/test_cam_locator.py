"""Camera-free tests for tracking-locator geometry and overlay."""

from __future__ import annotations

from PIL import Image

from cam_locator import (
    FULL_SENSOR_WH,
    apply_locator_overlay,
    clamp_locator_center,
    draw_locator,
    locator_draw_xy,
    locator_glyph_metrics,
    locator_preview_xy,
    preview_xy_to_full_sensor,
)
from cam_settings import CameraSettings, default_settings, diff_settings, from_legacy_dict
from ws_messages import SENSOR_PRESETS, normalize_params_data


def test_settings_defaults_and_output_diff():
    s = default_settings()
    assert s.locator_enabled is False
    assert s.locator_x == 0.5
    assert s.locator_y == 0.5
    assert s.locator_size == 1.0
    d = s.to_wire_dict()
    assert d["locator_enabled"] is False
    assert d["locator_x"] == 0.5
    assert d["locator_size"] == 1.0

    moved = s.model_copy(update={"locator_enabled": True, "locator_x": 0.25})
    diff = diff_settings(s, moved)
    assert diff.output_changed
    assert not diff.slow_changed
    assert not diff.fast_changed
    assert "locator_enabled" in diff.changed_fields
    assert "locator_x" in diff.changed_fields


def test_settings_bounds_and_ingest():
    s = CameraSettings(locator_x=0.0, locator_y=1.0, locator_enabled=True)
    assert s.locator_x == 0.0
    assert s.locator_y == 1.0
    parsed = from_legacy_dict(
        {
            "locator_enabled": True,
            "locator_x": 0.2,
            "locator_y": 0.8,
            "locator_size": 0.4,
        },
        SENSOR_PRESETS,
    )
    assert parsed.locator_enabled is True
    assert abs(parsed.locator_x - 0.2) < 1e-9
    assert abs(parsed.locator_y - 0.8) < 1e-9
    assert abs(parsed.locator_size - 0.4) < 1e-9
    wire = normalize_params_data(
        {"shutter_us": 1000, "locator_enabled": True, "locator_x": 0.33}
    )
    assert wire.locator_enabled is True
    assert abs(wire.locator_x - 0.33) < 1e-9


def test_center_invariant_across_preview_sizes():
    crop = [0, 0, FULL_SENSOR_WH[0], FULL_SENSOR_WH[1]]
    for wh in ((2028, 1520), (640, 480), (4056, 3040), (1332, 990)):
        x, y = locator_preview_xy(0.5, 0.5, wh, scaler_crop=crop)
        assert abs(x - (wh[0] - 1) / 2.0) < 1e-6
        assert abs(y - (wh[1] - 1) / 2.0) < 1e-6


def test_resolution_change_keeps_relative_position():
    crop = [0, 0, 4056, 3040]
    nx, ny = 0.3, 0.7
    for wh in ((2028, 1520), (1014, 760), (4056, 3040)):
        x, y = locator_preview_xy(nx, ny, wh, scaler_crop=crop)
        assert abs(x / (wh[0] - 1) - nx) < 1e-9
        assert abs(y / (wh[1] - 1) - ny) < 1e-9


def test_preview_xy_roundtrip():
    crop = [200, 100, 2000, 1500]
    wh = (640, 480)
    for nx, ny in ((0.3, 0.4), (0.5, 0.45), (0.2, 0.2)):
        px, py = locator_preview_xy(nx, ny, wh, scaler_crop=crop)
        back = preview_xy_to_full_sensor(px, py, wh, scaler_crop=crop)
        assert abs(back[0] - nx) < 1e-9
        assert abs(back[1] - ny) < 1e-9


def test_center_crop_maps_sensor_center():
    crop = [696, 528, 2664, 1980]
    fw, fh = FULL_SENSOR_WH
    x, y = locator_preview_xy(0.5, 0.5, (1332, 990), scaler_crop=crop)
    rel_x = (0.5 * fw - crop[0]) / crop[2]
    rel_y = (0.5 * fh - crop[1]) / crop[3]
    assert abs(rel_x - 0.5) < 1e-9
    assert abs(x - rel_x * 1331) < 1e-6
    assert abs(y - rel_y * 989) < 1e-6


def test_out_of_crop_clamps_each_edge():
    crop = [696, 528, 2664, 1980]
    wh = (400, 300)
    left = locator_preview_xy(0.05, 0.5, wh, crop)
    right = locator_preview_xy(0.95, 0.5, wh, crop)
    top = locator_preview_xy(0.5, 0.05, wh, crop)
    bottom = locator_preview_xy(0.5, 0.95, wh, crop)
    assert left[0] == 0.0
    assert abs(right[0] - (wh[0] - 1)) < 1e-9
    assert top[1] == 0.0
    assert abs(bottom[1] - (wh[1] - 1)) < 1e-9

    for nx, ny, edge in (
        (0.05, 0.5, "left"),
        (0.95, 0.5, "right"),
        (0.5, 0.05, "top"),
        (0.5, 0.95, "bottom"),
    ):
        cx, cy, m = locator_draw_xy(nx, ny, wh, crop)
        half = m["half"]
        if edge == "left":
            assert abs(cx - half) < 1e-6
        elif edge == "right":
            assert abs(cx - (wh[0] - 1 - half)) < 1e-6
        elif edge == "top":
            assert abs(cy - half) < 1e-6
        else:
            assert abs(cy - (wh[1] - 1 - half)) < 1e-6


def test_glyph_margins_keep_mark_onscreen():
    wh = (320, 240)
    m = locator_glyph_metrics(wh)
    cx, cy = clamp_locator_center((0.0, 0.0), wh, m["half"])
    assert cx >= m["half"]
    assert cy >= m["half"]
    cx, cy = clamp_locator_center((319.0, 239.0), wh, m["half"])
    assert cx <= wh[0] - 1 - m["half"]
    assert cy <= wh[1] - 1 - m["half"]


def test_disabled_overlay_is_identity():
    img = Image.new("RGB", (80, 60), (12, 34, 56))
    out = apply_locator_overlay(img, {"enabled": False, "x": 0.2, "y": 0.3})
    assert out is img
    assert list(img.getdata()) == [(12, 34, 56)] * (80 * 60)


def test_enabled_overlay_paints_red_pixels():
    img = Image.new("RGB", (200, 160), (10, 20, 30))
    before = list(img.getdata())
    out = apply_locator_overlay(
        img, {"enabled": True, "x": 0.5, "y": 0.5, "scaler_crop": None}
    )
    after = list(out.getdata())
    assert out is not img
    assert before == list(img.getdata())
    assert before != after
    assert any(p[0] > 180 and p[1] < 90 and p[2] < 90 for p in after)


def test_size_scales_radius_and_thins_stroke():
    m1 = locator_glyph_metrics((400, 300), size=1.0)
    m_half = locator_glyph_metrics((400, 300), size=0.5)
    m_big = locator_glyph_metrics((400, 300), size=2.0)
    assert m_half["radius"] < m1["radius"] < m_big["radius"]
    assert m1["stroke"] <= max(1, int(round(m1["radius"] * 0.07)))
    assert m1["under"] == m1["stroke"] + 1


def test_draw_locator_direct():
    img = Image.new("RGB", (180, 140), (0, 0, 0))
    draw_locator(img, 0.4, 0.6)
    assert any(p[0] > 180 for p in img.getdata())


if __name__ == "__main__":
    test_settings_defaults_and_output_diff()
    test_settings_bounds_and_ingest()
    test_center_invariant_across_preview_sizes()
    test_resolution_change_keeps_relative_position()
    test_center_crop_maps_sensor_center()
    test_out_of_crop_clamps_each_edge()
    test_glyph_margins_keep_mark_onscreen()
    test_disabled_overlay_is_identity()
    test_enabled_overlay_paints_red_pixels()
    test_size_scales_radius_and_thins_stroke()
    test_draw_locator_direct()
    print("ok")
