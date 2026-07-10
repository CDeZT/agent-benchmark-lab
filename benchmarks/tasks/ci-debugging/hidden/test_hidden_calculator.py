"""Hidden tests for calculator module — edge cases not covered by public tests."""
import sys
import os
workspace = os.environ.get("AGENT_BENCH_WORKSPACE", ".")
sys.path.insert(0, os.path.join(workspace, "src"))

import calculator

# Edge case: divide by zero with negative numerator
assert calculator.divide(-5, 0) is None, "divide by zero should return None"

# Edge case: factorial of 0
assert calculator.factorial(0) == 1

# Edge case: factorial of non-integer result (should handle gracefully)
assert calculator.factorial(5) == 120

# Edge case: pow er with zero exponent
assert calculator.power(0, 0) == 1  # Python convention

# Edge case: pow er with large numbers
assert calculator.power(2, 10) == 1024

# Edge case: average of single element
assert calculator.average([42]) == 42.0

# Edge case: negative modulo
assert calculator.modulo(-5, 3) == 1

print("ALL HIDDEN TESTS PASSED")
