from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    title: str
    instruction: str
    capabilities: list[str]
    domains: list[str]
    workspace: str = "workspace"
    test_command: list[str] = field(default_factory=list)
    hidden_test_command: list[str] = field(default_factory=list)
    test_timeout_seconds: float = 60.0
    protected_paths: list[str] = field(default_factory=list)
    visual_checks: list[dict[str, Any]] = field(default_factory=list)
    process_checks: list[dict[str, Any]] = field(default_factory=list)
    artifact_ignore_globs: list[str] = field(default_factory=list)
    scoring_weights: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    root: Path = Path(".")

    @property
    def workspace_path(self) -> Path:
        return self.root / self.workspace


def load_task(task_dir: Path) -> TaskSpec:
    manifest_path = task_dir / "task.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing task manifest: {manifest_path}")

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    required = ["id", "title", "instruction"]
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError(f"Task {task_dir} is missing required fields: {', '.join(missing)}")

    return TaskSpec(
        task_id=data["id"],
        title=data["title"],
        instruction=data["instruction"],
        capabilities=list(data.get("capabilities", [])),
        domains=list(data.get("domains", [])),
        workspace=data.get("workspace", "workspace"),
        test_command=list(data.get("test_command", [])),
        hidden_test_command=list(data.get("hidden_test_command", [])),
        test_timeout_seconds=float(data.get("test_timeout_seconds", 60.0)),
        protected_paths=list(data.get("protected_paths", [])),
        visual_checks=list(data.get("visual_checks", [])),
        process_checks=list(data.get("process_checks", [])),
        artifact_ignore_globs=list(data.get("artifact_ignore_globs", [])),
        scoring_weights=dict(data.get("scoring_weights", {})),
        metadata=dict(data.get("metadata", {})),
        root=task_dir,
    )
