"""Module for reading and parsing CSV sensor data files."""

import csv
import io
from datetime import datetime
from typing import List, Dict, Any, Optional

from pipeline.config import DEFAULT_DELIMITER, DEFAULT_ENCODING


def read_csv(source: str, delimiter: str = DEFAULT_DELIMITER) -> List[Dict[str, Any]]:
    """Read CSV data from a file path or string content.

    Args:
        source: File path or CSV string content.
        delimiter: Column delimiter character.

    Returns:
        List of row dictionaries with parsed values.

    Raises:
        FileNotFoundError: If source is a path and doesn't exist.
        ValueError: If CSV has no data rows.
    """
    if "\n" in source or "," in source[:100]:
        content = source
    else:
        with open(source, "r", encoding=DEFAULT_ENCODING) as f:
            content = f.read()

    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    rows = []

    for raw_row in reader:
        parsed = _parse_row(raw_row)
        if parsed is not None:
            rows.append(parsed)

    if not rows:
        raise ValueError("No valid data rows found in input")

    return rows


def _parse_row(raw: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Parse a raw CSV row into typed values."""
    parsed = {}

    for key, value in raw.items():
        if key is None:
            continue
        key = key.strip().lower()
        value = value.strip() if value else ""

        if value == "" or value.lower() in ("null", "none", "na", "n/a"):
            parsed[key] = None
            continue

        if key in ("timestamp", "date", "time", "datetime"):
            parsed[key] = _parse_timestamp(value)
            continue

        try:
            parsed[key] = float(value)
            if parsed[key] == int(parsed[key]):
                parsed[key] = int(parsed[key])
            continue
        except (ValueError, TypeError):
            pass

        parsed[key] = value

    return parsed


def _parse_timestamp(value: str) -> Optional[datetime]:
    """Try multiple timestamp formats."""
    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None
