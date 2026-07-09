"""Calculator module - fixed version."""


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
    """Divide a by b."""
    if b == 0:
        return None
    return a / b


def power(base, exp):
    """Raise base to the power of exp."""
    return base ** exp


def modulo(a, b):
    """Calculate a modulo b."""
    return a % b


def average(numbers):
    """Calculate average of a list of numbers."""
    if not numbers:
        return 0
    return sum(numbers) / len(numbers)


def factorial(n):
    """Calculate factorial of n."""
    if n < 0:
        return None
    if n == 0:
        return 1
    return n * factorial(n - 1)
