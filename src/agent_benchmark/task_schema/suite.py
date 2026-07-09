from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path


@dataclass(frozen=True)
class SuiteSpec:
    suite_id: str
    title: str
    description: str
    tasks: list[str]
    capability_focus: list[str] = field(default_factory=list)
    root: Path = Path(".")


def load_suite(path: Path) -> SuiteSpec:
    data = json.loads(path.read_text(encoding="utf-8"))
    return SuiteSpec(
        suite_id=data["id"],
        title=data["title"],
        description=data.get("description", ""),
        tasks=list(data.get("tasks", [])),
        capability_focus=list(data.get("capability_focus", [])),
        root=path.parent,
    )
