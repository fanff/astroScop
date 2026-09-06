"""Laptop tests for native RGB extract + shm latest-wins (no Picamera2)."""

import sys

import numpy as np
import pytest

from cam_settings import CameraSettings, default_settings, diff_settings, from_legacy_dict
from guide_handoff import (
    GuidePublisher,
    GuideTileSlot,
    extract_guide_tile,
    unique_slot_name,
)
from guide_roi import lock_to_roi
from ws_messages import SENSOR_PRESETS


def _blob_rgb(h=200, w=200, u=100, v=80, val=200):
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    rgb[v, u] = (val, val, val)
    return rgb


def test_extract_matches_lock_to_roi():
    rgb = _blob_rgb()
    roi = lock_to_roi(0.5, 0.5, (200, 200), roi_half=32)
    tile = extract_guide_tile(rgb, 0.5, 0.5, roi_half=32)
    assert tile is not None
    assert tile.origin_u == roi.origin_u
    assert tile.origin_v == roi.origin_v
    assert tile.rgb.shape == (64, 64, 3)
    lu, lv = int(round(tile.lock_u)), int(round(tile.lock_v))
    assert tile.rgb[lv, lu, 0] == rgb[roi.origin_v + lv, roi.origin_u + lu, 0]


def test_extract_outside_crop_none():
    rgb = _blob_rgb()
    crop = [2000, 1000, 800, 600]
    assert extract_guide_tile(rgb, 0.05, 0.5, scaler_crop=crop, roi_half=32) is None


def test_slot_roundtrip_and_latest_wins():
    name = unique_slot_name()
    slot = GuideTileSlot.create(name)
    try:
        a = extract_guide_tile(_blob_rgb(val=10), 0.5, 0.5, roi_half=32, t=1.0)
        b = extract_guide_tile(_blob_rgb(val=99), 0.5, 0.5, roi_half=32, t=2.0)
        assert a is not None and b is not None
        slot.write(a)
        reader = GuideTileSlot.attach(name)
        got = reader.read()
        assert got is not None
        assert int(got.rgb.max()) == 10
        slot.write(b)
        got2 = reader.read()
        assert got2 is not None
        assert int(got2.rgb.max()) == 99
        assert abs(got2.t - 2.0) < 1e-6
        reader.close(unlink=False)
    finally:
        slot.close(unlink=True)


def test_publisher_disabled_does_not_allocate():
    name = unique_slot_name()
    pub = GuidePublisher(name=name)
    rgb = _blob_rgb()
    assert pub.on_frame(
        rgb,
        track_enabled=False,
        track_x=0.5,
        track_y=0.5,
        track_roi=32,
    ) is None
    assert pub._slot is None
    pub.close()


def test_publisher_track_off_keeps_slot():
    name = unique_slot_name()
    pub = GuidePublisher(name=name)
    rgb = _blob_rgb(val=10)
    assert pub.on_frame(
        rgb,
        track_enabled=True,
        track_x=0.5,
        track_y=0.5,
        track_roi=32,
        t=1.0,
    ) is not None
    assert pub._slot is not None
    reader = GuideTileSlot.attach(name)
    try:
        assert pub.on_frame(
            rgb,
            track_enabled=False,
            track_x=0.5,
            track_y=0.5,
            track_roi=32,
        ) is None
        assert pub._slot is not None
        first = reader.read()
        assert first is not None
        rgb2 = _blob_rgb(val=99)
        assert pub.on_frame(
            rgb2,
            track_enabled=True,
            track_x=0.5,
            track_y=0.5,
            track_roi=32,
            t=2.0,
        ) is not None
        got = reader.read()
        assert got is not None
        assert int(got.rgb.max()) == 99
    finally:
        reader.close(unlink=False)
        pub.close()


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows keeps the shm name until every handle closes",
)
def test_unlink_recreate_orphans_old_reader():
    """Camera unlink+create is a new inode; an old attach stays frozen."""
    name = unique_slot_name()
    writer = GuideTileSlot.create(name)
    reader = GuideTileSlot.attach(name)
    try:
        a = extract_guide_tile(_blob_rgb(val=10), 0.5, 0.5, roi_half=32, t=1.0)
        b = extract_guide_tile(_blob_rgb(val=99), 0.5, 0.5, roi_half=32, t=2.0)
        assert a is not None and b is not None
        writer.write(a)
        assert int(reader.read().rgb.max()) == 10
        writer.close(unlink=True)
        writer2 = GuideTileSlot.create(name)
        writer2.write(b)
        stale = reader.read()
        if stale is not None:
            assert int(stale.rgb.max()) == 10
        reader.close(unlink=False)
        fresh = GuideTileSlot.attach(name)
        got = fresh.read()
        assert got is not None
        assert int(got.rgb.max()) == 99
        fresh.close(unlink=False)
        writer2.close(unlink=True)
    except Exception:
        try:
            writer.close(unlink=True)
        except Exception:
            pass
        raise


def test_track_settings_default_off_output_class():
    s = default_settings()
    assert s.track_enabled is False
    assert s.track_x == 0.5
    assert s.track_y == 0.5
    assert s.track_roi == 32
    moved = s.model_copy(update={"track_enabled": True, "track_x": 0.4, "track_roi": 48})
    d = diff_settings(s, moved)
    assert d.output_changed
    assert not d.slow_changed
    assert not d.fast_changed
    assert "track_enabled" in d.changed_fields
    parsed = from_legacy_dict(
        {"track_enabled": True, "track_x": 0.2, "track_y": 0.8, "track_roi": 16},
        SENSOR_PRESETS,
    )
    assert parsed.track_enabled is True
    assert abs(parsed.track_x - 0.2) < 1e-9
    assert parsed.track_roi == 16
    wire = CameraSettings().to_wire_dict()
    assert wire["track_enabled"] is False
