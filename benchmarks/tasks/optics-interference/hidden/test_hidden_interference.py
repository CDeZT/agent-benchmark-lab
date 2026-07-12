import math
import os
import sys
from pathlib import Path

workspace = Path(os.environ["AGENT_BENCH_WORKSPACE"])
sys.path.insert(0, str(workspace))
from interference import young_fringe_spacing, path_difference


def almost(a, b, eps=1e-12):
    return abs(a - b) <= eps * max(1.0, abs(b))


assert almost(young_fringe_spacing(632.8e-9, 1e-4, 2.5), 632.8e-9 * 2.5 / 1e-4)
assert almost(path_difference(1e-3, 0.0), 0.0)
assert almost(path_difference(1e-3, math.pi / 2), 1e-3)

for args in ((-1, 1, 1), (1, 0, 1), (1, 1, -1)):
    try:
        young_fringe_spacing(*args)
        raise AssertionError(args)
    except ValueError:
        pass

print("hidden ok")
