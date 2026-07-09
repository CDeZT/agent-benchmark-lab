from __future__ import annotations

import os
import shlex
import subprocess
import time
from pathlib import Path

from agent_benchmark.adapters.base import AdapterResult
from agent_benchmark.recorders import JsonlRecorder
from agent_benchmark.task_schema import TaskSpec


class ShellCommandAdapter:
    name = "shell-command"
    command_env = "AGENT_BENCH_COMMAND"
    timeout_env = "AGENT_BENCH_TIMEOUT_SECONDS"
    default_command_template: str | None = None

    def command_missing_message(self) -> str:
        return f"{self.command_env} is required for {self.name} adapter."

    def command_template(self) -> str | None:
        return os.environ.get(self.command_env) or self.default_command_template

    def timeout_seconds(self) -> float | None:
        raw = os.environ.get(self.timeout_env) or os.environ.get("AGENT_BENCH_TIMEOUT_SECONDS")
        if not raw:
            return None
        return float(raw)

    def run(self, task: TaskSpec, workspace: Path, recorder: JsonlRecorder) -> AdapterResult:
        command_template = self.command_template()
        if not command_template:
            message = self.command_missing_message()
            recorder.event("adapter.failed", {"adapter": self.name, "reason": message})
            return AdapterResult(adapter=self.name, exit_code=2, stderr=message)

        instruction_file = workspace.parent / "instruction.txt"
        instruction_file.write_text(task.instruction, encoding="utf-8")
        command = command_template.format(
            task_id=shlex.quote(task.task_id),
            title=shlex.quote(task.title),
            workspace=shlex.quote(str(workspace.resolve())),
            instruction_file=shlex.quote(str(instruction_file.resolve())),
            prompt=shlex.quote(task.instruction),
        )
        timeout = self.timeout_seconds()
        recorder.event("adapter.started", {"adapter": self.name})
        recorder.event("adapter.command", {"command": command, "timeout_seconds": timeout})

        start = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                cwd=workspace,
                input=task.instruction,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                timeout=timeout,
                check=False,
            )
            duration = time.monotonic() - start
            recorder.event(
                "adapter.finished",
                {
                    "adapter": self.name,
                    "exit_code": completed.returncode,
                    "duration_seconds": duration,
                    "stdout_tail": completed.stdout[-1000:],
                    "stderr_tail": completed.stderr[-1000:],
                },
            )
            return AdapterResult(
                adapter=self.name,
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                duration_seconds=duration,
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.monotonic() - start
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            message = f"Command timed out after {timeout} seconds."
            recorder.event(
                "adapter.failed",
                {
                    "adapter": self.name,
                    "reason": message,
                    "duration_seconds": duration,
                    "stdout_tail": stdout[-1000:],
                    "stderr_tail": stderr[-1000:],
                },
            )
            return AdapterResult(
                adapter=self.name,
                exit_code=124,
                stdout=stdout,
                stderr=stderr + message,
                duration_seconds=duration,
            )
