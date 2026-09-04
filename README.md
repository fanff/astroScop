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

Installed via [`backapp/deploy/install_on_pi.sh`](backapp/deploy/install_on_pi.sh)
(after syncing code with [`backapp/deploy/deploy.ps1`](backapp/deploy/deploy.ps1) / [`backapp/deploy/deploy.sh`](backapp/deploy/deploy.sh)):

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

Pi deploy (compiled static files on **port 80**, hub still `ws://<host>:8765`).
SSH host defaults to `piscope`; set `ASTROSCOP_PI_HOST` for another Pi (e.g. `piscope2`).

```bash
# Windows — backend then UI
$env:ASTROSCOP_PI_HOST = "piscope2"
powershell -File backapp/deploy/deploy.ps1
cd webapp/wasp; npm run deploy:pi

# bash
ASTROSCOP_PI_HOST=piscope2 ./backapp/deploy/deploy.sh
ASTROSCOP_PI_HOST=piscope2 ./webapp/wasp/deploy/deploy.sh
```

See [`webapp/wasp/README.md`](webapp/wasp/README.md).

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
