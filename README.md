# astroScop

Raspberry Pi HQ camera + dual-axis stepper telescope control, with a Vue UI and optional Bayer post-processing for Siril.

```text
UI (wasp) ──WebSocket──► rootserver :8765
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        cam_picamera2    motorControl     gyroControl
        (picamera2)      (USB serial)     (optional)
              │               │
              ▼               ▼
           IMX477          Pico 2 W
                           (ASC + DEC)
```

## Layout

| Path | Role |
|------|------|
| [`backapp/`](backapp/) | Pi services: WebSocket hub, HQ camera worker, motor worker |
| [`firm/pico2w/`](firm/pico2w/) | MicroPython firmware for Pico 2 W (ASC/DEC STEP/DIR) |
| [`webapp/wasp/`](webapp/wasp/) | Vue 3 + Vite control UI |
| [`postprocessing/`](postprocessing/) | Bayer `.npy` → CFA FITS for Siril (`astroscop-pp`) |

## Pi services

Installed via [`backapp/deploy/install_on_pi.sh`](backapp/deploy/install_on_pi.sh):

| systemd unit | Process |
|--------------|---------|
| `astroscop-rootserver` | [`backapp/rootserver.py`](backapp/rootserver.py) — WS hub |
| `astroscop-camera` | [`backapp/cam_picamera2.py`](backapp/cam_picamera2.py) — HQ capture + preview |
| `astroscop-motor` | [`backapp/motorControl.py`](backapp/motorControl.py) — rates ↔ Pico |

Camera settings contract (wire format, slow/fast fields): [`backapp/docs/camera-settings-contract.md`](backapp/docs/camera-settings-contract.md).  
Hardware / modes / science notes: [`backapp/docs/pi-hq-camera.md`](backapp/docs/pi-hq-camera.md).

## Firmware (Pico 2 W)

See [`firm/README.md`](firm/README.md) and [`firm/pico2w/README.md`](firm/pico2w/README.md).

```bash
cd firm/pico2w
mpremote connect COM5 cp main.py :main.py
mpremote connect COM5 reset
```

Host client: [`backapp/pico_motor.py`](backapp/pico_motor.py).

## UI (wasp)

```bash
cd webapp/wasp
npm install
npm run serve    # dev
npm run build    # production
```

Deploy helper: [`webapp/wasp/buildandpush.sh`](webapp/wasp/buildandpush.sh).

## Post-processing

Convert science Bayer captures to Siril-friendly FITS:

```bash
cd postprocessing
# see postprocessing/README.md
```

## Dev notes

- [`backapp/`](backapp/) is **uv-managed** (`pyproject.toml` + `uv.lock`). Dev: `cd backapp && uv sync`.
- Pi install does **not** need uv: on a host run [`backapp/deploy/export_pi_requirements.sh`](backapp/deploy/export_pi_requirements.sh), sync `deploy/requirements.generated.txt` to the Pi, then run [`backapp/deploy/install_on_pi.sh`](backapp/deploy/install_on_pi.sh). That script creates a `.venv` with `--system-site-packages`, `pip install`s the export, and keeps **apt** packages for picamera2 / numpy / opencv / PIL.
- Preview helpers live in [`backapp/imgutils.py`](backapp/imgutils.py); Bayer science saves go through [`backapp/cam_storage.py`](backapp/cam_storage.py).
