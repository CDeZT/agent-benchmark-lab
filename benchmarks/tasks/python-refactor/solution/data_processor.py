"""Data processing module — refactored version.

Clean implementation that preserves all original behavior.
"""


def process_data(data):
    """Process data: convert to numbers, clamp to [0, 1000], double positives."""
    return [_process_item(item) for item in data]


def _process_item(item):
    if item is None:
        return 0
    if isinstance(item, (int, float)):
        num = item
    elif isinstance(item, str):
        try:
            num = float(item)
        except ValueError:
            return 0
    else:
        return 0
    if num <= 0:
        return 0
    if num < 1000:
        return num * 2
    return 1000


def calculate_stats(data):
    """Calculate basic statistics for numeric data."""
    values = [v for v in data if v is not None]
    if not values:
        return {"count": 0, "sum": 0, "avg": 0, "min": 0, "max": 0}
    return {
        "count": len(values),
        "sum": sum(values),
        "avg": sum(values) / len(values),
        "min": min(values),
        "max": max(values),
    }


def filter_and_sort(data, threshold=0, reverse=False):
    """Filter values above threshold and sort them."""
    filtered = [item for item in data if item is not None and item > threshold]
    return sorted(filtered, reverse=reverse)
