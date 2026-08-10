"""Motor 1 (ASC) STEP/DIR short bursts — no USB command protocol, no TMC UART.

Run: mpremote connect COM5 run tests/test_step_burst.py
"""

from machine import Pin
import time

PIN_DIR, PIN_STEP, PIN_EN, PIN_CLK = 10, 11, 12, 13
STEPS = 50
HALF_PERIOD_US = 4000

dir_pin = Pin(PIN_DIR, Pin.OUT, value=0)
step_pin = Pin(PIN_STEP, Pin.OUT, value=0)
en_pin = Pin(PIN_EN, Pin.OUT, value=1)
Pin(PIN_CLK, Pin.IN)
led = Pin("LED", Pin.OUT)

print("ASC STEP/DIR burst test (EN off between bursts)")
direction = 0

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
