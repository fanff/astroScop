#!/usr/bin/env python3
"""Generate MD report from test_cam_settings_bench output."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def latest_run(root: Path) -> Path:
    runs = [p for p in root.iterdir() if p.is_dir() and (p / "manifest.json").exists()]
    if not runs:
        raise SystemExit(f"No bench runs under {root}")
    return sorted(runs, key=lambda p: p.name)[-1]


def rel(report: Path, target: Path) -> str:
    return Path(os.path.relpath(target, report.parent)).as_posix()


def build(run_dir: Path, report_path: Path) -> str:
    man = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    ok = man.get("ok")
    failures = man.get("failures") or []
    cases = man.get("cases") or {}
    gen = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "# Camera settings / spectrum / reconfig — bench report",
        "",
        f"Generated: **{gen}**  ",
        f"Run: `{run_dir.name}`  ",
        f"Duration: **{man.get('duration_s')} s**  ",
        f"Overall: **{'PASS' if ok else 'FAIL'}**",
        "",
        f"- Manifest: [`manifest.json`]({rel(report_path, run_dir / 'manifest.json')})",
        f"- Run folder: [`{run_dir.as_posix()}`]({rel(report_path, run_dir)})",
        "",
        "## Verdict",
        "",
    ]
    if failures:
        lines.append("Failures:")
        for f in failures:
            lines.append(f"- {f}")
    else:
        lines.append("All assertions passed. Acquisition, fast/slow apply, spectrum, and 8 fps emit policy behaved predictably on full-frame worst case.")
    lines += ["", "## Cases", ""]

    # settings unit
    if "settings_unit" in cases:
        lines += ["### Settings model", "", "```json", json.dumps(cases["settings_unit"], indent=2), "```", ""]

    if "open_full" in cases:
        c = cases["open_full"]
        lines += [
            "### Open full (4056×3040)",
            "",
            f"- open_s: **{c.get('open_s')}**",
            f"- mode_size: `{c.get('mode_size')}`",
            "",
        ]
    prev = run_dir / "full_preview.bmp"
    if prev.exists():
        lines += [f"![full preview]({rel(report_path, prev)})", ""]

    if "capture_full" in cases:
        lines += ["### Capture timings (full RGB)", "", "| i | shape | capture_s | shutter_us | gain |", "|---|-------|-----------|------------|------|"]
        for row in cases["capture_full"]:
            lines.append(
                f"| {row['i']} | {row['shape']} | {row['capture_s']} | {row['shutter_us']} | {row['analog_gain']} |"
            )
        lines.append("")

    if "spectrum" in cases:
        c = cases["spectrum"]
        lines += [
            "### Spectrum (256-bin RGB)",
            "",
            f"- full-res compute: **{c.get('full_res_s')} s**",
            f"- display 640×480 compute: **{c.get('display_640x480_s')} s**",
            f"- bins: {c.get('display_bins')} (hist_len={c.get('hist_len')})",
            f"- display mean R: {c.get('display_mean_r')}",
            "",
        ]
        sp = run_dir / "spectrum_display.json"
        if sp.exists():
            lines.append(f"- [`spectrum_display.json`]({rel(report_path, sp)})")
            lines.append("")

    if "apply_fast" in cases:
        lines += [
            "### Fast apply (set_controls)",
            "",
            "| apply_s | req gain | got | req shutter | got |",
            "|---------|----------|-----|-------------|-----|",
        ]
        for row in cases["apply_fast"]:
            lines.append(
                f"| {row['apply_s']} | {row['req_gain']} | {row['got_gain']} | {row['req_shutter']} | {row['got_shutter']} |"
            )
        lines.append("")

    if "apply_slow" in cases:
        lines += [
            "### Slow apply (reconfigure)",
            "",
            "| apply_s | preset | mode_size |",
            "|---------|--------|-----------|",
        ]
        for row in cases["apply_slow"]:
            lines.append(f"| {row['apply_s']} | {row['preset']} | {row['mode_size']} |")
        lines.append("")

    if "emit_8fps" in cases:
        c = cases["emit_8fps"]
        lines += [
            "### Emit path ≤8 fps (resize + spectrum + JPEG)",
            "",
            f"- emitted/skipped: **{c.get('emitted')}** / **{c.get('skipped')}**",
            f"- emit_fps: **{c.get('emit_fps')}**",
            f"- mean/max process_s: {c.get('mean_process_s')} / {c.get('max_process_s')}",
            "",
        ]

    lines += [
        "## Contract reminders",
        "",
        "- Canonical gain: `analog_gain` only (ISO stripped if present).",
        "- Slow: `sensor_preset` / main size / `include_raw`.",
        "- Fast: shutter, analogue gain, colour gains, ScalerCrop.",
        "- Live spectrum runs on display RGB (256 bins/channel).",
        "- Hard limit: on full 4056×3040, FrameDurationLimits min is ~85 ms — shorter shutter requests clamp.",
        "",
        "```powershell",
        "powershell -File backapp/scripts/run_cam_settings_bench.ps1",
        "```",
        "",
    ]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", nargs="?")
    args = ap.parse_args(argv)
    backapp = Path(__file__).resolve().parents[1]
    root = backapp / "cam_test_out"
    # Prefer dedicated settings bench dirs; also accept any manifest under cam_test_out
    if args.run_dir:
        run_dir = Path(args.run_dir).resolve()
    else:
        # Prefer folders that look like settings bench (have spectrum_display.json)
        cands = [
            p
            for p in root.iterdir()
            if p.is_dir() and (p / "manifest.json").exists() and (p / "spectrum_display.json").exists()
        ]
        run_dir = sorted(cands, key=lambda p: p.name)[-1] if cands else latest_run(root)

    docs = backapp / "docs" / "cam-settings-bench-report.md"
    run_report = run_dir / "REPORT.md"
    text = build(run_dir, docs)
    docs.write_text(text, encoding="utf-8")
    run_report.write_text(build(run_dir, run_report), encoding="utf-8")
    print(docs)
    print(run_report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
