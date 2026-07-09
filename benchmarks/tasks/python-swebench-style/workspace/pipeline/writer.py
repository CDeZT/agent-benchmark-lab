"""Module for writing validated pipeline output."""

import csv
import io
import json
from typing import Dict, Any, List, Optional


def write_csv(rows: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None) -> str:
    """Write rows to a CSV string.

    Args:
        rows: List of data dictionaries.
        fieldnames: Ordered list of column names. If None, inferred from first row.

    Returns:
        CSV content as string.
    """
    if not rows:
        return ""

    if fieldnames is None:
        fieldnames = list(rows[0].keys())

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)

    return output.getvalue()


def write_json(rows: List[Dict[str, Any]], indent: int = 2) -> str:
    """Write rows to a JSON string.

    Args:
        rows: List of data dictionaries.
        indent: JSON indentation level.

    Returns:
        JSON content as string.
    """
    return json.dumps(rows, indent=indent, default=str)


def write_summary(
    total: int,
    valid: int,
    invalid: int,
    errors: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Generate a pipeline run summary.

    Returns:
        Summary dictionary with counts and error details.
    """
    error_types = {}
    for err in errors:
        for msg in err.get("errors", []):
            # Extract error category from message
            category = msg.split(":")[0].strip() if ":" in msg else msg
            error_types[category] = error_types.get(category, 0) + 1

    return {
        "total_rows": total,
        "valid_rows": valid,
        "invalid_rows": invalid,
        "success_rate": round(valid / total * 100, 1) if total > 0 else 0.0,
        "error_breakdown": error_types,
        "sample_errors": errors[:5],
    }
