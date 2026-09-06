#!/usr/bin/env python3
"""On-Pi timing bench for star isolation (no camera).

Gates (evolution §10):
  64x64  p95 < 5 ms
  128x128 p95 < 15 ms

  python3 test_guide_isolate_bench.py --out /tmp/guide_isolate_bench/run1
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone

import numpy as np

from guide_isolate import isolate_star, synthetic_star_rgb

GATES = {64: 0.005, 128: 0.015}
SNR_PEAKS = (("high", 90.0), ("mid", 40.0), ("low", 22.0))
DEFAULT_ITERS = 400


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


def bench_case(size, peak, iters, rng):
    lock = size / 2.0
    tiles = []
    for i in range(iters):
        u = lock + 0.4 * ((i % 7) - 3)
        v = lock + 0.3 * ((i % 5) - 2)
        tiles.append(synthetic_star_rgb(size, size, u, v, sigma=2.8, peak=peak, rng=rng))
    isolate_star(tiles[0], lock, lock)  # warmup
    samples = []
    for tile in tiles:
        t0 = time.perf_counter()
        isolate_star(tile, lock, lock)
        samples.append(time.perf_counter() - t0)
    samples.sort()
    gate = GATES[size]
    p95 = percentile(samples, 95)
    return {
        "tile": size,
        "peak": peak,
        "iters": iters,
        "p50_s": percentile(samples, 50),
        "p95_s": p95,
        "max_s": samples[-1],
        "gate_p95_s": gate,
        "pass": p95 < gate,
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--iters", type=int, default=DEFAULT_ITERS)
    args = ap.parse_args(argv)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.out or os.path.join("/tmp/guide_isolate_bench", run_id)
    os.makedirs(out, exist_ok=True)

    rng = np.random.default_rng(7)
    cases = []
    for size in (64, 128):
        n = int(args.iters) if size == 64 else max(80, int(args.iters) // 2)
        for name, peak in SNR_PEAKS:
            c = bench_case(size, peak, n, rng)
            c["snr_level"] = name
            cases.append(c)

    timing_ok = all(c["pass"] for c in cases)
    host = platform.node()
    machine = platform.machine()
    on_pi = host.lower() == "piscope" and machine.lower() in ("aarch64", "arm64")
    passed = timing_ok and on_pi
    result = {
        "run_id": run_id,
        "stage": "guide_isolate",
        "host": host,
        "machine": machine,
        "cases": cases,
        "pass": passed,
        "timing_ok": timing_ok,
        "on_pi": on_pi,
    }
    write_json(os.path.join(out, "isolate_bench.json"), result)

    verdict = "PASS" if passed else "FAIL"
    print(f"guide_isolate bench {verdict}")
    print(f"  host={host} machine={machine}")
    for c in cases:
        print(
            f"  {c['tile']}² {c['snr_level']}: p50={c['p50_s']*1e3:.3f} ms "
            f"p95={c['p95_s']*1e3:.3f} ms max={c['max_s']*1e3:.3f} ms "
            f"gate={c['gate_p95_s']*1e3:.1f} ms {'PASS' if c['pass'] else 'FAIL'} iters={c['iters']}"
        )
    print(f"  out={out}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
