def measure_psf(samples):
    # Buggy baseline: always reports FWHM=1 and mishandles empty/non-positive peaks.
    if not samples:
        return (0.0, 1.0)
    return (max(samples) * 1.0, 1.0)
