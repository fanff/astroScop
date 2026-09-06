"""Unit tests for guide geometry (no camera)."""

import math

import pytest

from guide_geom import (
    ASC_ARCSEC_PER_STEP,
    COS_FLOOR,
    DEC_ARCSEC_PER_STEP,
    DEC_FREEZE_DEG,
    axis_steps_to_pixels,
    bin_factor_for_preset,
    pixels_to_axis_steps,
    plate_scale_arcsec_per_px,
    rotate_pixel_error,
)

_GEOM = dict(f_mm=400.0, bin=1, theta_deg=0.0, flip_asc=False, flip_dec=False)


def test_plate_scale_bin_and_focal():
    s1 = plate_scale_arcsec_per_px(400.0, 1)
    s2 = plate_scale_arcsec_per_px(400.0, 2)
    s800 = plate_scale_arcsec_per_px(800.0, 1)
    assert abs(s2 / s1 - 2.0) < 1e-12
    assert abs(s800 / s1 - 0.5) < 1e-12
    expected = 206.265 * 1.55 / 400.0
    assert abs(s1 - expected) < 1e-12


def test_bin_factor_for_preset():
    assert bin_factor_for_preset("full") == 1
    assert bin_factor_for_preset("full_2160") == 1
    assert bin_factor_for_preset("bin2x2") == 2
    assert bin_factor_for_preset("bin2x2_1080") == 2
    assert bin_factor_for_preset("bin2x2_crop") == 2
    with pytest.raises(ValueError):
        bin_factor_for_preset("nope")


def test_same_sky_error_asc_grows_as_1_over_cos_dec_flat():
    # 1 px along ASC+ on the chip, no rotation.
    refs = {}
    for dec in (0.0, 45.0, 80.0, 89.0):
        refs[dec] = pixels_to_axis_steps(1.0, 0.0, dec_deg=dec, **_GEOM)
        dec_only = pixels_to_axis_steps(0.0, 1.0, dec_deg=dec, **_GEOM)
        assert abs(dec_only.e_asc_steps) < 1e-12

    r0 = refs[0.0]
    assert abs(r0.cos_eff - 1.0) < 1e-12
    assert r0.pole_gate is False
    assert abs(r0.e_asc_px - 1.0) < 1e-12
    assert abs(r0.e_dec_px) < 1e-12

    for dec in (45.0, 80.0, 89.0):
        r = refs[dec]
        assert abs(r.e_asc_arcsec - r0.e_asc_arcsec) < 1e-12
        # Same on-sky ASC angle needs more mount steps as |cos δ| shrinks.
        expected_ratio = 1.0 / r.cos_eff
        assert abs(r.e_asc_steps / r0.e_asc_steps - expected_ratio) < 1e-9

    d0 = pixels_to_axis_steps(0.0, 1.0, dec_deg=0.0, **_GEOM)
    for dec in (45.0, 80.0, 89.0):
        d = pixels_to_axis_steps(0.0, 1.0, dec_deg=dec, **_GEOM)
        assert abs(d.e_dec_steps - d0.e_dec_steps) < 1e-12
        assert abs(d.e_dec_arcsec - d0.e_dec_arcsec) < 1e-12

    assert refs[80.0].pole_gate is False
    assert abs(refs[80.0].cos_eff - COS_FLOOR) < 1e-12
    assert refs[89.0].pole_gate is True
    assert abs(refs[89.0].cos_eff - COS_FLOOR) < 1e-12
    assert math.isfinite(refs[89.0].e_asc_steps)
    assert abs(DEC_FREEZE_DEG - 80.0) < 1e-12


def test_dec_steps_use_named_scale():
    r = pixels_to_axis_steps(0.0, 1.0, dec_deg=0.0, **_GEOM)
    s = plate_scale_arcsec_per_px(400.0, 1)
    assert abs(r.e_dec_arcsec - s) < 1e-12
    assert abs(r.e_dec_steps - s / DEC_ARCSEC_PER_STEP) < 1e-12
    assert abs(ASC_ARCSEC_PER_STEP - DEC_ARCSEC_PER_STEP) < 1e-12


def test_flips_reverse_matching_axis_only():
    base = pixels_to_axis_steps(0.4, -0.2, dec_deg=20.0, **_GEOM)
    fa = pixels_to_axis_steps(
        0.4, -0.2, f_mm=400.0, bin=1, dec_deg=20.0, flip_asc=True, flip_dec=False
    )
    fd = pixels_to_axis_steps(
        0.4, -0.2, f_mm=400.0, bin=1, dec_deg=20.0, flip_asc=False, flip_dec=True
    )
    assert abs(fa.e_asc_px + base.e_asc_px) < 1e-12
    assert abs(fa.e_dec_px - base.e_dec_px) < 1e-12
    assert abs(fd.e_dec_px + base.e_dec_px) < 1e-12
    assert abs(fd.e_asc_px - base.e_asc_px) < 1e-12


def test_theta_90_maps_u_to_minus_dec():
    # θ = 90°: ASC+ along +v, DEC+ along −u
    e_asc, e_dec = rotate_pixel_error(1.0, 0.0, theta_deg=90.0)
    assert abs(e_asc) < 1e-12
    assert abs(e_dec - (-1.0)) < 1e-12
    e_asc, e_dec = rotate_pixel_error(0.0, 1.0, theta_deg=90.0)
    assert abs(e_asc - 1.0) < 1e-12
    assert abs(e_dec) < 1e-12


def test_roundtrip_equator():
    e_u, e_v = 1.25, -0.4
    kw = dict(f_mm=400.0, bin=2, dec_deg=0.0, theta_deg=35.0, flip_asc=True, flip_dec=False)
    err = pixels_to_axis_steps(e_u, e_v, **kw)
    back = axis_steps_to_pixels(err.e_asc_steps, err.e_dec_steps, **kw)
    assert abs(back[0] - e_u) < 1e-9
    assert abs(back[1] - e_v) < 1e-9


def test_roundtrip_high_dec_uses_cos_floor():
    e_u, e_v = 0.5, 0.25
    kw = dict(f_mm=500.0, bin=1, dec_deg=89.0, theta_deg=0.0)
    err = pixels_to_axis_steps(e_u, e_v, **kw)
    back = axis_steps_to_pixels(err.e_asc_steps, err.e_dec_steps, **kw)
    assert abs(back[0] - e_u) < 1e-9
    assert abs(back[1] - e_v) < 1e-9
    assert err.pole_gate is True


def test_invalid_f_mm_and_bin():
    with pytest.raises(ValueError):
        plate_scale_arcsec_per_px(0.0, 1)
    with pytest.raises(ValueError):
        plate_scale_arcsec_per_px(-400.0, 1)
    with pytest.raises(ValueError):
        pixels_to_axis_steps(0.0, 0.0, f_mm=0.0, bin=1, dec_deg=0.0)
    with pytest.raises(ValueError):
        plate_scale_arcsec_per_px(400.0, 3)
    with pytest.raises(ValueError):
        plate_scale_arcsec_per_px(400.0, 0)
