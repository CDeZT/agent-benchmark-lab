import os
import sys
from pathlib import Path

workspace = Path(os.environ["AGENT_BENCH_WORKSPACE"])
sys.path.insert(0, str(workspace))
from abcd import free_space, thin_lens_matrix, cascade


def almost_mat(a, b, eps=1e-9):
    return all(abs(a[i][j] - b[i][j]) <= eps for i in range(2) for j in range(2))


# telescope-like: space d, lens f, space d
d, f = 10.0, 5.0
m = cascade([free_space(d), thin_lens_matrix(f), free_space(d)])
# Manual: M = free @ lens @ free  (last element is rightmost multiply-first in our convention M_n ... M_1)
# M1=free, M2=lens, M3=free => M = M3 @ M2 @ M1
assert almost_mat(m, [[1 - d / f, 2 * d - (d * d) / f], [-1 / f, 1 - d / f]]), m

try:
    thin_lens_matrix(0)
    raise AssertionError("expected ValueError")
except ValueError:
    pass

print("hidden ok")
