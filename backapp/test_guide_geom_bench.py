#!/usr/bin/env python3
"""On-Pi timing bench for guide_geom (no camera).

Gate (evolution §10): p95 of pixels_to_axis_steps < 0.5 ms.

  python3 test_guide_geom_bench.py --out /tmp/guide_geom_bench/run1
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone

from guide_geom import pixels_to_axis_steps

P95_GATE_S = 0.0005  # 0.5 ms
DEFAULT_ITERS = 10_000


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


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--iters", type=int, default=DEFAULT_ITERS)
    args = ap.parse_args(argv)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.out or os.path.join("/tmp/guide_geom_bench", run_id)
    os.makedirs(out, exist_ok=True)

    cases = [
        dict(e_u=0.4, e_v=-0.2, f_mm=400.0, bin=1, dec_deg=0.0, theta_deg=0.0),
        dict(e_u=1.0, e_v=0.0, f_mm=400.0, bin=2, dec_deg=45.0, theta_deg=90.0),
        dict(e_u=0.0, e_v=1.0, f_mm=800.0, bin=1, dec_deg=80.0, theta_deg=0.0, flip_asc=True),
        dict(e_u=0.3, e_v=0.3, f_mm=400.0, bin=2, dec_deg=89.0, theta_deg=35.0, flip_dec=True),
    ]

    # Warmup (import / first call)
    for c in cases:
        kw = {k: v for k, v in c.items() if k not in ("e_u", "e_v")}
        pixels_to_axis_steps(c["e_u"], c["e_v"], **kw)

    samples = []
    n = int(args.iters)
    t_all0 = time.perf_counter()
    for i in range(n):
        c = cases[i % len(cases)]
        kw = {k: v for k, v in c.items() if k not in ("e_u", "e_v")}
        t0 = time.perf_counter()
        pixels_to_axis_steps(c["e_u"], c["e_v"], **kw)
        samples.append(time.perf_counter() - t0)
    elapsed = time.perf_counter() - t_all0

    samples.sort()
    p50 = percentile(samples, 50)
    p95 = percentile(samples, 95)
    mx = samples[-1]
    passed = p95 < P95_GATE_S

    result = {
        "run_id": run_id,
        "stage": "guide_geom",
        "host": platform.node(),
        "machine": platform.machine(),
        "iters": n,
        "tile_size": None,
        "p50_s": p50,
        "p95_s": p95,
        "max_s": mx,
        "gate_p95_s": P95_GATE_S,
        "elapsed_s": elapsed,
        "pass": passed,
    }
    write_json(os.path.join(out, "geom_bench.json"), result)

    verdict = "PASS" if passed else "FAIL"
    print(f"guide_geom bench {verdict}")
    print(f"  host={result['host']} machine={result['machine']}")
    print(f"  iters={n} tile_size=n/a")
    print(f"  p50={p50 * 1e6:.2f} us  p95={p95 * 1e6:.2f} us  max={mx * 1e6:.2f} us")
    print(f"  gate p95 < {P95_GATE_S * 1e3:.1f} ms")
    print(f"  out={out}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
