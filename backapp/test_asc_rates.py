"""Tests for ASC sidereal calibration constants."""

from asc_rates import (
    ASC_FULLSTEPS_PER_SEC_SIDEREAL,
    ASC_HW_MICROSTEPS,
    ASC_SIDEREAL_STEP_US,
    ASC_SIDEREAL_STEPS_PER_SEC,
    ASC_SIDEREAL_UI_SPEED,
    ASC_STEPS_PER_DEGREE,
    SKY_DEG_PER_SEC,
    sidereal_speed_cmd,
)
from pico_motor import speed_to_dir_step_us


def test_hw_default_is_eighth():
    assert ASC_HW_MICROSTEPS == 8


def test_sidereal_ui_maps_to_66007us():
    assert ASC_SIDEREAL_UI_SPEED == -15.15
    assert ASC_SIDEREAL_STEPS_PER_SEC == 15.15
    assert ASC_SIDEREAL_STEP_US == 66_007
    dir_bit, step_us = speed_to_dir_step_us(ASC_SIDEREAL_UI_SPEED)
    assert dir_bit == 1
    assert step_us == 66_007


def test_steps_per_degree_from_sky_rate():
    expected = ASC_SIDEREAL_STEPS_PER_SEC / SKY_DEG_PER_SEC
    assert abs(ASC_STEPS_PER_DEGREE - expected) < 1e-9
    # ~3626 STEP edges / degree at 1/8
    assert 3610 < ASC_STEPS_PER_DEGREE < 3640


def test_fullstep_sidereal_rate():
    assert abs(ASC_FULLSTEPS_PER_SEC_SIDEREAL - (15.15 / 8)) < 1e-12


def test_sidereal_cmd_helper():
    assert sidereal_speed_cmd() == -15.15
