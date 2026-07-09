"""Main pipeline runner - orchestrates the ETL process."""

import sys
from typing import Optional

from pipeline.reader import read_csv
from pipeline.transformer import transform_rows
from pipeline.validator import validate_rows
from pipeline.writer import write_csv, write_json, write_summary
from pipeline.config import MAX_ERRORS_BEFORE_ABORT


def run_pipeline(
    source: str,
    output_format: str = "csv",
    strict: bool = False,
) -> dict:
    """Execute the full ETL pipeline.

    Args:
        source: CSV file path or inline CSV content.
        output_format: 'csv' or 'json'.
        strict: Enable strict validation mode.

    Returns:
        Dictionary with output data, summary, and any errors.
    """
    # Step 1: Read
    try:
        raw_rows = read_csv(source)
    except Exception as e:
        return {"error": f"Read failed: {e}", "output": None, "summary": None}

    # Step 2: Transform
    transformed = transform_rows(raw_rows)

    # Step 3: Validate
    valid_rows, invalid_rows = validate_rows(transformed, strict=strict)

    # Check error threshold
    if len(invalid_rows) >= MAX_ERRORS_BEFORE_ABORT:
        return {
            "error": f"Too many errors ({len(invalid_rows)}), aborting pipeline",
            "output": None,
            "summary": write_summary(
                len(raw_rows), len(valid_rows), len(invalid_rows), invalid_rows
            ),
        }

    # Step 4: Write output
    if output_format == "json":
        output = write_json(valid_rows)
    else:
        output = write_csv(valid_rows)

    summary = write_summary(
        len(raw_rows), len(valid_rows), len(invalid_rows), invalid_rows
    )

    return {"error": None, "output": output, "summary": summary}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_pipeline.py <csv_file> [--json] [--strict]")
        sys.exit(1)

    source = sys.argv[1]
    fmt = "json" if "--json" in sys.argv else "csv"
    strict = "--strict" in sys.argv

    result = run_pipeline(source, output_format=fmt, strict=strict)

    if result["error"]:
        print(f"ERROR: {result['error']}", file=sys.stderr)
        sys.exit(1)

    print(result["output"])
    print("\n--- Summary ---", file=sys.stderr)
    import json
    print(json.dumps(result["summary"], indent=2, default=str), file=sys.stderr)
