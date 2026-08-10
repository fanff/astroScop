"""Unit tests for camTiming rate / queue-fill helpers."""

from __future__ import annotations

import time

from cam_timing_rates import CaptureClock, compute_timing_rates


def test_capture_clock_ema_frame_time():
    clock = CaptureClock(_ema_alpha=1.0)  # last interval only
    t0 = 1000.0
    clock.note_capture(t0)
    clock.note_capture(t0 + 0.100)
    assert clock.count == 2
    assert abs(clock.frame_time_ms - 100.0) < 1e-6
    clock.note_capture(t0 + 0.150)
    assert abs(clock.frame_time_ms - 50.0) < 1e-6


def test_compute_rates_capture_and_emit():
    rates = compute_timing_rates(
        dt_s=2.0,
        capture_delta=20,
        frame_time_ms=100.0,
        published_delta=0,
        written_delta=0,
        emitted=8,
        science_pending=0,
        science_slots=16,
        save_enabled=False,
    )
    assert abs(rates.capture_fps - 10.0) < 1e-9
    assert abs(rates.frame_time_ms - 100.0) < 1e-9
    assert abs(rates.emit_fps - 4.0) < 1e-9
    assert rates.queue_fill_eta_s is None


def test_frame_time_fallback_from_fps():
    rates = compute_timing_rates(
        dt_s=1.0,
        capture_delta=5,
        frame_time_ms=0.0,
        published_delta=0,
        written_delta=0,
        emitted=0,
        science_pending=0,
        science_slots=16,
        save_enabled=False,
    )
    assert abs(rates.capture_fps - 5.0) < 1e-9
    assert abs(rates.frame_time_ms - 200.0) < 1e-9


def test_queue_eta_net_fill():
    # 10 free, publish 5/s, write 3/s → net 2/s → 5 s
    rates = compute_timing_rates(
        dt_s=1.0,
        capture_delta=5,
        frame_time_ms=200.0,
        published_delta=5,
        written_delta=3,
        emitted=0,
        science_pending=6,
        science_slots=16,
        save_enabled=True,
    )
    assert abs(rates.science_publish_fps - 5.0) < 1e-9
    assert abs(rates.science_write_fps - 3.0) < 1e-9
    assert abs(rates.queue_fill_eta_s - 5.0) < 1e-9


def test_queue_eta_not_filling_when_write_keeps_up():
    rates = compute_timing_rates(
        dt_s=1.0,
        capture_delta=4,
        frame_time_ms=250.0,
        published_delta=4,
        written_delta=4,
        emitted=0,
        science_pending=2,
        science_slots=100,
        save_enabled=True,
    )
    assert rates.queue_fill_eta_s is None


def test_queue_eta_full_now():
    rates = compute_timing_rates(
        dt_s=1.0,
        capture_delta=2,
        frame_time_ms=500.0,
        published_delta=2,
        written_delta=0,
        emitted=0,
        science_pending=16,
        science_slots=16,
        save_enabled=True,
    )
    assert rates.queue_fill_eta_s == 0.0


def test_capture_clock_real_mono():
    clock = CaptureClock()
    clock.note_capture(time.monotonic())
    time.sleep(0.02)
    clock.note_capture(time.monotonic())
    assert clock.count == 2
    assert clock.frame_time_ms > 0.0
