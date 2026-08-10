"""
Pure helpers for camTiming rate fields (no camera / picamera2 dependency).

Capture loop stamps wall-clock intervals; bg_job turns counter deltas into FPS
and net science-queue fill ETA.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class CaptureClock:
    """Wall-clock capture cadence shared between open_camera and bg_job."""

    count: int = 0
    last_mono: float = 0.0
    frame_time_ms: float = 0.0
    _ema_alpha: float = 0.25

    def note_capture(self, mono: float) -> None:
        if self.count > 0 and self.last_mono > 0.0:
            dt = mono - self.last_mono
            if dt > 0.0:
                ms = dt * 1000.0
                if self.frame_time_ms <= 0.0:
                    self.frame_time_ms = ms
                else:
                    a = self._ema_alpha
                    self.frame_time_ms = (1.0 - a) * self.frame_time_ms + a * ms
        self.last_mono = mono
        self.count += 1

    def snapshot(self) -> tuple[int, float]:
        """Return (capture_count, frame_time_ms)."""
        return int(self.count), float(self.frame_time_ms)


@dataclass(frozen=True)
class TimingRates:
    capture_fps: float = 0.0
    frame_time_ms: float = 0.0
    science_publish_fps: float = 0.0
    science_write_fps: float = 0.0
    emit_fps: float = 0.0
    queue_fill_eta_s: Optional[float] = None


def _safe_fps(delta_count: float, dt_s: float) -> float:
    if dt_s <= 0.0:
        return 0.0
    return max(0.0, float(delta_count) / float(dt_s))


def compute_timing_rates(
    *,
    dt_s: float,
    capture_delta: int,
    frame_time_ms: float,
    published_delta: int,
    written_delta: int,
    emitted: int,
    science_pending: int,
    science_slots: int,
    save_enabled: bool,
) -> TimingRates:
    """
    Derive camTiming rate fields from a timing window.

    ``queue_fill_eta_s`` is net fill only: free / max(0, publish_fps - write_fps).
    ``None`` when save is off or the queue is not filling.
    """
    capture_fps = _safe_fps(capture_delta, dt_s)
    publish_fps = _safe_fps(published_delta, dt_s)
    write_fps = _safe_fps(written_delta, dt_s)
    emit_fps = _safe_fps(emitted, dt_s)

    ft = float(frame_time_ms) if frame_time_ms > 0.0 else 0.0
    if ft <= 0.0 and capture_fps > 0.0:
        ft = 1000.0 / capture_fps

    eta: Optional[float] = None
    if save_enabled:
        free = max(0, int(science_slots) - int(science_pending))
        net_fill = publish_fps - write_fps
        if net_fill > 1e-6 and free > 0:
            eta = free / net_fill
        elif net_fill > 1e-6 and free == 0:
            eta = 0.0

    return TimingRates(
        capture_fps=capture_fps,
        frame_time_ms=ft,
        science_publish_fps=publish_fps,
        science_write_fps=write_fps,
        emit_fps=emit_fps,
        queue_fill_eta_s=eta,
    )
