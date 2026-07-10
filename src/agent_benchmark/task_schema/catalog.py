from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from agent_benchmark.task_schema.manifest import TaskSpec, load_task
from agent_benchmark.task_schema.validate import DIFFICULTY_LEVELS


def build_catalog(tasks_dir: Path) -> dict[str, Any]:
    """Return a stable, machine-readable view of the benchmark corpus."""
    tasks = [load_task(path) for path in sorted(tasks_dir.iterdir()) if path.is_dir()]
    return {
        "task_count": len(tasks),
        "difficulty_distribution": _ordered_counts(task.difficulty for task in tasks),
        "provenance_distribution": dict(sorted(Counter(_provenance_type(task) for task in tasks).items())),
        "tasks": [_task_record(task) for task in tasks],
    }


def _ordered_counts(values: Any) -> dict[str, int]:
    counts = Counter(values)
    return {level: counts.get(level, 0) for level in DIFFICULTY_LEVELS}


def _task_record(task: TaskSpec) -> dict[str, Any]:
    return {
        "id": task.task_id,
        "title": task.title,
        "difficulty": task.difficulty,
        "difficulty_rationale": task.difficulty_rationale,
        "provenance_type": _provenance_type(task),
        "source_benchmark": task.provenance.get("source_benchmark"),
        "capabilities": task.capabilities,
        "domains": task.domains,
        "has_public_tests": bool(task.test_command),
        "has_hidden_tests": bool(task.hidden_test_command),
        "environment": task.metadata.get("environment", "local"),
    }


def _provenance_type(task: TaskSpec) -> str:
    return str(task.provenance.get("type", "unspecified"))
