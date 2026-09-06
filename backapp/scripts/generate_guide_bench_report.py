#!/usr/bin/env python3
"""Write backapp/docs/guide-bench-report.md from pulled Pi bench JSON.

Merges new files into docs/guide-bench-latest/ so a geom-only or isolate-only
run does not wipe the other phase's Pi numbers.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone

STAGE_FILES = {
    "geom": "geom_bench.json",
    "isolate": "isolate_bench.json",
    "crop": "crop_bench.json",
    "worker": "worker_bench.json",
}


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def is_pi(blob):
    host = str(blob.get("host") or "").lower()
    machine = str(blob.get("machine") or "").lower()
    return host == "piscope" and machine in ("aarch64", "arm64")


def fmt_us(s):
    return f"{float(s) * 1e6:.2f} µs"


def fmt_ms(s):
    return f"{float(s) * 1e3:.3f} ms"


def geom_section(geom, rel_latest):
    on_pi = is_pi(geom)
    timing_ok = bool(geom.get("pass"))
    passed = timing_ok and on_pi
    return passed, [
        "## Phase B — `guide_geom` (`pixels_to_axis_steps`)",
        "",
        f"- host: **{geom.get('host', '?')}** (`{geom.get('machine', '?')}`)",
        f"- iters: **{geom['iters']}**",
        f"- tile_size: n/a (scalar math)",
        f"- p50: **{fmt_us(geom['p50_s'])}**",
        f"- p95: **{fmt_us(geom['p95_s'])}**",
        f"- max: **{fmt_us(geom['max_s'])}**",
        f"- gate: p95 **< {float(geom['gate_p95_s']) * 1e3:.1f} ms** → **{'PASS' if timing_ok else 'FAIL'}**",
        f"- Pi host check: **{'PASS' if on_pi else 'FAIL'}**",
        "",
        f"Raw: [`geom_bench.json`]({rel_latest}/geom_bench.json)",
        "",
    ]


def isolate_section(iso, rel_latest):
    on_pi = is_pi(iso)
    timing_ok = all(c.get("pass") for c in iso.get("cases", []))
    passed = timing_ok and on_pi
    lines = [
        "## Phase C — `guide_isolate` (`isolate_star`)",
        "",
        f"- host: **{iso.get('host', '?')}** (`{iso.get('machine', '?')}`)",
        f"- Pi host check: **{'PASS' if on_pi else 'FAIL'}**",
        "",
        "| tile | SNR | iters | p50 | p95 | max | gate | result |",
        "|------|-----|-------|-----|-----|-----|------|--------|",
    ]
    for c in iso.get("cases", []):
        lines.append(
            f"| {c['tile']}² | {c.get('snr_level', '')} | {c['iters']} | "
            f"{fmt_ms(c['p50_s'])} | {fmt_ms(c['p95_s'])} | {fmt_ms(c['max_s'])} | "
            f"< {float(c['gate_p95_s']) * 1e3:.1f} ms | **{'PASS' if c['pass'] else 'FAIL'}** |"
        )
    lines.extend(
        [
            "",
            f"Timing: **{'PASS' if timing_ok else 'FAIL'}**. "
            f"Raw: [`isolate_bench.json`]({rel_latest}/isolate_bench.json)",
            "",
        ]
    )
    return passed, lines


def crop_section(crop, rel_latest):
    on_pi = is_pi(crop)
    timing_ok = bool(crop.get("timing_ok", crop.get("pass")))
    passed = timing_ok and on_pi
    cases = crop.get("cases") or {}
    lines = [
        "## Phase D — `guide_handoff` (live RGB crop vs off)",
        "",
        f"- host: **{crop.get('host', '?')}** (`{crop.get('machine', '?')}`)",
        f"- Pi host check: **{'PASS' if on_pi else 'FAIL'}**",
        f"- timing: **{'PASS' if timing_ok else 'FAIL'}**",
        "",
    ]
    for key, label in (
        ("crop_off", "crop off"),
        ("crop_on_64", "crop on 64²"),
        ("crop_on_128", "crop on 128²"),
    ):
        c = cases.get(key) or {}
        ext = c.get("extract") or {}
        hof = c.get("handoff") or {}
        lines.append(
            f"- **{label}**: frame_time **{c.get('frame_time_ms', 0):.2f} ms**, "
            f"emit_fps **{c.get('emit_fps', 0):.3f}**"
            + (
                f", extract p95 **{fmt_ms(ext['p95_s'])}**, handoff p95 **{fmt_ms(hof['p95_s'])}**"
                if ext
                else ""
            )
        )
    fails = crop.get("failures") or []
    if fails:
        lines.append("")
        lines.append("Failures:")
        for f in fails:
            lines.append(f"- {f}")
    lines.extend(
        [
            "",
            f"Raw: [`crop_bench.json`]({rel_latest}/crop_bench.json)",
            "",
        ]
    )
    return passed, lines


def worker_section(w, rel_latest):
    on_pi = is_pi(w)
    timing_ok = bool(w.get("timing_ok", w.get("pass")))
    passed = timing_ok and on_pi
    cases = w.get("cases") or {}
    lines = [
        "## Phase E — `guideControl` (synthetic tile → PI)",
        "",
        f"- host: **{w.get('host', '?')}** (`{w.get('machine', '?')}`)",
        f"- Pi host check: **{'PASS' if on_pi else 'FAIL'}**",
        f"- timing: **{'PASS' if timing_ok else 'FAIL'}**",
        "",
        "| case | p50 | p95 | max | gen | proc | backlog | result |",
        "|------|-----|-----|-----|-----|------|---------|--------|",
    ]
    for name, c in cases.items():
        lp = c.get("loop") or {}
        ok = bool(lp.get("pass")) and int(c.get("backlog") or 0) == 0
        lines.append(
            f"| {name} | {fmt_ms(lp.get('p50_s', 0))} | {fmt_ms(lp.get('p95_s', 0))} | "
            f"{fmt_ms(lp.get('max_s', 0))} | {c.get('generated', 0)} | {c.get('processed', 0)} | "
            f"{c.get('backlog', 0)} | **{'PASS' if ok else 'FAIL'}** |"
        )
    fails = w.get("failures") or []
    if fails:
        lines.append("")
        lines.append("Failures:")
        for f in fails:
            lines.append(f"- {f}")
    lines.extend(["", f"Raw: [`worker_bench.json`]({rel_latest}/worker_bench.json)", ""])
    return passed, lines


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: generate_guide_bench_report.py <pulled_out_dir> [docs_dir]", file=sys.stderr)
        return 2
    out_dir = argv[0]
    docs_dir = argv[1] if len(argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "docs")
    latest = os.path.join(docs_dir, "guide-bench-latest")
    os.makedirs(latest, exist_ok=True)

    for name in STAGE_FILES.values():
        src = os.path.join(out_dir, name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(latest, name))

    geom_path = os.path.join(latest, STAGE_FILES["geom"])
    iso_path = os.path.join(latest, STAGE_FILES["isolate"])
    crop_path = os.path.join(latest, STAGE_FILES["crop"])
    worker_path = os.path.join(latest, STAGE_FILES["worker"])
    geom = load_json(geom_path) if os.path.isfile(geom_path) else None
    iso = load_json(iso_path) if os.path.isfile(iso_path) else None
    crop = load_json(crop_path) if os.path.isfile(crop_path) else None
    worker = load_json(worker_path) if os.path.isfile(worker_path) else None
    if geom is None and iso is None and crop is None and worker is None:
        print("no bench json in latest/", file=sys.stderr)
        return 2

    rel_latest = os.path.relpath(latest, docs_dir).replace("\\", "/")
    rel_out = os.path.relpath(out_dir, docs_dir).replace("\\", "/")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    section_pass = []
    body = []
    host = "?"
    machine = "?"
    if geom is not None:
        p, lines = geom_section(geom, rel_latest)
        section_pass.append(p)
        body.extend(lines)
        host = geom.get("host", host)
        machine = geom.get("machine", machine)
    if iso is not None:
        p, lines = isolate_section(iso, rel_latest)
        section_pass.append(p)
        body.extend(lines)
        host = iso.get("host", host)
        machine = iso.get("machine", machine)
    if crop is not None:
        p, lines = crop_section(crop, rel_latest)
        section_pass.append(p)
        body.extend(lines)
        host = crop.get("host", host)
        machine = crop.get("machine", machine)
    if worker is not None:
        p, lines = worker_section(worker, rel_latest)
        section_pass.append(p)
        body.extend(lines)
        host = worker.get("host", host)
        machine = worker.get("machine", machine)

    overall = all(section_pass) if section_pass else False
    verdict = "PASS" if overall else "FAIL"
    missing = []
    if geom is None:
        missing.append("geom not in latest/")
    if iso is None:
        missing.append("isolate not in latest/")
    if crop is None:
        missing.append("crop not in latest/")
    if worker is None:
        missing.append("worker not in latest/")
    note = f" ({'; '.join(missing)})" if missing else ""

    lines = [
        "# Guide loop — bench report",
        "",
        f"Generated: **{now}**  ",
        f"This pull: [`{os.path.basename(out_dir)}`]({rel_out})  ",
        f"Merged latest: [`guide-bench-latest`]({rel_latest})  ",
        f"Host: **{host}** (`{machine}`)  ",
        f"Overall: **{verdict}**{note}",
        "",
        "Pi is the timing authority (evolution §10). A section without `host=piscope` / `aarch64` is not a phase gate.",
        "",
    ]
    lines.extend(body)
    lines.append("Later phases append hub / UI sections here.")
    lines.append("")

    report = os.path.join(docs_dir, "guide-bench-report.md")
    with open(report, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(report)
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
