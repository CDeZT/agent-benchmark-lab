from stats import average


def test_average_regular_values():
    assert average([2, 4, 6]) == 4.0


def test_average_empty_values():
    assert average([]) == 0.0


if __name__ == "__main__":
    test_average_regular_values()
    test_average_empty_values()
