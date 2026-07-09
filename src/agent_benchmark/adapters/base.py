from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from agent_benchmark.recorders import JsonlRecorder
from agent_benchmark.task_schema import TaskSpec


@dataclass
class AdapterResult:
    adapter: str
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    notes: list[str] | None = None


class HarnessAdapter(Protocol):
    name: str

    def run(self, task: TaskSpec, workspace: Path, recorder: JsonlRecorder) -> AdapterResult:
        """Run the harness against the task workspace."""
