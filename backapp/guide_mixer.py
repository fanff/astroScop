"""ASC/DEC rate mixer: commanded = feedforward + guide trim.

Used by the motor worker. No serial, no pixels. Guide disabled (or zero
trims) is identical to today's absolute ASC/DEC setpoints.
"""

from __future__ import annotations

from typing import Optional

# Evolution §5.2 starting limits were ±2 / ±1 STEP/s for a long-FL
# guide. At 18 mm, 1 px is already ~18 STEP of sky error, and the
# operator's sidereal offset is several STEP/s — allow a real rate fix.
TRIM_ASC_MAX = 8.0
TRIM_DEC_MAX = 8.0
MIN_DELTA_STEP_S = 0.02
TRIM_TIMEOUT_S = 5.0


def clamp(v: float, lo: float, hi: float) -> float:
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def needs_write(prev: Optional[float], new: float, min_delta: float = MIN_DELTA_STEP_S) -> bool:
    """Skip Pico writes that cannot change integer step_us in a useful way.

    ``prev is None`` means this axis has not been written since link-up.
    Do not poke a still-idle axis with commanded 0 (keeps today's ASC-only
    writes from also sending DEC stop).
    """
    if prev is None:
        return float(new) != 0.0
    if new == 0.0 and prev != 0.0:
        return True
    if prev == 0.0 and new != 0.0:
        return True
    return abs(float(new) - float(prev)) >= float(min_delta)


class RateMixer:
    def __init__(
        self,
        *,
        trim_asc_max: float = TRIM_ASC_MAX,
        trim_dec_max: float = TRIM_DEC_MAX,
        min_delta: float = MIN_DELTA_STEP_S,
        trim_timeout_s: float = TRIM_TIMEOUT_S,
    ) -> None:
        self.trim_asc_max = float(trim_asc_max)
        self.trim_dec_max = float(trim_dec_max)
        self.min_delta = float(min_delta)
        self.trim_timeout_s = float(trim_timeout_s)
        self.enabled = False
        self.ff_asc = 0.0
        self.ff_dec = 0.0
        self.d_asc = 0.0
        self.d_dec = 0.0
        self.last_trim_mono: Optional[float] = None

    def commanded_asc(self) -> float:
        if not self.enabled:
            return self.ff_asc
        return self.ff_asc + self.d_asc

    def commanded_dec(self) -> float:
        if not self.enabled:
            return self.ff_dec
        return self.ff_dec + self.d_dec

    def snapshot(self) -> dict:
        d_asc = float(self.d_asc) if self.enabled else 0.0
        d_dec = float(self.d_dec) if self.enabled else 0.0
        ff_asc = float(self.ff_asc)
        ff_dec = float(self.ff_dec)
        cmd_asc = self.commanded_asc()
        cmd_dec = self.commanded_dec()
        return {
            "guideEnabled": bool(self.enabled),
            "dAsc": d_asc,
            "dDec": d_dec,
            "ffAsc": ff_asc,
            "ffDec": ff_dec,
            "cmdAsc": float(cmd_asc),
            "cmdDec": float(cmd_dec),
        }

    def set_ff_asc(self, v: float) -> None:
        speed = float(v)
        self.ff_asc = speed
        if speed == 0.0:
            self.d_asc = 0.0

    def set_ff_dec(self, v: float) -> None:
        speed = float(v)
        self.ff_dec = speed
        if speed == 0.0:
            self.d_dec = 0.0

    def set_trim_asc(self, v: float, now: float) -> bool:
        if not self.enabled:
            return False
        self.d_asc = clamp(float(v), -self.trim_asc_max, self.trim_asc_max)
        self.last_trim_mono = float(now)
        return True

    def set_trim_dec(self, v: float, now: float) -> bool:
        if not self.enabled:
            return False
        self.d_dec = clamp(float(v), -self.trim_dec_max, self.trim_dec_max)
        self.last_trim_mono = float(now)
        return True

    def enable(self) -> None:
        self.enabled = True

    def disable(self) -> None:
        self.enabled = False
        self.clear_trims()

    def clear_trims(self) -> None:
        self.d_asc = 0.0
        self.d_dec = 0.0
        self.last_trim_mono = None

    def clear_asc_trim(self) -> None:
        self.d_asc = 0.0

    def clear_dec_trim(self) -> None:
        self.d_dec = 0.0

    def expire(self, now: float) -> bool:
        """Zero trims after silence; True if a Pico rewrite may be needed."""
        if not self.enabled or self.last_trim_mono is None:
            return False
        if float(now) - self.last_trim_mono < self.trim_timeout_s:
            return False
        if self.d_asc == 0.0 and self.d_dec == 0.0:
            self.last_trim_mono = None
            return False
        self.d_asc = 0.0
        self.d_dec = 0.0
        self.last_trim_mono = None
        return True
