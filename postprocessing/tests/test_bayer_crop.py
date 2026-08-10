"""Tests for Bayer crop and pattern mapping."""

from __future__ import annotations

import numpy as np
import pytest

from astroscop_pp.bayer import (
    bayerpat_from_format,
    configured_size_wh,
    crop_to_configured,
)


def test_bayerpat_from_sbggr12():
    assert bayerpat_from_format("SBGGR12") == "BGGR"


def test_bayerpat_from_other_formats():
    assert bayerpat_from_format("SRGGB10") == "RGGB"
    assert bayerpat_from_format("SGRBG12") == "GRBG"
    assert bayerpat_from_format("SGBRG12") == "GBRG"


def test_bayerpat_rejects_unknown():
    with pytest.raises(ValueError, match="unsupported"):
        bayerpat_from_format("YUYV")


def test_configured_size_wh():
    meta = {"raw": {"configured_size": [2028, 1520], "format": "SBGGR12"}}
    assert configured_size_wh(meta) == (2028, 1520)


def test_crop_stride_pad():
    arr = np.arange(1520 * 2032, dtype=np.uint16).reshape(1520, 2032)
    meta = {
        "raw": {
            "format": "SBGGR12",
            "configured_size": [2028, 1520],
            "array_shape": [1520, 2032],
        }
    }
    out = crop_to_configured(arr, meta)
    assert out.shape == (1520, 2028)
    assert out.dtype == np.uint16
    assert out[0, 0] == arr[0, 0]
    assert out[0, -1] == arr[0, 2027]


def test_crop_rejects_undersized():
    arr = np.zeros((100, 100), dtype=np.uint16)
    meta = {"raw": {"configured_size": [2028, 1520]}}
    with pytest.raises(ValueError, match="smaller"):
        crop_to_configured(arr, meta)
