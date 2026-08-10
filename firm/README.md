# Telescope firmware (Pico 2 W)

MicroPython firmware for the **Raspberry Pi Pico 2 W**.

Host protocol (USB serial commands for the Raspberry Pi) lives next to the boot script:

→ **[`pico2w/README.md`](pico2w/README.md)**

Pi host for ASC+DEC is `backapp/motorControl.py` + `backapp/pico_motor.py` (systemd: `astroscop-motor`).

## Current status

- **ASC** and **DEC** motors are wired and controlled in **STEP/DIR** standalone mode (no TMC UART config yet).
- Pico emits regular STEP pulses from sparse USB commands (`asc` / `dec` with `dir`, `step_us`).
- Rate setpoints ease over ~100 ms (signed rate); step deadline is not reset on change.
- **CLK** on the TMC is left **open** (internal oscillator). Do not drive it from the Pico.
- TMC PDN UART is still unresolved; probes are kept under `pico2w/tests/`.

Current is set with the TMC **VREF** pot until UART works. Keep common **GND** between Pico, TMC, and 12V PSU (−).

## Hardware

The Pico 2 W will drive **two TMC2209** boards (ASC + DEC).

| Signal | Role (today) |
|--------|----------------|
| **EN** | Enable / disable driver (active-low `ENN`) |
| **STEP** / **DIR** | Motion |
| **CLK** | Leave open on TMC |
| **PDN / UART** | Planned; not used by `main.py` yet |

### Pin map (Pico 2 W ↔ TMC2209)

Physical pin numbers are the board edge connector pins.

**Motor 1 — ASC**

| TMC2209 | Pico 2 W GPIO | Board pin | Color |
|---------|---------------|-----------|-------|
| DIR | GP10 | 14 | Green |
| STEP | GP11 | 15 | White |
| EN | GP12 | 16 | Grey |
| CLK | (open on TMC) | — | — |
| PDN (future UART) | GP16 / GP17 + 1k single-wire | 21 / 22 | Blue / Yellow |

**Motor 2 — DEC**

| TMC2209 | Pico 2 W GPIO | Board pin | Color |
|---------|---------------|-----------|-------|
| DIR | GP18 | 24 | Green |
| STEP | GP19 | 25 | White |
| EN | GP20 | 26 | Grey |
| CLK | (open on TMC) | — | — |
| PDN (future UART) | GP8 / GP9 + 1k single-wire | 11 / 12 | Blue / Yellow |

## First-run setup

### 1. Flash MicroPython

1. Download the official MicroPython UF2 for **Pico 2 W**:
   https://micropython.org/download/RPI_PICO2_W/
2. Hold **BOOTSEL**, plug in USB, release BOOTSEL.
3. Copy the `.uf2` onto the `RPI-RP2` drive.

### 2. Install the upload tool

```bash
uv tool install mpremote
```

## Upload firmware

```bash
cd firm/pico2w
mpremote connect COM5 cp main.py :main.py
mpremote connect COM5 reset
```

On this machine the Pico is usually **COM5** (`2e8a:0005`).

Smoke-test over the USB REPL:

```bash
mpremote connect COM5 repl
```

Then type:

```text
ping
asc dir=1 step_us=2000
dec dir=0 step_us=2000
status
stop
```

### Hardware tests (optional)

```bash
mpremote connect COM5 run tests/test_step_burst.py
mpremote connect COM5 run tests/test_dec_step_burst.py
mpremote connect COM5 run tests/test_tmc_uart_pdn.py
```
