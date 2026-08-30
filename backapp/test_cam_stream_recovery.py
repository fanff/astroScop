"""Camera-free tests for Unicam hang / stream recovery helpers."""

from __future__ import annotations

from cam_stream_recovery import (
    STREAM_MAX_SOFT_FAILURES,
    capture_timeout_s,
    should_exit_after_failures,
    stream_retry_backoff_s,
)


def test_capture_timeout_floor_for_short_shutter():
    # Default 150 ms shutter → floor 10 s, not shutter+margin alone
    assert capture_timeout_s(150_000) == 10.0
    assert capture_timeout_s(1_000) == 10.0


def test_capture_timeout_tracks_long_shutter():
    # 30 s exposure + 5 s margin
    assert abs(capture_timeout_s(30_000_000) - 35.0) < 1e-9
    # 120 s exposure + 5 s margin
    assert abs(capture_timeout_s(120_000_000) - 125.0) < 1e-9


def test_capture_timeout_custom_margin_floor():
    assert abs(capture_timeout_s(1_000_000, margin_s=2.0, floor_s=3.0) - 3.0) < 1e-9
    assert abs(capture_timeout_s(5_000_000, margin_s=2.0, floor_s=3.0) - 7.0) < 1e-9


def test_stream_retry_backoff_exponential_capped():
    assert stream_retry_backoff_s(1) == 1.0
    assert stream_retry_backoff_s(2) == 2.0
    assert stream_retry_backoff_s(3) == 4.0
    assert stream_retry_backoff_s(4) == 8.0
    assert stream_retry_backoff_s(5) == 15.0  # capped
    assert stream_retry_backoff_s(10) == 15.0


def test_should_exit_after_failures():
    assert not should_exit_after_failures(0)
    assert not should_exit_after_failures(STREAM_MAX_SOFT_FAILURES - 1)
    assert should_exit_after_failures(STREAM_MAX_SOFT_FAILURES)
    assert should_exit_after_failures(STREAM_MAX_SOFT_FAILURES + 1)
    assert should_exit_after_failures(3, max_failures=3)
    assert not should_exit_after_failures(2, max_failures=3)
