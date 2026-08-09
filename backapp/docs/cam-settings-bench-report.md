# Camera settings / spectrum / reconfig — bench report

Generated: **2026-08-09 12:50:35 UTC**  
Run: `settings_20260809T145000`  
Duration: **27.05 s**  
Overall: **PASS**

**Contract under test:** [`camera-settings-contract.md`](camera-settings-contract.md) (`CameraSettings` in [`cam_settings.py`](../cam_settings.py))  
**Docs index:** [`README.md`](README.md)

- Manifest: [`manifest.json`](../cam_test_out/settings_20260809T145000/manifest.json)
- Run folder: [`C:/Users/franc/cko/astroScop/backapp/cam_test_out/settings_20260809T145000`](../cam_test_out/settings_20260809T145000)

## Verdict

All assertions passed. Acquisition, fast/slow apply, spectrum, and 8 fps emit policy behaved predictably on full-frame worst case.

## Cases

### Settings model

```json
{
  "ok": true,
  "diff_slow": {
    "slow_changed": true,
    "fast_changed": true,
    "output_changed": false,
    "changed_fields": [
      "sensor_preset",
      "shutter_us",
      "analog_gain",
      "colour_gain_r",
      "colour_gain_b"
    ]
  },
  "diff_fast": {
    "slow_changed": false,
    "fast_changed": true,
    "output_changed": false,
    "changed_fields": [
      "analog_gain"
    ]
  }
}
```

### Open full (4056×3040)

- open_s: **0.8393**
- mode_size: `[4056, 3040]`

![full preview](../cam_test_out/settings_20260809T145000/full_preview.bmp)

### Capture timings (full RGB)

| i | shape | capture_s | shutter_us | gain |
|---|-------|-----------|------------|------|
| 0 | [3040, 4056, 3] | 0.5684 | 19979 | 1.0 |
| 1 | [3040, 4056, 3] | 0.2794 | 19979 | 1.0 |
| 2 | [3040, 4056, 3] | 0.2794 | 19979 | 1.0 |

### Spectrum (256-bin RGB)

- full-res compute: **3.8837 s**
- display 640×480 compute: **0.0924 s**
- bins: 256 (hist_len=256)
- display mean R: 0.00015950520833333333

- [`spectrum_display.json`](../cam_test_out/settings_20260809T145000/spectrum_display.json)

### Fast apply (set_controls)

| apply_s | req gain | got | req shutter | got |
|---------|----------|-----|-------------|-----|
| 0.0012 | 1.0 | 1.0 | 100000 | 99954 |
| 0.0012 | 1.15 | 1.1492705345153809 | 110000 | 109985 |
| 0.0012 | 1.3 | 1.299492359161377 | 120000 | 119989 |
| 0.0012 | 1.45 | 1.4483734369277954 | 130000 | 129992 |
| 0.0012 | 1.6 | 1.600000023841858 | 140000 | 139996 |

### Slow apply (reconfigure)

| apply_s | preset | mode_size |
|---------|--------|-----------|
| 0.3154 | bin2x2 | [2028, 1520] |
| 0.3341 | full | [4056, 3040] |

### Emit path ≤8 fps (resize + spectrum + JPEG)

- emitted/skipped: **30** / **0**
- emit_fps: **2.3757**
- mean/max process_s: 0.1357 / 0.1718

## Contract reminders

- Canonical gain: `analog_gain` only (ISO stripped if present).
- Slow: `sensor_preset` / main size / `include_raw`.
- Fast: shutter, analogue gain, colour gains, ScalerCrop.
- Live spectrum runs on display RGB (256 bins/channel).
- Hard limit: on full 4056×3040, FrameDurationLimits min is ~85 ms — shorter shutter requests clamp.

```powershell
powershell -File backapp/scripts/run_cam_settings_bench.ps1
```
