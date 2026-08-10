# Pico 2 W ↔ Raspberry Pi — ASC + DEC stepper protocol

Sparse **USB serial** (CDC) text commands. The Pico generates STEP pulses on its own; the Pi only sends occasional setpoints (direction + step period). No continuous streaming required.

## Role split

| Side | Responsibility |
|------|----------------|
| **Raspberry Pi** | Compute tracking rate → `dir` + `step_us`; send when it changes |
| **Pico 2 W** | Enable drivers, set DIR, emit STEP edges; ease rate changes over ~100 ms |
| **TMC2209** | Standalone STEP/DIR for now (VREF pot = current). TMC UART config later if/when PDN works |

Motors: **ASC** (Motor 1) and **DEC** (Motor 2).

## Link

- Transport: Pico USB serial (same port as `mpremote`, e.g. `COM5` on Windows)
- Encoding: UTF-8 / ASCII lines
- Line ending: `\n` ( `\r\n` accepted)
- Baud: N/A for USB CDC (host opens the virtual COM port; 115200 is fine if a baud must be set)

## Command format

```
<cmd> [key=value] [key=value] ...
```

Whitespace-separated. Keys are case-insensitive. Unknown commands get an error line.

### Commands (implemented on Pico)

| Command | Meaning |
|---------|---------|
| `ping` | Liveness check |
| `status` | Report ASC + DEC commanded state |
| `stop` | Immediate disable both drivers |
| `asc ...` | Set ASC motion parameters |
| `dec ...` | Set DEC motion parameters |

Alias: `motor` is accepted as the same as `asc`.

### `asc` / `dec` parameters

| Key | Values | Meaning |
|-----|--------|---------|
| `dir` | `0` or `1` | Direction pin level (commanded) |
| `step_us` | integer µs | Target period between STEP rising edges. `0` = ramp to stop |
| `step_time` | integer µs | **Alias of `step_us`** (same units) |
| `en` / `enable` | `0` or `1` | `0` = immediate hard stop for that axis. If omitted and `step_us>0`, Pico enables automatically |

Limits on Pico: `step_us` clamped to **50 … 10_000_000** µs.

### Examples (Pi → Pico)

```text
ping
asc dir=1 step_us=2000
dec dir=0 step_us=3000
asc dir=0 step_time=1500
asc step_us=0
stop
status
```

### Replies (Pico → Pi)

One line per handled command. No periodic telemetry unless the Pi asks (`status` / after `asc`/`dec`).

| Reply | Meaning |
|-------|---------|
| `ok boot motor=asc,dec` | Firmware started |
| `ok pong` | `ping` |
| `ok motor=asc\|dec en=<0\|1> dir=<0\|1> step_us=<n>` | After `asc` / `dec` (commanded target) |
| `ok asc en=… dir=… step_us=… dec en=… dir=… step_us=…` | After `status` |
| `ok stopped` | After `stop` |
| `err ...` | Parse / unknown command |

## Timing semantics

- `step_us` = full period between steps (not the pulse width).
- Pico STEP high time is a short fixed pulse (~4 µs); low fills the rest of the period.
- Rate ≈ `1e6 / step_us` steps per second.
- **Rate changes** (including reverse / start / `step_us=0`) ease as a **signed** steps/s ramp over **~100 ms**. The step deadline is **not** reset on setpoint change (avoids ghost steps / “bzz”).
- `stop` and `en=0` are **immediate** hard cuts (no ramp).
- No microstepping control from software yet: driver MS pins / pot define the mechanical step size.
- If the Pico falls behind, it resyncs (does not dump a burst of catch-up steps).

## Host on the Raspberry Pi (live)

Production host:

| Piece | Path |
|-------|------|
| Serial client | `backapp/pico_motor.py` |
| Worker (WS ↔ serial) | `backapp/motorControl.py` |
| systemd | `backapp/deploy/astroscop-motor.service` |
| Smoke test | `backapp/test_pico_motor_firmware_win.py --port /dev/ttyACM0` |

UI sends `ctlparams` `{k:"ASC"|"DEC", v:<signed steps/sec>}`. The worker maps that to
`asc|dec dir=… step_us=…` (`step_us = 1e6 / |v|`, stop on `0`).

```bash
# Manual protocol check (stop motor worker / mpremote first)
cd /home/fanf/astroScop/backapp
python3 -c "from pico_motor import PicoMotorClient, resolve_pico_port; c=PicoMotorClient(resolve_pico_port()); print(c.drain_boot()); print(c.ping()); c.close()"
```

Open the port **without** leaving a second tool (`mpremote repl`) attached.

## Pin map

### ASC = Motor 1

| Signal | Pico GPIO | Notes |
|--------|-----------|--------|
| DIR | GP10 | |
| STEP | GP11 | |
| EN | GP12 | Active-low on TMC (`ENN`) |
| TMC UART | GP16/GP17 | Not used by `main.py` yet |

### DEC = Motor 2

| Signal | Pico GPIO | Notes |
|--------|-----------|--------|
| DIR | GP18 | |
| STEP | GP19 | |
| EN | GP20 | Active-low on TMC (`ENN`) |
| TMC UART | GP8/GP9 | Not used by `main.py` yet |

CLK: leave **open** on both TMCs (internal oscillator). Common **GND** between Pico, TMC, and 12V PSU (−). VM=12V on TMC. VREF pot sets current.

## Upload

```bash
cd firm/pico2w
mpremote connect COM5 cp main.py :main.py
mpremote connect COM5 reset
```

Manual check:

```bash
mpremote connect COM5 repl
# then type: ping
#          asc dir=1 step_us=2000
#          dec dir=0 step_us=2000
#          status
#          stop
```

## Tests (not installed as boot)

| Script | Purpose |
|--------|---------|
| `tests/test_step_burst.py` | ASC STEP/DIR smoke test (no serial protocol) |
| `tests/test_dec_step_burst.py` | DEC STEP/DIR smoke test (GP18/19/20, no UART) |
| `tests/test_tmc_uart_pdn.py` | TMC PDN UART probe (still unresolved) |

```bash
mpremote connect COM5 run tests/test_step_burst.py
mpremote connect COM5 run tests/test_dec_step_burst.py
```

## Future (not in this firmware)

- TMC UART current / microstep config once PDN wiring works
- Optional Bluetooth link instead of USB
