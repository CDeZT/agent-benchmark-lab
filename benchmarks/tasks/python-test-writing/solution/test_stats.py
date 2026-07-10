"""Reference tests that intentionally fail against the supplied buggy module."""

from stats import mean, median, mode, percentile, std_dev


def test_mean_empty_input_should_not_return_zero():
    assert mean([]) != 0


def test_median_even_values_is_average():
    assert median([1, 2, 3, 4]) == 2.5


def test_mode_returns_only_most_common_value():
    assert mode([1, 1, 2, 3]) == [1]


def test_std_dev_single_value_is_zero():
    assert std_dev([5]) == 0.0


def test_percentile_100_returns_final_value():
    assert percentile([1, 2, 3], 100) == 3
