from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any, Callable

from agent_benchmark.runner.container import docker_ready


@dataclass(frozen=True)
class AuthoritativeCorpus:
    corpus_id: str
    status: str
    official_repository: str
    dataset: str
    official_evaluator: str
    license_note: str
    pilot_policy: str
    tool_requirements: tuple[dict[str, str], ...]
    dataset_version: str | None = None


def load_authoritative_corpora(path: Path) -> list[AuthoritativeCorpus]:
    """Load and validate upstream evaluator contracts without downloading data."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("Authoritative corpus registry must be a schema_version 1 object.")
    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("Authoritative corpus registry must contain a non-empty sources list.")

    parsed: list[AuthoritativeCorpus] = []
    seen_ids: set[str] = set()
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            raise ValueError(f"Authoritative corpus source {index} must be an object.")
        required = (
            "id",
            "status",
            "official_repository",
            "dataset",
            "official_evaluator",
            "license_note",
            "pilot_policy",
        )
        missing = [field for field in required if not isinstance(source.get(field), str) or not source[field].strip()]
        requirements = source.get("tool_requirements")
        if missing:
            raise ValueError(f"Authoritative corpus '{source.get('id', index)}' is missing {', '.join(missing)}.")
        if not isinstance(requirements, list) or not requirements:
            raise ValueError(f"Authoritative corpus '{source.get('id', index)}' needs non-empty tool_requirements.")
        normalized_requirements: list[dict[str, str]] = []
        for requirement in requirements:
            if not isinstance(requirement, dict):
                raise ValueError(f"Authoritative corpus '{source['id']}' has an invalid tool requirement.")
            kind = requirement.get("kind")
            value = requirement.get("value")
            interpreter = requirement.get("interpreter")
            if kind not in {"python_module", "command"} or not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"Authoritative corpus '{source['id']}' tool requirements need kind=python_module|command and value."
                )
            if interpreter is not None and (kind != "python_module" or not isinstance(interpreter, str) or not interpreter.strip()):
                raise ValueError(f"Authoritative corpus '{source['id']}' has an invalid tool requirement interpreter.")
            normalized = {"kind": kind, "value": value}
            if isinstance(interpreter, str):
                normalized["interpreter"] = interpreter
            normalized_requirements.append(normalized)
        corpus_id = source["id"].strip()
        if corpus_id in seen_ids:
            raise ValueError(f"Duplicate authoritative corpus id '{corpus_id}'.")
        seen_ids.add(corpus_id)
        dataset_version = source.get("dataset_version")
        if dataset_version is not None and (not isinstance(dataset_version, str) or not dataset_version.strip()):
            raise ValueError(f"Authoritative corpus '{corpus_id}' has an invalid dataset_version.")
        parsed.append(
            AuthoritativeCorpus(
                corpus_id=corpus_id,
                status=source["status"].strip(),
                official_repository=source["official_repository"].strip(),
                dataset=source["dataset"].strip(),
                dataset_version=dataset_version.strip() if isinstance(dataset_version, str) else None,
                official_evaluator=source["official_evaluator"].strip(),
                license_note=source["license_note"].strip(),
                pilot_policy=source["pilot_policy"].strip(),
                tool_requirements=tuple(normalized_requirements),
            )
        )
    return parsed


def preflight_authoritative_corpora(
    registry_path: Path,
    corpus_id: str | None = None,
    *,
    docker_status: Callable[[], tuple[bool, str]] = docker_ready,
    command_exists: Callable[[str], str | None] = shutil.which,
    module_available: Callable[[str], bool] | None = None,
) -> dict[str, Any]:
    """Report whether official evaluator bridges are runnable, without importing tasks.

    A ready toolchain is deliberately not treated as an imported corpus. A
    separate importer must still freeze upstream instance identifiers and retain
    official evaluator output before a task can be marked external_imported.
    """
    corpora = load_authoritative_corpora(registry_path)
    selected = [corpus for corpus in corpora if corpus_id is None or corpus.corpus_id == corpus_id]
    if corpus_id is not None and not selected:
        raise ValueError(f"Unknown authoritative corpus '{corpus_id}'.")
    docker_is_ready, docker_detail = docker_status()
    sources: list[dict[str, Any]] = []
    for corpus in selected:
        requirements = []
        for requirement in corpus.tool_requirements:
            if requirement["kind"] == "python_module":
                ready = (
                    module_available(requirement["value"])
                    if module_available is not None
                    else _module_is_available(requirement["value"], requirement.get("interpreter"), registry_path)
                )
            else:
                ready = bool(command_exists(requirement["value"]))
            requirements.append({**requirement, "ready": ready})
        execution_ready = docker_is_ready and all(requirement["ready"] for requirement in requirements)
        sources.append(
            {
                "id": corpus.corpus_id,
                "status": corpus.status,
                "official_repository": corpus.official_repository,
                "dataset": corpus.dataset,
                "dataset_version": corpus.dataset_version,
                "official_evaluator": corpus.official_evaluator,
                "tool_requirements": requirements,
                "docker_required": True,
                "docker_ready": docker_is_ready,
                "execution_ready": execution_ready,
                "imported": False,
                "next_requirement": (
                    "Freeze a stratified instance list and retain official evaluator output."
                    if execution_ready
                    else "Install or repair every missing tool requirement before attempting an import."
                ),
            }
        )
    return {
        "registry_path": str(registry_path),
        "registry_valid": True,
        "docker": {"ready": docker_is_ready, "detail": docker_detail},
        "source_count": len(sources),
        "execution_ready_count": sum(1 for source in sources if source["execution_ready"]),
        "sources": sources,
    }


def _module_is_available(module: str, interpreter: str | None, registry_path: Path) -> bool:
    if interpreter is None:
        return find_spec(module) is not None
    executable = Path(interpreter)
    if not executable.is_absolute():
        executable = registry_path.parent.parent / executable
    if not executable.is_file():
        return False
    try:
        completed = subprocess.run(
            [str(executable), "-c", f"import {module}"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0
