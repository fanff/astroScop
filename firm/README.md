# Telescope firmware (Pico 2 W)

MicroPython firmware for the **Raspberry Pi Pico 2 W** (Bluetooth).

Legacy Arduino sketches remain in `scopFirm/` and `stepperFirm/` — they are not used for the Pico workflow.

## Hardware

The **Raspberry Pi Pico 2 W** drives **two TMC2209** stepper driver boards for full control of the telescope motors.

Per TMC2209, these signals are used:

| Signal | Role |
|--------|------|
| **EN** | Enable / disable the driver |
| **RX** / **TX** | UART link for driver configuration and status |
| **CLK** | Clock |
| **STEP** | Step pulse |
| **DIR** | Direction |

Each driver has its own UART on the Pico 2 W (`UART0` / `UART1`), so MS1/MS2 stay at the module default (address `0`). Cross the UART wires: **Pico 2 W TX → TMC RX**, **Pico 2 W RX → TMC TX**.

### Pin map (Pico 2 W ↔ TMC2209)

Physical pin numbers are the board edge connector pins (same layout as Pico / Pico W).

**Motor 1 — UART0**

| TMC2209 | Pico 2 W GPIO | Board pin | Color |
|---------|---------------|-----------|-------|
| DIR | GP10 | 14 | Green |
| STEP | GP11 | 15 | White |
| EN | GP12 | 16 | Grey |
| CLK | GP13 | 17 | Purple |
| RX | GP16 (UART0 TX) | 21 | Blue |
| TX | GP17 (UART0 RX) | 22 | Yellow |

**Motor 2 — UART1**

| TMC2209 | Pico 2 W GPIO | Board pin | Color |
|---------|---------------|-----------|-------|
| DIR | GP18 | 24 | Green |
| STEP | GP19 | 25 | White |
| EN | GP20 | 26 | Grey |
| CLK | GP21 | 27 | Purple |
| RX | GP8 (UART1 TX) | 11 | Blue |
| TX | GP9 (UART1 RX) | 12 | Yellow |

Also connect **GND** (common) and supply the TMC boards per their power requirements (logic + motor VM). Leave DIAG / INDEX / VREF unconnected for now. VREF pot can stay as-is (or fully up); current is set over UART.

## First-run setup

### 1. Flash MicroPython

1. Download the official MicroPython UF2 for **Pico 2 W**:
   https://micropython.org/download/RPI_PICO2_W/
2. Hold **BOOTSEL** on the board, plug in USB, then release BOOTSEL.
3. A drive named `RPI-RP2` appears — copy the downloaded `.uf2` onto it.
4. The board reboots into MicroPython (the drive disappears).

### 2. Install the upload tool

```bash
uv tool install mpremote
```

## Upload new firmware

From `firm/pico2w`:

```bash
cd firm/pico2w
```

Install as the boot program, then **reset** so it starts (needed — upload alone leaves the REPL stopped):

```bash
mpremote connect auto cp main.py :main.py
mpremote connect auto reset
```

On this machine the Pico is usually **COM5** (`2e8a:0005`). If `auto` picks the wrong port:

```bash
mpremote connect COM5 cp main.py :main.py
mpremote connect COM5 reset
```

Run once without overwriting stored `main.py` (blinks immediately while connected):

```bash
mpremote connect auto run main.py
```

Open the REPL (this **stops** `main.py` until the next reset):

```bash
mpremote connect auto repl
```

### LED not blinking?

1. Confirm firmware is **Pico 2 W** (`RPI_PICO2_W`), not plain Pico 2 — the LED is on the wireless chip, so the wrong UF2 will not drive it.
2. After every `cp` / `repl` / `exec`, run `mpremote connect auto reset` (or unplug USB) so `main.py` starts again.
3. Look at the small green LED near the USB connector (easy to miss in bright light).
4. Quick live test:

```bash
mpremote connect auto run main.py
```

You should see the LED blink while that command is attached.
