from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any
import uuid

from agent_benchmark.runner import ExperimentConfig, run_task
from agent_benchmark.task_schema import load_suite, load_task, validate_all


@dataclass
class AuditCheck:
    name: str
    passed: bool
    duration_seconds: float
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditOptions:
    project_root: Path
    tasks_dir: Path
    suites_dir: Path
    runs_dir: Path
    suite: str = "foundation"
    include_unit_tests: bool = True
    include_compile: bool = True
    include_smoke: bool = True


def run_audit(options: AuditOptions) -> dict[str, Any]:
    audit_id = f"audit-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    audit_dir = options.runs_dir / audit_id
    audit_dir.mkdir(parents=True, exist_ok=True)

    checks: list[AuditCheck] = []
    checks.append(_check_validate(options))
    if options.include_unit_tests:
        checks.append(_check_command("unit_tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests"], options))
    if options.include_compile:
        checks.append(_check_command("compileall", [sys.executable, "-m", "compileall", "-q", "src", "tests"], options))
    if options.include_smoke:
        checks.append(_check_smoke_suite(options, audit_dir))

    summary = {
        "audit_id": audit_id,
        "audit_dir": str(audit_dir),
        "passed": all(check.passed for check in checks),
        "checks": [asdict(check) for check in checks],
    }
    (audit_dir / "audit_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown(audit_dir / "audit_report.md", summary)
    return summary


def format_audit(summary: dict[str, Any]) -> str:
    lines = [
        f"Audit: {summary['audit_id']}",
        f"Passed: {summary['passed']}",
        f"Report: {summary['audit_dir']}",
        "",
        "| Check | Passed | Seconds |",
        "| --- | --- | ---: |",
    ]
    for check in summary["checks"]:
        lines.append(f"| {check['name']} | {check['passed']} | {check['duration_seconds']} |")
    return "\n".join(lines)


def _check_validate(options: AuditOptions) -> AuditCheck:
    start = time.monotonic()
    result = validate_all(options.tasks_dir, options.suites_dir)
    return AuditCheck(
        name="validate",
        passed=result.ok,
        duration_seconds=round(time.monotonic() - start, 4),
        details={"errors": result.errors, "warnings": result.warnings},
    )


def _check_command(name: str, command: list[str], options: AuditOptions) -> AuditCheck:
    start = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=options.project_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return AuditCheck(
        name=name,
        passed=completed.returncode == 0,
        duration_seconds=round(time.monotonic() - start, 4),
        details={
            "command": command,
            "exit_code": completed.returncode,
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
        },
    )


def _check_smoke_suite(options: AuditOptions, audit_dir: Path) -> AuditCheck:
    start = time.monotonic()
    try:
        suite = load_suite(_resolve_suite(options.suite, options.suites_dir))
        smoke_runs_dir = audit_dir / "smoke_runs"
        task_summaries = []
        for task_id in suite.tasks:
            task = load_task(options.tasks_dir / task_id)
            task_summaries.append(
                run_task(
                    task,
                    ExperimentConfig(
                        adapter="dummy",
                        model="audit-smoke",
                        budget_profile="audit",
                        repetitions=1,
                        runs_dir=smoke_runs_dir,
                    ),
                )
            )
        failed_tasks = [
            summary["task_id"]
            for summary in task_summaries
            if not all(run.get("public_test_passed") and run.get("hidden_test_passed") for run in summary["runs"])
        ]
        return AuditCheck(
            name="smoke_suite",
            passed=not failed_tasks,
            duration_seconds=round(time.monotonic() - start, 4),
            details={
                "suite": suite.suite_id,
                "task_count": len(task_summaries),
                "failed_tasks": failed_tasks,
                "mean_score": round(sum(summary["mean_score"] for summary in task_summaries) / len(task_summaries), 2)
                if task_summaries
                else 0.0,
                "smoke_runs_dir": str(smoke_runs_dir),
            },
        )
    except Exception as exc:  # noqa: BLE001 - audit should report failures as data.
        return AuditCheck(
            name="smoke_suite",
            passed=False,
            duration_seconds=round(time.monotonic() - start, 4),
            details={"error": str(exc)},
        )


def _resolve_suite(suite: str, suites_dir: Path) -> Path:
    direct = Path(suite)
    if direct.exists():
        return direct
    candidate = suites_dir / suite
    if candidate.exists():
        return candidate
    candidate_json = suites_dir / f"{suite}.json"
    if candidate_json.exists():
        return candidate_json
    raise FileNotFoundError(f"Could not find suite '{suite}' in {suites_dir}")


def _write_markdown(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        f"# Audit Report: {summary['audit_id']}",
        "",
        f"- Passed: {summary['passed']}",
        "",
        "| Check | Passed | Seconds |",
        "| --- | --- | ---: |",
    ]
    for check in summary["checks"]:
        lines.append(f"| `{check['name']}` | {check['passed']} | {check['duration_seconds']} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
