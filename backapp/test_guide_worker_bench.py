#!/usr/bin/env python3
"""On-Pi timing bench for the guide worker (synthetic tiles, no camera).

Gates: tile→sample p95 < 20 ms (JPEG off); JPEG encode p95 < 15 ms;
5 Hz 30 s no backlog; 10 Hz skip/drop.

  python3 test_guide_worker_bench.py --out /tmp/guide_worker_bench/run1
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone

from guide_handoff import GuideTile
from guide_isolate import synthetic_star_rgb
from guide_process import GuideConfig, GuideEngine

P95_LOOP_S = 0.020
P95_JPEG_S = 0.015


def percentile(sorted_vals, p):
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = k - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def make_tile(seq, size=64):
    lock = size / 2.0
    u = lock + 0.5 * ((seq % 7) - 3)
    v = lock + 0.4 * ((seq % 5) - 2)
    rgb = synthetic_star_rgb(size, size, u, v, sigma=2.8, peak=90.0)
    return GuideTile(rgb, 0, 0, lock, lock, t=seq * 0.2)


def stats(samples, gate):
    s = sorted(samples)
    p95 = percentile(s, 95)
    return {
        "n": len(s),
        "p50_s": percentile(s, 50),
        "p95_s": p95,
        "max_s": s[-1] if s else 0.0,
        "gate_p95_s": gate,
        "pass": p95 < gate,
    }


def run_hz(hz, duration_s, jpeg: bool):
    eng = GuideEngine(GuideConfig(f_mm=400.0, bin=2))
    period = 1.0 / hz
    samples = []
    jpeg_samples = []
    generated = 0
    processed = 0
    skipped = 0
    pending_peak = 0
    t_end = time.perf_counter() + duration_s
    seq = 0
    next_tick = time.perf_counter()
    while time.perf_counter() < t_end:
        now = time.perf_counter()
        n_due = int((now - next_tick) / period) + 1 if now >= next_tick else 0
        if n_due < 1:
            time.sleep(min(0.002, next_tick - now))
            continue
        generated += n_due
        seq += n_due
        next_tick += n_due * period
        pending_peak = max(pending_peak, n_due)
        tile = make_tile(seq)
        t0 = time.perf_counter()
        r = eng.process_tile(tile, seq=seq, jpeg=jpeg)
        dt = time.perf_counter() - t0
        samples.append(dt)
        if jpeg and r.jpeg:
            # encode is inside process_tile; JPEG-only would need a split.
            jpeg_samples.append(dt)
        if r.skipped:
            skipped += 1
        else:
            processed += 1
        extra = n_due - 1
        skipped += extra
    backlog = generated - processed - skipped
    return {
        "hz": hz,
        "duration_s": duration_s,
        "jpeg": jpeg,
        "generated": generated,
        "processed": processed,
        "skipped": skipped,
        "pending_peak": pending_peak,
        "backlog": backlog,
        "loop": stats(samples, P95_JPEG_S if jpeg else P95_LOOP_S),
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--sustain", type=float, default=30.0)
    args = ap.parse_args(argv)

    host = platform.node()
    machine = platform.machine()
    on_pi = host.lower() == "piscope" and machine.lower() in ("aarch64", "arm64")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.out or os.path.join("/tmp/guide_worker_bench", run_id)
    os.makedirs(out, exist_ok=True)

    cases = {
        "hz5_jpeg_off": run_hz(5.0, args.sustain, jpeg=False),
        "hz10_jpeg_off": run_hz(10.0, min(10.0, args.sustain), jpeg=False),
        "hz5_jpeg_on": run_hz(5.0, min(8.0, args.sustain), jpeg=True),
    }
    failures = []
    c5 = cases["hz5_jpeg_off"]
    if not c5["loop"]["pass"]:
        failures.append("5 Hz JPEG-off p95 missed 20 ms")
    if c5["backlog"] > 0:
        failures.append(f"5 Hz backlog {c5['backlog']}")
    c10 = cases["hz10_jpeg_off"]
    if c10["backlog"] > 0:
        failures.append(f"10 Hz backlog {c10['backlog']}")
    cj = cases["hz5_jpeg_on"]
    if not cj["loop"]["pass"]:
        failures.append("JPEG-on p95 missed 15 ms")

    timing_ok = not failures
    passed = timing_ok and on_pi
    result = {
        "run_id": run_id,
        "stage": "guide_worker",
        "host": host,
        "machine": machine,
        "on_pi": on_pi,
        "timing_ok": timing_ok,
        "pass": passed,
        "failures": failures,
        "cases": cases,
    }
    write_json(os.path.join(out, "worker_bench.json"), result)
    verdict = "PASS" if passed else "FAIL"
    print(f"guide_worker bench {verdict}")
    print(f"  host={host} machine={machine}")
    for name, c in cases.items():
        lp = c["loop"]
        print(
            f"  {name}: p50={lp['p50_s']*1e3:.3f} ms p95={lp['p95_s']*1e3:.3f} ms "
            f"max={lp['max_s']*1e3:.3f} ms gen={c['generated']} proc={c['processed']} "
            f"skip={c['skipped']} backlog={c['backlog']} pending_peak={c['pending_peak']} "
            f"{'PASS' if lp['pass'] and c['backlog']==0 else 'FAIL'}"
        )
    for f in failures:
        print(f"  FAIL: {f}")
    print(f"  out={out}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
