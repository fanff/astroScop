#!/usr/bin/env python3
"""
Camera-free unit tests for ``compute_rgb_spectrum``.

The live UI histogram is computed on **display RGB uint8** (JPEG path),
not on 12-bit Bayer sitting in a uint16 container. These tests lock that
contract and show what goes wrong if 12-bit values are mis-scaled as 16-bit.
"""

from __future__ import annotations

import sys
import unittest

import numpy as np

from cam_spectrum import compute_rgb_spectrum


class TestRgbSpectrumUint8(unittest.TestCase):
    def test_mid_grey_peak_and_mean(self):
        rgb = np.full((64, 80, 3), 128, dtype=np.uint8)
        spec = compute_rgb_spectrum(rgb)
        self.assertEqual(spec.bins, 256)
        self.assertEqual(spec.pixels, 64 * 80)
        self.assertEqual(spec.shape, (64, 80, 3))
        for mean in (spec.mean_r, spec.mean_g, spec.mean_b):
            self.assertAlmostEqual(mean, 128.0, places=5)
        self.assertEqual(spec.min_r, 128)
        self.assertEqual(spec.max_r, 128)
        self.assertEqual(sum(spec.hist_r), spec.pixels)
        self.assertEqual(spec.hist_r[128], spec.pixels)
        self.assertEqual(sum(spec.hist_r[:128]), 0)
        self.assertEqual(sum(spec.hist_r[129:]), 0)

    def test_channel_separation(self):
        rgb = np.zeros((32, 32, 3), dtype=np.uint8)
        rgb[:, :, 0] = 200  # R
        rgb[:, :, 1] = 40  # G
        rgb[:, :, 2] = 10  # B
        spec = compute_rgb_spectrum(rgb)
        self.assertEqual(spec.hist_r[200], 32 * 32)
        self.assertEqual(spec.hist_g[40], 32 * 32)
        self.assertEqual(spec.hist_b[10], 32 * 32)
        self.assertAlmostEqual(spec.mean_r, 200.0, places=5)
        self.assertAlmostEqual(spec.mean_g, 40.0, places=5)
        self.assertAlmostEqual(spec.mean_b, 10.0, places=5)

    def test_bright_frame_not_left_skewed(self):
        """A bright uint8 frame must put mass in high bins (not look 'dark')."""
        rgb = np.full((48, 48, 3), 220, dtype=np.uint8)
        spec = compute_rgb_spectrum(rgb)
        low = sum(spec.hist_r[:64])
        high = sum(spec.hist_r[192:])
        self.assertEqual(low, 0)
        self.assertEqual(high, spec.pixels)
        self.assertGreater(spec.mean_r, 200.0)

    def test_rejects_bad_shape(self):
        with self.assertRaises(ValueError):
            compute_rgb_spectrum(np.zeros((10, 10), dtype=np.uint8))
        with self.assertRaises(ValueError):
            compute_rgb_spectrum(np.zeros((10, 10, 3), dtype=np.uint8), bins=1)


class TestBitDepthConfusion(unittest.TestCase):
    """
    Document the 12-bit-in-uint16 footgun.

    Science Bayer is 12-bit ADC stored in uint16 (typical max ~4095).
    If those samples were fed to ``compute_rgb_spectrum`` as-is, the
    ``clip(..., 0, 255)`` path would crush almost everything toward the
    low end — a falsely 'dark' histogram. The live worker must NOT do that:
    spectrum runs on RGB888 display frames only.
    """

    def test_12bit_values_above_255_saturate_when_naively_cast(self):
        # Mid-grey on a 12-bit scale ≈ 2048 in a uint16 buffer.
        # compute_rgb_spectrum clips to 0..255 then cast → saturates to white.
        mid12 = np.full((32, 32, 3), 2048, dtype=np.uint16)
        crushed = compute_rgb_spectrum(mid12)
        self.assertEqual(crushed.mean_r, 255.0)
        self.assertEqual(crushed.hist_r[255], 32 * 32)

    def test_correct_12bit_to_uint8_scale_is_bright_when_scene_is(self):
        """Scale 12-bit DN → uint8 the honest way; mid-grey stays mid."""
        dn12 = np.full((40, 40, 3), 2048, dtype=np.uint16)  # ~50% of 4095
        rgb8 = np.clip((dn12.astype(np.float32) * (255.0 / 4095.0)), 0, 255).astype(
            np.uint8
        )
        spec = compute_rgb_spectrum(rgb8)
        self.assertGreater(spec.mean_r, 100.0)
        self.assertLess(spec.mean_r, 160.0)
        peak = int(np.argmax(spec.hist_r))
        self.assertGreaterEqual(peak, 100)
        self.assertLessEqual(peak, 160)

    def test_wrong_16bit_fullscale_assumption_makes_12bit_look_dark(self):
        """If you scale 12-bit DN as if FS=65535, mid-grey collapses."""
        dn12 = np.full((40, 40, 3), 2048, dtype=np.uint16)
        wrong8 = np.clip((dn12.astype(np.float32) * (255.0 / 65535.0)), 0, 255).astype(
            np.uint8
        )
        spec = compute_rgb_spectrum(wrong8)
        # 2048/65535*255 ≈ 8 — looks almost black
        self.assertLess(spec.mean_r, 20.0)
        self.assertGreater(sum(spec.hist_r[:32]), spec.pixels * 0.9)


class TestMatchesJpegPath(unittest.TestCase):
    def test_spectrum_matches_array_used_for_encode(self):
        """Same array the JPEG path would encode must match spectrum moments."""
        rng = np.random.default_rng(0)
        rgb = rng.integers(0, 256, size=(120, 160, 3), dtype=np.uint8)
        spec = compute_rgb_spectrum(rgb)
        self.assertAlmostEqual(spec.mean_r, float(rgb[:, :, 0].mean()), places=4)
        self.assertAlmostEqual(spec.mean_g, float(rgb[:, :, 1].mean()), places=4)
        self.assertAlmostEqual(spec.mean_b, float(rgb[:, :, 2].mean()), places=4)
        # Recompute hist independently
        hr = np.bincount(rgb[:, :, 0].ravel(), minlength=256)
        self.assertTrue(np.array_equal(hr, np.asarray(spec.hist_r)))


def main(argv=None):
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
