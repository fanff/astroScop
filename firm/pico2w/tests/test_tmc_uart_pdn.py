"""Motor 1 PDN single-wire UART probe.

Wiring:
  Pico GP16 (TX) --[1k]--+---- TMC PDN (pin after MS2)
  Pico GP17 (RX) --------+
  Common GND: Pico <-> 12V- <-> TMC
"""

from machine import Pin, UART
import time

PIN_DIR, PIN_STEP, PIN_EN, PIN_CLK = 10, 11, 12, 13
PIN_TX, PIN_RX = 16, 17
REG_IOIN = 0x06
REG_IFCNT = 0x02
REG_GCONF = 0x00

Pin(PIN_DIR, Pin.OUT, value=0)
Pin(PIN_STEP, Pin.OUT, value=0)
en_pin = Pin(PIN_EN, Pin.OUT, value=1)
Pin(PIN_CLK, Pin.IN)
led = Pin("LED", Pin.OUT)


def crc8(data):
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if (crc & 0x80) else (crc << 1) & 0xFF
    return crc


def parse_reply(buf):
    if not buf:
        return None, None, "no bytes"
    data = bytes(buf)
    for i in range(0, len(data) - 7):
        chunk = data[i : i + 8]
        if chunk[0] != 0x05 or chunk[1] != 0xFF:
            continue
        if crc8(chunk[:7]) != chunk[7]:
            continue
        value = (chunk[3] << 24) | (chunk[4] << 16) | (chunk[5] << 8) | chunk[6]
        return value, chunk, None
    return None, data, "echo only / no reply in %s" % data.hex()


def open_uart(baud):
    return UART(
        0,
        baudrate=baud,
        bits=8,
        parity=None,
        stop=1,
        tx=Pin(PIN_TX),
        rx=Pin(PIN_RX),
        timeout=50,
        timeout_char=20,
    )


def try_read(uart, slave, settle_ms=20):
    while uart.any():
        uart.read()
    req = bytearray([0x05, slave & 0xFF, REG_IOIN & 0x7F])
    req.append(crc8(req))
    uart.write(req)
    time.sleep_ms(settle_ms)
    raw = b""
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < 80:
        n = uart.any()
        if n:
            raw += uart.read(n)
        elif len(raw) >= 12:
            break
        else:
            time.sleep_ms(2)
    return bytes(req), raw


def try_ifcnt_bump(uart, slave):
    def read_ifcnt():
        while uart.any():
            uart.read()
        req = bytearray([0x05, slave & 0xFF, REG_IFCNT & 0x7F])
        req.append(crc8(req))
        uart.write(req)
        time.sleep_ms(20)
        raw = b""
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < 80:
            n = uart.any()
            if n:
                raw += uart.read(n)
            elif len(raw) >= 12:
                break
            else:
                time.sleep_ms(2)
        return parse_reply(raw)

    before, _, err = read_ifcnt()
    if err:
        return False, err
    payload = bytearray([0x05, slave & 0xFF, REG_GCONF | 0x80, 0, 0, 0, 0x40])
    payload.append(crc8(payload))
    while uart.any():
        uart.read()
    uart.write(payload)
    time.sleep_ms(20)
    while uart.any():
        uart.read()
    after, _, err = read_ifcnt()
    if err:
        return False, err
    bumped = ((after & 0xFF) - (before & 0xFF)) & 0xFF
    return bumped >= 1, "IFCNT %d -> %d" % (before & 0xFF, after & 0xFF)


print("=== UART probe (common GND) ===")
ok = False

for en_level, en_name in ((1, "disabled"), (0, "enabled")):
    en_pin.value(en_level)
    time.sleep_ms(50)
    for baud in (115200, 57600, 9600):
        uart = open_uart(baud)
        time.sleep_ms(10)
        for slave in (0, 1, 2, 3):
            req, raw = try_read(uart, slave)
            ioin, chunk, err = parse_reply(raw)
            tag = "EN=%s baud=%d addr=%d" % (en_name, baud, slave)
            if err:
                if slave == 0 and baud == 115200:
                    print("[%s] %s (raw_len=%d)" % (tag, err, len(raw)))
                continue
            version = (ioin >> 24) & 0xFF
            print("[%s] IOIN=0x%08X VERSION=0x%02X" % (tag, ioin, version))
            bump_ok, bump_msg = try_ifcnt_bump(uart, slave)
            print("  %s bump=%s" % (bump_msg, bump_ok))
            if version == 0x21:
                ok = True
        uart.deinit()

en_pin.value(1)
print("RESULT: %s" % ("PASS" if ok else "FAIL"))
delay_ms = 120 if ok else 800
while True:
    led.toggle()
    time.sleep_ms(delay_ms)
