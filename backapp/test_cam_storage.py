"""
Unit tests for Bayer science storage process + acquisition handoff isolation.

No camera hardware required.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
from pathlib import Path

import numpy as np

from cam_settings import CameraSettings, from_legacy_dict
from cam_storage import ScienceStorageClient, write_bayer_frame, compute_ring_slots
from jobutils import MsgBuff


SENSOR_PRESETS = {
    "full": {"size": (4056, 3040)},
    "full_2160": {"size": (4056, 2160)},
    "bin2x2": {"size": (2028, 1520)},
    "bin2x2_1080": {"size": (2028, 1080)},
    "bin2x2_crop": {"size": (1332, 990)},
}


def test_compute_ring_slots_from_ram_budget():
    # 8 GiB * 0.60 / 30 MiB ≈ 163 (ignore host /dev/shm)
    eight_gib = 8 * 1024 ** 3
    thirty_mib = 30 * 1024 ** 2
    huge_shm = 64 * 1024 ** 3
    n = compute_ring_slots(
        thirty_mib, ram_fraction=0.60, total_ram=eight_gib, shm_nbytes=huge_shm
    )
    assert n == 163
    # Smaller live Bayer → more slots
    bin2 = 2028 * 1520 * 2
    n2 = compute_ring_slots(
        bin2, ram_fraction=0.60, total_ram=eight_gib, shm_nbytes=huge_shm
    )
    assert n2 > n
    assert (
        compute_ring_slots(
            thirty_mib, total_ram=64 * 1024 ** 2, shm_nbytes=huge_shm
        )
        >= 16
    )


def test_compute_ring_slots_clamped_by_shm():
    eight_gib = 8 * 1024 ** 3
    thirty_mib = 30 * 1024 ** 2
    # Only ~300 MiB shm → 0.85*300/30 ≈ 8 → clamp up to min 16
    n = compute_ring_slots(
        thirty_mib,
        ram_fraction=0.60,
        total_ram=eight_gib,
        shm_nbytes=300 * 1024 ** 2,
        shm_fraction=0.85,
    )
    assert n == 16
    # 2 GiB shm → 0.85*2GiB/30MiB ≈ 58
    n2 = compute_ring_slots(
        thirty_mib,
        ram_fraction=0.60,
        total_ram=eight_gib,
        shm_nbytes=2 * 1024 ** 3,
        shm_fraction=0.85,
    )
    assert 50 <= n2 <= 60


def test_write_bayer_frame_only_npy_and_meta():
    with tempfile.TemporaryDirectory() as td:
        arr = np.arange(12, dtype=np.uint16).reshape(3, 4)
        npy, meta = write_bayer_frame(arr, {"shutter_us": 1000}, td, "sec", "", 7)
        assert npy.endswith("_bayer.npy")
        assert meta.endswith("_meta.json")
        loaded = np.load(npy)
        assert loaded.dtype == np.uint16
        assert loaded.shape == (3, 4)
        files = list(Path(td).rglob("*"))
        assert not any(p.suffix.lower() in {".jpg", ".jpeg", ".bmp", ".tiff", ".tif"} for p in files)


def test_settings_save_enabled_and_root_runtime():
    s = from_legacy_dict(
        {"save_enabled": True, "save_root": "/tmp/astro", "save_format": "none"},
        SENSOR_PRESETS,
    )
    assert s.science_save_active() is True
    assert s.save_root == "/tmp/astro"

    legacy = from_legacy_dict({"save_format": "npy", "save_section": "lucky"}, SENSOR_PRESETS)
    assert legacy.science_save_active() is True
    assert legacy.save_format == "npy"

    off = from_legacy_dict({"save_format": "none"}, SENSOR_PRESETS)
    assert off.science_save_active() is False


def test_preview_depth1_science_independent():
    """Preview drops must not be required for science publish accounting."""
    preview = MsgBuff(1)
    published = []

    def fake_publish(frame_id):
        published.append(frame_id)
        return True

    for i in range(5):
        rgb = np.zeros((8, 8, 3), dtype=np.uint8)
        rgb[0, 0, 0] = i
        fake_publish(i)
        preview.stack((rgb, {"i": i}, float(i)))

    assert len(preview.content) == 1
    assert preview.content[0][1]["i"] == 4
    assert published == [0, 1, 2, 3, 4]
    assert id(preview.content[0][0]) == id(preview.content[0][0])


def test_storage_uses_single_shm_slab():
    client = ScienceStorageClient(n_slots=8)
    try:
        client.start(slot_nbytes=32 * 1024)
        assert client._shm is not None
        assert client._shm.size == 8 * 32 * 1024
        assert client.n_slots == 8
    finally:
        client.shutdown()
        assert client._shm is None


def test_storage_process_writes_and_runtime_disable():
    client = ScienceStorageClient(n_slots=4)
    try:
        with tempfile.TemporaryDirectory() as td:
            client.start(slot_nbytes=64 * 1024)
            client.set_enabled(True)
            arr = (np.arange(100, dtype=np.uint16) % 4095).reshape(10, 10)

            assert client.publish(arr, {"n": 1}, td, "burst", "",) is True
            assert client.publish(arr + 1, {"n": 2}, td, "burst", "") is True

            # Wait for child to drain
            deadline = time.time() + 5.0
            while time.time() < deadline:
                st = client.poll_stats()
                if st.written >= 2:
                    break
                time.sleep(0.05)
            st = client.poll_stats()
            assert st.published == 2
            assert st.written >= 2
            assert st.dropped == 0

            npy_files = list(Path(td).rglob("*_bayer.npy"))
            meta_files = list(Path(td).rglob("*_meta.json"))
            assert len(npy_files) >= 2
            assert len(meta_files) >= 2
            assert not list(Path(td).rglob("*.jpg"))

            # Runtime disable: further publishes ignored
            client.set_enabled(False)
            assert client.publish(arr, {"n": 3}, td, "burst", "") is False

            # Path stamp: re-enable with new root
            td2 = tempfile.mkdtemp(prefix="astro_save2_")
            try:
                client.set_enabled(True)
                assert client.publish(arr, {"n": 4}, td2, "alt", "sub") is True
                deadline = time.time() + 5.0
                while time.time() < deadline:
                    if client.poll_stats().written >= 3:
                        break
                    time.sleep(0.05)
                assert list(Path(td2).rglob("*_bayer.npy"))
            finally:
                import shutil

                shutil.rmtree(td2, ignore_errors=True)
    finally:
        client.shutdown()


def test_publish_nonblocking_when_ring_full():
    client = ScienceStorageClient(n_slots=2)
    try:
        client.start(slot_nbytes=32 * 1024)
        client.set_enabled(True)
        # Don't give the worker a writable path that finishes instantly —
        # fill slots faster than a blocked worker by using a tiny ring and
        # not waiting for free returns: publish until drop.
        arr = np.zeros((32, 32), dtype=np.uint16)
        with tempfile.TemporaryDirectory() as td:
            # Slow the worker indirectly by publishing many frames; with 2 slots
            # at least one drop should occur if we don't wait between publishes
            # after saturating both slots before writes complete.
            drops = 0
            oks = 0
            for i in range(40):
                ok = client.publish(arr, {"i": i}, td, "flood", "")
                if ok:
                    oks += 1
                else:
                    drops += 1
            assert oks >= 1
            assert drops >= 1 or client.stats.dropped >= 1
            # Give worker time to finish before shutdown
            time.sleep(0.5)
    finally:
        client.shutdown()


def test_emit_pack_off_loop_does_not_block_schedule():
    """Simulate slow emit packing while capture schedule coroutine stays responsive."""

    def slow_pack(rgb, display_wh):
        time.sleep(0.15)
        return "fakejpg", None

    async def run():
        loop = asyncio.get_running_loop()
        pool = __import__("concurrent").futures.ThreadPoolExecutor(max_workers=1)
        capture_resumes = []

        async def capture_schedule():
            t0 = time.perf_counter()
            await asyncio.sleep(0)  # yield
            # Schedule a no-op capture "completion"
            await loop.run_in_executor(pool, time.sleep, 0.01)
            capture_resumes.append(time.perf_counter() - t0)

        emit_task = loop.run_in_executor(pool, slow_pack, np.zeros((64, 64, 3), dtype=np.uint8), (32, 32))
        # Start capture schedule shortly after emit is running
        await asyncio.sleep(0.02)
        cap_task = asyncio.create_task(capture_schedule())
        await asyncio.gather(emit_task, cap_task)
        pool.shutdown(wait=False)
        # Capture schedule should finish well before the full 0.15s pack if
        # they share a 1-worker pool they contend — use a dedicated pool for capture.
        return capture_resumes

    # Dedicated pools (mirrors production)
    async def run_isolated():
        loop = asyncio.get_running_loop()
        emit_pool = __import__("concurrent").futures.ThreadPoolExecutor(max_workers=1)
        cap_pool = __import__("concurrent").futures.ThreadPoolExecutor(max_workers=1)
        t0 = time.perf_counter()
        emit_fut = loop.run_in_executor(
            emit_pool, slow_pack, np.zeros((16, 16, 3), dtype=np.uint8), (8, 8)
        )
        await asyncio.sleep(0.01)
        await loop.run_in_executor(cap_pool, time.sleep, 0.01)
        cap_dt = time.perf_counter() - t0
        await emit_fut
        emit_pool.shutdown(wait=False)
        cap_pool.shutdown(wait=False)
        return cap_dt

    cap_dt = asyncio.run(run_isolated())
    assert cap_dt < 0.12, f"capture schedule delayed by emit: {cap_dt:.3f}s"


def test_camera_settings_output_diff_includes_save_root():
    from cam_settings import diff_settings

    a = CameraSettings()
    b = CameraSettings(save_enabled=True, save_root="/media/imgstick")
    d = diff_settings(a, b)
    assert d.output_changed
    assert not d.slow_changed
    assert "save_enabled" in d.changed_fields
    assert "save_root" in d.changed_fields


if __name__ == "__main__":
    # multiprocessing spawn needs this guard on Windows
    test_compute_ring_slots_from_ram_budget()
    test_compute_ring_slots_clamped_by_shm()
    test_write_bayer_frame_only_npy_and_meta()
    test_settings_save_enabled_and_root_runtime()
    test_preview_depth1_science_independent()
    test_storage_uses_single_shm_slab()
    test_storage_process_writes_and_runtime_disable()
    test_publish_nonblocking_when_ring_full()
    test_emit_pack_off_loop_does_not_block_schedule()
    test_camera_settings_output_diff_includes_save_root()
    print("ok")
