import math
import os
import sys
from pathlib import Path

workspace = Path(os.environ["AGENT_BENCH_WORKSPACE"])
sys.path.insert(0, str(workspace))
from beam import gaussian_beam


def almost(a, b, eps=1e-9):
    if math.isinf(a) and math.isinf(b):
        return True
    return abs(a - b) <= eps * max(1.0, abs(b))


lam = 1064e-9
w0 = 2.5e-4
zr = math.pi * w0 ** 2 / lam
z = -3.0 * zr
out = gaussian_beam(lam, w0, z)
assert almost(out["rayleigh_m"], zr)
assert almost(out["w_m"], w0 * math.sqrt(1.0 + (z / zr) ** 2))
assert almost(out["curvature_m"], z * (1.0 + (zr / z) ** 2))

for bad in ((-1e-6, 1e-3, 0), (1e-6, 0, 0), (1e-6, -1, 0)):
    try:
        gaussian_beam(*bad)
        raise AssertionError(bad)
    except ValueError:
        pass

print("hidden ok")
