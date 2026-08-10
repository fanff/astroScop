"""Write CFA monochrome FITS frames for Siril."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from astropy.io import fits

from .bayer import bayerpat_from_format, crop_to_configured


def _parse_date_obs(meta: dict[str, Any]) -> str | None:
    raw = meta.get("triggerDateStr")
    if isinstance(raw, str) and raw.strip():
        # Capture format: "2026-08-09 22:37:43.704254" → FITS-friendly ISO
        text = raw.strip().replace(" ", "T", 1)
        return text
    ts = meta.get("triggerDate")
    if ts is not None:
        try:
            return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.%f"
            )
        except (TypeError, ValueError, OSError):
            return None
    return None


def build_header(meta: dict[str, Any], *, bayerpat: str, source_npy: Path) -> fits.Header:
    """Build a Siril-friendly CFA FITS header from science metadata."""
    hdr = fits.Header()
    hdr["SIMPLE"] = True
    hdr["BITPIX"] = 16
    hdr["NAXIS"] = 2
    hdr["BZERO"] = 32768
    hdr["BSCALE"] = 1
    hdr["BAYERPAT"] = (bayerpat, "Bayer color pattern")
    hdr["XBAYROFF"] = (0, "X offset of Bayer array")
    hdr["YBAYROFF"] = (0, "Y offset of Bayer array")
    hdr["ROWORDER"] = ("TOP-DOWN", "Image row order; do not flip pixels")
    hdr["INSTRUME"] = ("IMX477", "Sensor")

    shutter_us = meta.get("shutter_us")
    if shutter_us is not None:
        hdr["EXPTIME"] = (float(shutter_us) / 1_000_000.0, "[s] Exposure time")
        hdr["EXPOSURE"] = (float(shutter_us) / 1_000_000.0, "[s] Exposure time")

    gain = meta.get("analog_gain")
    if gain is not None:
        hdr["GAIN"] = (float(gain), "Analogue gain")

    date_obs = _parse_date_obs(meta)
    if date_obs:
        hdr["DATE-OBS"] = (date_obs, "Frame trigger time")

    seq = meta.get("sequence")
    if seq is not None:
        hdr["FRAMENUM"] = (int(seq), "Capture sequence number")

    preset = meta.get("sensor_preset")
    if preset:
        hdr["SENSORPR"] = (str(preset)[:68], "Sensor preset")

    raw = meta.get("raw") or {}
    fmt = raw.get("format")
    if fmt:
        hdr["RAWFMT"] = (str(fmt)[:68], "libcamera raw format")

    colour_r = meta.get("colour_gain_r")
    colour_b = meta.get("colour_gain_b")
    if colour_r is not None:
        hdr["COLGAINR"] = (float(colour_r), "Colour gain R (ISP; not applied to CFA)")
    if colour_b is not None:
        hdr["COLGAINB"] = (float(colour_b), "Colour gain B (ISP; not applied to CFA)")

    hdr["ORIGFILE"] = (source_npy.name[:68], "Source Bayer npy basename")
    hdr["HISTORY"] = "Converted from astroScop science Bayer npy (undebayered CFA)"
    return hdr


def write_cfa_fits(
    array_u16: np.ndarray,
    meta: dict[str, Any],
    dest: Path,
    *,
    source_npy: Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    """
    Crop Bayer data and write an unsigned 16-bit CFA FITS file.

    Returns a small summary dict for the conversion manifest.
    """
    dest = Path(dest)
    if dest.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing file: {dest}")

    cropped = crop_to_configured(array_u16, meta)
    raw = meta.get("raw") or {}
    bayerpat = bayerpat_from_format(raw.get("format"))
    header = build_header(meta, bayerpat=bayerpat, source_npy=Path(source_npy))

    # Astropy stores uint16 as int16 + BZERO=32768 in the file on disk.
    hdu = fits.PrimaryHDU(data=cropped, header=header)
    dest.parent.mkdir(parents=True, exist_ok=True)
    hdu.writeto(dest, overwrite=overwrite, output_verify="exception")

    return {
        "dest": str(dest),
        "shape": list(cropped.shape),
        "dtype": str(cropped.dtype),
        "bayerpat": bayerpat,
        "min": int(cropped.min()),
        "max": int(cropped.max()),
        "mean": float(cropped.mean()),
    }
