# Offline Bayer → Siril CFA FITS

Convert astroScop science captures (`frame_*_bayer.npy` + `frame_*_meta.json`) into a numbered series of **undebayered CFA** FITS files that Siril can stack.

This package is for an **x86 processing PC**. It is not deployed on the Pi or telescope.

## Requirements

- Python ≥ 3.12
- [uv](https://github.com/astral-sh/uv) (recommended)

## Install / run

```powershell
cd postprocessing
uv sync --group dev
uv run astroscop-pp convert D:\cko\astropic\sat1 -o D:\cko\astropic\sat1_siril --basename lights
```

Useful flags:

| Flag | Meaning |
|------|---------|
| `--limit N` | Convert only the first N frames (smoke test) |
| `--dry-run` | List planned outputs without writing |
| `--overwrite` | Replace existing `.fits` |
| `--no-recursive` | Do not scan one subdirectory level (`bigs/`, etc.) |

## What the converter does

1. Pairs `*_bayer.npy` with `*_meta.json`, sorted by `sequence`
2. Crops stride padding using `raw.configured_size` `[W, H]` (e.g. 2032 → 2028)
3. Maps `SBGGR12` → FITS `BAYERPAT=BGGR` (no demosaic)
4. Writes `lights_00001.fits`, `lights_00002.fits`, … plus `conversion_manifest.json`

## Siril

1. Set the working directory to the output folder.
2. In **Conversion**, add the `.fits` files and use sequence name `lights` (or load the sequence if already named).
3. Keep **Debayer unchecked** through calibration / registration of OSC lights; debayer after preprocessing if you follow a colour workflow.
4. For current HQ captures, Bayer pattern should read as **BGGR**.

## Tests

```powershell
cd postprocessing
uv run pytest
```
