import os
import sys
from pathlib import Path

workspace = os.environ.get("AGENT_BENCH_WORKSPACE", ".")
sys.path.insert(0, str(workspace))

from sort_utils import merge_sorted

# Edge cases
assert merge_sorted([1, 2, 3], [4, 5, 6]) == [1, 2, 3, 4, 5, 6]
assert merge_sorted([4, 5, 6], [1, 2, 3]) == [1, 2, 3, 4, 5, 6]
assert merge_sorted([1, 3, 5, 7], [2, 4]) == [1, 2, 3, 4, 5, 7]
assert merge_sorted([-3, -1, 0], [-2, 1, 2]) == [-3, -2, -1, 0, 1, 2]
assert merge_sorted([1, 1, 1], [1, 1]) == [1, 1, 1, 1, 1]
assert merge_sorted(list(range(100)), list(range(100, 200))) == list(range(200))
print("ALL HIDDEN TESTS PASSED")
