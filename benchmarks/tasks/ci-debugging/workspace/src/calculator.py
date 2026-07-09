"""Calculator module with intentional bugs for CI debugging task."""


def add(a, b):
    """Add two numbers."""
    return a + b


def subtract(a, b):
    """Subtract b from a."""
    return a - b


def multiply(a, b):
    """Multiply two numbers."""
    return a * b


def divide(a, b):
    """Divide a by b.

    BUG: Doesn't handle division by zero properly.
    Should return None or raise a clear error, but currently crashes.
    """
    return a / b


def power(base, exp):
    """Raise base to the power of exp.

    BUG: Uses wrong operator for exponentiation.
    """
    return base * exp  # Should be base ** exp


def modulo(a, b):
    """Calculate a modulo b.

    BUG: Doesn't handle negative numbers correctly.
    """
    return a % b


def average(numbers):
    """Calculate average of a list of numbers.

    BUG: Doesn't handle empty list.
    """
    return sum(numbers) / len(numbers)


def factorial(n):
    """Calculate factorial of n.

    BUG: Doesn't handle negative numbers.
    """
    if n == 0:
        return 1
    return n * factorial(n - 1)
