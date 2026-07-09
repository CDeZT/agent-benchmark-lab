from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProcessScoreResult:
    dimensions: dict[str, float] = field(default_factory=dict)
    checks: list[dict[str, Any]] = field(default_factory=list)


SUPPORTED_DIMENSIONS = {"planning", "self_repair", "tool_use", "intent_understanding", "test_discipline"}


def score_process_checks(workspace: Path, checks: list[dict[str, Any]]) -> ProcessScoreResult:
    if not checks:
        return ProcessScoreResult()

    check_results = [_run_check(workspace, check) for check in checks]
    dimensions: dict[str, float] = {}
    for dimension in sorted({str(check.get("dimension", "")) for check in check_results}):
        if dimension not in SUPPORTED_DIMENSIONS:
            continue
        matching = [check for check in check_results if check.get("dimension") == dimension]
        if matching:
            dimensions[dimension] = round(100.0 * sum(1 for check in matching if check["passed"]) / len(matching), 2)
    return ProcessScoreResult(dimensions=dimensions, checks=check_results)


def _run_check(workspace: Path, check: dict[str, Any]) -> dict[str, Any]:
    kind = check.get("type", "")
    dimension = str(check.get("dimension", ""))
    if dimension not in SUPPORTED_DIMENSIONS:
        return {"type": kind, "dimension": dimension, "passed": False, "error": "Unsupported process dimension."}
    if kind == "file_exists":
        return _file_exists(workspace, check)
    if kind == "file_contains":
        return _file_contains(workspace, check)
    return {"type": kind, "dimension": dimension, "passed": False, "error": f"Unknown process check type: {kind}"}


def _file_exists(workspace: Path, check: dict[str, Any]) -> dict[str, Any]:
    relative = str(check.get("path", ""))
    path = workspace / relative
    return {
        "type": "file_exists",
        "dimension": check.get("dimension"),
        "path": relative,
        "passed": path.is_file(),
    }


def _file_contains(workspace: Path, check: dict[str, Any]) -> dict[str, Any]:
    relative = str(check.get("path", ""))
    expected = str(check.get("text", ""))
    path = workspace / relative
    if not path.is_file():
        return {
            "type": "file_contains",
            "dimension": check.get("dimension"),
            "path": relative,
            "text": expected,
            "passed": False,
            "error": "File not found.",
        }
    content = path.read_text(encoding="utf-8")
    return {
        "type": "file_contains",
        "dimension": check.get("dimension"),
        "path": relative,
        "text": expected,
        "passed": expected in content,
    }
