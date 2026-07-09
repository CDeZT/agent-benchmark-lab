"""Module for validating transformed sensor data against expected ranges.

FIX: Heat index validation now uses the same Celsius range as temperature,
since the transformer now correctly outputs heat_index in Celsius.
"""

from typing import Dict, Any, List, Tuple

from pipeline.config import (
    TEMPERATURE_MIN,
    TEMPERATURE_MAX,
    HUMIDITY_MIN,
    HUMIDITY_MAX,
    PRESSURE_MIN,
    PRESSURE_MAX,
    STRICT_MODE,
    SKIP_INVALID_ROWS,
)


def validate_rows(
    rows: List[Dict[str, Any]], strict: bool = STRICT_MODE
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Validate rows and separate into valid and invalid lists."""
    valid = []
    invalid = []

    for i, row in enumerate(rows):
        errors = _validate_single(row, strict)
        if errors:
            invalid.append({"row_index": i, "data": row, "errors": errors})
        else:
            valid.append(row)

    return valid, invalid


def _validate_single(row: Dict[str, Any], strict: bool) -> List[str]:
    """Validate a single row. Returns list of error messages."""
    errors = []

    required = ["temperature", "humidity", "pressure"]
    for field in required:
        if field not in row or row[field] is None:
            if strict:
                errors.append(f"Missing required field: {field}")
            continue

    if "temperature" in row and row["temperature"] is not None:
        temp = row["temperature"]
        if not isinstance(temp, (int, float)):
            errors.append(f"Temperature must be numeric, got {type(temp).__name__}")
        elif temp < TEMPERATURE_MIN or temp > TEMPERATURE_MAX:
            errors.append(
                f"Temperature {temp} out of range [{TEMPERATURE_MIN}, {TEMPERATURE_MAX}]"
            )

    if "humidity" in row and row["humidity"] is not None:
        hum = row["humidity"]
        if not isinstance(hum, (int, float)):
            errors.append(f"Humidity must be numeric, got {type(hum).__name__}")
        elif hum < HUMIDITY_MIN or hum > HUMIDITY_MAX:
            errors.append(
                f"Humidity {hum} out of range [{HUMIDITY_MIN}, {HUMIDITY_MAX}]"
            )

    if "pressure" in row and row["pressure"] is not None:
        pres = row["pressure"]
        if not isinstance(pres, (int, float)):
            errors.append(f"Pressure must be numeric, got {type(pres).__name__}")
        elif pres < PRESSURE_MIN or pres > PRESSURE_MAX:
            errors.append(
                f"Pressure {pres} out of range [{PRESSURE_MIN}, {PRESSURE_MAX}]"
            )

    # FIX: Heat index is now in Celsius, so validate against the same range
    if "heat_index" in row and row["heat_index"] is not None:
        hi = row["heat_index"]
        if not isinstance(hi, (int, float)):
            errors.append(f"Heat index must be numeric, got {type(hi).__name__}")
        elif hi < TEMPERATURE_MIN or hi > TEMPERATURE_MAX:
            errors.append(
                f"Heat index {hi} out of range [{TEMPERATURE_MIN}, {TEMPERATURE_MAX}]"
            )

    return errors
