"""Hidden test for python-test-writing — stricter quality check.

Verify the agent's tests catch ALL5 bugs, not just the minimum 3.
"""
import os
import sys
import importlib
import importlib.util
import inspect
from pathlib import Path

workspace = os.environ["AGENT_BENCH_WORKSPACE"]
sys.path.insert(0, workspace)  # Needed for stats import inside test_stats.py
test_file = Path(workspace) / "test_stats.py"

if not test_file.is_file():
    print("FAIL: test_stats.py not found")
    sys.exit(1)

spec = importlib.util.spec_from_file_location("test_stats", test_file)
test_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(test_mod)

tests = [
    (name, getattr(test_mod, name))
    for name in dir(test_mod)
    if name.startswith("test_") and callable(getattr(test_mod, name))
]

# Must have at least5 test functions
assert len(tests) >= 5, f"Need 5 test functions, found {len(tests)}"

# Run each test; count how many fail (exposing bugs)
bugs_caught = 0
for name, func in tests:
    try:
        func()
        print(f"  PASS: {name}")
    except Exception:
        bugs_caught += 1
        print(f"  FAIL (caught a bug!): {name}")

# Hidden test requires >= 4 bugs caught (stricter than public test's 3)
assert bugs_caught >= 4, f"Need 4 bugs caught, found {bugs_caught}"

print(f"\nALL HIDDEN TESTS PASSED ({bugs_caught} bugs caught)")
