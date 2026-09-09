"""PI rate trims on axis-pixel error. Kd stays 0 (evolution §5).

Error is e_asc_px / e_dec_px (not e_*_steps). At 18 mm, a few pixels of
lock error must not rail the mixer.
"""

from __future__ import annotations

from dataclasses import dataclass

from guide_mixer import TRIM_ASC_MAX, TRIM_DEC_MAX, clamp

# STEP/s per axis pixel. Sky traces at 0.25 / 0.02 hunted (ζ≈0.15, I-dominated).
# Plant G≈0.028 px/s per STEP/s at 18 mm bin2 → this pair is ζ≈0.75, Tn≈7 min.
# ~6 px → ~4.8 STEP/s P, still under the ±8 mixer rail.
KP = 0.80
KI = 0.008
KP_MIN, KP_MAX = 0.0, 4.0
KI_MIN, KI_MAX = 0.0, 0.5
KD = 0.0
DT_MIN = 0.05
DT_MAX = 1.0
LOST_HOLD_N = 8
LOST_DROP_S = 5.0
DEADBAND_PX = 0.5


def clamp_dt(dt: float) -> float:
    return clamp(float(dt), DT_MIN, DT_MAX)


def clamp_kp(v) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        x = KP
    if x != x:  # NaN
        x = KP
    return clamp(x, KP_MIN, KP_MAX)


def clamp_ki(v) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        x = KI
    if x != x:
        x = KI
    return clamp(x, KI_MIN, KI_MAX)


@dataclass
class AxisPI:
    kp: float = KP
    ki: float = KI
    out_max: float = TRIM_ASC_MAX
    i: float = 0.0
    last_out: float = 0.0
    freeze_i: bool = False

    def reset(self) -> None:
        self.i = 0.0
        self.last_out = 0.0
        self.freeze_i = False

    def update(
        self,
        e_px: float,
        dt: float,
        *,
        in_deadband: bool = False,
        force_zero: bool = False,
    ) -> float:
        if force_zero:
            self.freeze_i = True
            self.last_out = 0.0
            return 0.0
        e = float(e_px)
        if in_deadband:
            return self.last_out
        p = self.kp * e
        raw = p + self.i
        sat = clamp(raw, -self.out_max, self.out_max)
        unsaturated = abs(raw) <= self.out_max + 1e-15
        would_unwind = (self.i * e) < 0.0
        if not self.freeze_i and (unsaturated or would_unwind):
            self.i = clamp(
                self.i + self.ki * e * float(dt),
                -self.out_max,
                self.out_max,
            )
            sat = clamp(p + self.i, -self.out_max, self.out_max)
        self.last_out = sat
        return sat


class GuidePI:
    def __init__(self) -> None:
        self.asc = AxisPI(out_max=TRIM_ASC_MAX)
        self.dec = AxisPI(out_max=TRIM_DEC_MAX)
        self.misses = 0
        self.lost_since: float | None = None
        self.holding = False

    def reset(self) -> None:
        self.asc.reset()
        self.dec.reset()
        self.misses = 0
        self.lost_since = None
        self.holding = False

    def set_gains(self, kp: float, ki: float) -> None:
        """Live retune. Leaves I and last_out alone so hunting can be damped in place."""
        self.asc.kp = self.dec.kp = clamp_kp(kp)
        self.asc.ki = self.dec.ki = clamp_ki(ki)

    def note_ok(self) -> None:
        self.misses = 0
        self.lost_since = None
        self.holding = False
        self.asc.freeze_i = False
        self.dec.freeze_i = False

    def note_miss(self, now: float) -> tuple[float, float]:
        """Hold last trim, then drop after N misses and T seconds."""
        if self.lost_since is None:
            self.lost_since = float(now)
        self.misses += 1
        self.asc.freeze_i = True
        self.dec.freeze_i = True
        dropped = self.misses >= LOST_HOLD_N and (
            float(now) - self.lost_since >= LOST_DROP_S
        )
        if dropped:
            self.asc.last_out = 0.0
            self.dec.last_out = 0.0
            self.holding = False
            return 0.0, 0.0
        self.holding = True
        return self.asc.last_out, self.dec.last_out

    def update(
        self,
        e_asc_px: float,
        e_dec_px: float,
        dt: float,
        *,
        pole_gate: bool = False,
        in_deadband: bool = False,
    ) -> tuple[float, float]:
        dt = clamp_dt(dt)
        d_asc = self.asc.update(
            e_asc_px,
            dt,
            in_deadband=in_deadband,
            force_zero=pole_gate,
        )
        d_dec = self.dec.update(
            e_dec_px,
            dt,
            in_deadband=in_deadband,
            force_zero=False,
        )
        return d_asc, d_dec
