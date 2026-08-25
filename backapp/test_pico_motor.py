"""Unit tests for pico_motor speed mapping and status parsing (no hardware)."""

from pico_motor import (
    PicoNotFoundError,
    parse_dual_status,
    parse_status_fields,
    resolve_pico_port,
    resolve_pico_port_required,
    speed_to_dir_step_us,
)


def test_speed_zero_means_stop():
    dir_bit, step_us = speed_to_dir_step_us(0)
    assert step_us is None


def test_speed_500_is_2000us():
    dir_bit, step_us = speed_to_dir_step_us(500)
    assert dir_bit == 0
    assert step_us == 2000


def test_negative_speed_flips_dir():
    dir_bit, step_us = speed_to_dir_step_us(-500)
    assert dir_bit == 1
    assert step_us == 2000


def test_clamp_min_step_us():
    _, step_us = speed_to_dir_step_us(1_000_000)
    assert step_us == 50


def test_invert_flag():
    dir_bit, _ = speed_to_dir_step_us(500, invert=True)
    assert dir_bit == 1


def test_parse_status():
    fields = parse_status_fields("ok motor=asc en=1 dir=0 step_us=2000")
    assert fields["motor"] == "asc"
    assert fields["en"] == 1
    assert fields["dir"] == 0
    assert fields["step_us"] == 2000


def test_parse_dual_status():
    axes = parse_dual_status(
        "ok asc en=1 dir=0 step_us=2000 dec en=0 dir=1 step_us=0"
    )
    assert axes["asc"] == {"en": 1, "dir": 0, "step_us": 2000}
    assert axes["dec"] == {"en": 0, "dir": 1, "step_us": 0}


def test_parse_dual_from_motor_reply():
    axes = parse_dual_status("ok motor=dec en=1 dir=1 step_us=3000")
    assert axes["dec"] == {"en": 1, "dir": 1, "step_us": 3000}


def test_resolve_preferred_port():
    assert resolve_pico_port_required("COM9") == "COM9"
    assert resolve_pico_port("COM9") == "COM9"


def test_resolve_required_raises_without_pico(monkeypatch):
    monkeypatch.setattr("pico_motor.find_pico_ports", lambda: [])
    try:
        resolve_pico_port_required(None)
        assert False, "expected PicoNotFoundError"
    except PicoNotFoundError as e:
        assert "2e8a" in str(e).lower() or "pico" in str(e).lower()


def test_resolve_fallback_still_returns_default(monkeypatch):
    monkeypatch.setattr("pico_motor.find_pico_ports", lambda: [])
    port = resolve_pico_port(None)
    assert port in ("COM5", "/dev/ttyACM0")

