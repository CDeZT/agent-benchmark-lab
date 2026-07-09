"""Tests for data_processor — verifies refactoring preserves behavior."""
import data_processor


def test_process_data_basic():
    assert data_processor.process_data([1, 2, 3]) == [2, 4, 6]


def test_process_data_none():
    assert data_processor.process_data([None, None]) == [0, 0]


def test_process_data_negative():
    assert data_processor.process_data([-5, -1]) == [0, 0]


def test_process_data_zero():
    assert data_processor.process_data([0]) == [0]


def test_process_data_large():
    assert data_processor.process_data([2000]) == [1000]


def test_process_data_strings():
    assert data_processor.process_data(["5", "abc", "100"]) == [10, 0, 200]


def test_process_data_mixed():
    assert data_processor.process_data([1, None, "3", -2, "abc", 5000]) == [2, 0, 6, 0, 0, 1000]


def test_calculate_stats_normal():
    stats = data_processor.calculate_stats([1, 2, 3, 4, 5])
    assert stats["count"] == 5
    assert stats["sum"] == 15
    assert stats["avg"] == 3.0
    assert stats["min"] == 1
    assert stats["max"] == 5


def test_calculate_stats_empty():
    stats = data_processor.calculate_stats([])
    assert stats == {"count": 0, "sum": 0, "avg": 0, "min": 0, "max": 0}


def test_calculate_stats_with_none():
    stats = data_processor.calculate_stats([1, None, 3])
    assert stats["count"] == 2
    assert stats["sum"] == 4
    assert stats["avg"] == 2.0


def test_filter_and_sort_ascending():
    assert data_processor.filter_and_sort([3, 1, 4, 1, 5, 9, 2, 6]) == [1, 1, 2, 3, 4, 5, 6, 9]


def test_filter_and_sort_descending():
    assert data_processor.filter_and_sort([3, 1, 4, 1, 5, 9, 2, 6], reverse=True) == [9, 6, 5, 4, 3, 2, 1, 1]


def test_filter_and_sort_threshold():
    assert data_processor.filter_and_sort([1, 2, 3, 4, 5], threshold=3) == [4, 5]


def test_filter_and_sort_with_none():
    assert data_processor.filter_and_sort([1, None, 3, None, 5]) == [1, 3, 5]


if __name__ == "__main__":
    import sys
    passed = 0
    failed = 0
    for name, func in list(globals().items()):
        if name.startswith("test_") and callable(func):
            try:
                func()
                passed += 1
            except Exception as e:
                print(f"FAIL: {name}: {e}")
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
