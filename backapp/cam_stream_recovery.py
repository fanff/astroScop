"""
Unicam / stream hang recovery helpers (camera-free).

Used by ``cam_picamera2`` when libcamera reports started but never delivers
frames (``capture_request`` hangs). Soft failures reopen in-process; hangs
exit so systemd ``Restart=always`` can recover.
"""

from __future__ import annotations

STREAM_BOOT_GRACE_S = 4.0
STREAM_MAX_SOFT_FAILURES = 5


class CameraStreamError(Exception):
    """Camera opened/started but streaming failed (may retry in-process)."""


class CameraStreamHangError(CameraStreamError):
    """capture_request hung; capture pool may be poisoned — exit for systemd."""


def capture_timeout_s(shutter_us, margin_s=5.0, floor_s=10.0):
    """Seconds to wait for one frame before treating the stream as dead."""
    return max(float(floor_s), float(shutter_us) / 1e6 + float(margin_s))


def stream_retry_backoff_s(failure_count, base_s=1.0, cap_s=15.0):
    """Exponential backoff after consecutive soft stream failures (1-based count)."""
    n = max(1, int(failure_count))
    return min(float(cap_s), float(base_s) * (2 ** (n - 1)))


def should_exit_after_failures(failure_count, max_failures=STREAM_MAX_SOFT_FAILURES):
    """True when in-process reopen attempts are exhausted."""
    return int(failure_count) >= int(max_failures)
