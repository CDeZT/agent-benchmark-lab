from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any

from agent_benchmark.task_schema import load_task


def audit_corpus(tasks_dir: Path) -> dict[str, Any]:
    """Verify that locally runnable tasks distinguish their baseline and solution.

    A task is only a useful deterministic benchmark gate when its reference
    solution passes and its untouched workspace fails at least one configured
    acceptance command. Refactor-like tasks may legitimately need a different
    quality gate; they are reported as weak contrast rather than silently
    accepted.
    """
    tasks = []
    for task_dir in sorted(path for path in tasks_dir.iterdir() if path.is_dir()):
        task = load_task(task_dir)
        tasks.append(_audit_task(task))
    return {
        "task_count": len(tasks),
        "summary": _summary(tasks),
        "tasks": tasks,
    }


def _audit_task(task: Any) -> dict[str, Any]:
    environment = task.metadata.get("environment", "local")
    result: dict[str, Any] = {
        "task_id": task.task_id,
        "environment": environment,
        "benchmark_role": task.metadata.get("benchmark_role", "comparative_candidate"),
    }
    if environment != "local":
        result.update({"classification": "skipped_environment", "reason": "requires non-local environment"})
        return result

    solution_dir = task.root / "solution"
    if not solution_dir.is_dir():
        result.update({"classification": "missing_reference_solution", "reason": "solution/ directory is missing"})
        return result

    with tempfile.TemporaryDirectory(prefix=f"agent-benchmark-{task.task_id}-") as tmp:
        root = Path(tmp)
        baseline = root / "baseline"
        reference = root / "reference"
        shutil.copytree(task.workspace_path, baseline)
        shutil.copytree(task.workspace_path, reference)
        _overlay(solution_dir, reference)
        baseline_checks = _run_checks(task, baseline)
        reference_checks = _run_checks(task, reference)

    baseline_failed = any(check["configured"] and not check["passed"] for check in baseline_checks)
    reference_passed = all(not check["configured"] or check["passed"] for check in reference_checks)
    if not reference_passed:
        classification = "reference_failure"
    elif not baseline_failed:
        classification = "weak_baseline_contrast"
    else:
        classification = "passes"
    result.update(
        {
            "classification": classification,
            "baseline_checks": baseline_checks,
            "reference_checks": reference_checks,
            "baseline_failed": baseline_failed,
            "reference_passed": reference_passed,
        }
    )
    return result


def _overlay(source: Path, destination: Path) -> None:
    for path in source.rglob("*"):
        if path.is_file():
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def _run_checks(task: Any, workspace: Path) -> list[dict[str, Any]]:
    checks = [("public", task.test_command, workspace), ("hidden", task.hidden_test_command, task.root / "hidden")]
    return [_run_command(kind, command, cwd, workspace, task.test_timeout_seconds) for kind, command, cwd in checks]


def _run_command(kind: str, command: list[str], cwd: Path, workspace: Path, timeout: float) -> dict[str, Any]:
    if not command:
        return {"kind": kind, "configured": False, "passed": None}
    environment = os.environ.copy()
    environment["AGENT_BENCH_WORKSPACE"] = str(workspace.resolve())
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        return {"kind": kind, "configured": True, "passed": completed.returncode == 0, "exit_code": completed.returncode, "stdout_tail": completed.stdout[-500:], "stderr_tail": completed.stderr[-500:]}
    except subprocess.TimeoutExpired:
        return {"kind": kind, "configured": True, "passed": False, "exit_code": 124, "timed_out": True}


def _summary(tasks: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for task in tasks:
        key = str(task["classification"])
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))
