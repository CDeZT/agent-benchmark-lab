"""Statistics utility module.

NOTE: This module contains several bugs. Your task is to write tests that
expose them. Each function has at least one edge case where it produces
incorrect results or crashes.
"""


def mean(numbers: list[float]) -> float:
    """Return the arithmetic mean of a list of numbers.

    BUG: Returns 0 for empty list instead of raising an error.
    An empty list has no meaningful mean.
    """
    if not numbers:
        return 0
    return sum(numbers) / len(numbers)


def median(numbers: list[float]) -> float:
    """Return the median value.

    BUG: For even-length lists, returns the upper-middle element instead
    of the average of the two middle elements.
    median([1, 2, 3, 4]) should be 2.5, not 3.
    """
    sorted_nums = sorted(numbers)
    n = len(sorted_nums)
    mid = n // 2
    return sorted_nums[mid]


def mode(numbers: list[float]) -> list[float]:
    """Return the most frequently occurring value(s).

    BUG: Always returns all input values instead of only the most
    frequent one(s).
    mode([1, 1, 2, 3]) should return [1], not [1, 2, 3].
    """
    return list(set(numbers))


def std_dev(numbers: list[float]) -> float:
    """Return the population standard deviation.

    BUG: Uses sample standard deviation formula (divides by n-1) but
    still calls it "population" std_dev. For a single element, this
    crashes with ZeroDivisionError.
    """
    avg = mean(numbers)
    variance = sum((x - avg) ** 2 for x in numbers) / (len(numbers) - 1)
    return variance ** 0.5


def percentile(numbers: list[float], p: float) -> float:
    """Return the p-th percentile (0-100).

    BUG: Off-by-one at p=100. The formula k = int(p/100 * n) gives
    k=n when p=100, which causes an IndexError.
    """
    sorted_nums = sorted(numbers)
    n = len(sorted_nums)
    k = int(p / 100 * n)
    return sorted_nums[k]
