"""Hidden tests for the data pipeline.

These test edge cases and cross-module correctness:
1. Fahrenheit data should produce valid heat_index values
2. Heat index should be in Celsius (matching temperature)
3. Pipeline should handle mixed valid/invalid data
4. Validation should not reject valid Fahrenheit-converted data
"""

import sys
import os
from pathlib import Path

workspace = Path(os.environ["AGENT_BENCH_WORKSPACE"])
sys.path.insert(0, str(workspace))

from pipeline.reader import read_csv
from pipeline.transformer import transform_rows, _calculate_heat_index
from pipeline.validator import validate_rows
from run_pipeline import run_pipeline


# --- Critical Cross-Module Bug Test ---

def test_fahrenheit_data_not_rejected_by_validator():
    """BUG TEST: Fahrenheit data that gets converted to Celsius should NOT be
    rejected by the validator. The bug is that heat_index is calculated in
    Fahrenheit but validated against Celsius range."""
    csv_data = """timestamp,temperature,humidity,pressure
2024-01-15T10:00:00,72.0,45.0,1013.2
2024-01-15T11:00:00,85.0,60.0,1012.0
"""
    rows = read_csv(csv_data)
    transformed = transform_rows(rows)
    valid, invalid = validate_rows(transformed)

    # With the bug, rows with Fahrenheit data get heat_index in F (e.g., 72.0)
    # which is then validated against Celsius range [-50, 60]. This passes for
    # low F values but fails for higher ones like 85F where heat_index > 60.
    assert len(invalid) == 0, (
        f"Valid Fahrenheit data was rejected by validator: {invalid}. "
        "This indicates a mismatch between heat_index units and validation range."
    )


def test_heat_index_is_in_celsius():
    """After fixing the bug, heat_index should be in Celsius for data that
    was converted from Fahrenheit."""
    csv_data = """timestamp,temperature,humidity,pressure
2024-01-15T10:00:00,85.0,70.0,1012.0
"""
    rows = read_csv(csv_data)
    transformed = transform_rows(rows)

    temp_c = transformed[0]["temperature"]
    hi = transformed[0]["heat_index"]

    # Heat index should be in the same unit range as temperature
    # If temp is ~29.4C, heat_index should also be in Celsius range
    assert hi < 60, f"Heat index {hi} is out of Celsius range (temp={temp_c}C)"
    assert hi > -50, f"Heat index {hi} is out of Celsius range"


def test_pipeline_with_mixed_valid_invalid():
    """Pipeline should process valid rows and report invalid ones."""
    csv_data = """timestamp,temperature,humidity,pressure
2024-01-15T10:00:00,22.5,45.0,1013.2
2024-01-15T11:00:00,999.0,55.0,1015.0
2024-01-15T12:00:00,20.0,40.0,1014.0
"""
    result = run_pipeline(csv_data)
    assert result["error"] is None
    assert result["summary"]["invalid_rows"] == 1
    assert result["summary"]["valid_rows"] == 2


def test_empty_csv_raises_error():
    """Empty CSV should raise a clear error."""
    csv_data = "timestamp,temperature,humidity,pressure\n"
    try:
        result = run_pipeline(csv_data)
        # Should either raise or return an error
        assert result.get("error") is not None, "Empty CSV should produce an error"
    except ValueError:
        pass  # Also acceptable


def test_null_handling():
    """Null values should be handled gracefully."""
    csv_data = """timestamp,temperature,humidity,pressure
2024-01-15T10:00:00,null,45.0,1013.2
2024-01-15T11:00:00,22.0,NA,1015.0
"""
    rows = read_csv(csv_data)
    assert rows[0]["temperature"] is None
    assert rows[1]["humidity"] is None


def test_heat_index_consistency():
    """Heat index should be consistent with temperature (same unit system)."""
    # Celsius data
    celsius_csv = """timestamp,temperature,humidity,pressure
2024-01-15T10:00:00,25.0,50.0,1013.0
"""
    rows = read_csv(celsius_csv)
    transformed = transform_rows(rows)
    temp = transformed[0]["temperature"]
    hi = transformed[0]["heat_index"]

    # For Celsius data, heat_index formula gets 25.0 as input (treated as F)
    # After the fix, it should be in Celsius
    # The point is: if temp is 25C, heat_index should not be -4 (which is what
    # you get when plugging 25 into the F formula)
    if temp > 20:
        assert hi > 0, f"Heat index {hi} seems wrong for temperature {temp}C"


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
            print(f"  PASS: {test.__name__}")
        except Exception as e:
            failed += 1
            print(f"  FAIL: {test.__name__}: {e}")
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed > 0 else 0)
