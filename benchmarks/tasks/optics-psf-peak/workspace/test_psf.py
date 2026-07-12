from psf import measure_psf


def almost(a, b, eps=1e-6):
    return abs(a - b) <= eps


def check(samples, peak, fwhm):
    got_peak, got_fwhm = measure_psf(samples)
    assert almost(got_peak, peak), (got_peak, peak)
    assert almost(got_fwhm, fwhm), (got_fwhm, fwhm)


# Triangle peak at center: half-max width should be 4 samples with interpolation.
check([0.0, 0.5, 1.0, 0.5, 0.0], 1.0, 2.0)
check([0.0, 0.0, 0.0], 0.0, 0.0)
check([], 0.0, 0.0)
# Wider lobe (half-max between 0.2 and 0.8 on each side)
check([0.1, 0.2, 0.8, 1.0, 0.8, 0.2, 0.1], 1.0, 3.0)
print("ok")
