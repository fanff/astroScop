"""Pico 2 W — ASC + DEC stepper controller over USB serial.

Receives sparse text commands from the Raspberry Pi; generates STEP pulses
locally. Rate setpoints ease over ~100 ms (signed rate) so period changes do
not inject ghost steps. No TMC UART yet (standalone STEP/DIR).
See README.md in this folder for the host protocol.
"""

from machine import Pin
import sys
import time
import uselect

# Motor 1 = ASC (ascension)
PIN_ASC_DIR = 10
PIN_ASC_STEP = 11
PIN_ASC_EN = 12

# Motor 2 = DEC
PIN_DEC_DIR = 18
PIN_DEC_STEP = 19
PIN_DEC_EN = 20

# STEP pulse high time (us). Period between steps comes from current rate.
PULSE_HIGH_US = 4
MIN_STEP_US = 50
MAX_STEP_US = 10_000_000
RAMP_MS = 100
RATE_EPS = 0.5  # below this |rate|, treat as stopped

led = Pin("LED", Pin.OUT)

poll = uselect.poll()
poll.register(sys.stdin, uselect.POLLIN)
_rx = ""


def _clamp_step_us(period_us):
    period_us = int(period_us)
    if period_us <= 0:
        return 0
    if period_us < MIN_STEP_US:
        return MIN_STEP_US
    if period_us > MAX_STEP_US:
        return MAX_STEP_US
    return period_us


def _period_to_rate(dir_bit, step_us):
    """Signed steps/s from commanded dir + period. 0 period → 0 rate."""
    step_us = _clamp_step_us(step_us)
    if step_us <= 0:
        return 0.0
    rate = 1_000_000.0 / float(step_us)
    return rate if int(dir_bit) == 0 else -rate


class Motor:
    def __init__(self, name, pin_dir, pin_step, pin_en):
        self.name = name
        self.dir_pin = Pin(pin_dir, Pin.OUT, value=0)
        self.step_pin = Pin(pin_step, Pin.OUT, value=0)
        self.en_pin = Pin(pin_en, Pin.OUT, value=1)  # ENN high = disabled
        self.enabled = False
        self.cmd_dir = 0
        self.cmd_step_us = 0
        self.target_rate = 0.0
        self.current_rate = 0.0
        self._ramp_from = 0.0
        self._ramp_to = 0.0
        self._ramp_t0_ms = time.ticks_ms()
        self._ramping = False
        self._next_step_us = time.ticks_us()

    def set_enabled(self, on):
        self.enabled = bool(on)
        self.en_pin.value(0 if self.enabled else 1)

    def hard_stop(self):
        """Immediate disable — used by stop / en=0."""
        self.target_rate = 0.0
        self.current_rate = 0.0
        self.cmd_step_us = 0
        self._ramping = False
        self.set_enabled(False)
        self.step_pin.value(0)

    def _start_ramp(self, new_target):
        self._ramp_from = self.current_rate
        self._ramp_to = float(new_target)
        self.target_rate = self._ramp_to
        self._ramp_t0_ms = time.ticks_ms()
        self._ramping = True
        if abs(self._ramp_to) > RATE_EPS and not self.enabled:
            self.set_enabled(True)
            # First motion: schedule first pulse after one period at start rate
            # (or target if starting from zero — use a gentle initial period).
            start_abs = abs(self._ramp_from)
            if start_abs < RATE_EPS:
                start_abs = abs(self._ramp_to)
            period = _clamp_step_us(int(round(1_000_000.0 / start_abs)))
            self._next_step_us = time.ticks_add(time.ticks_us(), period)

    def apply_command(self, args):
        """Apply asc/dec key=value args. Mutates motor state."""
        if "dir" in args:
            self.cmd_dir = 1 if int(args["dir"]) else 0

        force_en = None
        if "en" in args or "enable" in args:
            force_en = args.get("en", args.get("enable"))
            if int(force_en) == 0:
                self.hard_stop()
                return
            self.set_enabled(True)

        period = None
        if "step_us" in args:
            period = _clamp_step_us(args["step_us"])
        elif "step_time" in args:
            period = _clamp_step_us(args["step_time"])

        if period is not None:
            self.cmd_step_us = period
            if period <= 0:
                self._start_ramp(0.0)
            else:
                if force_en is None and not self.enabled:
                    self.set_enabled(True)
                self._start_ramp(_period_to_rate(self.cmd_dir, period))
        elif "dir" in args and self.cmd_step_us > 0 and self.enabled:
            # Direction-only change while moving: retarget signed rate.
            self._start_ramp(_period_to_rate(self.cmd_dir, self.cmd_step_us))

    def update_ramp(self):
        if not self._ramping:
            return
        elapsed = time.ticks_diff(time.ticks_ms(), self._ramp_t0_ms)
        if elapsed >= RAMP_MS:
            self.current_rate = self._ramp_to
            self._ramping = False
            if abs(self.current_rate) < RATE_EPS:
                self.current_rate = 0.0
                self.cmd_step_us = 0
                self.set_enabled(False)
            return
        if elapsed <= 0:
            self.current_rate = self._ramp_from
            return
        t = elapsed / float(RAMP_MS)
        self.current_rate = self._ramp_from + (self._ramp_to - self._ramp_from) * t

    def maybe_step(self):
        self.update_ramp()
        if not self.enabled or abs(self.current_rate) < RATE_EPS:
            return
        period = _clamp_step_us(int(round(1_000_000.0 / abs(self.current_rate))))
        if period <= 0:
            return
        dir_bit = 0 if self.current_rate > 0 else 1
        self.dir_pin.value(dir_bit)

        now = time.ticks_us()
        if time.ticks_diff(now, self._next_step_us) < 0:
            return
        self.step_pin.value(1)
        time.sleep_us(PULSE_HIGH_US)
        self.step_pin.value(0)
        # Advance from previous deadline; do not reset to now (avoids ghost steps).
        self._next_step_us = time.ticks_add(self._next_step_us, period)
        # If badly behind, resync without bursting catch-up pulses.
        if time.ticks_diff(now, self._next_step_us) > period:
            self._next_step_us = now
        led.toggle()

    def status_tokens(self):
        """Tokens for status / command reply (commanded target)."""
        return "motor=%s en=%d dir=%d step_us=%d" % (
            self.name,
            1 if self.enabled else 0,
            self.cmd_dir,
            self.cmd_step_us,
        )


asc = Motor("asc", PIN_ASC_DIR, PIN_ASC_STEP, PIN_ASC_EN)
dec = Motor("dec", PIN_DEC_DIR, PIN_DEC_STEP, PIN_DEC_EN)
MOTORS = {"asc": asc, "dec": dec, "motor": asc}


def reply(msg):
    sys.stdout.write(msg + "\n")


def handle_line(line):
    line = line.strip()
    if not line or line.startswith("#"):
        return False

    parts = line.split()
    cmd = parts[0].lower()
    args = {}
    for token in parts[1:]:
        if "=" not in token:
            reply("err bad_token %s" % token)
            return True
        key, val = token.split("=", 1)
        args[key.lower()] = val

    if cmd == "ping":
        reply("ok pong")
        return True

    if cmd == "status":
        reply(
            "ok asc en=%d dir=%d step_us=%d dec en=%d dir=%d step_us=%d"
            % (
                1 if asc.enabled else 0,
                asc.cmd_dir,
                asc.cmd_step_us,
                1 if dec.enabled else 0,
                dec.cmd_dir,
                dec.cmd_step_us,
            )
        )
        return True

    if cmd == "stop":
        asc.hard_stop()
        dec.hard_stop()
        reply("ok stopped")
        return True

    if cmd in MOTORS:
        m = MOTORS[cmd]
        m.apply_command(args)
        reply("ok %s" % m.status_tokens())
        return True

    reply("err unknown_cmd %s" % cmd)
    return True


def poll_serial():
    global _rx
    while poll.poll(0):
        ch = sys.stdin.read(1)
        if not ch:
            break
        if ch in ("\n", "\r"):
            if _rx:
                handle_line(_rx)
                _rx = ""
        else:
            _rx += ch
            if len(_rx) > 200:
                _rx = ""
                reply("err line_too_long")


reply("ok boot motor=asc,dec")
while True:
    poll_serial()
    asc.maybe_step()
    dec.maybe_step()
