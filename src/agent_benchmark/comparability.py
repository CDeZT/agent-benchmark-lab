from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_benchmark.adapters import available_adapters
from agent_benchmark.model_identity import summarize_model_identity
from agent_benchmark.runner.container import docker_ready
from agent_benchmark.task_schema import TaskSpec, load_task


def preflight_matrix(
    suite: object,
    combination_specs: list[dict[str, object]],
    tasks_dir: Path,
    *,
    registry_used: bool,
) -> dict[str, object]:
    """Assess whether a matrix can start and what claims it can support.

    This is deliberately non-executing: it does not invoke a harness, build an
    image, or create a run directory.  Model identity can only be verified by
    saved output after a run, so this report calls out that remaining gate.
    """
    task_root = tasks_dir
    checks: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    blockers: list[dict[str, str]] = []

    def add(status: str, code: str, message: str) -> None:
        item = {"status": status, "code": code, "message": message}
        checks.append(item)
        if status == "warning":
            warnings.append(item)
        elif status == "blocked":
            blockers.append(item)

    if not combination_specs:
        add("blocked", "no_combinations", "Matrix needs at least one adapter/model/profile combination.")

    available = set(available_adapters())
    adapters = {str(spec.get("adapter", "")) for spec in combination_specs}
    unknown_adapters = sorted(adapter for adapter in adapters if adapter not in available)
    if unknown_adapters:
        add("blocked", "unknown_adapter", "Unknown adapters: " + ", ".join(unknown_adapters) + ".")
    else:
        add("pass", "adapters_available", "All requested adapters are installed in the benchmark registry.")

    repetitions = [int(spec.get("repetitions", 0)) for spec in combination_specs]
    if any(value < 1 for value in repetitions):
        add("blocked", "invalid_repetitions", "Every combination must request at least one repetition.")
    elif min(repetitions, default=0) < 3:
        add("warning", "insufficient_repetitions", "Fewer than 3 repetitions cannot support the standard mean/variance comparison gate.")
    else:
        add("pass", "repetitions", "Every combination has at least 3 repetitions.")

    duplicate_keys: set[tuple[str, str, str]] = set()
    duplicates: set[tuple[str, str, str]] = set()
    for spec in combination_specs:
        key = (str(spec.get("adapter")), str(spec.get("model")), str(spec.get("budget_profile")))
        if key in duplicate_keys:
            duplicates.add(key)
        duplicate_keys.add(key)
    if duplicates:
        rendered = ", ".join("/".join(item) for item in sorted(duplicates))
        add("blocked", "duplicate_combination", "Duplicate matrix combinations: " + rendered + ".")
    else:
        add("pass", "unique_combinations", "Each adapter/model/profile combination is unique.")

    task_reports: list[dict[str, object]] = []
    comparative_ids: list[str] = []
    excluded_ids: list[str] = []
    container_tasks: list[str] = []
    for task_id in list(getattr(suite, "tasks", [])):
        try:
            task = load_task(task_root / task_id)
        except Exception as exc:  # noqa: BLE001 - preflight must explain malformed suites.
            add("blocked", "task_unavailable", f"Task '{task_id}' cannot be loaded: {exc}")
            continue
        task_report = _task_report(task)
        task_reports.append(task_report)
        if task_report["benchmark_role"] == "comparative_candidate":
            comparative_ids.append(task.task_id)
        else:
            excluded_ids.append(task.task_id)
        if task_report["environment"] == "container_required":
            container_tasks.append(task.task_id)
        if not task.test_command:
            add("blocked", "missing_public_test", f"Task '{task.task_id}' has no public test command.")
        if not task.hidden_test_command:
            add("warning", "missing_hidden_test", f"Task '{task.task_id}' has no hidden test command.")

    if comparative_ids:
        add("pass", "comparative_tasks", f"Suite contains {len(comparative_ids)} comparative task(s).")
    else:
        add("blocked", "no_comparative_tasks", "Suite contains no comparative_candidate tasks.")
    if excluded_ids:
        add("warning", "noncomparative_tasks_excluded", "Excluded from leaderboard: " + ", ".join(excluded_ids) + ".")

    if container_tasks:
        ready, detail = docker_ready()
        if ready:
            add("pass", "docker_ready", "Docker is ready for container tasks: " + ", ".join(container_tasks) + ".")
        else:
            add("blocked", "docker_unavailable", "Docker is required by " + ", ".join(container_tasks) + ": " + detail)
    else:
        add("pass", "local_environment", "All selected tasks use local evaluator environments.")

    mappings: list[dict[str, object]] = []
    for spec in combination_specs:
        model = str(spec.get("model", "unspecified"))
        adapter = str(spec.get("adapter", ""))
        adapter_model = str(spec.get("adapter_model") or model)
        identity_hint = summarize_model_identity(model, [adapter_model])
        mapping = {
            "adapter": adapter,
            "canonical_model": model,
            "adapter_model": adapter_model,
            "identity_hint": identity_hint["status"],
        }
        mappings.append(mapping)
        if registry_used and identity_hint["status"] == "mismatch":
            add(
                "warning",
                "registry_identity_hint_mismatch",
                f"Registry maps canonical '{model}' to '{adapter_model}' for '{adapter}', which does not normalize to the canonical id. Post-run evidence must resolve this before comparison.",
            )

    if registry_used:
        add("pass", "model_registry", "Adapter-specific invocation identifiers were resolved from the supplied model registry.")
    elif len(adapters) > 1:
        add("warning", "no_model_registry", "Multiple harnesses use raw model identifiers; same-model claims remain provisional until actual identities are recorded.")
    else:
        add("warning", "no_model_registry", "No model registry was supplied; post-run model identity still needs checking.")

    execution_ready = not blockers
    identity_configuration_clean = (
        not any(item["code"] == "registry_identity_hint_mismatch" for item in warnings)
        and (registry_used or len(adapters) <= 1)
    )
    ranking_ready = (
        execution_ready
        and min(repetitions, default=0) >= 3
        and bool(comparative_ids)
        and identity_configuration_clean
    )
    same_model_claim_requires_postrun_verification = len(adapters) > 1
    return {
        "suite_id": str(getattr(suite, "suite_id", "unknown")),
        "combination_count": len(combination_specs),
        "execution_ready": execution_ready,
        "comparative_ranking_ready": ranking_ready,
        "identity_configuration_clean": identity_configuration_clean,
        "same_model_claim_requires_postrun_verification": same_model_claim_requires_postrun_verification,
        "checks": checks,
        "warnings": warnings,
        "blockers": blockers,
        "tasks": task_reports,
        "comparative_task_ids": comparative_ids,
        "excluded_task_ids": excluded_ids,
        "model_mappings": mappings,
    }


def _task_report(task: TaskSpec) -> dict[str, object]:
    return {
        "task_id": task.task_id,
        "difficulty": task.difficulty,
        "benchmark_role": str(task.metadata.get("benchmark_role", "comparative_candidate")),
        "environment": str(task.metadata.get("environment", "local")),
        "has_public_tests": bool(task.test_command),
        "has_hidden_tests": bool(task.hidden_test_command),
    }
