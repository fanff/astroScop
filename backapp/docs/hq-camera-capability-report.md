# Pi HQ Camera (IMX477) — capability report

Generated: **2026-08-09 12:02:30 UTC**  
Suite run: `20260809T140213`  
Host: `piscope` / Raspberry Pi HQ camera  
Suite duration: **5.33 s**  
Bayer raw enabled end-to-end: **True**

**Settings / wire contract for rootserver + UI:** [`camera-settings-contract.md`](camera-settings-contract.md)  
**Hardware & ops overview:** [`pi-hq-camera.md`](pi-hq-camera.md) · [docs index](README.md)

This report aggregates the live suite outputs so you can eyeball what the hardware
can and cannot do (modes, bit depth, exposure trust, and timing/framerate limits).

- Manifest: [`manifest.json`](../cam_test_out/20260809T140213/manifest.json)
- Probe: [`probe.json`](../cam_test_out/20260809T140213/probe.json)
- Run folder: [`C:/Users/franc/cko/astroScop/backapp/cam_test_out/20260809T140213`](../cam_test_out/20260809T140213)

## Executive summary

| Test | Verdict | Mode | Depth | Exposure req→got | Proc (s) | Filesize |
|------|---------|------|-------|------------------|----------|----------|
| [`full`](#full) | PASS | bayer | 12-bit | 50000→49963 | 1.0393 | 23.6 MiB |
| [`bin2x2`](#bin2x2) | PASS | bayer | 12-bit | 50000→49992 | 0.1926 | 5.9 MiB |
| [`bin2x2_crop`](#bin2x2-crop) | PASS | bayer | 12-bit | 50000→49999 | 0.0785 | 2.5 MiB |
| [`crop`](#crop) | PASS | bayer | 12-bit | 50000→49963 | 0.2803 | 23.6 MiB |
| [`fast`](#fast) | PASS | bayer | 12-bit | 5000→4996 | 0.1998 | 5.9 MiB |

## Hard limits & trustable operating range

Findings from this hardware + software stack:

1. **Bayer RAW is available** (`SBGGR12` unpacked uint16). Prefer this for signal work; do not demosaic on the Pi during acquisition.
2. **AE/AWB can be forced off**; colour gains stay fixed — good for constant-parameter series.
3. **Long exposures**: requested `ExposureTime` tracks metadata closely through at least the longest test in this run (see long_* sections). `FrameDurationLimits` on this Pi allow multi-minute caps.
4. **ScalerCrop** changes the **RGB main FOV** but does **not** shrink the Bayer raw buffer (still full sensor). For less data / faster raw, use a binned sensor mode (`bin2x2`), not crop alone.
5. **Framerate hard floor** is exposure time (and sensor `FrameDuration`). Suite disk writes (npy+bmp) are much slower than RAM stacking — production should keep frames in RAM.
6. **Bayer width may be stride-padded** (e.g. 4064 vs 4056) — crop using `configured_size` from metadata.
7. Daytime long frames will **saturate** (mean near 4095 on 12-bit). That does not invalidate exposure-control tests.
8. **Suite timing caveat (this run):** early suite builds captured Bayer then RGB as two requests, so long-* `processing_s` ≈ **2× exposure** (e.g. 120 s → ~360 s wall). Exposure metadata itself is still trustworthy. Newer suite code uses a single `capture_request()` for raw+main.

### Sensor modes seen in probe

Count: **15**

Sizes: `1332×990`, `2028×1080`, `2028×1520`, `4056×2160`, `4056×3040`

---

# Per-test details

## `full`

**PASS** — as expected

![preview full](../cam_test_out/20260809T140213/full/frame_000_preview.bmp)

| Field | Value |
|-------|-------|
| Acquisition mode | `bayer` + RGB preview |
| Sensor mode size | `[4056, 3040]` |
| Bayer / science shape | `[3040, 4064]` |
| RGB shape | `[3040, 4056, 3]` |
| Color depth | **12-bit** (`SBGGR12`) |
| Science dtype | `uint16` |
| Science filesize | 23.6 MiB |
| Preview filesize | 898.2 KiB |
| Requested exposure | 0.05 s / µs |
| Got exposure | 0.049963 |
| Exposure check | err=37 µs (0.074%) |
| AnalogueGain | `1.0` (req `1.0`) |
| ColourGains | R=`1.0` B=`1.0` |
| ScalerCrop | `[0, 0, 4056, 3040]` |
| FrameDuration | `85335` µs |
| Science mean | `3617.8707142949647` |
| RGB mean | `187.98824129403266` |

### Timing

| Metric | Seconds |
|--------|---------|
| Requested exposure | 0.05 |
| Got exposure | 0.049963 |
| FrameDuration | 0.085335 |
| Acquire (single request) | 0.6716 |
| Acquire raw (legacy split) | n/a |
| Acquire RGB (legacy split) | n/a |
| Save science `.npy` | 0.0259 |
| Save preview BMP | 0.2303 |
| Processing total (suite path) | 1.0393 |
| Single-request capture | True |

### Framerate estimates

| Estimate | FPS | Period (s) | Meaning |
|----------|-----|------------|---------|
| Exposure-limited max | 11.719 | 0.085335 | Cannot exceed 1/exposure (or FrameDuration) |
| Suite+disk observed | 0.962 | 1.0393 | This harness (raw+rgb+npy+bmp) |
| RAM science estimate | 1.489 | 0.6716 | Keep arrays in RAM, skip disk (production-like) |

### Files

- Science: [`frame_000_bayer.npy`](../cam_test_out/20260809T140213/full/frame_000_bayer.npy)
- Preview: [`frame_000_preview.bmp`](../cam_test_out/20260809T140213/full/frame_000_preview.bmp)
- Meta: [`frame_000_meta.json`](../cam_test_out/20260809T140213/full/frame_000_meta.json)
- Preset: [`preset.json`](../cam_test_out/20260809T140213/full/preset.json)

---

## `bin2x2`

**PASS** — as expected

![preview bin2x2](../cam_test_out/20260809T140213/bin2x2/frame_000_preview.bmp)

| Field | Value |
|-------|-------|
| Acquisition mode | `bayer` + RGB preview |
| Sensor mode size | `[2028, 1520]` |
| Bayer / science shape | `[1520, 2032]` |
| RGB shape | `[1520, 2028, 3]` |
| Color depth | **12-bit** (`SBGGR12`) |
| Science dtype | `uint16` |
| Science filesize | 5.9 MiB |
| Preview filesize | 898.2 KiB |
| Requested exposure | 0.05 s / µs |
| Got exposure | 0.049992 |
| Exposure check | err=8 µs (0.016%) |
| AnalogueGain | `1.0` (req `1.0`) |
| ColourGains | R=`1.0` B=`1.0` |
| ScalerCrop | `[0, 0, 4056, 3040]` |
| FrameDuration | `50303` µs |
| Science mean | `3626.039701292478` |
| RGB mean | `190.12874320910757` |

### Timing

| Metric | Seconds |
|--------|---------|
| Requested exposure | 0.05 |
| Got exposure | 0.049992 |
| FrameDuration | 0.050303 |
| Acquire (single request) | 0.0986 |
| Acquire raw (legacy split) | n/a |
| Acquire RGB (legacy split) | n/a |
| Save science `.npy` | 0.0064 |
| Save preview BMP | 0.0583 |
| Processing total (suite path) | 0.1926 |
| Single-request capture | True |

### Framerate estimates

| Estimate | FPS | Period (s) | Meaning |
|----------|-----|------------|---------|
| Exposure-limited max | 19.880 | 0.050303 | Cannot exceed 1/exposure (or FrameDuration) |
| Suite+disk observed | 5.192 | 0.1926 | This harness (raw+rgb+npy+bmp) |
| RAM science estimate | 10.142 | 0.0986 | Keep arrays in RAM, skip disk (production-like) |

### Files

- Science: [`frame_000_bayer.npy`](../cam_test_out/20260809T140213/bin2x2/frame_000_bayer.npy)
- Preview: [`frame_000_preview.bmp`](../cam_test_out/20260809T140213/bin2x2/frame_000_preview.bmp)
- Meta: [`frame_000_meta.json`](../cam_test_out/20260809T140213/bin2x2/frame_000_meta.json)
- Preset: [`preset.json`](../cam_test_out/20260809T140213/bin2x2/preset.json)

---

## `bin2x2_crop`

**PASS** — as expected

![preview bin2x2_crop](../cam_test_out/20260809T140213/bin2x2_crop/frame_000_preview.bmp)

| Field | Value |
|-------|-------|
| Acquisition mode | `bayer` + RGB preview |
| Sensor mode size | `[1332, 990]` |
| Bayer / science shape | `[990, 1344]` |
| RGB shape | `[990, 1332, 3]` |
| Color depth | **12-bit** (`SBGGR12`) |
| Science dtype | `uint16` |
| Science filesize | 2.5 MiB |
| Preview filesize | 890.7 KiB |
| Requested exposure | 0.05 s / µs |
| Got exposure | 0.049999 |
| Exposure check | err=1 µs (0.002%) |
| AnalogueGain | `1.0` (req `1.0`) |
| ColourGains | R=`1.0` B=`1.0` |
| ScalerCrop | `[696, 528, 2664, 1980]` |
| FrameDuration | `50208` µs |
| Science mean | `3602.7254644660893` |
| RGB mean | `177.33386189219522` |

### Timing

| Metric | Seconds |
|--------|---------|
| Requested exposure | 0.05 |
| Got exposure | 0.049999 |
| FrameDuration | 0.050208 |
| Acquire (single request) | 0.0338 |
| Acquire raw (legacy split) | n/a |
| Acquire RGB (legacy split) | n/a |
| Save science `.npy` | 0.003 |
| Save preview BMP | 0.0285 |
| Processing total (suite path) | 0.0785 |
| Single-request capture | True |

### Framerate estimates

| Estimate | FPS | Period (s) | Meaning |
|----------|-----|------------|---------|
| Exposure-limited max | 19.917 | 0.050208 | Cannot exceed 1/exposure (or FrameDuration) |
| Suite+disk observed | 12.739 | 0.0785 | This harness (raw+rgb+npy+bmp) |
| RAM science estimate | 19.917 | 0.050208 | Keep arrays in RAM, skip disk (production-like) |

### Files

- Science: [`frame_000_bayer.npy`](../cam_test_out/20260809T140213/bin2x2_crop/frame_000_bayer.npy)
- Preview: [`frame_000_preview.bmp`](../cam_test_out/20260809T140213/bin2x2_crop/frame_000_preview.bmp)
- Meta: [`frame_000_meta.json`](../cam_test_out/20260809T140213/bin2x2_crop/frame_000_meta.json)
- Preset: [`preset.json`](../cam_test_out/20260809T140213/bin2x2_crop/preset.json)

---

## `crop`

**UNKNOWN** — ScalerCrop not visible in metadata

![preview crop](../cam_test_out/20260809T140213/crop/frame_000_preview.bmp)

| Field | Value |
|-------|-------|
| Acquisition mode | `bayer` + RGB preview |
| Sensor mode size | `[4056, 3040]` |
| Bayer / science shape | `[3040, 4064]` |
| RGB shape | `[1520, 2028, 3]` |
| Color depth | **12-bit** (`SBGGR12`) |
| Science dtype | `uint16` |
| Science filesize | 23.6 MiB |
| Preview filesize | 898.2 KiB |
| Requested exposure | 0.05 s / µs |
| Got exposure | 0.049963 |
| Exposure check | err=37 µs (0.074%) |
| AnalogueGain | `1.0` (req `1.0`) |
| ColourGains | R=`1.0` B=`1.0` |
| ScalerCrop | `[0, 0, 4056, 3040]` |
| FrameDuration | `85335` µs |
| Science mean | `3616.1508980489793` |
| RGB mean | `186.509863879373` |

### Timing

| Metric | Seconds |
|--------|---------|
| Requested exposure | 0.05 |
| Got exposure | 0.049963 |
| FrameDuration | 0.085335 |
| Acquire (single request) | 0.14 |
| Acquire raw (legacy split) | n/a |
| Acquire RGB (legacy split) | n/a |
| Save science `.npy` | 0.0287 |
| Save preview BMP | 0.0615 |
| Processing total (suite path) | 0.2803 |
| Single-request capture | True |

### Framerate estimates

| Estimate | FPS | Period (s) | Meaning |
|----------|-----|------------|---------|
| Exposure-limited max | 11.719 | 0.085335 | Cannot exceed 1/exposure (or FrameDuration) |
| Suite+disk observed | 3.568 | 0.2803 | This harness (raw+rgb+npy+bmp) |
| RAM science estimate | 7.143 | 0.14 | Keep arrays in RAM, skip disk (production-like) |

### Files

- Science: [`frame_000_bayer.npy`](../cam_test_out/20260809T140213/crop/frame_000_bayer.npy)
- Preview: [`frame_000_preview.bmp`](../cam_test_out/20260809T140213/crop/frame_000_preview.bmp)
- Meta: [`frame_000_meta.json`](../cam_test_out/20260809T140213/crop/frame_000_meta.json)
- Preset: [`preset.json`](../cam_test_out/20260809T140213/crop/preset.json)

---

## `fast`

**PASS** — as expected

![preview fast](../cam_test_out/20260809T140213/fast/frame_000_preview.bmp)

| Field | Value |
|-------|-------|
| Acquisition mode | `bayer` + RGB preview |
| Sensor mode size | `[2028, 1520]` |
| Bayer / science shape | `[1520, 2032]` |
| RGB shape | `[1520, 2028, 3]` |
| Color depth | **12-bit** (`SBGGR12`) |
| Science dtype | `uint16` |
| Science filesize | 5.9 MiB |
| Preview filesize | 898.2 KiB |
| Requested exposure | 0.005 s / µs |
| Got exposure | 0.004996 |
| Exposure check | err=4 µs (0.080%) |
| AnalogueGain | `1.0` (req `1.0`) |
| ColourGains | R=`1.0` B=`1.0` |
| ScalerCrop | `[0, 0, 4056, 3040]` |
| FrameDuration | `22131` µs |
| Science mean | `774.8282457651264` |
| RGB mean | `92.56671240786878` |

### Timing

| Metric | Seconds |
|--------|---------|
| Requested exposure | 0.005 |
| Got exposure | 0.004996 |
| FrameDuration | 0.022131 |
| Acquire (single request) | 0.1011 |
| Acquire raw (legacy split) | n/a |
| Acquire RGB (legacy split) | n/a |
| Save science `.npy` | 0.0066 |
| Save preview BMP | 0.0624 |
| Processing total (suite path) | 0.1998 |
| Single-request capture | True |

### Framerate estimates

| Estimate | FPS | Period (s) | Meaning |
|----------|-----|------------|---------|
| Exposure-limited max | 45.185 | 0.022131 | Cannot exceed 1/exposure (or FrameDuration) |
| Suite+disk observed | 5.766 | 0.173441 | This harness (raw+rgb+npy+bmp) |
| RAM science estimate | 9.891 | 0.1011 | Keep arrays in RAM, skip disk (production-like) |

Burst frames: **4**
Inter-frame mean/min/max: 0.17344146966934204 / 0.16029739379882812 / 0.2006211280822754 s
Approx FPS (manifest): **5.765633800880797**

### Files

- Science: [`frame_000_bayer.npy`](../cam_test_out/20260809T140213/fast/frame_000_bayer.npy)
- Preview: [`frame_000_preview.bmp`](../cam_test_out/20260809T140213/fast/frame_000_preview.bmp)
- Meta: [`frame_000_meta.json`](../cam_test_out/20260809T140213/fast/frame_000_meta.json)
- Preset: [`preset.json`](../cam_test_out/20260809T140213/fast/preset.json)

---

## How to reproduce

```powershell
powershell -File backapp/scripts/run_hq_cam_tests.ps1
python backapp/scripts/generate_hq_capability_report.py
```

Static camera notes: [`pi-hq-camera.md`](pi-hq-camera.md)
