"""Crop saved Bayer frames around a full-sensor lock (default 60% / 40%).

Writes even-aligned Bayer tiles plus a stretched RGB PNG for later isolate tests.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from guide_roi import lock_to_roi  # noqa: E402


def bggr_superpixel(bayer: np.ndarray) -> np.ndarray:
    """SBGGR 2x2 → float RGB at half resolution."""
    y = (bayer.shape[0] // 2) * 2
    x = (bayer.shape[1] // 2) * 2
    b = bayer[0:y:2, 0:x:2].astype(np.float64)
    g1 = bayer[0:y:2, 1:x:2].astype(np.float64)
    g2 = bayer[1:y:2, 0:x:2].astype(np.float64)
    r = bayer[1:y:2, 1:x:2].astype(np.float64)
    g = 0.5 * (g1 + g2)
    return np.stack([r, g, b], axis=-1)


def stretch_u8(rgb: np.ndarray) -> np.ndarray:
    lo = float(np.percentile(rgb, 1.0))
    hi = float(np.percentile(rgb, 99.8))
    if hi <= lo:
        hi = lo + 1.0
    scaled = np.clip((rgb - lo) / (hi - lo), 0.0, 1.0)
    return np.round(scaled * 255.0).astype(np.uint8)


def configured_wh(meta: dict, bayer: np.ndarray) -> tuple[int, int]:
    raw = meta.get("raw") or {}
    size = raw.get("configured_size")
    if isinstance(size, (list, tuple)) and len(size) == 2:
        return int(size[0]), int(size[1])
    h, w = int(bayer.shape[0]), int(bayer.shape[1])
    return w, h


def crop_one(
    npy_path: Path,
    *,
    track_x: float,
    track_y: float,
    roi_half: int,
    out_dir: Path,
) -> dict:
    meta_path = npy_path.with_name(npy_path.name.replace("_bayer.npy", "_meta.json"))
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
    bayer = np.load(npy_path)
    cfg_w, cfg_h = configured_wh(meta, bayer)
    scaler = meta.get("ScalerCrop")
    roi = lock_to_roi(
        track_x,
        track_y,
        (cfg_w, cfg_h),
        scaler_crop=scaler,
        roi_half=roi_half,
    )
    if not roi.ok:
        return {"stem": npy_path.stem, "ok": False, "reason": roi.reason}
    tile = np.ascontiguousarray(
        bayer[roi.origin_v : roi.origin_v + roi.size_v, roi.origin_u : roi.origin_u + roi.size_u]
    )
    stem = npy_path.name.replace("_bayer.npy", "")
    npy_out = out_dir / f"{stem}_crop_bayer.npy"
    png_out = out_dir / f"{stem}_crop.png"
    np.save(npy_out, tile)
    rgb8 = stretch_u8(bggr_superpixel(tile))
    Image.fromarray(rgb8, mode="RGB").save(png_out)
    rec = (meta.get("settings") or {})
    return {
        "stem": stem,
        "ok": True,
        "npy": npy_out.name,
        "png": png_out.name,
        "origin_u": roi.origin_u,
        "origin_v": roi.origin_v,
        "size_u": roi.size_u,
        "size_v": roi.size_v,
        "lock_u": roi.lock_u,
        "lock_v": roi.lock_v,
        "track_x_used": track_x,
        "track_y_used": track_y,
        "track_x_recorded": rec.get("track_x"),
        "track_y_recorded": rec.get("track_y"),
        "analog_gain": meta.get("analog_gain"),
        "shutter_us": meta.get("shutter_us"),
        "sequence": meta.get("sequence"),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--src",
        type=Path,
        default=ROOT / "savedimgs" / "test",
    )
    ap.add_argument(
        "--dst",
        type=Path,
        default=ROOT / "savedimgs" / "test_lock_crops",
    )
    ap.add_argument("--track-x", type=float, default=0.60)
    ap.add_argument("--track-y", type=float, default=0.40)
    ap.add_argument("--roi-half", type=int, default=128, help="Bayer crop half-size (256² default)")
    args = ap.parse_args()
    src = args.src
    dst = args.dst
    dst.mkdir(parents=True, exist_ok=True)
    frames = sorted(src.glob("frame_*_bayer.npy"))
    if not frames:
        raise SystemExit(f"no frames in {src}")
    rows = []
    for path in frames:
        rows.append(
            crop_one(
                path,
                track_x=args.track_x,
                track_y=args.track_y,
                roi_half=args.roi_half,
                out_dir=dst,
            )
        )
        if len(rows) % 25 == 0:
            print(f"cropped {len(rows)}/{len(frames)}", flush=True)
    manifest = {
        "src": str(src),
        "track_x": args.track_x,
        "track_y": args.track_y,
        "roi_half": args.roi_half,
        "n": len(rows),
        "ok": sum(1 for r in rows if r.get("ok")),
        "frames": rows,
    }
    (dst / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"wrote {manifest['ok']}/{manifest['n']} crops under {dst}")


if __name__ == "__main__":
    main()
