"""Hidden tests for the imaging pipeline – catches real bugs.

Run with:  python3 test_hidden_pipeline.py

Uses AGENT_BENCH_WORKSPACE to locate the workspace implementation.
"""

import os
import sys
import unittest

import numpy as np

ws = os.environ.get("AGENT_BENCH_WORKSPACE", os.path.join(os.path.dirname(__file__), "..", "workspace"))
sys.path.insert(0, ws)

import imaging_pipeline as ip


# ======================================================================
# Dark-frame subtraction – edge cases
# ======================================================================

class TestDarkSubtractionEdgeCases(unittest.TestCase):

    def test_zero_image_and_dark(self):
        """Both zero arrays must produce zeros."""
        img = np.zeros((4, 4))
        dark = np.zeros((4, 4))
        result = ip.dark_frame_subtraction(img, dark)
        np.testing.assert_array_equal(result, np.zeros((4, 4)))

    def test_large_values(self):
        """Very large values must not overflow (float64 handles this, but check)."""
        img = np.full((3, 3), 1e15)
        dark = np.full((3, 3), 1e15 - 1.0)
        result = ip.dark_frame_subtraction(img, dark)
        np.testing.assert_allclose(result, 1.0, rtol=1e-10)

    def test_negative_dark_frame(self):
        """A negative dark frame (bias-subtracted) should increase values."""
        img = np.full((3, 3), 100.0)
        dark = np.full((3, 3), -10.0)
        result = ip.dark_frame_subtraction(img, dark)
        np.testing.assert_allclose(result, 110.0)

    def test_1x1_image(self):
        """Single-pixel image must work."""
        result = ip.dark_frame_subtraction(np.array([[5.0]]), np.array([[2.0]]))
        np.testing.assert_allclose(result, np.array([[3.0]]))

    def test_2x2_image(self):
        img = np.array([[1.0, 2.0], [3.0, 4.0]])
        dark = np.array([[0.5, 0.5], [0.5, 0.5]])
        result = ip.dark_frame_subtraction(img, dark)
        expected = np.array([[0.5, 1.5], [2.5, 3.5]])
        np.testing.assert_allclose(result, expected)

    def test_output_is_float64(self):
        """Output must always be float64 regardless of input dtype."""
        img = np.ones((2, 2), dtype=np.int32)
        dark = np.zeros((2, 2), dtype=np.int32)
        result = ip.dark_frame_subtraction(img, dark)
        self.assertEqual(result.dtype, np.float64)


# ======================================================================
# Flat-field correction – edge cases
# ======================================================================

class TestFlatFieldEdgeCases(unittest.TestCase):

    def test_all_zero_flat_field(self):
        """An entirely zero flat field (dead sensor) must not crash."""
        img = np.array([[10.0, 20.0]])
        flat = np.zeros((1, 2))
        dark_flat = np.zeros((1, 2))
        result = ip.flat_field_correction(img, flat, dark_flat)
        self.assertTrue(np.all(np.isfinite(result)))
        # Result should be zeros since we cannot correct
        np.testing.assert_array_equal(result, np.zeros((1, 2)))

    def test_flat_equals_dark(self):
        """When flat == dark, corrected flat is all zeros."""
        img = np.array([[100.0, 200.0]])
        flat = np.array([[50.0, 50.0]])
        dark_flat = np.array([[50.0, 50.0]])
        result = ip.flat_field_correction(img, flat, dark_flat)
        self.assertTrue(np.all(np.isfinite(result)))

    def test_single_pixel(self):
        """Single pixel must not crash."""
        img = np.array([[42.0]])
        flat = np.array([[10.0]])
        dark_flat = np.array([[2.0]])
        result = ip.flat_field_correction(img, flat, dark_flat)
        self.assertEqual(result.shape, (1, 1))
        self.assertTrue(np.isfinite(result[0, 0]))

    def test_shape_mismatch_raises(self):
        with self.assertRaises(ValueError):
            ip.flat_field_correction(
                np.ones((3, 3)), np.ones((3, 4)), np.ones((3, 3))
            )

    def test_no_negative_output(self):
        """Output should not contain negatives from correction artifacts."""
        img = np.array([[10.0, 20.0, 30.0]])
        flat = np.array([[100.0, 0.001, 100.0]])
        dark_flat = np.array([[1.0, 0.0, 1.0]])
        result = ip.flat_field_correction(img, flat, dark_flat)
        # The middle pixel gets a huge correction factor; check finiteness
        self.assertTrue(np.all(np.isfinite(result)))


# ======================================================================
# Hot-pixel detection – edge cases
# ======================================================================

class TestHotPixelEdgeCases(unittest.TestCase):

    def test_empty_image(self):
        """An empty image must return an empty boolean mask."""
        img = np.empty((0, 0))
        mask = ip.detect_hot_pixels(img, sigma_threshold=5.0, neighborhood=5)
        self.assertEqual(mask.shape, (0, 0))
        self.assertEqual(mask.dtype, bool)

    def test_1x1_image(self):
        """A single pixel cannot be an outlier – should return False."""
        img = np.array([[999.0]])
        mask = ip.detect_hot_pixels(img, sigma_threshold=5.0, neighborhood=5)
        self.assertFalse(mask[0, 0])

    def test_2x2_image(self):
        """Very small image – must not crash."""
        img = np.array([[1.0, 1.0], [1.0, 1000.0]])
        mask = ip.detect_hot_pixels(img, sigma_threshold=5.0, neighborhood=3)
        self.assertEqual(mask.shape, (2, 2))
        self.assertEqual(mask.dtype, bool)

    def test_no_hot_pixels_uniform(self):
        """Uniform image – no hot pixels regardless of threshold."""
        img = np.full((20, 20), 100.0)
        mask = ip.detect_hot_pixels(img, sigma_threshold=1.0, neighborhood=5)
        self.assertFalse(np.any(mask))

    def test_multiple_hot_pixels(self):
        """Multiple hot pixels should all be detected."""
        img = np.zeros((15, 15))
        hot_coords = [(2, 2), (7, 7), (13, 13)]
        for r, c in hot_coords:
            img[r, c] = 1e6
        mask = ip.detect_hot_pixels(img, sigma_threshold=5.0, neighborhood=5)
        for r, c in hot_coords:
            self.assertTrue(mask[r, c], f"Hot pixel at ({r},{c}) not detected")

    def test_threshold_sensitivity(self):
        """Higher threshold should flag fewer pixels."""
        img = np.random.RandomState(42).randn(20, 20) * 10
        img[10, 10] = 200.0  # moderate outlier
        mask_loose = ip.detect_hot_pixels(img, sigma_threshold=3.0, neighborhood=5)
        mask_strict = ip.detect_hot_pixels(img, sigma_threshold=10.0, neighborhood=5)
        # At low threshold, more pixels may be flagged
        self.assertGreaterEqual(mask_loose.sum(), mask_strict.sum())


# ======================================================================
# Gaussian blur – edge cases
# ======================================================================

class TestGaussianBlurEdgeCases(unittest.TestCase):

    def test_preserves_sum_energy(self):
        """Gaussian blur must preserve the total energy (sum of pixels)."""
        img = np.zeros((21, 21))
        img[10, 10] = 1000.0  # all energy in one pixel
        result = ip.apply_gaussian_blur(img, kernel_size=7, sigma=2.0)
        # With zero-padding some energy leaks out of the boundary, so allow
        # a small tolerance.  But most should be preserved.
        self.assertAlmostEqual(result.sum(), 1000.0, delta=50.0)

    def test_constant_image_preserved(self):
        """A constant image must remain constant after blur."""
        img = np.full((10, 10), 7.5)
        result = ip.apply_gaussian_blur(img, kernel_size=5, sigma=1.0)
        np.testing.assert_allclose(result, 7.5, atol=1e-12)

    def test_output_shape_matches_input(self):
        """Output shape must always equal input shape."""
        for shape in [(1, 1), (3, 5), (50, 30)]:
            img = np.ones(shape)
            result = ip.apply_gaussian_blur(img, kernel_size=5, sigma=1.0)
            self.assertEqual(result.shape, shape, f"Shape mismatch for input {shape}")

    def test_1x1_image(self):
        """Single-pixel image – blur must not crash."""
        img = np.array([[42.0]])
        result = ip.apply_gaussian_blur(img, kernel_size=3, sigma=0.5)
        self.assertEqual(result.shape, (1, 1))
        self.assertTrue(np.isfinite(result[0, 0]))

    def test_kernel_sums_to_one(self):
        """The Gaussian kernel itself must sum to 1."""
        k = ip._gaussian_kernel(7, 2.0)
        self.assertAlmostEqual(k.sum(), 1.0, places=12)

    def test_kernel_symmetric(self):
        """The kernel must be symmetric."""
        k = ip._gaussian_kernel(5, 1.0)
        np.testing.assert_allclose(k, k.T, atol=1e-15)
        np.testing.assert_allclose(k, k[::-1, ::-1], atol=1e-15)


# ======================================================================
# Pipeline integration
# ======================================================================

class TestPipelineIntegration(unittest.TestCase):

    def test_deterministic(self):
        """Running the pipeline twice must give bit-identical results."""
        np.random.seed(99)
        image = np.random.rand(15, 15) * 100
        dark = np.random.rand(15, 15)
        flat = np.random.rand(15, 15) * 40 + 10
        dark_flat = np.random.rand(15, 15)
        r1 = ip.run_pipeline(image, dark, flat, dark_flat)
        r2 = ip.run_pipeline(image, dark, flat, dark_flat)
        np.testing.assert_array_equal(r1, r2)

    def test_pipeline_no_nan_inf(self):
        """Pipeline must never produce NaN or Inf under any normal input."""
        np.random.seed(7)
        image = np.random.rand(10, 10) * 500
        dark = np.random.rand(10, 10) * 5
        flat = np.random.rand(10, 10) * 50 + 1
        dark_flat = np.random.rand(10, 10) * 5
        result = ip.run_pipeline(image, dark, flat, dark_flat)
        self.assertTrue(np.all(np.isfinite(result)), "Pipeline produced NaN or Inf")

    def test_pipeline_with_hot_pixels(self):
        """Hot pixels in the input should be suppressed in the output."""
        np.random.seed(123)
        image = np.random.rand(20, 20) * 50
        image[5, 5] = 1e6  # hot pixel
        dark = np.ones((20, 20))
        flat = np.full((20, 20), 40.0)
        dark_flat = np.ones((20, 20))
        result = ip.run_pipeline(image, dark, flat, dark_flat)
        # The hot pixel should have been replaced and blurred – its value
        # should be far less than 1e6
        self.assertLess(result[5, 5], 1e4,
                        "Hot pixel was not adequately suppressed")

    def test_pipeline_output_nonnegative(self):
        """Output values must all be >= 0."""
        np.random.seed(0)
        image = np.random.rand(10, 10) * 100
        dark = np.random.rand(10, 10) * 10
        flat = np.random.rand(10, 10) * 30 + 5
        dark_flat = np.random.rand(10, 10) * 10
        result = ip.run_pipeline(image, dark, flat, dark_flat)
        self.assertTrue(np.all(result >= 0), "Pipeline produced negative values")

    def test_pipeline_dtype_float64(self):
        """Final output must be float64."""
        image = np.ones((5, 5))
        dark = np.zeros((5, 5))
        flat = np.full((5, 5), 20.0)
        dark_flat = np.zeros((5, 5))
        result = ip.run_pipeline(image, dark, flat, dark_flat)
        self.assertEqual(result.dtype, np.float64)


if __name__ == "__main__":
    unittest.main()
