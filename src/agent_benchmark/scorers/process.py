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
    if kind == "instruction_match":
        return _instruction_match(workspace, check, baseline)
    if kind == "code_quality":
        return _code_quality(workspace, check)
    if kind == "performance_check":
        return _performance_check(workspace, check)
    if kind == "documentation_check":
        return _documentation_check(workspace, check)
    return {"type": kind, "dimension": dimension, "passed": False, "error": f"Unknown process check type: {kind}"}


def _file_exists(workspace: Path, check: dict[str, Any]) -> dict[str, Any]:
    relative = str(check.get("path", ""))
    path = workspace / relative
    min_bytes = int(check.get("min_bytes", 0) or 0)
    exists = path.is_file()
    size = path.stat().st_size if exists else 0
    passed = exists and size >= min_bytes
    result = {
        "type": "file_exists",
        "dimension": check.get("dimension"),
        "path": relative,
        "passed": passed,
        "size_bytes": size,
    }
    if min_bytes:
        result["min_bytes"] = min_bytes
    if exists and not passed:
        result["error"] = f"File exists but is smaller than {min_bytes} bytes."
    elif not exists:
        result["error"] = "File not found."
    return result


def _file_contains(workspace: Path, check: dict[str, Any]) -> dict[str, Any]:
    relative = str(check.get("path", ""))
    expected = str(check.get("text", ""))
    case_sensitive = bool(check.get("case_sensitive", True))
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
    passed = expected in content if case_sensitive else expected.casefold() in content.casefold()
    return {
        "type": "file_contains",
        "dimension": check.get("dimension"),
        "path": relative,
        "text": expected,
        "case_sensitive": case_sensitive,
        "passed": passed,
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

    # Count assertions: plain assert and self.assert* methods.
    # Using two non-overlapping patterns to avoid double-counting.
    assertion_patterns = [
        r"\bassert\b",
        r"\.assert\w+\(",
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


def _instruction_match(workspace: Path, check: dict[str, Any], baseline: Path | None) -> dict[str, Any]:
    """Check that the agent modified files relevant to the task instruction.

    Verifies intent_understanding by confirming the agent changed at least one
    of the expected files (SHA-256 diff from baseline). A file that exists in
    the workspace but not in the baseline counts as changed (created).

    Expected check fields:
        expected_changed_files: list of relative paths that should have been modified
    """
    import hashlib

    expected_files = check.get("expected_changed_files", [])
    result: dict[str, Any] = {
        "type": "instruction_match",
        "dimension": check.get("dimension"),
        "expected_changed_files": expected_files,
    }

    if baseline is None:
        result["passed"] = False
        result["error"] = "No baseline provided for comparison."
        return result

    file_details: list[dict[str, Any]] = []
    any_changed = False

    for relative in expected_files:
        workspace_file = workspace / relative
        baseline_file = baseline / relative
        detail: dict[str, Any] = {"path": relative}

        if not workspace_file.is_file():
            detail["status"] = "missing"
            file_details.append(detail)
            continue

        if not baseline_file.is_file():
            # File exists in workspace but not baseline — created by agent
            detail["status"] = "created"
            any_changed = True
            file_details.append(detail)
            continue

        try:
            workspace_hash = hashlib.sha256(workspace_file.read_bytes()).hexdigest()
            baseline_hash = hashlib.sha256(baseline_file.read_bytes()).hexdigest()
            changed = workspace_hash != baseline_hash
            detail["status"] = "modified" if changed else "unchanged"
            detail["workspace_hash"] = workspace_hash[:16]
            detail["baseline_hash"] = baseline_hash[:16]
            if changed:
                any_changed = True
        except Exception as exc:
            detail["status"] = "error"
            detail["error"] = str(exc)

        file_details.append(detail)

    result["passed"] = any_changed
    result["files"] = file_details
    return result


def _code_quality(workspace: Path, check: dict[str, Any]) -> dict[str, Any]:
    """Check code quality metrics for a file.

    Analyzes:
    - Function length (max_function_lines)
    - Nesting depth (max_nesting_depth)
    - Has docstrings (require_docstrings)
    - Has comments (require_comments)

    Expected check fields:
        path: relative path to the file to check
        max_function_lines: maximum allowed lines per function (default 50)
        max_nesting_depth: maximum allowed nesting depth (default 4)
        require_docstrings: whether functions need docstrings (default False)
        require_comments: whether code needs comments (default False)
    """
    import re

    relative = str(check.get("path", ""))
    max_func_lines = int(check.get("max_function_lines", 50))
    max_nesting = int(check.get("max_nesting_depth", 4))
    require_docstrings = check.get("require_docstrings", False)
    require_comments = check.get("require_comments", False)

    path = workspace / relative
    result: dict[str, Any] = {
        "type": "code_quality",
        "dimension": check.get("dimension"),
        "path": relative,
    }

    if not path.is_file():
        result["passed"] = False
        result["error"] = "File not found."
        return result

    try:
        content = path.read_text(encoding="utf-8")
        lines = content.splitlines()
    except Exception as exc:
        result["passed"] = False
        result["error"] = f"Cannot read file: {exc}"
        return result

    issues: list[str] = []
    metrics: dict[str, Any] = {}

    # Check function length
    func_pattern = re.compile(r"^\s*(?:async\s+)?def\s+\w+|^\s*(?:async\s+)?function\s+\w+|^\s*\w+\s*=\s*(?:async\s+)?function")
    func_starts = [i for i, line in enumerate(lines) if func_pattern.match(line)]

    if func_starts:
        func_lengths = []
        for idx, start in enumerate(func_starts):
            end = func_starts[idx + 1] if idx + 1 < len(func_starts) else len(lines)
            # Find actual end of function (next def or end of file)
            for i in range(start + 1, end):
                if lines[i].strip() and not lines[i].startswith(" ") and not lines[i].startswith("\t"):
                    end = i
                    break
            func_lengths.append(end - start)

        max_found = max(func_lengths) if func_lengths else 0
        avg_found = sum(func_lengths) / len(func_lengths) if func_lengths else 0
        metrics["function_count"] = len(func_lengths)
        metrics["max_function_lines"] = max_found
        metrics["avg_function_lines"] = round(avg_found, 1)

        if max_found > max_func_lines:
            issues.append(f"Function too long: {max_found} lines (max {max_func_lines})")

    # Check nesting depth
    max_nesting_found = 0
    for line in lines:
        if not line.strip():
            continue
        # Count leading whitespace (tabs =4 spaces for consistency)
        expanded = line.replace("\t", "    ")
        indent = len(expanded) - len(expanded.lstrip())
        nesting = indent // 4  # Assuming4-space indent
        max_nesting_found = max(max_nesting_found, nesting)

    metrics["max_nesting_depth"] = max_nesting_found
    if max_nesting_found > max_nesting:
        issues.append(f"Nesting too deep: {max_nesting_found} levels (max {max_nesting})")

    # Check for docstrings
    if require_docstrings:
        docstring_count = content.count('"""') + content.count("'''")
        has_docstrings = docstring_count >= 2  # At least one function with docstring
        metrics["has_docstrings"] = has_docstrings
        if not has_docstrings:
            issues.append("No docstrings found")

    # Check for comments
    if require_comments:
        comment_lines = sum(1 for line in lines if line.strip().startswith("#"))
        comment_ratio = comment_lines / len(lines) if lines else 0
        metrics["comment_lines"] = comment_lines
        metrics["comment_ratio"] = round(comment_ratio, 3)
        if comment_ratio < 0.05:  # Less than 5% comments
            issues.append(f"Too few comments: {comment_ratio:.1%}")

    passed = len(issues) == 0
    result["passed"] = passed
    result["metrics"] = metrics
    if issues:
        result["issues"] = issues

    return result


def _performance_check(workspace: Path, check: dict[str, Any]) -> dict[str, Any]:
    """Check if code runs within time/memory limits.

    Runs the test command and checks if it completes within the time limit.
    This is useful for verifying that the agent's solution is not just correct
    but also efficient.

    Expected check fields:
        command: list of command parts to run (e.g., ["python3", "test.py"])
        max_seconds: maximum allowed execution time (default 10.0)
        cwd: working directory relative to workspace (default ".")
    """
    import os
    import subprocess
    import time

    command = check.get("command", [])
    max_seconds = float(check.get("max_seconds", 10.0))
    cwd_rel = str(check.get("cwd", "."))

    result: dict[str, Any] = {
        "type": "performance_check",
        "dimension": check.get("dimension"),
        "command": command,
        "max_seconds": max_seconds,
    }

    if not command:
        result["passed"] = False
        result["error"] = "No command specified."
        return result

    cwd = workspace / cwd_rel
    if not cwd.exists():
        result["passed"] = False
        result["error"] = f"Working directory not found: {cwd_rel}"
        return result

    try:
        start_time = time.monotonic()
        completed = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=max_seconds + 5,  # Add buffer for subprocess overhead
            check=False,
        )
        elapsed = time.monotonic() - start_time

        result["exit_code"] = completed.returncode
        result["elapsed_seconds"] = round(elapsed, 3)
        result["passed"] = elapsed <= max_seconds and completed.returncode == 0
        result["stdout_tail"] = completed.stdout[-500:] if completed.stdout else ""
        result["stderr_tail"] = completed.stderr[-500:] if completed.stderr else ""

        if elapsed > max_seconds:
            result["issues"] = [f"Execution too slow: {elapsed:.2f}s (max {max_seconds}s)"]
        elif completed.returncode != 0:
            result["issues"] = [f"Command failed with exit code {completed.returncode}"]

    except subprocess.TimeoutExpired:
        result["passed"] = False
        result["error"] = f"Command timed out after {max_seconds + 5}s"
    except Exception as exc:
        result["passed"] = False
        result["error"] = f"Cannot run command: {exc}"

    return result


def _documentation_check(workspace: Path, check: dict[str, Any]) -> dict[str, Any]:
    """Check documentation quality for a code file.

    Verifies:
    - File has module docstring
    - Functions have docstrings
    - README exists (if check_readme=True)

    Expected check fields:
        path: relative path to the file to check
        min_docstring_ratio: minimum ratio of functions with docstrings (default 0.5)
        check_readme: whether to check for README.md (default False)
    """
    import re

    relative = str(check.get("path", ""))
    min_docstring_ratio = float(check.get("min_docstring_ratio", 0.5))
    check_readme = check.get("check_readme", False)

    path = workspace / relative
    result: dict[str, Any] = {
        "type": "documentation_check",
        "dimension": check.get("dimension"),
        "path": relative,
    }

    if not path.is_file():
        result["passed"] = False
        result["error"] = "File not found."
        return result

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:
        result["passed"] = False
        result["error"] = f"Cannot read file: {exc}"
        return result

    issues: list[str] = []
    metrics: dict[str, Any] = {}

    # Check for module docstring
    has_module_docstring = content.strip().startswith('"""') or content.strip().startswith("'''")
    metrics["has_module_docstring"] = has_module_docstring
    if not has_module_docstring:
        issues.append("No module docstring")

    # Check function docstrings
    func_pattern = re.compile(r"^\s*(?:async\s+)?def\s+(\w+)\s*\(", re.MULTILINE)
    functions = func_pattern.findall(content)

    if functions:
        # Count functions with docstrings
        func_with_docstring = 0
        for func_name in functions:
            # Look for docstring after function definition
            pattern = rf"def\s+{func_name}\s*\([^)]*\)\s*(?:->[^:]*)?:\s*\n\s*(?:\"\"\"|\'\'\')"
            if re.search(pattern, content):
                func_with_docstring += 1

        docstring_ratio = func_with_docstring / len(functions) if functions else 0
        metrics["function_count"] = len(functions)
        metrics["functions_with_docstring"] = func_with_docstring
        metrics["docstring_ratio"] = round(docstring_ratio, 3)

        if docstring_ratio < min_docstring_ratio:
            issues.append(f"Too few function docstrings: {docstring_ratio:.1%} (min {min_docstring_ratio:.1%})")

    # Check for README
    if check_readme:
        readme_path = workspace / "README.md"
        has_readme = readme_path.is_file()
        metrics["has_readme"] = has_readme
        if not has_readme:
            issues.append("No README.md found")

    passed = len(issues) == 0
    result["passed"] = passed
    result["metrics"] = metrics
    if issues:
        result["issues"] = issues

    return result
