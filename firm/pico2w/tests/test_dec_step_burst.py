"""Motor 2 (DEC) STEP/DIR short bursts — no USB command protocol, no TMC UART.

Pins from firm/README.md: DIR=GP18, STEP=GP19, EN=GP20 (ENN active-low).

Run: mpremote connect COM5 run tests/test_dec_step_burst.py
Ctrl-C / disconnect to stop (leaves EN high = disabled).
"""

from machine import Pin
import time

PIN_DIR, PIN_STEP, PIN_EN = 18, 19, 20
STEPS = 50
HALF_PERIOD_US = 4000

dir_pin = Pin(PIN_DIR, Pin.OUT, value=0)
step_pin = Pin(PIN_STEP, Pin.OUT, value=0)
en_pin = Pin(PIN_EN, Pin.OUT, value=1)  # ENN high = disabled
led = Pin("LED", Pin.OUT)

print("DEC STEP/DIR burst test (EN off between bursts)")
print("DIR=GP%d STEP=GP%d EN=GP%d" % (PIN_DIR, PIN_STEP, PIN_EN))
direction = 0

try:
    while True:
        for _ in range(2):
            led.on()
            time.sleep_ms(80)
            led.off()
            time.sleep_ms(80)

        en_pin.value(0)
        time.sleep_ms(20)
        dir_pin.value(direction)
        print("EN=0 dir=%d steps=%d" % (direction, STEPS))
        for _ in range(STEPS):
            step_pin.value(1)
            time.sleep_us(HALF_PERIOD_US)
            step_pin.value(0)
            time.sleep_us(HALF_PERIOD_US)
            led.toggle()

        en_pin.value(1)
        print("EN=1 (off)")
        direction ^= 1
        time.sleep_ms(1500)
finally:
    en_pin.value(1)
    step_pin.value(0)
    print("stopped EN=1")
