import math
import os
import sys
from pathlib import Path

workspace = Path(os.environ["AGENT_BENCH_WORKSPACE"])
sys.path.insert(0, str(workspace))
from snell import snell_refract, critical_angle


def almost(a, b, eps=1e-6):
    return abs(a - b) <= eps


# Normal incidence
assert almost(snell_refract(1.33, 1.0, 0.0), 0.0)

# Just below critical for water->air
n1, n2 = 1.33, 1.0
crit = math.degrees(math.asin(n2 / n1))
assert snell_refract(n1, n2, crit - 0.5) is not None
assert snell_refract(n1, n2, crit + 0.5) is None
assert almost(critical_angle(n1, n2), crit)

for bad in ((0, 1, 10), (1, 0, 10), (1, 1, -1), (1, 1, 91)):
    try:
        snell_refract(*bad)
        raise AssertionError(bad)
    except ValueError:
        pass

print("hidden ok")
