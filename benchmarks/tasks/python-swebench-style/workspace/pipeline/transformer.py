"""Module for transforming and normalizing sensor data."""

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
    """Apply transformations to a list of parsed data rows.

    Transformations:
    1. Normalize column names (lowercase, strip whitespace)
    2. Convert temperature from Fahrenheit to Celsius if needed
    3. Format timestamps to standard format
    4. Round numeric values to configured precision
    5. Add derived fields (e.g., heat_index)
    """
    transformed = []
    for row in rows:
        t = _transform_single(row)
        if t is not None:
            transformed.append(t)
    return transformed


def _transform_single(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Transform a single data row."""
    result = {}

    # Copy and normalize keys
    for key, value in row.items():
        result[key] = value

    # Convert temperature if it looks like Fahrenheit
    if "temperature" in result and result["temperature"] is not None:
        temp = result["temperature"]
        if _is_fahrenheit(temp):
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

    # BUG: The heat_index calculation passes temperature as-is without checking
    # if it was converted from Fahrenheit. After conversion above, temperature is
    # in Celsius, but heat_index_formula expects Fahrenheit input.
    # This means the heat index will be wildly wrong for data that was converted.
    if "temperature" in result and "humidity" in result:
        result["heat_index"] = _calculate_heat_index(
            result["temperature"], result["humidity"]
        )

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

    T = temperature  # BUG: should convert back to F before calling this
    R = humidity

    # Rothfusz regression (simplified)
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
