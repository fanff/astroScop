#!/usr/bin/env python3
"""
Build HQ camera capability report markdown from a pulled suite run directory.

Usage:
  python backapp/scripts/generate_hq_capability_report.py backapp/cam_test_out/<run_id>
  python backapp/scripts/generate_hq_capability_report.py   # latest under cam_test_out/
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def human_bytes(n):
    if n is None:
        return "n/a"
    n = float(n)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TiB"


def load_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def rel_to(report_path: Path, target: Path) -> str:
    try:
        return Path(os.path.relpath(target, report_path.parent)).as_posix()
    except Exception:
        return target.as_posix()


def first_meta(preset_dir: Path):
    metas = sorted(preset_dir.glob("frame_*_meta.json"))
    if not metas:
        return None
    return load_json(metas[0])


def all_metas(preset_dir: Path):
    return [load_json(p) for p in sorted(preset_dir.glob("frame_*_meta.json"))]


def exposure_ok(meta, tol_frac=0.02, tol_abs_us=500):
    req = meta.get("requested_shutter")
    got = meta.get("used", {}).get("shutterSpeed")
    if req is None or got is None:
        return None, "missing shutter metadata"
    try:
        req_f = float(req)
        got_f = float(got)
    except Exception:
        return False, f"unparseable shutter req={req} got={got}"
    err = abs(got_f - req_f)
    ok = err <= max(tol_abs_us, tol_frac * req_f)
    return ok, f"err={err:.0f} µs ({100.0 * err / req_f:.3f}%)"


def verdict_line(ok, detail):
    if ok is True:
        return f"**PASS** — {detail}"
    if ok is False:
        return f"**FAIL** — {detail}"
    return f"**UNKNOWN** — {detail}"


def bit_depth_from_meta(meta, preset_json):
    raw = meta.get("raw") or {}
    fmt = raw.get("format") or ""
    if "12" in str(fmt):
        return 12, str(fmt)
    if "10" in str(fmt):
        return 10, str(fmt)
    if "8" in str(fmt):
        return 8, str(fmt)
    sensor = (preset_json or {}).get("config", {}).get("sensor") or {}
    if sensor.get("bit_depth"):
        return int(sensor["bit_depth"]), str(fmt or "unknown")
    return None, str(fmt or "unknown")


def estimate_fps(meta, inter_frame=None):
    """Estimate achievable fps bounds for this acquisition pattern."""
    timing = meta.get("timing") or {}
    exp = timing.get("got_exposure_s") or timing.get("requested_exposure_s")
    fd = timing.get("frame_duration_s")
    proc = timing.get("processing_s") or meta.get("capture_s")
    acquire = timing.get("acquire_s")
    if acquire is None:
        acquire = timing.get("acquire_raw_s")
    if acquire is None:
        acquire = timing.get("acquire_rgb_s")

    # Hard floor from exposure / frame duration
    period_exp = fd if fd else exp
    # Observed wall period when saving to disk (suite pattern: raw+rgb+npy+bmp)
    period_disk = inter_frame or proc

    # RAM-only science path estimate: exposure-limited + raw acquire overhead (no disk)
    ram_period = None
    if period_exp is not None:
        overhead = 0.0
        if acquire is not None and period_exp is not None:
            # acquire includes waiting for exposure; overhead ~= acquire - exposure
            overhead = max(0.0, float(acquire) - float(period_exp))
        ram_period = float(period_exp) + overhead

    out = {
        "exposure_limited_fps_max": (1.0 / float(period_exp)) if period_exp and period_exp > 0 else None,
        "disk_suite_fps": (1.0 / float(period_disk)) if period_disk and period_disk > 0 else None,
        "ram_estimate_fps_max": (1.0 / float(ram_period)) if ram_period and ram_period > 0 else None,
        "period_exp_s": period_exp,
        "period_disk_s": period_disk,
        "period_ram_est_s": ram_period,
    }
    return out


def section_for_preset(run_dir: Path, report_path: Path, name: str, manifest_entry: dict) -> str:
    preset_dir = run_dir / name
    preset_json = load_json(preset_dir / "preset.json") if (preset_dir / "preset.json").exists() else {}
    metas = all_metas(preset_dir)
    meta0 = metas[0] if metas else None

    lines = [f"## `{name}`", ""]

    if meta0 is None:
        lines += [verdict_line(False, "no frame meta found"), ""]
        return "\n".join(lines)

    ok_exp, exp_detail = exposure_ok(meta0)
    path = meta0.get("capture_path")
    bit_depth, fmt = bit_depth_from_meta(meta0, preset_json)
    shape = meta0.get("science_shape")
    rgb_shape = meta0.get("rgb_shape")
    cfg = preset_json.get("config") or {}
    mode_size = cfg.get("mode_size") or preset_json.get("mode_size")
    scaler = meta0.get("used", {}).get("ScalerCrop")
    timing = meta0.get("timing") or {}

    # Overall verdict
    notes = []
    if path != "bayer":
        notes.append(f"capture_path={path} (expected bayer)")
    if ok_exp is False:
        notes.append(f"exposure mismatch ({exp_detail})")
    if name.startswith("long_") and meta0.get("science_mean") is not None:
        # 12-bit sat ~4095
        mean = float(meta0["science_mean"])
        if bit_depth == 12 and mean > 4000:
            notes.append("daytime saturation expected (near 12-bit full scale)")
        elif bit_depth == 12 and mean > 3500:
            notes.append("very bright / near saturation (daytime)")
    overall_ok = (path == "bayer") and (ok_exp is not False)
    if name == "crop":
        # ScalerCrop applied on RGB; raw still full — expected limitation
        if scaler and list(scaler) != [0, 0, 4056, 3040]:
            notes.append("ScalerCrop applied to RGB FOV; Bayer buffer remains full-sensor (known limit)")
        else:
            notes.append("ScalerCrop not visible in metadata")
            overall_ok = False

    if overall_ok:
        lines.append(verdict_line(True, "; ".join(notes) if notes else "as expected"))
    else:
        lines.append(verdict_line(False if ok_exp is False else None, "; ".join(notes) if notes else "see details"))
    lines.append("")

    preview = preset_dir / "frame_000_preview.bmp"
    if preview.exists():
        lines += [f"![preview {name}]({rel_to(report_path, preview)})", ""]

    science = None
    for cand in sorted(preset_dir.glob("frame_000_*.npy")):
        science = cand
        break
    filesize = meta0.get("science_filesize_bytes")
    if filesize is None and science and science.exists():
        filesize = science.stat().st_size

    inter = None
    if name == "fast" and manifest_entry.get("inter_frame_s_mean"):
        inter = manifest_entry["inter_frame_s_mean"]
    fps = estimate_fps(meta0, inter_frame=inter)

    lines += [
        "| Field | Value |",
        "|-------|-------|",
        f"| Acquisition mode | `{path}` + RGB preview |",
        f"| Sensor mode size | `{mode_size}` |",
        f"| Bayer / science shape | `{shape}` |",
        f"| RGB shape | `{rgb_shape}` |",
        f"| Color depth | **{bit_depth}-bit** (`{fmt}`) |" if bit_depth else f"| Color depth | `{fmt}` |",
        f"| Science dtype | `{meta0.get('science_dtype')}` |",
        f"| Science filesize | {human_bytes(filesize)} |",
        f"| Preview filesize | {human_bytes(meta0.get('preview_filesize_bytes'))} |",
        f"| Requested exposure | {timing.get('requested_exposure_s', meta0.get('requested_shutter'))} s / µs |",
        f"| Got exposure | {timing.get('got_exposure_s', meta0.get('used', {}).get('shutterSpeed'))} |",
        f"| Exposure check | {exp_detail} |",
        f"| AnalogueGain | `{meta0.get('used', {}).get('analog_gain')}` (req `{meta0.get('requested_analog_gain')}`) |",
        f"| ColourGains | R=`{meta0.get('used', {}).get('redgain')}` B=`{meta0.get('used', {}).get('bluegain')}` |",
        f"| ScalerCrop | `{scaler}` |",
        f"| FrameDuration | `{meta0.get('used', {}).get('FrameDuration')}` µs |",
        f"| Science mean | `{meta0.get('science_mean')}` |",
        f"| RGB mean | `{meta0.get('rgb_mean')}` |",
        "",
        "### Timing",
        "",
        "| Metric | Seconds |",
        "|--------|---------|",
        f"| Requested exposure | {timing.get('requested_exposure_s', 'n/a')} |",
        f"| Got exposure | {timing.get('got_exposure_s', 'n/a')} |",
        f"| FrameDuration | {timing.get('frame_duration_s', 'n/a')} |",
        f"| Acquire (single request) | {timing.get('acquire_s', 'n/a')} |",
        f"| Acquire raw (legacy split) | {timing.get('acquire_raw_s', 'n/a')} |",
        f"| Acquire RGB (legacy split) | {timing.get('acquire_rgb_s', 'n/a')} |",
        f"| Save science `.npy` | {timing.get('save_science_s', 'n/a')} |",
        f"| Save preview BMP | {timing.get('save_preview_s', 'n/a')} |",
        f"| Processing total (suite path) | {timing.get('processing_s', meta0.get('capture_s'))} |",
        f"| Single-request capture | {timing.get('single_request', 'n/a (legacy split)')} |",
        "",
        "### Framerate estimates",
        "",
        "| Estimate | FPS | Period (s) | Meaning |",
        "|----------|-----|------------|---------|",
        f"| Exposure-limited max | {_fmt_fps(fps['exposure_limited_fps_max'])} | {_fmt_num(fps['period_exp_s'])} | Cannot exceed 1/exposure (or FrameDuration) |",
        f"| Suite+disk observed | {_fmt_fps(fps['disk_suite_fps'])} | {_fmt_num(fps['period_disk_s'])} | This harness (raw+rgb+npy+bmp) |",
        f"| RAM science estimate | {_fmt_fps(fps['ram_estimate_fps_max'])} | {_fmt_num(fps['period_ram_est_s'])} | Keep arrays in RAM, skip disk (production-like) |",
        "",
    ]

    if name == "fast" and len(metas) > 1:
        dts = [m.get("inter_frame_s") for m in metas if m.get("inter_frame_s") is not None]
        # first frame inter_frame includes setup; still report
        lines += [
            f"Burst frames: **{len(metas)}**",
            f"Inter-frame mean/min/max: "
            f"{manifest_entry.get('inter_frame_s_mean')} / "
            f"{manifest_entry.get('inter_frame_s_min')} / "
            f"{manifest_entry.get('inter_frame_s_max')} s",
            f"Approx FPS (manifest): **{manifest_entry.get('approx_fps')}**",
            "",
        ]

    # File links
    lines.append("### Files")
    lines.append("")
    if science and science.exists():
        lines.append(f"- Science: [`{science.name}`]({rel_to(report_path, science)})")
    if preview.exists():
        lines.append(f"- Preview: [`{preview.name}`]({rel_to(report_path, preview)})")
    meta_path = preset_dir / "frame_000_meta.json"
    if meta_path.exists():
        lines.append(f"- Meta: [`frame_000_meta.json`]({rel_to(report_path, meta_path)})")
    pj = preset_dir / "preset.json"
    if pj.exists():
        lines.append(f"- Preset: [`preset.json`]({rel_to(report_path, pj)})")
    lines.append("")
    return "\n".join(lines)


def _fmt_fps(v):
    if v is None:
        return "n/a"
    return f"{v:.3f}"


def _fmt_num(v):
    if v is None:
        return "n/a"
    return f"{float(v):.6g}"


def build_report(run_dir: Path, report_path: Path) -> str:
    manifest = load_json(run_dir / "manifest.json")
    probe = load_json(run_dir / "probe.json") if (run_dir / "probe.json").exists() else {}

    # Order sections logically
    names = [p["name"] for p in manifest.get("presets", [])]
    spatial = [n for n in ("full", "bin2x2", "bin2x2_crop", "crop") if n in names]
    longs = sorted([n for n in names if n.startswith("long_")], key=lambda s: _long_sort_key(s))
    other = [n for n in names if n not in spatial and n not in longs]

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "# Pi HQ Camera (IMX477) — capability report",
        "",
        f"Generated: **{generated}**  ",
        f"Suite run: `{run_dir.name}`  ",
        f"Host: `piscope` / Raspberry Pi HQ camera  ",
        f"Suite duration: **{manifest.get('duration_s')} s**  ",
        f"Bayer raw enabled end-to-end: **{manifest.get('raw_enabled_final')}**",
        "",
        "This report aggregates the live suite outputs so you can eyeball what the hardware",
        "can and cannot do (modes, bit depth, exposure trust, and timing/framerate limits).",
        "",
        f"- Manifest: [`manifest.json`]({rel_to(report_path, run_dir / 'manifest.json')})",
        f"- Probe: [`probe.json`]({rel_to(report_path, run_dir / 'probe.json')})" if (run_dir / "probe.json").exists() else "",
        f"- Run folder: [`{run_dir.as_posix()}`]({rel_to(report_path, run_dir)})",
        "",
        "## Executive summary",
        "",
    ]

    # Summary table
    lines += [
        "| Test | Verdict | Mode | Depth | Exposure req→got | Proc (s) | Filesize |",
        "|------|---------|------|-------|------------------|----------|----------|",
    ]
    by_name = {p["name"]: p for p in manifest.get("presets", [])}
    for name in spatial + longs + other:
        preset_dir = run_dir / name
        meta0 = first_meta(preset_dir)
        if not meta0:
            lines.append(f"| `{name}` | missing | | | | | |")
            continue
        ok_exp, _ = exposure_ok(meta0)
        path = meta0.get("capture_path")
        bit_depth, fmt = bit_depth_from_meta(meta0, {})
        timing = meta0.get("timing") or {}
        proc = timing.get("processing_s", meta0.get("capture_s"))
        fs = meta0.get("science_filesize_bytes")
        if fs is None:
            for cand in preset_dir.glob("frame_000_*.npy"):
                fs = cand.stat().st_size
                break
        verdict = "PASS" if path == "bayer" and ok_exp is not False else "CHECK"
        if ok_exp is False:
            verdict = "FAIL"
        req = meta0.get("requested_shutter")
        got = meta0.get("used", {}).get("shutterSpeed")
        lines.append(
            f"| [`{name}`](#{name.replace('_', '-')}) | {verdict} | {path} | {bit_depth}-bit | {req}→{got} | {proc} | {human_bytes(fs)} |"
        )

    lines += [
        "",
        "## Hard limits & trustable operating range",
        "",
        "Findings from this hardware + software stack:",
        "",
        "1. **Bayer RAW is available** (`SBGGR12` unpacked uint16). Prefer this for signal work; do not demosaic on the Pi during acquisition.",
        "2. **AE/AWB can be forced off**; colour gains stay fixed — good for constant-parameter series.",
        "3. **Long exposures**: requested `ExposureTime` tracks metadata closely through at least the longest test in this run (see long_* sections). `FrameDurationLimits` on this Pi allow multi-minute caps.",
        "4. **ScalerCrop** changes the **RGB main FOV** but does **not** shrink the Bayer raw buffer (still full sensor). For less data / faster raw, use a binned sensor mode (`bin2x2`), not crop alone.",
        "5. **Framerate hard floor** is exposure time (and sensor `FrameDuration`). Suite disk writes (npy+bmp) are much slower than RAM stacking — production should keep frames in RAM.",
        "6. **Bayer width may be stride-padded** (e.g. 4064 vs 4056) — crop using `configured_size` from metadata.",
        "7. Daytime long frames will **saturate** (mean near 4095 on 12-bit). That does not invalidate exposure-control tests.",
        "8. **Suite timing caveat (this run):** early suite builds captured Bayer then RGB as two requests, so long-* `processing_s` ≈ **2× exposure** (e.g. 120 s → ~360 s wall). Exposure metadata itself is still trustworthy. Newer suite code uses a single `capture_request()` for raw+main.",
        "",
    ]

    if probe:
        modes = probe.get("sensor_modes") or []
        lines += [
            "### Sensor modes seen in probe",
            "",
            f"Count: **{len(modes)}**",
            "",
        ]
        # compact unique sizes
        sizes = sorted({tuple(m.get("size") or ()) for m in modes})
        lines.append("Sizes: " + ", ".join(f"`{s[0]}×{s[1]}`" for s in sizes if len(s) == 2))
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("# Per-test details")
    lines.append("")

    for name in spatial + longs + other:
        lines.append(section_for_preset(run_dir, report_path, name, by_name.get(name, {})))
        lines.append("---")
        lines.append("")

    lines += [
        "## How to reproduce",
        "",
        "```powershell",
        "powershell -File backapp/scripts/run_hq_cam_tests.ps1",
        "python backapp/scripts/generate_hq_capability_report.py",
        "```",
        "",
        "Static camera notes: [`pi-hq-camera.md`](pi-hq-camera.md)",
        "",
    ]
    return "\n".join(lines)


def _long_sort_key(name: str):
    # long_1s, long_30s, long_120s, long_5000us …
    if name.startswith("long_") and name.endswith("s") and name[5:-1].isdigit():
        return int(name[5:-1])
    return 10**9


def latest_run(root: Path) -> Path:
    runs = [p for p in root.iterdir() if p.is_dir() and (p / "manifest.json").exists()]
    if not runs:
        raise SystemExit(f"No suite runs with manifest.json under {root}")
    return sorted(runs, key=lambda p: p.name)[-1]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", nargs="?", default=None, help="cam_test_out/<run_id> directory")
    ap.add_argument(
        "--out",
        default=None,
        help="report markdown path (default: docs/hq-camera-capability-report.md + run_dir/REPORT.md)",
    )
    args = ap.parse_args(argv)

    backapp = Path(__file__).resolve().parents[1]
    out_root = backapp / "cam_test_out"
    run_dir = Path(args.run_dir) if args.run_dir else latest_run(out_root)
    run_dir = run_dir.resolve()

    docs_report = backapp / "docs" / "hq-camera-capability-report.md"
    run_report = run_dir / "REPORT.md"
    report_path = Path(args.out).resolve() if args.out else docs_report

    text = build_report(run_dir, report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(text, encoding="utf-8")
    # Also drop a copy next to the artifacts with links relative to that folder
    run_text = build_report(run_dir, run_report)
    run_report.write_text(run_text, encoding="utf-8")
    print(report_path)
    print(run_report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
