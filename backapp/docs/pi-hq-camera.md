# Raspberry Pi HQ Camera (IMX477)

Static reference for the HQ camera used by astroScop on host **`piscope`**.

**Implementing rootserver or UI parameter plumbing?** Use the contract first:

→ **[`camera-settings-contract.md`](camera-settings-contract.md)** — canonical wire format, slow/fast/output fields, forbidden keys, WS messages.

Docs index: [`README.md`](README.md)

| Artifact | Path |
|----------|------|
| Worker | [`cam_picamera2.py`](../cam_picamera2.py) |
| Settings model | [`cam_settings.py`](../cam_settings.py) |
| Spectrum | [`cam_spectrum.py`](../cam_spectrum.py) |
| systemd | [`deploy/astroscop-camera.service`](../deploy/astroscop-camera.service) |
| Capability evidence | [`hq-camera-capability-report.md`](hq-camera-capability-report.md) |
| Settings bench evidence | [`cam-settings-bench-report.md`](cam-settings-bench-report.md) |

---

## Hardware

| Item | Value |
|------|--------|
| Module | Raspberry Pi High Quality Camera |
| Sensor | Sony **IMX477** |
| Native resolution | **4056 × 3040** (12.3 MP) |
| Pixel size | 1.55 µm |
| Optical format | 1/2.3″ |
| Interface | CSI-2 ribbon to Pi CSI port |
| Host (this project) | `piscope` (`ssh piscope`) |
| OS stack | Raspberry Pi OS + **libcamera** / **picamera2** (legacy `picamera` / `picamerax` not used) |
| Max ADC depth | **12-bit** (uint16 is a container only) |

Legacy camera detection (`vcgencmd get_camera`) may report `supported=0 detected=0`. That is normal on modern Pi OS: the camera is managed by **libcamera**, not the old firmware stack. Trust `rpicam-hello --list-cameras` instead.

---

## Detected sensor modes (live on `piscope`)

Output of `rpicam-hello --list-cameras` (IMX477):

```
0 : imx477 [4056x3040 12-bit] (.../imx477@1a)
Modes:
  SBGGR10_CSI2P / SBGGR8 / SBGGR12_CSI2P
    1332 × 990
    2028 × 1080
    2028 × 1520
    4056 × 2160
    4056 × 3040
```

Named presets exposed to UI/rootserver (`SENSOR_PRESETS` in [`cam_picamera2.py`](../cam_picamera2.py)):

| Preset | Size | Notes |
|--------|------|-------|
| `full` | 4056×3040 | Whole sensor, 1×1 |
| `full_2160` | 4056×2160 | Full-width 16:9 crop, 1×1 |
| `bin2x2` | 2028×1520 | **Native 2×2**, full FOV (worker default) |
| `bin2x2_1080` | 2028×1080 | 2×2 + 16:9 vertical crop |
| `bin2x2_crop` | 1332×990 | 2×2 of **center** crop — *not* full-FOV 3×3/4×4 |

**Not available natively:** true full-FOV **3×3** or **4×4** binning.

---

## Software stack on `piscope`

**apt (system / camera):**

- `python3-picamera2`, `python3-libcamera`
- `python3-numpy`, `python3-opencv`, `python3-pil`
- `libcamera` + IPA modules / `rpicam-apps` as needed

**uv on host → pip on Pi:** pure-Python deps (`websockets`, `pyserial`, `pydantic`, `psutil`, …) are locked in [`../pyproject.toml`](../pyproject.toml) / `uv.lock`. Export with [`../deploy/export_pi_requirements.sh`](../deploy/export_pi_requirements.sh), then [`../deploy/install_on_pi.sh`](../deploy/install_on_pi.sh) creates `backapp/.venv` (`--system-site-packages`) and `pip install`s the generated requirements. The Pi does not need uv installed.

User `fanf` is in groups **`video`**, **`render`**, etc. (required for camera access).

---

## Role in astroScop

```text
UI  →  rootserver (ws://…:8765)  →  cam_picamera2.py  →  Picamera2 / IMX477
         params / overwhelm              │
                                         └─ srcimage (+ spectrum) + camTiming
```

- Default camera WebSocket URI: `ws://localhost:8765/camera`.
- Inbound `msgtype: "params"` is validated into `CameraSettings` (see [contract](camera-settings-contract.md)).
- Preview emit: resized JPEG as `srcimage`, capped at **`max_emit_fps` (default 8)**; extras skipped.
- Optional Bayer science save: runtime `save_enabled` + `save_root` → separate storage **process** writes `*_bayer.npy` + `*_meta.json` (see [`cam_storage.py`](../cam_storage.py)). RGB/JPEG are preview-only.

### Control mapping (canonical → libcamera)

Full field list and legacy aliases: [camera-settings-contract.md](camera-settings-contract.md).

| Canonical key | libcamera / picamera2 | Notes |
|---------------|------------------------|--------|
| `shutter_us` | `ExposureTime` | µs; may clamp to mode `FrameDurationLimits` floor |
| `analog_gain` | `AnalogueGain` | **Only** gain setpoint; ISO keys stripped |
| `colour_gain_r/b` | `ColourGains` | `AwbEnable=False` |
| `sensor_preset` (+ optional `main_*`) | still config + sensor mode | **Slow** — reconfigure |
| `scaler_crop` | `ScalerCrop` | **Fast**; RGB FOV only (Bayer stays full) |
| `display_width/height` | client resize only | Does not change sensor capture |
| `max_emit_fps` | emit throttle | Default 8 |

Science path forces AE off, AWB off, minimal NR, neutral tone mapping.

---

## Exclusive access (important)

Only **one** process may own the IMX477 at a time.

```text
astroscop-camera.service  →  backapp/.venv/bin/python …/cam_picamera2.py
```

If that service is running, ad-hoc `Picamera2()` / suite scripts will fail. Stop/disable before manual tests.

---

## Science capture notes

Goals: constant parameters across a series, no auto processing, keep the camera warm.

Helpers in [`cam_picamera2.py`](../cam_picamera2.py): `apply_settings_fast` / `apply_settings_slow` / `open_from_settings`, `capture_raw_frame`, `set_scaler_crop` / `center_scaler_crop`, `capture_rgb_with_metadata`.

Disk policy for suite dumps:

- Science: **`.npy`** (Bayer preferred)
- Preview: **BMP**. **No JPEG / compressed TIFF** in the suite.
- Production worker stacks in RAM; suite writes files for offline check.

### ScalerCrop vs sensor mode

| Approach | RGB FOV | Bayer raw size |
|----------|---------|----------------|
| `scaler_crop` | Cropped | Still full sensor on this stack |
| Binned/cropped `sensor_preset` | Matches mode | Smaller / faster |

Bayer `.npy` width may be stride-padded (e.g. `(3040, 4064)` for 4056-wide) — crop using metadata `configured_size`.

### Exposure trust (verified)

Long exposures track metadata through at least **120 s** on this Pi (see capability report). Full-res frame-duration floor is ~**85 ms** — shorter shutters clamp.

Daytime long frames often **saturate**; that does not invalidate control tests.

---

## Typed settings (summary)

Canonical gain is continuous **`analog_gain` only**. Details, examples, and agent checklists:

→ **[`camera-settings-contract.md`](camera-settings-contract.md)**

| Class | Apply path |
|-------|------------|
| **Slow** (`sensor_preset`, `main_*`, `include_raw`) | stop → configure → start |
| **Fast** (shutter, gain, colour, scaler_crop, …) | one `set_controls` |
| **Output** (display, save, `max_emit_fps`) | no sensor reconfig |

Spectrum: 256-bin R/G/B on **display-sized** RGB, attached to `srcimage` as `spectrum`.

### Re-verify settings contract on device

```powershell
powershell -File backapp/scripts/run_cam_settings_bench.ps1
```

Report: [`cam-settings-bench-report.md`](cam-settings-bench-report.md).

---

## Safe live test process

### 0. Prerequisites

```bash
ssh piscope
rpicam-hello --list-cameras   # expect imx477
```

### 1. Stop the camera worker

```bash
sudo systemctl disable --now astroscop-camera.service
systemctl is-enabled astroscop-camera.service   # disabled
systemctl is-active astroscop-camera.service    # inactive
```

### 2. Suite / bench from Windows

```powershell
powershell -File backapp/scripts/run_hq_cam_tests.ps1
powershell -File backapp/scripts/run_cam_settings_bench.ps1
```

Results land under `backapp/cam_test_out/` (gitignored).

### 3. Restore production (when ready)

```bash
sudo systemctl enable --now astroscop-camera.service
```

### Safety

- Never run suite / `rpicam-*` while `astroscop-camera.service` is active.
- Prefer `disable --now` / `enable --now` over `kill -9`.

---

## Related files

| Path | Role |
|------|------|
| [`camera-settings-contract.md`](camera-settings-contract.md) | **Contract for rootserver + UI agents** |
| [`cam_picamera2.py`](../cam_picamera2.py) | HQ worker |
| [`cam_settings.py`](../cam_settings.py) | Enforced settings model |
| [`cam_spectrum.py`](../cam_spectrum.py) | Display spectrum |
| [`rootserver.py`](../rootserver.py) | WS hub (params relay / image broadcast) |
| [`test_cam_picamera2.py`](../test_cam_picamera2.py) | Mode / science suite |
| [`test_cam_settings_bench.py`](../test_cam_settings_bench.py) | Settings contract bench |
| [`scripts/run_hq_cam_tests.ps1`](../scripts/run_hq_cam_tests.ps1) | Sync → suite → pull |
| [`scripts/run_cam_settings_bench.ps1`](../scripts/run_cam_settings_bench.ps1) | Sync → settings bench → pull |
| [`hq-camera-capability-report.md`](hq-camera-capability-report.md) | Capability aggregation |
| [`cam-settings-bench-report.md`](cam-settings-bench-report.md) | Latest settings bench |
| [`deploy/astroscop-camera.service`](../deploy/astroscop-camera.service) | systemd unit |
| [`deploy/install_on_pi.sh`](../deploy/install_on_pi.sh) | Pi install helper |
