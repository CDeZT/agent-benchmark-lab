from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from agent_benchmark.task_schema.manifest import TaskSpec, load_task
from agent_benchmark.task_schema.suite import load_suite


DIFFICULTY_LEVELS = ("easy", "medium", "hard", "expert")
PROVENANCE_TYPES = ("custom_seed", "domain_seed", "inspired_by_external", "external_imported")


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
    _validate_catalog_metadata(task, result)
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
        check_type = check.get("type", "")
        if check_type == "instruction_match":
            expected = check.get("expected_changed_files")
            if not isinstance(expected, list) or not expected:
                result.errors.append(f"{task.task_id}: process_checks[{index}] instruction_match is missing expected_changed_files")
        else:
            path = check.get("path")
            if not isinstance(path, str) or not path:
                result.errors.append(f"{task.task_id}: process_checks[{index}] is missing path")
        if "type" not in check:
            result.errors.append(f"{task.task_id}: process_checks[{index}] is missing type")
        if "dimension" not in check:
            result.errors.append(f"{task.task_id}: process_checks[{index}] is missing dimension")
    return result


def _validate_catalog_metadata(task: TaskSpec, result: ValidationResult) -> None:
    """Validate fields that make corpus composition and source claims auditable."""
    if task.difficulty == "unspecified":
        result.warnings.append(f"{task.task_id}: missing difficulty metadata")
    elif task.difficulty not in DIFFICULTY_LEVELS:
        result.errors.append(
            f"{task.task_id}: difficulty must be one of {', '.join(DIFFICULTY_LEVELS)}"
        )
    elif not task.difficulty_rationale.strip():
        result.warnings.append(f"{task.task_id}: missing difficulty_rationale")

    environment = task.metadata.get("environment", "local")
    if environment not in {"local", "container_required"}:
        result.errors.append(
            f"{task.task_id}: metadata.environment must be local or container_required"
        )
    if environment == "container_required":
        packages = task.metadata.get("required_python_packages")
        if not isinstance(packages, list) or not packages:
            result.errors.append(f"{task.task_id}: container_required tasks need required_python_packages")
        elif any(not isinstance(package, str) or "==" not in package for package in packages):
            result.errors.append(f"{task.task_id}: container packages must be exact-version strings")
        container = task.metadata.get("container", {})
        if container and not isinstance(container, dict):
            result.errors.append(f"{task.task_id}: metadata.container must be an object")

    if not task.provenance:
        result.warnings.append(f"{task.task_id}: missing provenance metadata")
        return

    provenance_type = task.provenance.get("type")
    if provenance_type not in PROVENANCE_TYPES:
        result.errors.append(
            f"{task.task_id}: provenance.type must be one of {', '.join(PROVENANCE_TYPES)}"
        )
        return

    if provenance_type == "external_imported":
        required = ("source_benchmark", "source_id", "source_url", "source_version", "license_note", "importer_version")
        missing = [field for field in required if not str(task.provenance.get(field, "")).strip()]
        if missing:
            result.errors.append(
                f"{task.task_id}: external_imported provenance is missing {', '.join(missing)}"
            )
    elif not str(task.provenance.get("source", "")).strip():
        result.warnings.append(f"{task.task_id}: custom provenance should include source")
