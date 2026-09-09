"""PI unit tests (no camera)."""

from guide_mixer import TRIM_ASC_MAX
from guide_pid import KD, KP, LOST_DROP_S, LOST_HOLD_N, AxisPI, GuidePI


def test_set_gains_clamps():
    g = GuidePI()
    g.set_gains(-1.0, 9.0)
    assert g.asc.kp == 0.0
    assert g.asc.ki == 0.5
    assert g.dec.kp == 0.0
    assert g.dec.ki == 0.5


def test_p_on_pixel_offset():
    ax = AxisPI()
    out = ax.update(1.0, 0.2)
    assert abs(out - KP) < 0.02  # Kp plus small I
    assert ax.i != 0.0


def test_i_eats_constant_bias():
    ax = AxisPI()
    outs = [ax.update(1.0, 0.2) for _ in range(40)]
    assert outs[-1] > outs[0]
    assert outs[-1] <= TRIM_ASC_MAX + 1e-12


def test_modest_pixel_error_does_not_saturate():
    ax = AxisPI()
    out = ax.update(6.5, 0.2)
    assert abs(out - KP * 6.5) < 0.1
    assert abs(out) < TRIM_ASC_MAX - 1.0


def test_deadband_holds_last_trim():
    ax = AxisPI()
    held = ax.update(1.0, 0.2)
    i0 = ax.i
    out = ax.update(1.0, 0.2, in_deadband=True)
    assert out == held
    assert ax.i == i0


def test_anti_windup_on_sat_from_rest():
    ax = AxisPI()
    ax.update(100.0, 0.2)
    assert ax.i == 0.0
    assert ax.last_out == TRIM_ASC_MAX


def test_reversed_error_unwinds_i_while_sat():
    ax = AxisPI()
    ax.i = TRIM_ASC_MAX
    ax.last_out = TRIM_ASC_MAX
    ax.update(-2.0, 0.2)
    assert ax.i < TRIM_ASC_MAX


def test_pole_gate_zeros_asc_only():
    g = GuidePI()
    d_asc, d_dec = g.update(2.0, 1.0, 0.2, pole_gate=True)
    assert d_asc == 0.0
    assert d_dec != 0.0
    assert g.asc.freeze_i is True


def test_lost_star_hold_then_drop():
    g = GuidePI()
    g.asc.last_out = 0.4
    g.dec.last_out = 0.1
    held = []
    for i in range(LOST_HOLD_N):
        a, d = g.note_miss(0.2 * i)
        held.append((a, d))
        assert a == 0.4 and d == 0.1
    a, d = g.note_miss(LOST_DROP_S)
    assert a == 0.0 and d == 0.0
    assert g.asc.freeze_i is True
