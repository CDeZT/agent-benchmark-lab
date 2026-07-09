from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from agent_benchmark.task_schema.manifest import TaskSpec, load_task
from agent_benchmark.task_schema.suite import load_suite


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def extend(self, other: "ValidationResult") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


def validate_all(tasks_dir: Path, suites_dir: Path) -> ValidationResult:
    result = ValidationResult()
    tasks = {}
    for task_dir in sorted(path for path in tasks_dir.iterdir() if path.is_dir()):
        try:
            task = load_task(task_dir)
            tasks[task.task_id] = task
            result.extend(validate_task(task))
        except Exception as exc:  # noqa: BLE001 - validation should collect malformed task errors.
            result.errors.append(f"{task_dir}: {exc}")

    for suite_path in sorted(suites_dir.glob("*.json")):
        try:
            suite = load_suite(suite_path)
            missing = [task_id for task_id in suite.tasks if task_id not in tasks]
            for task_id in missing:
                result.errors.append(f"{suite_path}: references missing task '{task_id}'")
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"{suite_path}: {exc}")

    from agent_benchmark.adapters import available_adapters

    if not available_adapters():
        result.errors.append("No adapters registered.")
    return result


def validate_task(task: TaskSpec) -> ValidationResult:
    result = ValidationResult()
    if not task.workspace_path.exists():
        result.errors.append(f"{task.task_id}: workspace path does not exist: {task.workspace_path}")
    if not task.test_command:
        result.warnings.append(f"{task.task_id}: no public test_command configured")
    if task.test_timeout_seconds <= 0:
        result.errors.append(f"{task.task_id}: test_timeout_seconds must be positive")
    if task.hidden_test_command and not (task.root / "hidden").exists():
        result.errors.append(f"{task.task_id}: hidden_test_command configured but hidden/ directory is missing")
    for protected_path in task.protected_paths:
        if not (task.workspace_path / protected_path).exists():
            result.errors.append(f"{task.task_id}: protected path is missing from workspace: {protected_path}")
    for index, check in enumerate(task.visual_checks):
        path = check.get("path")
        if not isinstance(path, str) or not path:
            result.errors.append(f"{task.task_id}: visual_checks[{index}] is missing path")
        elif not (task.workspace_path / path).exists():
            result.errors.append(f"{task.task_id}: visual check path is missing: {path}")
        if "type" not in check:
            result.errors.append(f"{task.task_id}: visual_checks[{index}] is missing type")
    for index, check in enumerate(task.process_checks):
        path = check.get("path")
        if not isinstance(path, str) or not path:
            result.errors.append(f"{task.task_id}: process_checks[{index}] is missing path")
        if "type" not in check:
            result.errors.append(f"{task.task_id}: process_checks[{index}] is missing type")
        if "dimension" not in check:
            result.errors.append(f"{task.task_id}: process_checks[{index}] is missing dimension")
    return result
