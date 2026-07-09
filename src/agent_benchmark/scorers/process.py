from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProcessScoreResult:
    dimensions: dict[str, float] = field(default_factory=dict)
    checks: list[dict[str, Any]] = field(default_factory=list)


SUPPORTED_DIMENSIONS = {"planning", "self_repair", "tool_use", "intent_understanding", "test_discipline", "execution_quality", "cost_efficiency"}


def score_process_checks(workspace: Path, checks: list[dict[str, Any]], baseline: Path | None = None) -> ProcessScoreResult:
    if not checks:
        return ProcessScoreResult()

    check_results = [_run_check(workspace, check, baseline) for check in checks]
    dimensions: dict[str, float] = {}
    for dimension in sorted({str(check.get("dimension", "")) for check in check_results}):
        if dimension not in SUPPORTED_DIMENSIONS:
            continue
        matching = [check for check in check_results if check.get("dimension") == dimension]
        if matching:
            dimensions[dimension] = round(100.0 * sum(1 for check in matching if check["passed"]) / len(matching), 2)
    return ProcessScoreResult(dimensions=dimensions, checks=check_results)


def _run_check(workspace: Path, check: dict[str, Any], baseline: Path | None = None) -> dict[str, Any]:
    kind = check.get("type", "")
    dimension = str(check.get("dimension", ""))
    if dimension not in SUPPORTED_DIMENSIONS:
        return {"type": kind, "dimension": dimension, "passed": False, "error": "Unsupported process dimension."}
    if kind == "file_exists":
        return _file_exists(workspace, check)
    if kind == "file_contains":
        return _file_contains(workspace, check)
    if kind == "test_file_quality":
        return _test_file_quality(workspace, check)
    if kind == "file_changed":
        return _file_changed(workspace, check, baseline)
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


def _test_file_quality(workspace: Path, check: dict[str, Any]) -> dict[str, Any]:
    """Check that a test file exists and has meaningful test content.

    Expected check fields:
        path: relative path to the test file
        min_test_functions: minimum number of test functions required (default 2)
        min_assertions: minimum number of assert/assertTrue/assertFalse calls (default 2)
        must_import: string that must appear in imports (e.g., the module under test)
    """
    import re

    relative = str(check.get("path", ""))
    min_funcs = int(check.get("min_test_functions", 2))
    min_asserts = int(check.get("min_assertions", 2))
    must_import = str(check.get("must_import", ""))
    path = workspace / relative

    if not path.is_file():
        return {
            "type": "test_file_quality",
            "dimension": check.get("dimension"),
            "path": relative,
            "passed": False,
            "error": "Test file not found.",
            "test_function_count": 0,
            "assertion_count": 0,
        }

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:
        return {
            "type": "test_file_quality",
            "dimension": check.get("dimension"),
            "path": relative,
            "passed": False,
            "error": f"Cannot read test file: {exc}",
            "test_function_count": 0,
            "assertion_count": 0,
        }

    # Count test functions: def test_... or async def test_...
    test_funcs = re.findall(r"^\s*(?:async\s+)?def\s+(test_\w+)", content, re.MULTILINE)
    func_count = len(test_funcs)

    # Count assertions: assert ..., self.assert..., assertEqual, assertTrue, etc.
    assertion_patterns = [
        r"\bassert\b",
        r"\.assert\w+\(",
        r"\.assertEqual\(",
        r"\.assertTrue\(",
        r"\.assertFalse\(",
        r"\.assertRaises\(",
        r"\.assertIn\(",
        r"\.assertIs\(",
    ]
    assert_count = 0
    for pattern in assertion_patterns:
        assert_count += len(re.findall(pattern, content))

    # Check must_import
    import_ok = True
    if must_import:
        import_ok = must_import in content

    passed = func_count >= min_funcs and assert_count >= min_asserts and import_ok

    details = []
    if func_count < min_funcs:
        details.append(f"need {min_funcs} test functions, found {func_count}")
    if assert_count < min_asserts:
        details.append(f"need {min_asserts} assertions, found {assert_count}")
    if not import_ok:
        details.append(f"missing import of '{must_import}'")

    result: dict[str, Any] = {
        "type": "test_file_quality",
        "dimension": check.get("dimension"),
        "path": relative,
        "passed": passed,
        "test_function_count": func_count,
        "assertion_count": assert_count,
        "import_ok": import_ok,
        "test_function_names": test_funcs[:10],  # cap for readability
    }
    if details:
        result["details"] = "; ".join(details)
    return result


def _file_changed(workspace: Path, check: dict[str, Any], baseline: Path | None) -> dict[str, Any]:
    """Check that a file in workspace differs from the same file in baseline.

    This verifies the agent actually modified the file rather than leaving it
    untouched. Used for execution_quality scoring.

    Expected check fields:
        path: relative path to the file to check
    """
    import hashlib

    relative = str(check.get("path", ""))
    workspace_file = workspace / relative
    result: dict[str, Any] = {
        "type": "file_changed",
        "dimension": check.get("dimension"),
        "path": relative,
    }

    if not workspace_file.is_file():
        result["passed"] = False
        result["error"] = "File not found in workspace."
        return result

    if baseline is None:
        result["passed"] = False
        result["error"] = "No baseline provided for comparison."
        return result

    baseline_file = baseline / relative
    if not baseline_file.is_file():
        # File exists in workspace but not in baseline — it was created
        result["passed"] = True
        result["status"] = "created"
        return result

    try:
        workspace_hash = hashlib.sha256(workspace_file.read_bytes()).hexdigest()
        baseline_hash = hashlib.sha256(baseline_file.read_bytes()).hexdigest()
        changed = workspace_hash != baseline_hash
        result["passed"] = changed
        result["status"] = "modified" if changed else "unchanged"
        result["workspace_hash"] = workspace_hash[:16]
        result["baseline_hash"] = baseline_hash[:16]
    except Exception as exc:
        result["passed"] = False
        result["error"] = f"Cannot compare files: {exc}"

    return result
