"""Hidden tests for data_processor refactoring — deep behavior checks."""
import os
import sys
workspace = os.environ["AGENT_BENCH_WORKSPACE"]
sys.path.insert(0, workspace)

import data_processor

# Edge case: all None input
assert data_processor.process_data([None, None, None]) == [0, 0, 0]

# Edge case: very large dataset
large_data = list(range(1000))
result = data_processor.process_data(large_data)
assert len(result) == 1000
assert result[0] == 0  # 0 * 2 = 0
assert result[1] == 2  # 1 * 2 = 2
assert result[500] == 1000  # Clamped

# Edge case: empty input
assert data_processor.process_data([]) == []

# Edge case: stats with extreme values
stats = data_processor.calculate_stats([-1000, 0, 1000000])
assert stats["min"] == -1000
assert stats["max"] == 1000000
assert stats["count"] == 3

# Edge case: filter and sort with custom threshold
result = data_processor.filter_and_sort([5, 10, 15, 20], threshold=10)
assert result == [15, 20]

# Edge case: filter_and_sort all excluded
result = data_processor.filter_and_sort([1, 2, 3], threshold=10)
assert result == []

print("ALL HIDDEN TESTS PASSED")
