"""Module for transforming and normalizing sensor data.

FIX: Heat index calculation now correctly converts Celsius back to Fahrenheit
before applying the Rothfusz formula, then converts the result back to Celsius.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional

from pipeline.config import (
    TEMPERATURE_PRECISION,
    HUMIDITY_PRECISION,
    PRESSURE_PRECISION,
    OUTPUT_DATE_FORMAT,
    OUTPUT_TIMESTAMP_FORMAT,
)


def transform_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Apply transformations to a list of parsed data rows."""
    transformed = []
    for row in rows:
        t = _transform_single(row)
        if t is not None:
            transformed.append(t)
    return transformed


def _transform_single(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Transform a single data row."""
    result = {}

    for key, value in row.items():
        result[key] = value

    was_fahrenheit = False

    # Convert temperature if it looks like Fahrenheit
    if "temperature" in result and result["temperature"] is not None:
        temp = result["temperature"]
        if _is_fahrenheit(temp):
            was_fahrenheit = True
            temp = (temp - 32) * 5 / 9
        result["temperature"] = round(temp, TEMPERATURE_PRECISION)

    # Normalize humidity
    if "humidity" in result and result["humidity"] is not None:
        result["humidity"] = round(result["humidity"], HUMIDITY_PRECISION)

    # Normalize pressure
    if "pressure" in result and result["pressure"] is not None:
        result["pressure"] = round(result["pressure"], PRESSURE_PRECISION)

    # Format timestamp
    if "timestamp" in result and isinstance(result["timestamp"], datetime):
        result["date"] = result["timestamp"].strftime(OUTPUT_DATE_FORMAT)
        result["timestamp"] = result["timestamp"].strftime(OUTPUT_TIMESTAMP_FORMAT)

    # FIX: Convert temperature back to Fahrenheit for heat index calculation,
    # then convert the result to Celsius.
    if "temperature" in result and "humidity" in result:
        temp_c = result["temperature"]
        # Convert to Fahrenheit for the Rothfusz formula
        temp_f = temp_c * 9 / 5 + 32
        hi_f = _calculate_heat_index(temp_f, result["humidity"])
        # Convert result back to Celsius
        hi_c = (hi_f - 32) * 5 / 9
        result["heat_index"] = round(hi_c, TEMPERATURE_PRECISION)

    return result


def _is_fahrenheit(temp: float) -> bool:
    """Heuristic: if temperature is above 50, assume Fahrenheit."""
    return temp > 50


def _calculate_heat_index(temperature: float, humidity: float) -> float:
    """Calculate heat index using the Rothfusz regression equation.

    This formula expects temperature in Fahrenheit and humidity as percentage.
    Returns heat index in Fahrenheit.
    """
    if temperature is None or humidity is None:
        return 0.0

    T = temperature
    R = humidity

    hi = (
        -42.379
        + 2.04901523 * T
        + 10.14333127 * R
        - 0.22475541 * T * R
        - 0.00683783 * T * T
        - 0.05481717 * R * R
        + 0.00122874 * T * T * R
        + 0.00085282 * T * R * R
        - 0.00000199 * T * T * R * R
    )

    return round(hi, 2)
