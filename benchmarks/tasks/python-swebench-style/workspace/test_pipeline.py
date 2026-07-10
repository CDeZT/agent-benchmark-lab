"""Public tests for the data pipeline.

These tests verify basic pipeline functionality.
The pipeline should process sensor CSV data correctly.
"""

import sys
import os

# Ensure workspace modules are importable
sys.path.insert(0, os.path.dirname(__file__))

from pipeline.reader import read_csv
from pipeline.transformer import transform_rows, _calculate_heat_index
from pipeline.validator import validate_rows
from pipeline.writer import write_csv, write_json, write_summary
from run_pipeline import run_pipeline


# --- Test Data ---

BASIC_CSV = """timestamp,temperature,humidity,pressure
2024-01-15T10:00:00,22.5,45.0,1013.2
2024-01-15T11:00:00,23.0,46.5,1013.0
2024-01-15T12:00:00,24.2,48.0,1012.8
"""

CELSIUS_DATA_CSV = """timestamp,temperature,humidity,pressure
2024-01-15T10:00:00,22.5,45.0,1013.2
2024-01-15T11:00:00,18.0,55.0,1015.0
"""

FAHRENHEIT_DATA_CSV = """timestamp,temperature,humidity,pressure
2024-01-15T10:00:00,72.0,45.0,1013.2
2024-01-15T11:00:00,75.0,55.0,1015.0
"""


# --- Reader Tests ---

def test_read_csv_basic():
    rows = read_csv(BASIC_CSV)
    assert len(rows) == 3
    assert "temperature" in rows[0]
    assert rows[0]["temperature"] == 22.5


def test_read_csv_numeric_parsing():
    rows = read_csv(BASIC_CSV)
    assert isinstance(rows[0]["temperature"], (int, float))
    assert isinstance(rows[0]["humidity"], (int, float))


def test_read_csv_timestamp_parsing():
    from datetime import datetime
    rows = read_csv(BASIC_CSV)
    assert isinstance(rows[0]["timestamp"], datetime)


# --- Transformer Tests ---

def test_transform_preserves_celsius():
    rows = read_csv(CELSIUS_DATA_CSV)
    transformed = transform_rows(rows)
    # 22.5 C should stay ~22.5 (not be converted)
    assert abs(transformed[0]["temperature"] - 22.5) < 0.1


def test_transform_converts_fahrenheit():
    rows = read_csv(FAHRENHEIT_DATA_CSV)
    transformed = transform_rows(rows)
    # 72F should become ~22.22C
    assert transformed[0]["temperature"] < 25
    assert transformed[0]["temperature"] > 20


def test_transform_adds_heat_index():
    rows = read_csv(BASIC_CSV)
    transformed = transform_rows(rows)
    assert "heat_index" in transformed[0]
    assert isinstance(transformed[0]["heat_index"], float)


def test_transform_formats_date():
    rows = read_csv(BASIC_CSV)
    transformed = transform_rows(rows)
    assert "date" in transformed[0]
    assert transformed[0]["date"] == "2024-01-15"


# --- Validator Tests ---

def test_validate_accepts_valid_data():
    rows = read_csv(CELSIUS_DATA_CSV)
    transformed = transform_rows(rows)
    valid, invalid = validate_rows(transformed)
    # All rows should be valid
    assert len(invalid) == 0
    assert len(valid) == len(transformed)


def test_validate_rejects_out_of_range():
    bad_row = {"temperature": 999.0, "humidity": 50.0, "pressure": 1013.0, "heat_index": 20.0}
    valid, invalid = validate_rows([bad_row])
    assert len(invalid) == 1


# --- Writer Tests ---

def test_write_csv_format():
    rows = [{"temperature": 22.5, "humidity": 45.0}]
    output = write_csv(rows)
    assert "temperature" in output
    assert "22.5" in output


def test_write_json_format():
    rows = [{"temperature": 22.5, "humidity": 45.0}]
    output = write_json(rows)
    import json
    parsed = json.loads(output)
    assert parsed[0]["temperature"] == 22.5


def test_write_summary_counts():
    summary = write_summary(10, 8, 2, [{"errors": ["Temperature out of range"]}, {"errors": ["Humidity out of range"]}])
    assert summary["total_rows"] == 10
    assert summary["valid_rows"] == 8
    assert summary["success_rate"] == 80.0


# --- Full Pipeline Test ---

def test_full_pipeline_celsius():
    result = run_pipeline(CELSIUS_DATA_CSV)
    assert result["error"] is None
    assert result["output"] is not None
    assert result["summary"]["invalid_rows"] == 0


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
