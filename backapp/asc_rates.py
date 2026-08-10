"""ASC axis timing / sidereal calibration (hardware STEP edges).

Empirical lock-in (2026-08-09, Pico + TMC2209, MS pins unwired):
  UI: -15.15 STEP/s  →  dir=1, step_us=66007
  Fine-tuned after initial -16 / 62500 was slightly fast.

TMC2209 standalone default with MS1/MS2 open (internal pull-downs):
  1/8 microstep on the STEP input (MicroPlyer still interpolates internally
  to 256 for the sine table; host STEP edges remain 1/8 of a full step).

Do not change software microstepping until UART/MS wiring exists — these
numbers are at the current hardware STEP resolution.
"""

from __future__ import annotations

# --- hardware ---
# TMC2209 datasheet: MS2=GND, MS1=GND → 8 microsteps (pins open = pull-down).
ASC_HW_MICROSTEPS = 8

# --- empirical sidereal lock (STEP edges at ASC_HW_MICROSTEPS) ---
ASC_SIDEREAL_UI_SPEED = -15.15  # signed steps/sec as sent by ctlparams ASC
ASC_SIDEREAL_STEPS_PER_SEC = 15.15  # abs(ASC_SIDEREAL_UI_SPEED)
ASC_SIDEREAL_STEP_US = 66_007  # round(1e6 / 15.15)
ASC_SIDEREAL_DIR = 1  # Pico DIR for the negative UI speed (DIR_INVERT_ASC=False)

# Mean sidereal day (seconds); 360° of RA / this = sky rate on ASC.
SIDEREAL_DAY_S = 86164.0905
SKY_DEG_PER_SEC = 360.0 / SIDEREAL_DAY_S  # ≈ 0.004178 °/s ≈ 15.041 ″/s

# Open-loop degrees from STEP count at this hardware resolution:
#   steps_per_deg = sidereal_steps_per_sec / sky_deg_per_sec
ASC_STEPS_PER_DEGREE = ASC_SIDEREAL_STEPS_PER_SEC / SKY_DEG_PER_SEC
# ≈ 3626.1 STEP edges per degree of mount ASC

# Full-step equivalents (for docs / cross-checks only):
ASC_FULLSTEPS_PER_SEC_SIDEREAL = ASC_SIDEREAL_STEPS_PER_SEC / ASC_HW_MICROSTEPS
ASC_FULLSTEPS_PER_DEGREE = ASC_STEPS_PER_DEGREE / ASC_HW_MICROSTEPS


def sidereal_speed_cmd() -> float:
    """ctlparams ASC value that commands empirical sidereal tracking."""
    return ASC_SIDEREAL_UI_SPEED


def steps_to_degrees(steps: float) -> float:
    return float(steps) / ASC_STEPS_PER_DEGREE


def degrees_to_steps(deg: float) -> float:
    return float(deg) * ASC_STEPS_PER_DEGREE
