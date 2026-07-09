from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any


DEFAULT_STATUS_PATH = Path("status/implementation_status.json")


def load_status(path: Path = DEFAULT_STATUS_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def format_status(status: dict[str, Any]) -> str:
    items = status.get("items", [])
    counts = Counter(item.get("status", "unknown") for item in items)
    lines = [
        f"Current phase: {status.get('summary', {}).get('current_phase', 'unknown')}",
        "",
        str(status.get("summary", {}).get("plain_language", "")),
        "",
        "Counts:",
        f"- implemented: {counts.get('implemented', 0)}",
        f"- partial: {counts.get('partial', 0)}",
        f"- planned: {counts.get('planned', 0)}",
        "",
        "Implemented:",
    ]
    lines.extend(_items_for_status(items, "implemented"))
    lines.append("")
    lines.append("Partial:")
    lines.extend(_items_for_status(items, "partial"))
    lines.append("")
    lines.append("Planned:")
    lines.extend(_items_for_status(items, "planned"))
    return "\n".join(lines)


def _items_for_status(items: list[dict[str, Any]], status: str) -> list[str]:
    matching = [item for item in items if item.get("status") == status]
    if not matching:
        return ["- none"]
    return [f"- {item['id']}: {item['title']}" for item in matching]
