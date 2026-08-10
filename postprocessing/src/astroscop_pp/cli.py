"""CLI for converting astroScop Bayer science frames to Siril CFA FITS."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from . import __version__
from .discover import discover_frames
from .fits_export import write_cfa_fits


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="astroscop-pp",
        description=(
            "Convert astroScop science Bayer .npy + JSON sidecars into "
            "CFA monochrome FITS frames for Siril stacking."
        ),
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = p.add_subparsers(dest="command", required=True)

    convert = sub.add_parser("convert", help="Convert a capture folder to CFA FITS")
    convert.add_argument(
        "input_dir",
        type=Path,
        help="Folder containing frame_*_bayer.npy and *_meta.json",
    )
    convert.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        required=True,
        help="Destination directory for lights_XXXXX.fits",
    )
    convert.add_argument(
        "--basename",
        default="lights",
        help="Siril sequence basename (default: lights)",
    )
    convert.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing FITS files",
    )
    convert.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover and plan only; do not write FITS",
    )
    convert.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Convert at most N frames (after sort)",
    )
    convert.add_argument(
        "--no-recursive",
        action="store_true",
        help="Do not scan one level of subdirectories",
    )
    return p


def cmd_convert(args: argparse.Namespace) -> int:
    result = discover_frames(args.input_dir, recursive=not args.no_recursive)
    if result.skipped:
        preview = result.skipped[:5]
        for msg in preview:
            print(f"skip: {msg}", file=sys.stderr)
        remaining = len(result.skipped) - len(preview)
        if remaining > 0:
            print(f"skip: ... and {remaining} more orphan .npy file(s)", file=sys.stderr)

    frames = result.frames
    if args.limit is not None:
        if args.limit < 0:
            raise SystemExit("--limit must be >= 0")
        frames = frames[: args.limit]

    if not frames:
        print(f"no frames found in {args.input_dir}", file=sys.stderr)
        return 1

    out_dir = Path(args.output_dir)
    records: list[dict] = []

    print(
        f"found {len(result.frames)} paired frame(s) in {args.input_dir}"
        + (f" ({len(result.skipped)} skipped)" if result.skipped else "")
        + (f"; converting {len(frames)}" if args.limit is not None else "")
    )
    for index, pair in enumerate(frames, start=1):
        dest = out_dir / f"{args.basename}_{index:05d}.fits"
        print(
            f"[{index}/{len(frames)}] seq={pair.sequence} "
            f"{pair.npy_path.name} -> {dest.name}"
        )
        if args.dry_run:
            records.append(
                {
                    "index": index,
                    "sequence": pair.sequence,
                    "source_npy": str(pair.npy_path),
                    "source_meta": str(pair.meta_path),
                    "dest": str(dest),
                    "dry_run": True,
                }
            )
            continue

        array = np.load(pair.npy_path)
        summary = write_cfa_fits(
            array,
            pair.meta,
            dest,
            source_npy=pair.npy_path,
            overwrite=args.overwrite,
        )
        records.append(
            {
                "index": index,
                "sequence": pair.sequence,
                "source_npy": str(pair.npy_path),
                "source_meta": str(pair.meta_path),
                "shutter_us": pair.meta.get("shutter_us"),
                "analog_gain": pair.meta.get("analog_gain"),
                **summary,
            }
        )

    manifest = {
        "version": __version__,
        "input_dir": str(Path(args.input_dir).resolve()),
        "output_dir": str(out_dir.resolve()),
        "basename": args.basename,
        "frame_count": len(records),
        "skipped_count": len(result.skipped),
        "skipped": result.skipped,
        "dry_run": bool(args.dry_run),
        "frames": records,
    }

    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = out_dir / "conversion_manifest.json"
        with manifest_path.open("w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        print(f"wrote manifest {manifest_path}")
    else:
        print(json.dumps(manifest, indent=2))

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "convert":
        return cmd_convert(args)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
