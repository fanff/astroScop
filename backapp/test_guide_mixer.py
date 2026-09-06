"""Unit tests for the ASC/DEC guide rate mixer (no hardware)."""

from guide_mixer import (
    MIN_DELTA_STEP_S,
    TRIM_ASC_MAX,
    TRIM_DEC_MAX,
    TRIM_TIMEOUT_S,
    RateMixer,
    needs_write,
)
from ws_messages import (
    CTL_GUIDE_DASC,
    CTL_GUIDE_DISABLE,
    CTL_GUIDE_ENABLE,
    GuideSample,
    MotorInfoGuideFields,
)


def test_disabled_ignores_trim_state():
    m = RateMixer()
    m.d_asc = 9.0
    m.d_dec = 9.0
    m.ff_asc = -15.15
    m.ff_dec = 0.1
    assert m.commanded_asc() == -15.15
    assert m.commanded_dec() == 0.1
    snap = m.snapshot()
    assert snap["guideEnabled"] is False
    assert snap["dAsc"] == 0.0
    assert snap["ffAsc"] == -15.15
    assert snap["cmdAsc"] == -15.15


def test_enabled_snapshot_cmd_includes_trim():
    m = RateMixer()
    m.enable()
    m.set_ff_asc(-13.15)
    m.set_trim_asc(-2.0, now=1.0)
    snap = m.snapshot()
    assert snap["guideEnabled"] is True
    assert abs(snap["dAsc"] + 2.0) < 1e-12
    assert abs(snap["cmdAsc"] + 15.15) < 1e-12


def test_enabled_sums_ff_and_trim():
    m = RateMixer()
    m.enable()
    m.set_ff_asc(-15.15)
    m.set_ff_dec(0.0)
    assert m.set_trim_asc(0.3, now=1.0)
    assert m.set_trim_dec(-0.05, now=1.0)
    assert abs(m.commanded_asc() - (-14.85)) < 1e-12
    assert abs(m.commanded_dec() - (-0.05)) < 1e-12


def test_trim_clamp():
    m = RateMixer()
    m.enable()
    m.set_trim_asc(99.0, now=1.0)
    m.set_trim_dec(-99.0, now=1.0)
    assert m.d_asc == TRIM_ASC_MAX
    assert m.d_dec == -TRIM_DEC_MAX


def test_trim_ignored_when_disabled():
    m = RateMixer()
    assert m.set_trim_asc(0.5, now=1.0) is False
    assert m.d_asc == 0.0
    assert m.commanded_asc() == 0.0


def test_zero_ff_clears_that_axis_trim():
    m = RateMixer()
    m.enable()
    m.set_ff_asc(-15.15)
    m.set_trim_asc(0.4, now=1.0)
    m.set_ff_dec(0.2)
    m.set_trim_dec(0.1, now=1.0)
    m.set_ff_asc(0.0)
    assert m.d_asc == 0.0
    assert m.d_dec == 0.1
    assert m.commanded_asc() == 0.0
    assert abs(m.commanded_dec() - 0.3) < 1e-12


def test_disable_zeros_trim_keeps_ff():
    m = RateMixer()
    m.enable()
    m.set_ff_asc(-15.15)
    m.set_trim_asc(0.5, now=1.0)
    m.disable()
    assert m.enabled is False
    assert m.d_asc == 0.0
    assert m.commanded_asc() == -15.15


def test_expire_after_timeout():
    m = RateMixer()
    m.enable()
    m.set_ff_asc(-15.0)
    m.set_trim_asc(0.5, now=10.0)
    assert m.expire(10.0 + TRIM_TIMEOUT_S - 0.01) is False
    assert m.d_asc == 0.5
    assert m.expire(10.0 + TRIM_TIMEOUT_S) is True
    assert m.d_asc == 0.0
    assert m.commanded_asc() == -15.0
    assert m.expire(20.0 + TRIM_TIMEOUT_S) is False


def test_needs_write_min_delta():
    assert needs_write(None, 0.0) is False
    assert needs_write(None, -15.15) is True
    assert needs_write(-15.15, -15.15) is False
    assert needs_write(-15.15, -15.15 + MIN_DELTA_STEP_S / 2) is False
    assert needs_write(-15.15, -15.15 + MIN_DELTA_STEP_S + 1e-9) is True
    assert needs_write(-15.15, 0.0) is True
    assert needs_write(0.0, -15.15) is True


def test_wire_names_and_models():
    assert CTL_GUIDE_ENABLE == "GUIDE_ENABLE"
    assert CTL_GUIDE_DISABLE == "GUIDE_DISABLE"
    assert CTL_GUIDE_DASC == "GUIDE_DASC"
    sample = GuideSample(ok=True, u=1.5, dAsc=-0.07)
    assert sample.msgtype == "guideSample"
    fields = MotorInfoGuideFields(guideEnabled=True, ffAsc=-15.15)
    assert fields.dAsc == 0.0
    assert fields.ffAsc == -15.15
