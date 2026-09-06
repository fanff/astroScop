"""GuideEngine tests on synthetic tiles."""

import numpy as np

from guide_handoff import GuideTile
from guide_isolate import synthetic_star_rgb
from guide_pid import DEADBAND_PX, KD
from guide_process import GuideConfig, GuideEngine, config_from_settings


def _tile(u, v, *, size=64, t=0.0, peak=90.0, rng=None):
    rgb = synthetic_star_rgb(size, size, u, v, sigma=2.8, peak=peak, rng=rng)
    return GuideTile(
        rgb=rgb,
        origin_u=0,
        origin_v=0,
        lock_u=size / 2.0,
        lock_v=size / 2.0,
        t=t,
    )


def test_engine_reset_clears_pid():
    eng = GuideEngine(GuideConfig(f_mm=400.0, bin=2))
    rng = np.random.default_rng(3)
    eng.process_tile(_tile(36.0, 32.0, t=1.0, rng=rng), seq=1)
    eng.reset()
    assert eng.pid.asc.i == 0.0
    assert eng.pid.dec.i == 0.0
    assert eng.last_t is None
    assert eng.stack.count == 0


def test_kd_stays_zero_on_engine():
    assert KD == 0.0
    GuideEngine()


def test_18mm_few_px_does_not_rail():
    eng = GuideEngine(GuideConfig(f_mm=18.0, bin=2, stack_n=1, dec_deg=0.0))
    r = eng.process_tile(_tile(38.0, 32.0, t=1.0, peak=120.0, rng=None), seq=1)
    assert r.sample.ok
    assert abs(r.sample.dAsc) < 7.0
    assert abs(r.sample.e_asc_px) > 1.0


def test_ok_star_near_lock():
    eng = GuideEngine(GuideConfig(f_mm=400.0, bin=2, dec_deg=0.0))
    rng = np.random.default_rng(1)
    r = eng.process_tile(_tile(32.2, 31.8, t=1.0, rng=rng), seq=1)
    assert r.skipped is False
    assert r.sample.ok
    assert r.sample.dAsc == r.sample.dAsc  # finite
    assert abs(KD) == 0.0


def test_invalid_focal_does_not_arm():
    eng = GuideEngine(GuideConfig(f_mm=0.0))
    r = eng.process_tile(_tile(32.0, 32.0, t=1.0), seq=1)
    assert r.sample.ok is False
    assert r.sample.focal_mm == 0.0
    assert r.sample.reason == "no_focal"


def test_pole_gate_zeros_asc_trim():
    eng = GuideEngine(GuideConfig(f_mm=400.0, bin=1, dec_deg=89.0))
    # Offset star along +u (ASC at θ=0) so ASC error is real.
    r = eng.process_tile(_tile(36.0, 32.0, t=1.0, peak=120.0, rng=None), seq=1)
    assert r.sample.ok
    assert r.sample.dAsc == 0.0


def test_deadband_quiet_on_tiny_error():
    eng = GuideEngine(GuideConfig(f_mm=400.0, bin=2))
    lock = 32.0
    r = eng.process_tile(_tile(lock, lock, t=1.0, peak=120.0, rng=None), seq=1)
    assert r.sample.ok
    # After EMA, residual should be inside deadband for a centered PSF.
    assert abs(r.sample.u - lock) <= DEADBAND_PX + 0.4


def test_same_seq_skipped():
    eng = GuideEngine()
    t = _tile(32.0, 32.0, t=1.0)
    a = eng.process_tile(t, seq=3)
    b = eng.process_tile(t, seq=3)
    assert a.skipped is False
    assert b.skipped is True


def test_lost_star_holds_then_drops():
    eng = GuideEngine(GuideConfig(f_mm=400.0, bin=2, stack_n=1))
    rng = np.random.default_rng(2)
    r0 = eng.process_tile(_tile(34.0, 32.0, t=0.0, rng=rng), seq=1)
    assert r0.sample.ok
    last = None
    for i in range(8):
        dark = np.zeros((64, 64, 3), dtype=np.uint8)
        tile = GuideTile(dark, 0, 0, 32.0, 32.0, t=0.2 * (i + 1))
        r = eng.process_tile(tile, seq=2 + i)
        assert r.sample.ok is False
        last = r.sample
        if i < 7:
            assert abs(last.dAsc - r0.sample.dAsc) < 1e-12
    # Still within 5 s after first miss — hold
    assert last is not None
    assert abs(last.dAsc - r0.sample.dAsc) < 1e-12
    dark = np.zeros((64, 64, 3), dtype=np.uint8)
    r_drop = eng.process_tile(GuideTile(dark, 0, 0, 32.0, 32.0, t=6.0), seq=20)
    assert r_drop.sample.dAsc == 0.0
    assert r_drop.sample.dDec == 0.0


def test_config_from_settings():
    cfg = config_from_settings(
        {
            "sensor_preset": "full",
            "guide_focal_mm": 500,
            "guide_dec_deg": -12.5,
            "track_theta_deg": 90,
            "track_flip_asc": True,
            "track_flip_dec": False,
            "guide_show_crop": True,
            "guide_stack_n": 8,
            "guide_kp": 0.1,
            "guide_ki": 0.005,
        }
    )
    assert cfg.preset == "full"
    assert cfg.f_mm == 500.0
    assert cfg.dec_deg == -12.5
    assert cfg.theta_deg == 90.0
    assert cfg.flip_asc is True
    assert cfg.flip_dec is False
    assert cfg.show_crop is True
    assert cfg.stack_n == 8
    assert abs(cfg.kp - 0.1) < 1e-12
    assert abs(cfg.ki - 0.005) < 1e-12
    assert cfg.resolved_bin() == 1


def test_apply_config_rebuilds_stack():
    eng = GuideEngine(GuideConfig(stack_n=5))
    eng.stack.push(np.zeros((8, 8, 3), dtype=np.uint8))
    assert eng.stack.count == 1
    eng.apply_config(GuideConfig(stack_n=3))
    assert eng.cfg.stack_n == 3
    assert eng.stack.count == 0
    assert eng.stack.n == 3


def test_apply_config_sets_gains_without_resetting_i():
    eng = GuideEngine(GuideConfig(kp=0.25, ki=0.02))
    eng.pid.asc.i = 1.5
    eng.pid.dec.last_out = 0.4
    eng.apply_config(GuideConfig(kp=0.08, ki=0.005, stack_n=5))
    assert abs(eng.pid.asc.kp - 0.08) < 1e-12
    assert abs(eng.pid.dec.ki - 0.005) < 1e-12
    assert abs(eng.pid.asc.i - 1.5) < 1e-12
    assert abs(eng.pid.dec.last_out - 0.4) < 1e-12
