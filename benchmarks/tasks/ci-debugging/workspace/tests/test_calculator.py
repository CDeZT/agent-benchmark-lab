"""Tests for calculator module."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import calculator


def test_add():
    assert calculator.add(2, 3) == 5
    assert calculator.add(-1, 1) == 0


def test_subtract():
    assert calculator.subtract(5, 3) == 2
    assert calculator.subtract(3, 5) == -2


def test_multiply():
    assert calculator.multiply(2, 3) == 6
    assert calculator.multiply(-2, 3) == -6


def test_divide():
    assert calculator.divide(6, 3) == 2.0
    assert calculator.divide(5, 2) == 2.5
    # BUG: This will crash with ZeroDivisionError
    assert calculator.divide(5, 0) is None


def test_power():
    assert calculator.power(2, 3) == 8
    assert calculator.power(5, 0) == 1


def test_modulo():
    assert calculator.modulo(10, 3) == 1
    assert calculator.modulo(-1, 3) == 2  # Python returns 2, not -1


def test_average():
    assert calculator.average([1, 2, 3]) == 2.0
    # BUG: This will crash with ZeroDivisionError
    assert calculator.average([]) == 0


def test_factorial():
    assert calculator.factorial(5) == 120
    assert calculator.factorial(0) == 1
    # BUG: This will crash with RecursionError
    assert calculator.factorial(-1) is None
