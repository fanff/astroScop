"""Tests for frame discovery and FITS export."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from astropy.io import fits

from astroscop_pp.discover import discover_frames
from astroscop_pp.fits_export import write_cfa_fits
from astroscop_pp.cli import main


def _write_pair(
    directory: Path,
    sequence: int,
    *,
    shape=(32, 40),
    configured=(36, 32),
    fmt="SBGGR12",
) -> None:
    h, w = shape
    arr = np.arange(h * w, dtype=np.uint16).reshape(h, w)
    stem = f"frame_{sequence:06d}"
    np.save(directory / f"{stem}_bayer.npy", arr)
    meta = {
        "sequence": sequence,
        "shutter_us": 50000,
        "analog_gain": 2.5,
        "triggerDateStr": "2026-08-09 22:37:43.704254",
        "sensor_preset": "bin2x2",
        "raw": {
            "format": fmt,
            "configured_size": list(configured),
            "array_shape": list(shape),
            "dtype": "uint16",
        },
        "array_shape": list(shape),
        "dtype": "uint16",
    }
    with (directory / f"{stem}_meta.json").open("w", encoding="utf-8") as f:
        json.dump(meta, f)


def test_discover_sorts_by_sequence(tmp_path: Path):
    _write_pair(tmp_path, 3)
    _write_pair(tmp_path, 1)
    _write_pair(tmp_path, 2)
    result = discover_frames(tmp_path, recursive=False)
    assert [p.sequence for p in result.frames] == [1, 2, 3]
    assert result.skipped == []


def test_discover_one_level_subdir(tmp_path: Path):
    _write_pair(tmp_path, 1)
    sub = tmp_path / "bigs"
    sub.mkdir()
    _write_pair(sub, 2)
    result = discover_frames(tmp_path, recursive=True)
    assert [p.sequence for p in result.frames] == [1, 2]


def test_discover_missing_meta_skipped(tmp_path: Path):
    arr = np.zeros((8, 8), dtype=np.uint16)
    np.save(tmp_path / "frame_000001_bayer.npy", arr)
    result = discover_frames(tmp_path, recursive=False)
    assert result.frames == []
    assert len(result.skipped) == 1
    assert "missing metadata" in result.skipped[0]


def test_write_cfa_fits_roundtrip(tmp_path: Path):
    shape = (32, 40)
    configured = (36, 32)
    arr = np.arange(shape[0] * shape[1], dtype=np.uint16).reshape(shape)
    meta = {
        "sequence": 7,
        "shutter_us": 70387,
        "analog_gain": 8.8,
        "triggerDateStr": "2026-08-09 22:37:43.704254",
        "sensor_preset": "bin2x2",
        "raw": {
            "format": "SBGGR12",
            "configured_size": list(configured),
            "array_shape": list(shape),
        },
    }
    src = tmp_path / "frame_000007_bayer.npy"
    dest = tmp_path / "lights_00001.fits"
    summary = write_cfa_fits(arr, meta, dest, source_npy=src, overwrite=False)
    assert summary["shape"] == [32, 36]
    assert summary["bayerpat"] == "BGGR"
    assert dest.is_file()

    with fits.open(dest) as hdul:
        data = hdul[0].data
        hdr = hdul[0].header
    assert data.shape == (32, 36)
    assert data.dtype == np.uint16
    np.testing.assert_array_equal(data, arr[:32, :36])
    assert hdr["BAYERPAT"].strip() == "BGGR"
    assert hdr["ROWORDER"].strip() == "TOP-DOWN"
    assert hdr["XBAYROFF"] == 0
    assert hdr["YBAYROFF"] == 0
    assert abs(hdr["EXPTIME"] - 0.070387) < 1e-9
    assert hdr["FRAMENUM"] == 7


def test_cli_convert(tmp_path: Path):
    src = tmp_path / "in"
    src.mkdir()
    _write_pair(src, 1)
    _write_pair(src, 2)
    out = tmp_path / "out"
    rc = main(
        [
            "convert",
            str(tmp_path / "in"),
            "-o",
            str(out),
            "--basename",
            "lights",
        ]
    )
    assert rc == 0
    assert (out / "lights_00001.fits").is_file()
    assert (out / "lights_00002.fits").is_file()
    assert (out / "conversion_manifest.json").is_file()
    manifest = json.loads((out / "conversion_manifest.json").read_text(encoding="utf-8"))
    assert manifest["frame_count"] == 2
