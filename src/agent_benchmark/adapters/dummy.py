from __future__ import annotations

import shutil
import time
from pathlib import Path

from agent_benchmark.adapters.base import AdapterResult
from agent_benchmark.recorders import JsonlRecorder
from agent_benchmark.task_schema import TaskSpec


class DummyAdapter:
    """Deterministic framework-validation adapter.

    This is not a real benchmark harness. It copies files from a task's
    `solution/` directory into the run workspace so the runner, scorer, and
    reports can be tested end-to-end.
    """

    name = "dummy"

    def run(self, task: TaskSpec, workspace: Path, recorder: JsonlRecorder) -> AdapterResult:
        start = time.monotonic()
        solution_dir = task.root / "solution"
        recorder.event("adapter.started", {"adapter": self.name, "solution_dir": str(solution_dir)})

        if not solution_dir.exists():
            message = "Dummy adapter expected a solution/ directory."
            recorder.event("adapter.failed", {"reason": message})
            return AdapterResult(self.name, 2, stderr=message, duration_seconds=time.monotonic() - start)

        copied: list[str] = []
        for source in solution_dir.rglob("*"):
            if source.is_dir():
                continue
            relative = source.relative_to(solution_dir)
            target = workspace / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied.append(str(relative))

        duration = time.monotonic() - start
        recorder.event("adapter.finished", {"adapter": self.name, "copied_files": copied, "duration_seconds": duration})
        return AdapterResult(
            adapter=self.name,
            exit_code=0,
            stdout=f"Copied {len(copied)} solution file(s).",
            duration_seconds=duration,
            notes=["framework-validation adapter"],
        )
