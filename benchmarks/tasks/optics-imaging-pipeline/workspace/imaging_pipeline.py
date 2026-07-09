"""
Camera Sensor Calibration and Imaging Pipeline

This module implements a raw image processing pipeline for scientific CCD/CMOS
cameras. Raw sensor data contains several sources of error that must be corrected
before the image is suitable for analysis:

1. **Dark current / read noise**: Even with the shutter closed, thermal electrons
   accumulate on the sensor.  A "dark frame" captured with the shutter closed
   records this pattern and is subtracted from every science exposure.

2. **Pixel-to-pixel sensitivity variation**: No sensor has perfectly uniform
   quantum efficiency across every pixel.  A "flat field" image, taken of an
   evenly illuminated target, reveals the sensitivity map.  Dividing the
   science image by the (dark-subtracted) flat field normalises the response.

3. **Hot pixels**: Some pixels are defective and produce anomalously high
   signals regardless of illumination.  These are detected as statistical
   outliers in a local neighbourhood and flagged/replaced.

4. **Noise reduction**: A Gaussian low-pass filter suppresses high-frequency
   noise while preserving large-scale structure.

All images are represented as 2-D numpy float64 arrays (row, col).
"""

import numpy as np
from scipy import ndimage


# ---------------------------------------------------------------------------
# Helper – already implemented so you can focus on the pipeline steps
# ---------------------------------------------------------------------------

def _gaussian_kernel(size: int, sigma: float) -> np.ndarray:
    """Return a 2-D Gaussian kernel of shape (size, size).

    The kernel is normalised so that its elements sum to 1.0.

    Parameters
    ----------
    size : int
        Kernel side length (must be odd).
    sigma : float
        Standard deviation of the Gaussian in pixels.

    Returns
    -------
    np.ndarray
        2-D array of shape (size, size) with float64 dtype.
    """
    ax = np.arange(size) - size // 2
    xx, yy = np.meshgrid(ax, ax)
    kernel = np.exp(-(xx ** 2 + yy ** 2) / (2.0 * sigma ** 2))
    return kernel / kernel.sum()


# ---------------------------------------------------------------------------
# Pipeline stages – implement each of these
# ---------------------------------------------------------------------------

def dark_frame_subtraction(image: np.ndarray, dark_frame: np.ndarray) -> np.ndarray:
    """Subtract a dark frame from a science image to remove readout noise.

    The dark frame captures the thermal / read-noise pattern of the sensor
    when no light reaches it.  Subtracting it isolates the photo-electron
    signal.  Any resulting negative values should be clipped to zero because
    a physical sensor cannot produce a negative photon count.

    Parameters
    ----------
    image : np.ndarray
        2-D raw science image (float64).
    dark_frame : np.ndarray
        2-D dark frame with the same shape as *image*.

    Returns
    -------
    np.ndarray
        Dark-subtracted image, clipped to >= 0, dtype float64.

    Raises
    ------
    ValueError
        If the shapes of *image* and *dark_frame* do not match.
    """
    raise NotImplementedError


def flat_field_correction(
    image: np.ndarray,
    flat_field: np.ndarray,
    dark_for_flat: np.ndarray,
) -> np.ndarray:
    """Normalise pixel sensitivity using a flat-field frame.

    A flat-field image is taken under uniform illumination and reveals the
    relative sensitivity of every pixel.  After subtracting the dark current
    that was present during the flat-field exposure (*dark_for_flat*), the
    result is a sensitivity map.  Dividing the science image by this map
    (after normalising the map so its maximum equals 1) corrects for vignetting,
    dust shadows, and pixel QE variation.

    Division-by-zero protection: if a pixel in the corrected flat is zero
    (e.g. a dead pixel or dust mote), the output for that pixel should be set
    to 0.0 rather than producing inf or NaN.

    Parameters
    ----------
    image : np.ndarray
        2-D science image (already dark-subtracted, float64).
    flat_field : np.ndarray
        2-D flat-field image (float64).
    dark_for_flat : np.ndarray
        2-D dark frame taken at the same exposure as the flat field.

    Returns
    -------
    np.ndarray
        Flat-field-corrected image, dtype float64.

    Raises
    ------
    ValueError
        If array shapes do not all match.
    """
    raise NotImplementedError


def detect_hot_pixels(
    image: np.ndarray,
    sigma_threshold: float = 5.0,
    neighborhood: int = 5,
) -> np.ndarray:
    """Detect hot pixels as local statistical outliers.

    A *hot pixel* is one whose value is significantly higher than its local
    neighbourhood mean.  Specifically, a pixel is flagged if:

        value > local_mean + sigma_threshold * local_std

    The local mean and standard deviation are computed over a square
    neighbourhood of side *neighborhood* centred on each pixel, using
    reflected boundaries.

    Parameters
    ----------
    image : np.ndarray
        2-D image (float64).
    sigma_threshold : float
        Number of standard deviations above the local mean to flag.
    neighborhood : int
        Side length of the local window (must be odd).

    Returns
    -------
    np.ndarray
        Boolean mask with True at hot-pixel locations, same shape as *image*.
    """
    raise NotImplementedError


def apply_gaussian_blur(
    image: np.ndarray,
    kernel_size: int = 5,
    sigma: float = 1.0,
) -> np.ndarray:
    """Apply Gaussian low-pass filtering for noise reduction.

    Convolve the image with a normalised Gaussian kernel.  Use reflected
    boundary handling to avoid energy loss at image edges.  Use the provided
    ``_gaussian_kernel`` helper.

    Parameters
    ----------
    image : np.ndarray
        2-D image (float64).
    kernel_size : int
        Side length of the Gaussian kernel (odd integer).
    sigma : float
        Standard deviation of the Gaussian in pixels.

    Returns
    -------
    np.ndarray
        Blurred image, same shape as *image*, dtype float64.
    """
    raise NotImplementedError


def run_pipeline(
    image: np.ndarray,
    dark_frame: np.ndarray,
    flat_field: np.ndarray,
    dark_for_flat: np.ndarray,
) -> np.ndarray:
    """Execute the full calibration pipeline in order:

    1. Dark-frame subtraction
    2. Flat-field correction
    3. Hot-pixel detection and replacement (replace hot pixels with local mean)
    4. Gaussian blur (noise reduction)

    Parameters
    ----------
    image : np.ndarray
        Raw science image (float64).
    dark_frame : np.ndarray
        Dark frame for the science exposure.
    flat_field : np.ndarray
        Flat-field image.
    dark_for_flat : np.ndarray
        Dark frame for the flat-field exposure.

    Returns
    -------
    np.ndarray
        Fully calibrated image, dtype float64.
    """
    raise NotImplementedError
