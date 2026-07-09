import os
import sys
from pathlib import Path

workspace = Path(os.environ["AGENT_BENCH_WORKSPACE"])
sys.path.insert(0, str(workspace))

from optics import normalize_profile


def close_list(left, right, eps=1e-9):
    return len(left) == len(right) and all(abs(a - b) < eps for a, b in zip(left, right))


assert close_list(normalize_profile([10.0, 12.0, 14.0]), [0.0, 0.5, 1.0])
assert close_list(normalize_profile([-5.0, -3.0, -1.0]), [0.0, 0.5, 1.0])
assert close_list(normalize_profile([0.0, 0.0]), [0.0, 0.0])
