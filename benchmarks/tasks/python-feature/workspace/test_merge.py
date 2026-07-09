from sort_utils import merge_sorted

assert merge_sorted([1, 3, 5], [2, 4, 6]) == [1, 2, 3, 4, 5, 6]
assert merge_sorted([], [1, 2]) == [1, 2]
assert merge_sorted([1, 2], []) == [1, 2]
assert merge_sorted([], []) == []
assert merge_sorted([1], [1]) == [1, 1]
print("ALL TESTS PASSED")
