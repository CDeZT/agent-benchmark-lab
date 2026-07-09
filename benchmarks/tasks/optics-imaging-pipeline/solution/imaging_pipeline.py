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
# Pipeline stages
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
    image = np.asarray(image, dtype=np.float64)
    dark_frame = np.asarray(dark_frame, dtype=np.float64)

    if image.shape != dark_frame.shape:
        raise ValueError(
            f"Shape mismatch: image {image.shape} vs dark_frame {dark_frame.shape}"
        )

    result = image - dark_frame
    return np.clip(result, 0.0, None).astype(np.float64)


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
    (after normalising the map to a max of 1) corrects for vignetting,
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
    image = np.asarray(image, dtype=np.float64)
    flat_field = np.asarray(flat_field, dtype=np.float64)
    dark_for_flat = np.asarray(dark_for_flat, dtype=np.float64)

    if not (image.shape == flat_field.shape == dark_for_flat.shape):
        raise ValueError(
            f"Shape mismatch: image {image.shape}, flat_field {flat_field.shape}, "
            f"dark_for_flat {dark_for_flat.shape}"
        )

    # Correct the flat field by subtracting its own dark frame
    corrected_flat = flat_field - dark_for_flat
    # Clip to zero: negative values are unphysical (dark > flat means noise)
    corrected_flat = np.clip(corrected_flat, 0.0, None)

    # Normalise so the max of the corrected flat is 1 (relative sensitivity map)
    max_val = np.max(corrected_flat)
    if max_val == 0.0:
        # Entire flat is zero after dark subtraction – return zeros
        return np.zeros_like(image, dtype=np.float64)

    normalised_flat = corrected_flat / max_val

    # Protect against division by zero on a per-pixel basis
    with np.errstate(divide="ignore", invalid="ignore"):
        result = np.where(normalised_flat != 0.0, image / normalised_flat, 0.0)

    return result.astype(np.float64)


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
    zero-padded boundaries.

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
    image = np.asarray(image, dtype=np.float64)

    if image.size == 0:
        return np.zeros(image.shape, dtype=bool)

    n_total = neighborhood * neighborhood  # total pixels in window

    # Compute local sum and sum-of-squares via uniform_filter (reflect boundaries)
    local_sum = ndimage.uniform_filter(image, size=neighborhood, mode="reflect") * n_total
    local_sq_sum = ndimage.uniform_filter(image ** 2, size=neighborhood, mode="reflect") * n_total

    # Exclude the center pixel from local statistics so that a hot pixel
    # does not inflate its own neighbourhood mean / std.
    n = n_total - 1  # pixels excluding center
    sum_excl = local_sum - image
    mean_excl = sum_excl / n

    # Variance excluding center: (sum_sq_excl - sum_excl^2 / n) / (n - 1)
    sum_sq_excl = local_sq_sum - image ** 2
    local_var = (sum_sq_excl - sum_excl ** 2 / n) / (n - 1)
    local_var = np.clip(local_var, 0.0, None)
    local_std = np.sqrt(local_var)

    # Where local_std is 0 (uniform neighbourhood), any pixel differing from
    # the mean is an outlier by definition; use mean as threshold.
    threshold_map = np.where(local_std > 0,
                             mean_excl + sigma_threshold * local_std,
                             mean_excl)

    return (image > threshold_map).astype(bool)


def apply_gaussian_blur(
    image: np.ndarray,
    kernel_size: int = 5,
    sigma: float = 1.0,
) -> np.ndarray:
    """Apply Gaussian low-pass filtering for noise reduction.

    Convolve the image with a normalised Gaussian kernel.  Boundary pixels
    should be handled by zero-padding (i.e. values outside the image are
    assumed to be 0).  Use the provided ``_gaussian_kernel`` helper.

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
    image = np.asarray(image, dtype=np.float64)
    kernel = _gaussian_kernel(kernel_size, sigma)
    # Reflect boundary to avoid energy loss at edges
    result = ndimage.convolve(image, kernel, mode="reflect")
    return result.astype(np.float64)


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
    # Step 1: Dark subtraction
    calibrated = dark_frame_subtraction(image, dark_frame)

    # Step 2: Flat-field correction
    calibrated = flat_field_correction(calibrated, flat_field, dark_for_flat)

    # Step 3: Hot-pixel detection and replacement
    hot_mask = detect_hot_pixels(calibrated)
    if np.any(hot_mask):
        # Replace hot pixels with local mean (excluding the hot pixel itself)
        local_mean = ndimage.uniform_filter(calibrated, size=5, mode="constant", cval=0.0)
        calibrated = np.where(hot_mask, local_mean, calibrated)

    # Step 4: Gaussian blur
    calibrated = apply_gaussian_blur(calibrated)

    # Final safety clip – physical sensor output cannot be negative
    return np.clip(calibrated, 0.0, None).astype(np.float64)
