"""Public tests for the imaging pipeline.

Run with:  python3 test_pipeline.py
"""

import os
import sys
import unittest

import numpy as np

# ---------------------------------------------------------------------------
# Import from workspace – honour AGENT_BENCH_WORKSPACE if set
# ---------------------------------------------------------------------------
ws = os.environ.get("AGENT_BENCH_WORKSPACE", os.path.dirname(__file__))
sys.path.insert(0, ws)

import imaging_pipeline as ip


class TestDarkFrameSubtraction(unittest.TestCase):
    """Basic dark-frame subtraction tests."""

    def test_simple_subtraction(self):
        img = np.array([[10.0, 20.0], [30.0, 40.0]])
        dark = np.array([[1.0, 2.0], [3.0, 4.0]])
        result = ip.dark_frame_subtraction(img, dark)
        expected = np.array([[9.0, 18.0], [27.0, 36.0]])
        np.testing.assert_allclose(result, expected)

    def test_clip_to_zero(self):
        """Negative values after subtraction must be clipped to 0."""
        img = np.array([[1.0, 2.0]])
        dark = np.array([[5.0, 1.0]])
        result = ip.dark_frame_subtraction(img, dark)
        self.assertTrue(np.all(result >= 0))
        self.assertAlmostEqual(result[0, 0], 0.0)
        self.assertAlmostEqual(result[0, 1], 1.0)

    def test_shape_mismatch_raises(self):
        img = np.ones((3, 3))
        dark = np.ones((2, 2))
        with self.assertRaises(ValueError):
            ip.dark_frame_subtraction(img, dark)

    def test_returns_float64(self):
        img = np.ones((2, 2), dtype=np.float32)
        dark = np.zeros((2, 2), dtype=np.float32)
        result = ip.dark_frame_subtraction(img, dark)
        self.assertEqual(result.dtype, np.float64)


class TestFlatFieldCorrection(unittest.TestCase):
    """Flat-field correction tests."""

    def test_uniform_flat(self):
        """A uniform flat field should leave the image unchanged."""
        img = np.array([[100.0, 200.0], [300.0, 400.0]])
        flat = np.full((2, 2), 50.0)
        dark_flat = np.full((2, 2), 5.0)
        result = ip.flat_field_correction(img, flat, dark_flat)
        # corrected flat = flat - dark_flat = 45; normalised flat = 45/45 = 1
        np.testing.assert_allclose(result, img, rtol=1e-10)

    def test_nonuniform_flat(self):
        """Non-uniform flat field should scale pixels inversely."""
        img = np.array([[100.0, 100.0]])
        flat = np.array([[50.0, 100.0]])
        dark_flat = np.array([[0.0, 0.0]])
        result = ip.flat_field_correction(img, flat, dark_flat)
        # normalised flat = [0.5, 1.0] -> corrected = [200, 100]
        self.assertAlmostEqual(result[0, 0], 200.0, places=5)
        self.assertAlmostEqual(result[0, 1], 100.0, places=5)

    def test_zero_flat_no_crash(self):
        """Division by zero in flat field must not produce inf/NaN."""
        img = np.array([[10.0, 20.0]])
        flat = np.array([[0.0, 10.0]])
        dark_flat = np.array([[0.0, 0.0]])
        result = ip.flat_field_correction(img, flat, dark_flat)
        self.assertTrue(np.all(np.isfinite(result)))


class TestDetectHotPixels(unittest.TestCase):
    """Hot-pixel detection tests."""

    def test_obvious_hot_pixel(self):
        """A single extreme outlier must be detected."""
        img = np.zeros((7, 7))
        img[3, 3] = 1000.0  # obvious hot pixel
        mask = ip.detect_hot_pixels(img, sigma_threshold=5.0, neighborhood=5)
        self.assertTrue(mask[3, 3])
        # Neighbouring pixels should NOT be flagged
        self.assertFalse(mask[2, 3])
        self.assertFalse(mask[4, 3])

    def test_no_hot_pixels_in_uniform(self):
        """A uniform image should have no hot pixels."""
        img = np.full((10, 10), 50.0)
        mask = ip.detect_hot_pixels(img, sigma_threshold=5.0, neighborhood=5)
        self.assertFalse(np.any(mask))

    def test_returns_boolean(self):
        img = np.ones((5, 5))
        mask = ip.detect_hot_pixels(img)
        self.assertEqual(mask.dtype, bool)


class TestGaussianBlur(unittest.TestCase):
    """Gaussian blur tests."""

    def test_impulse_response(self):
        """Blur of a delta function should produce a Gaussian-like blob."""
        img = np.zeros((11, 11))
        img[5, 5] = 100.0
        result = ip.apply_gaussian_blur(img, kernel_size=5, sigma=1.0)
        # Peak should be at centre and reduced
        self.assertEqual(np.unravel_index(result.argmax(), result.shape), (5, 5))
        self.assertLess(result[5, 5], 100.0)

    def test_preserves_shape(self):
        img = np.random.rand(20, 30)
        result = ip.apply_gaussian_blur(img, kernel_size=5, sigma=1.0)
        self.assertEqual(result.shape, img.shape)

    def test_uniform_image_unchanged(self):
        """A constant image should pass through the blur unchanged."""
        img = np.full((10, 10), 42.0)
        result = ip.apply_gaussian_blur(img, kernel_size=5, sigma=1.0)
        np.testing.assert_allclose(result, 42.0, atol=1e-10)


class TestRunPipeline(unittest.TestCase):
    """Integration test for the full pipeline."""

    def test_full_pipeline_runs(self):
        """The pipeline must execute without errors on realistic data."""
        np.random.seed(42)
        image = np.random.rand(20, 20) * 100
        dark_frame = np.random.rand(20, 20) * 2
        flat_field = np.random.rand(20, 20) * 50 + 10  # avoid zeros
        dark_for_flat = np.random.rand(20, 20) * 2
        result = ip.run_pipeline(image, dark_frame, flat_field, dark_for_flat)
        self.assertEqual(result.shape, (20, 20))
        self.assertTrue(np.all(np.isfinite(result)))
        self.assertTrue(np.all(result >= 0))

    def test_pipeline_deterministic(self):
        """Running the pipeline twice on the same input must give the same result."""
        np.random.seed(0)
        image = np.random.rand(10, 10) * 50
        dark_frame = np.ones((10, 10))
        flat_field = np.full((10, 10), 30.0)
        dark_for_flat = np.ones((10, 10))
        r1 = ip.run_pipeline(image, dark_frame, flat_field, dark_for_flat)
        r2 = ip.run_pipeline(image, dark_frame, flat_field, dark_for_flat)
        np.testing.assert_array_equal(r1, r2)


if __name__ == "__main__":
    unittest.main()
