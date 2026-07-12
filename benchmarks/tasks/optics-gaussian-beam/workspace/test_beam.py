import math
from beam import gaussian_beam


def almost(a, b, eps=1e-9):
    if math.isinf(a) and math.isinf(b):
        return True
    return abs(a - b) <= eps * max(1.0, abs(b))


lam = 632.8e-9
w0 = 1.0e-3
out = gaussian_beam(lam, w0, 0.0)
zr = math.pi * w0 ** 2 / lam
assert almost(out["rayleigh_m"], zr)
assert almost(out["w_m"], w0)
assert math.isinf(out["curvature_m"])

out2 = gaussian_beam(lam, w0, zr)
assert almost(out2["w_m"], w0 * math.sqrt(2.0))
assert almost(out2["curvature_m"], 2.0 * zr)

try:
    gaussian_beam(0.0, w0, 0.0)
    raise AssertionError("expected ValueError")
except ValueError:
    pass

print("ok")
