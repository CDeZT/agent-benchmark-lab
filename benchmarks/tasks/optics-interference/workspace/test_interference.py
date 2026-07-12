import math
from interference import young_fringe_spacing, path_difference


def almost(a, b, eps=1e-12):
    return abs(a - b) <= eps * max(1.0, abs(b))


dy = young_fringe_spacing(500e-9, 0.25e-3, 1.0)
assert almost(dy, 500e-9 * 1.0 / 0.25e-3), dy

pd = path_difference(0.25e-3, math.radians(0.1))
assert almost(pd, 0.25e-3 * math.sin(math.radians(0.1))), pd

try:
    young_fringe_spacing(0, 1e-3, 1.0)
    raise AssertionError("expected ValueError")
except ValueError:
    pass

print("ok")
