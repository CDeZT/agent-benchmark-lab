import os
import sys
from pathlib import Path

workspace = Path(os.environ["AGENT_BENCH_WORKSPACE"])
sys.path.insert(0, str(workspace))
from psf import measure_psf


def almost(a, b, eps=1e-6):
    return abs(a - b) <= eps


peak, fwhm = measure_psf([0.0, 0.25, 0.5, 1.0, 0.5, 0.25, 0.0])
assert almost(peak, 1.0)
assert almost(fwhm, 2.0)

peak, fwhm = measure_psf([2.0, 2.0, 2.0])
assert almost(peak, 2.0)
assert almost(fwhm, 0.0)

peak, fwhm = measure_psf([-1.0, 0.0, 3.0, 0.0, -1.0])
assert almost(peak, 3.0)
assert almost(fwhm, 1.0)
print("hidden ok")
