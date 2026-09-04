# Camera settings contract (HQ / IMX477)

**Audience:** agents updating [`rootserver.py`](../rootserver.py) and the web UI so they pass parameters the camera worker already enforces.

**Status:** camera worker is the source of truth. Rootserver today is a mostly opaque relay; UI still speaks a legacy shape. Both should migrate to the **canonical wire format** below.

---

## Source of truth (code)

| File | Role |
|------|------|
| [`cam_settings.py`](../cam_settings.py) | Pydantic `CameraSettings`, field classes (slow/fast/output), forbidden keys, `from_legacy_dict`, `diff_settings` |
| [`cam_spectrum.py`](../cam_spectrum.py) | `SpectrumStats` + `compute_rgb_spectrum` (display RGB) |
| [`cam_picamera2.py`](../cam_picamera2.py) | Worker: ingest → apply fast/slow → capture → WS emit (`srcimage`, `camTiming`) |
| [`cam_storage.py`](../cam_storage.py) | Bayer science storage **process** (shm ring → `*_bayer.npy` + meta) |
| [`test_cam_storage.py`](../test_cam_storage.py) | Camera-free storage / handoff tests |
| [`test_cam_settings_bench.py`](../test_cam_settings_bench.py) | On-device contract tests (must stay PASS) |
| [`pi-hq-camera.md`](pi-hq-camera.md) | Hardware, modes, ops / safe testing |
| [`hq-camera-capability-report.md`](hq-camera-capability-report.md) | Verified limits on `piscope` |
| [`cam-settings-bench-report.md`](cam-settings-bench-report.md) | Latest settings/spectrum/reconfig bench |

Do **not** invent overlapping gain controls. If code and this doc disagree, trust **`cam_settings.py`**.

---

## End-to-end data path

```text
UI  --msgtype:"params"-->  rootserver  --same msg-->  cam_picamera2
                                                         │
                                                         ├─ from_legacy_dict → CameraSettings
                                                         ├─ slow? reconfigure : fast? set_controls
                                                         └─ capture → srcimage (+ spectrum) → rootserver → UI
```

- Camera WS path: `ws://…:8765/camera` (worker connects here).
- Browser clients use the default user path; they send `params` and receive broadcast images / `camTiming`.
- Worker never applies settings on the WS receive thread: it queues `pending_settings`; the capture loop applies them between frames.

---

## WebSocket messages the camera understands

### Inbound to camera (from rootserver)

```json
{ "msgtype": "params", "data": { /* CameraSettings wire object — see below */ } }
```

Also:

```json
{ "msgtype": "serverOverwhelmed", "data": true }
```

When overwhelmed is true, the worker still acquires but **skips** WS JPEG emit.

Invalid `data` is logged and **ignored** (previous settings stay live). Validation errors must not crash the worker.

### Outbound from camera

**`srcimage`** (preview frame, rate-limited):

```json
{
  "msgtype": "srcimage",
  "imageData": "<base64 JPEG of display-sized RGB>",
  "usedParams": { /* see usedParams */ },
  "spectrum": { /* SpectrumStats — optional if compute fails */ }
}
```

**`camTiming`** (≈ every 3 s):

```json
{
  "msgtype": "camTiming",
  "data": {
    "imgbuffcount": 0,
    "science_published": 40,
    "science_dropped": 0,
    "science_written": 38,
    "science_errors": 0,
    "science_pending": 2,
    "science_slots": 199,
    "save_enabled": true,
    "save_root": "./savedimgs",
    "emitted": 12,
    "skipped": 40,
    "max_emit_fps": 8.0,
    "capture_fps": 11.2,
    "frame_time_ms": 89.3,
    "science_publish_fps": 11.2,
    "science_write_fps": 10.5,
    "emit_fps": 4.0,
    "queue_fill_eta_s": 281.4
  }
}
```

Rate fields are computed over the last timing window:

- `capture_fps` / `frame_time_ms` — wall-clock capture loop (independent of preview latency).
- `science_publish_fps` / `science_write_fps` — science ring enqueue / disk write rates.
- `emit_fps` — preview WS emits in the window (`emitted / Δt`).
- `queue_fill_eta_s` — net fill ETA: `(slots − pending) / max(0, publish − write)`; `null` when save is off or the queue is not filling.

Emit policy: **≤ `max_emit_fps` (default 8)**. Extra frames are skipped so acquisition keeps CPU. UI/rootserver must not assume every captured frame is sent.

Steady-state acquisition priority:

- Capture runs in a dedicated thread pool; preview JPEG/spectrum packing runs in a separate emit pool (not on the asyncio loop).
- Bayer science frames (when `save_enabled`) are published into a **single contiguous shared_memory slab** (ring of slots) and written by a **separate OS process** ([`cam_storage.py`](../cam_storage.py)) — never RGB/JPEG to disk. Ring size ≈ 60% RAM / frame (also capped by `/dev/shm`).
- Preview uses a depth-1 buffer; science publish does **not** go through that buffer.
- Slow reconfigure (sensor mode / `include_raw`) may briefly block; output fields (`save_*`, display, emit FPS) do not.

---

## Canonical wire format (`CameraSettings`)

Preferred `params.data` shape. Extra keys are **ignored** (`extra="ignore"`). Types and bounds are enforced by Pydantic.

### Fields

| Field | Type | Default | Class | Notes |
|-------|------|---------|-------|-------|
| `sensor_preset` | `"full"` \| `"full_2160"` \| `"bin2x2"` \| `"bin2x2_1080"` \| `"bin2x2_crop"` | `"bin2x2"` | **slow** | Native IMX477 modes only |
| `main_width` | int ≥ 2 or null | `null` | **slow** | Must pair with `main_height`; if both null → preset size |
| `main_height` | int ≥ 2 or null | `null` | **slow** | |
| `include_raw` | bool | `true` | **slow** | Configure raw Bayer stream |
| `shutter_us` | int 1…600_000_000 | `150000` | **fast** | Exposure microseconds |
| `analog_gain` | float (0, 64] | `1.0` | **fast** | **Only** gain control |
| `colour_gain_r` | float (0, 32] | `3.5` | **fast** | AWB always off |
| `colour_gain_b` | float (0, 32] | `1.5` | **fast** | |
| `scaler_crop` | `[x,y,w,h]` or null | `null` | **fast** | Sensor coords; w/h forced even |
| `science_neutral` | bool | `true` | **fast** | Worker path is always manual / neutral tone |
| `preview_div` | `1` \| `2` \| `4` \| `8` | `2` | **output** | JPEG downsample vs capture RGB (full / ½ / ¼ / ⅛); aspect preserved |
| `save_enabled` | bool | `false` | **output** | Runtime arm/disarm Bayer disk persistence |
| `save_root` | string | `"./savedimgs"` | **output** | Runtime destination root (SD, `/dev/shm`, USB, …) |
| `save_format` | string | `"none"` | **output** | Legacy: `"none"` / `"npy"` map to `save_enabled`; science writes Bayer `.npy` only |
| `save_section` | string | `"test"` | **output** | |
| `save_subsection` | string | `""` | **output** | |
| `max_emit_fps` | float (0, 60] | `8.0` | **output** | Preview emit cap |
| `locator_enabled` | bool | `false` | **output** | Burn tracking mark into preview JPEG only |
| `locator_x` | float 0…1 | `0.5` | **output** | Full IMX477 sensor X (0 = left) |
| `locator_y` | float 0…1 | `0.5` | **output** | Full IMX477 sensor Y (0 = top) |
| `locator_size` | float 0.15…3.0 | `1.0` | **output** | Circle radius scale vs the default mark |

### Apply classes (what rootserver/UI should expect latency-wise)

| Class | Fields | Camera behaviour |
|-------|--------|------------------|
| **Slow** | `sensor_preset`, `main_*`, `include_raw` | stop → configure → start (brief blackout) |
| **Fast** | `shutter_us`, `analog_gain`, `colour_gain_*`, `scaler_crop`, `science_neutral` | single `set_controls` (streaming) |
| **Output** | `preview_div`, `save_*`, `max_emit_fps`, `locator_*` | no sensor reconfig |

Classification is implemented by `diff_settings()` in [`cam_settings.py`](../cam_settings.py). Changing a slow field forces a full reopen of the capture loop.

### Example (canonical)

```json
{
  "msgtype": "params",
  "data": {
    "sensor_preset": "bin2x2",
    "include_raw": true,
    "shutter_us": 500000,
    "analog_gain": 2.5,
    "colour_gain_r": 3.5,
    "colour_gain_b": 1.5,
    "scaler_crop": null,
    "science_neutral": true,
    "preview_div": 2,
    "save_enabled": false,
    "save_root": "./savedimgs",
    "save_format": "none",
    "max_emit_fps": 8.0,
    "locator_enabled": false,
    "locator_x": 0.5,
    "locator_y": 0.5,
    "locator_size": 1.0
  }
}
```

---

## Forbidden / non-overlapping controls

These keys are **stripped on ingest** and never applied as exposure/gain:

- `isovalue`, `iso`, `ISO`
- `digital_gain`, `digitalGain`

**Rule:** continuous **`analog_gain` only**. Do not expose ISO in the UI as a live camera control. Do not map ISO→gain in rootserver.

Libcamera may still report `DigitalGain` in metadata; that is read-only status, not a setpoint.

---

## Legacy aliases (transition only)

`from_legacy_dict()` still accepts old UI blobs so existing rootserver pass-through keeps working:

| Legacy key | Maps to |
|------------|---------|
| `shutterSpeed` | `shutter_us` |
| `redgain` / `bluegain` | `colour_gain_r` / `colour_gain_b` |
| `shootresol.name` in preset set | `sensor_preset` |
| `shootresol.width/height` matching a preset size | `sensor_preset` |
| `shootresol` size not matching a preset | `main_width` / `main_height` |
| `dispresol.width/height` | actual emitted JPEG size (from capture ÷ `preview_div`) |

**New UI and rootserver should emit canonical keys**, not legacy ones. Legacy remains for compatibility during migration.

Ignored / unused for science path (may appear in old blobs): `expomode`, `brightness`, `contrast`, `saturation`, `sharpness`, `denoise`, `cameraZoom`, `crop`, `exposure_compensation`. Worker science path forces manual AE/AWB off and neutral tone.

---

## Sensor presets (supported)

| `sensor_preset` | Size | Meaning |
|-----------------|------|---------|
| `full` | 4056×3040 | Full sensor, 1×1 |
| `full_2160` | 4056×2160 | Full-width 16:9 crop, 1×1 |
| `bin2x2` | 2028×1520 | Native 2×2, full FOV (default) |
| `bin2x2_1080` | 2028×1080 | 2×2 + 16:9 vertical crop |
| `bin2x2_crop` | 1332×990 | 2×2 of **center** crop (~2664×1980 window), high fps |

**Not supported as sensor modes:** full-FOV 3×3 or 4×4 binning. Do not add UI options that claim otherwise.

**ScalerCrop vs mode:** `scaler_crop` shrinks the **RGB** FOV; Bayer raw stays full sensor on this stack. For less data / faster raw, change `sensor_preset`, not crop alone. See [`hq-camera-capability-report.md`](hq-camera-capability-report.md).

**Locator:** `locator_x` / `locator_y` are fractions of the physical IMX477 (`4056×3040`), not of the current JPEG. The worker maps that point through the frame’s `ScalerCrop` into the emitted preview, then clamps the full circle+ticks inside the image if the crop excludes the point. Changing `sensor_preset`, `main_*`, or `preview_div` must not move the mark on the sky. `locator_size` scales the circle (and ticks) vs the default radius so the mark can match optical zoom; stroke stays thin. The locator is burned into the **preview JPEG only**; Bayer science files are unchanged. Helpers live in [`cam_locator.py`](../cam_locator.py).

**Bit depth:** max **12-bit** ADC. `uint16` buffers are containers only.

**Frame duration floor:** e.g. ~85 ms on full 4056×3040 — shorter `shutter_us` is clamped. Warn in UI when requesting below mode floor if known.

---

## Outbound `usedParams` (camera → rootserver → UI)

Built by `used_params_from_settings()` in [`cam_picamera2.py`](../cam_picamera2.py). Useful keys:

| Key | Meaning |
|-----|---------|
| `settings` | Full `CameraSettings.to_wire_dict()` echo |
| `shutter_us` / `requested_shutter_us` | Got vs requested exposure |
| `analog_gain` / `requested_analog_gain` | Got vs requested gain |
| `colour_gain_r` / `colour_gain_b` | From metadata |
| `sensor_preset`, `frame_width`, `frame_height` | Geometry |
| `ScalerCrop`, `FrameDuration`, `SensorTimestamp` | Libcamera metadata |
| `save_enabled`, `save_root`, `save_section`, `save_subsection` | Bayer save routing |
| `save_format` | Legacy enable hint (`none`/`npy`) |
| `dispresol` | Actual emitted JPEG WxH (capture ÷ `preview_div`, even) |
| `preview_div` | Configured JPEG scale divisor `1`/`2`/`4`/`8` |
| `shutterSpeed`, `redgain`, `bluegain`, `shootresol` | **Legacy aliases** for old overlay code |

Rootserver overlay today still reads some legacy keys (`cameraWfov`, etc.). When updating rootserver, prefer `usedParams.settings` / new names; keep aliases until UI/overlay migrate.

### `spectrum` object (`SpectrumStats`)

Computed on the **display-sized** uint8 RGB (not full sensor). See [`cam_spectrum.py`](../cam_spectrum.py).

| Field | Meaning |
|-------|---------|
| `bins` | 256 |
| `mean_r/g/b`, `min_*`, `max_*`, `std_*` | Per-channel moments |
| `hist_r/g/b` | Length-256 integer histograms |
| `pixels`, `shape` | `[H, W, 3]` |

UI should treat spectrum as live feedback for exposure/gain, not as science photometry of the raw Bayer.

---

## Work for the **rootserver** agent

Hub behaviour ([`rootserver.py`](../rootserver.py) + [`ws_messages.py`](../ws_messages.py)):

1. **Normalize inbound `params.data`** with shared `CameraSettings` / `from_legacy_dict` before storing and forwarding (canonical wire object).
2. **Strip forbidden keys** at the hub (defense in depth); never invent ISO→gain mapping. Invalid params are logged and **not** forwarded.
3. **Passthrough preview JPEG** — no decode/overlay/re-encode on the event loop. Broadcast `imgData` = camera `imageData`.
4. **Relay `spectrum`** in `imgStats` (plus cheap `histData` derived from spectrum histograms for legacy UI).
5. Prefer reading **`usedParams.settings`** / `shutter_us` / `analog_gain` in consumers; camera still emits legacy aliases.
6. Do not assume 1:1 frame delivery; respect `camTiming.skipped` / `max_emit_fps`.
7. **Overwhelm on drop**: preview queue depth 1; when a newer `srcimage` replaces an unconsumed frame, send edge-triggered `serverOverwhelmed: true` to the camera; when the queue drains, send `false`.
8. **`sysInfo`**: disk paths + `ram` + non-blocking `cpu` (`psutil.cpu_percent(interval=None)`).
9. Keep large WS frame limits suitable for HQ previews (32 MiB).

Camera-free hub tests: [`test_rootserver_hub.py`](../test_rootserver_hub.py).

Out of scope for camera contract: motor `ctlparams`.

---

## Work for the **UI** agent

Expose controls that match the canonical fields. Suggested UX:

| Control | Bound to | Notes |
|---------|----------|-------|
| Sensor mode | `sensor_preset` (+ optional `main_*`) | Five native IMX477 modes; UI may offer RGB main downscales |
| Exposure | `shutter_us` | µs; optional human “seconds” display |
| Gain | `analog_gain` | Continuous float — **no ISO slider** |
| Colour R/B | `colour_gain_r/b` | Default 3.5 / 1.5; AWB off |
| ROI (optional) | `scaler_crop` | Or “center crop %” helper that sends `[x,y,w,h]` |
| Preview scale | `preview_div` | `1`/`2`/`4`/`8` — aspect-preserving JPEG downsample; UI paints with `object-fit: contain` |
| Preview FPS cap | `max_emit_fps` | Default 8 |
| Locator | `locator_enabled` + `locator_x` / `locator_y` + `locator_size` | Preview JPEG overlay; X/Y are full-sensor fractions; size scales the circle; crop clamps to the visible edge |
| Save arm | `save_enabled` | Runtime on/off; Bayer `.npy` only (separate storage process) |
| Save path | `save_root` + section | Runtime destination; no sensor reconfig |

Remove or hide: ISO / `isovalue`, digital gain as setpoints, fake 3×3/4×4 modes.
Do **not** expect RGB/JPEG science files from the camera worker.

Show live: `usedParams` got vs requested shutter/gain; optional histogram from `spectrum`.

When changing `sensor_preset`, expect a short stream interruption (slow path).

---

## Verification

On `piscope` with `astroscop-camera.service` **stopped**:

```powershell
powershell -File backapp/scripts/run_cam_settings_bench.ps1
```

Expect overall **PASS** in [`cam-settings-bench-report.md`](cam-settings-bench-report.md). That bench covers ingest (ISO stripped), slow vs fast diff, open full, spectrum 256-bin, fast gain/shutter track, slow reconfig, and ≤8 fps emit.

Camera-free storage / handoff tests:

```powershell
python backapp/test_cam_storage.py
python backapp/test_cam_locator.py
```

Hardware capability evidence: [`hq-camera-capability-report.md`](hq-camera-capability-report.md).

---

## Quick “do / don’t”

**Do**

- Send `analog_gain` + `shutter_us` + `sensor_preset`
- Treat slow preset changes as reconfig events
- Cap preview with `max_emit_fps`
- Use spectrum only on display RGB
- Arm Bayer save with `save_enabled` + `save_root` at runtime (`include_raw` must stay true)

**Don’t**

- Send ISO as a control
- Claim 3×3 / 4×4 full-FOV binning
- Expect ScalerCrop to shrink Bayer readout
- Expect every frame on the wire
- Expect RGB/JPEG science files from the camera worker
- Bypass `CameraSettings` validation with ad-hoc overlapping controls
