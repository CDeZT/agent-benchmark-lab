"""Verify that the agent's test_stats.py exposes bugs in the buggy stats.py.

Strategy: Run the agent's tests against the BUGGY code. If the tests are
well-written, they should FAIL because they detect the bugs.

A test that PASSES against buggy code means the test either:
- Accommodates the bug (e.g., catches the exception and treats it as OK)
- Tests the wrong thing

A test that FAILS against buggy code means the test:
- Correctly expects behavior the buggy code doesn't deliver
- Exposes a bug through a failing assertion

We pass if enough tests fail (demonstrating the agent caught the bugs).
"""
import importlib
import importlib.util
import inspect
import sys
import traceback
import unittest
from pathlib import Path

MIN_BUGS_CAUGHT = 3  # agent must expose at least 3 of the 5 bugs


def _collect_tests(test_mod):
    """Collect test functions and test class instances from the module."""
    tests = []

    # Collect standalone test functions
    for name in dir(test_mod):
        obj = getattr(test_mod, name)
        if name.startswith("test_") and callable(obj) and not inspect.isclass(obj):
            tests.append((name, obj))

    # Collect unittest.TestCase subclasses and their test methods
    for name in dir(test_mod):
        obj = getattr(test_mod, name)
        if inspect.isclass(obj) and issubclass(obj, unittest.TestCase) and obj is not unittest.TestCase:
            instance = obj()
            for method_name in dir(instance):
                if method_name.startswith("test_"):
                    method = getattr(instance, method_name)
                    if callable(method):
                        tests.append((f"{name}.{method_name}", method))

    return tests


def main():
    test_file = Path(__file__).parent / "test_stats.py"
    if not test_file.is_file():
        print("FAIL: test_stats.py not found")
        sys.exit(1)

    # Import the agent's test module
    spec = importlib.util.spec_from_file_location("test_stats", test_file)
    if spec is None or spec.loader is None:
        print("FAIL: cannot load test_stats.py")
        sys.exit(1)

    test_mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(test_mod)
    except Exception as exc:
        print(f"FAIL: cannot import test_stats.py: {exc}")
        traceback.print_exc()
        sys.exit(1)

    # Collect all test functions
    tests = _collect_tests(test_mod)

    if len(tests) < 3:
        print(f"FAIL: expected at least 3 test functions, found {len(tests)}")
        sys.exit(1)

    # Run each test. A test that FAILS (raises any exception) is considered
    # to have caught a bug — it expects behavior the buggy code can't deliver.
    bugs_caught = 0
    tests_passed = 0

    for test_name, func in tests:
        try:
            func()
            tests_passed += 1
            print(f"  PASS (didn't catch bug): {test_name}")
        except Exception as exc:
            # Any exception (AssertionError, ZeroDivisionError, etc.)
            # means the test exposed a problem in the code.
            bugs_caught += 1
            print(f"  FAIL (caught a bug!): {test_name} -> {type(exc).__name__}: {exc}")

    print(f"\nSummary: {bugs_caught} bugs caught, {tests_passed} tests passed")
    print(f"Need {MIN_BUGS_CAUGHT} bugs caught to pass.")

    if bugs_caught >= MIN_BUGS_CAUGHT:
        print("PASS: Agent wrote effective bug-detecting tests!")
        sys.exit(0)
    else:
        print("FAIL: Agent's tests don't catch enough bugs.")
        sys.exit(1)


if __name__ == "__main__":
    main()
