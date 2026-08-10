#!/usr/bin/env python3
"""
Grab one live preview from the rootserver hub and validate spectrum vs JPEG.

Does not stop astroscop-camera.service — attaches as a UI WebSocket client.

  python3 capture_validate_spectrum.py --uri ws://127.0.0.1:8765 --out /tmp/hist_check
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import io
import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
from PIL import Image

from cam_spectrum import compute_rgb_spectrum


async def grab_one(uri: str, timeout_s: float = 20.0):
    import websockets

    jpeg_b64 = None
    img_stats = None
    img_props = None
    deadline = time.time() + timeout_s

    async with websockets.connect(uri, max_size=32 * 1024 * 1024) as ws:
        while time.time() < deadline:
            raw = await asyncio.wait_for(ws.recv(), timeout=max(0.1, deadline - time.time()))
            msg = json.loads(raw)
            mt = msg.get("msgtype")
            if mt == "imgData":
                jpeg_b64 = msg.get("data")
            elif mt == "imgStats":
                img_stats = msg.get("data") or {}
            elif mt == "imgProps":
                img_props = msg.get("data") or {}
            if jpeg_b64 is not None and img_stats is not None:
                break

    if jpeg_b64 is None or img_stats is None:
        raise TimeoutError(f"did not receive imgData+imgStats from {uri} within {timeout_s}s")
    return jpeg_b64, img_stats, img_props


def compare_spectrum(jpeg_b64: str, img_stats: dict):
    raw = base64.b64decode(jpeg_b64)
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    arr = np.asarray(img)
    local = compute_rgb_spectrum(arr)

    wire = img_stats.get("spectrum") or {}
    report = {
        "jpeg_shape": list(arr.shape),
        "jpeg_dtype": str(arr.dtype),
        "jpeg_mean_rgb": [float(arr[:, :, i].mean()) for i in range(3)],
        "jpeg_max_rgb": [int(arr[:, :, i].max()) for i in range(3)],
        "local_spectrum_means": [local.mean_r, local.mean_g, local.mean_b],
        "wire_spectrum_means": [
            wire.get("mean_r"),
            wire.get("mean_g"),
            wire.get("mean_b"),
        ],
        "wire_has_spectrum": bool(wire),
        "wire_has_histData": "histData" in (img_stats or {}),
    }

    failures = []
    if not wire:
        failures.append("imgStats missing spectrum object")
    else:
        for name, a, b in (
            ("mean_r", local.mean_r, wire.get("mean_r")),
            ("mean_g", local.mean_g, wire.get("mean_g")),
            ("mean_b", local.mean_b, wire.get("mean_b")),
        ):
            if b is None or abs(float(a) - float(b)) > 2.0:
                failures.append(f"{name} mismatch local={a} wire={b}")

        for ch, local_h, key in (
            ("r", local.hist_r, "hist_r"),
            ("g", local.hist_g, "hist_g"),
            ("b", local.hist_b, "hist_b"),
        ):
            wh = wire.get(key) or []
            if len(wh) != 256:
                failures.append(f"hist_{ch} len={len(wh)}")
                continue
            # Wire spectrum is from pre-JPEG RGB; we recompute from decoded JPEG.
            # Means must match tightly; per-bin L1 can drift from JPEG quantization.
            l1 = sum(abs(int(a) - int(b)) for a, b in zip(local_h, wh))
            report[f"hist_{ch}_l1"] = l1
            report[f"hist_{ch}_l1_frac"] = l1 / float(local.pixels)

        # Primary contract: wire spectrum describes the same brightness as the JPEG.
        for name, jpeg_m, wire_m in (
            ("mean_r", report["jpeg_mean_rgb"][0], wire.get("mean_r")),
            ("mean_g", report["jpeg_mean_rgb"][1], wire.get("mean_g")),
            ("mean_b", report["jpeg_mean_rgb"][2], wire.get("mean_b")),
        ):
            if wire_m is None or abs(float(jpeg_m) - float(wire_m)) > 3.0:
                failures.append(f"jpeg vs wire {name}: jpeg={jpeg_m} wire={wire_m}")

    # Darkness heuristic on the actual JPEG the UI shows
    mean_y = float(arr.mean())
    report["jpeg_mean_luma_approx"] = mean_y
    report["looks_dark"] = mean_y < 40.0
    report["bit_depth_note"] = (
        "Preview spectrum is uint8 RGB (0..255), not 12-bit Bayer in uint16. "
        "A dark JPEG means the RGB preview itself is dark (exposure/gains/scene), "
        "not a 16-bit-vs-12-bit histogram scale bug on this path."
    )
    report["failures"] = failures
    report["ok"] = not failures
    return report, arr, local


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--uri", default="ws://127.0.0.1:8765")
    ap.add_argument("--out", default=None)
    ap.add_argument("--timeout", type=float, default=20.0)
    args = ap.parse_args(argv)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.out or os.path.join("cam_test_out", f"hist_check_{run_id}")
    os.makedirs(out, exist_ok=True)

    jpeg_b64, img_stats, img_props = asyncio.run(grab_one(args.uri, args.timeout))
    report, arr, local = compare_spectrum(jpeg_b64, img_stats)

    jpg_path = os.path.join(out, "preview.jpg")
    with open(jpg_path, "wb") as f:
        f.write(base64.b64decode(jpeg_b64))
    Image.fromarray(arr).save(os.path.join(out, "preview_rgb.bmp"))

    with open(os.path.join(out, "imgStats.json"), "w", encoding="utf-8") as f:
        json.dump(img_stats, f, indent=2)
    with open(os.path.join(out, "imgProps.json"), "w", encoding="utf-8") as f:
        json.dump(img_props, f, indent=2, default=str)
    with open(os.path.join(out, "local_spectrum.json"), "w", encoding="utf-8") as f:
        json.dump(local.model_dump(), f, indent=2)
    with open(os.path.join(out, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(json.dumps(report, indent=2))
    print(f"wrote {out}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
