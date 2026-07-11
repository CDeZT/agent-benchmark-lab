from __future__ import annotations

import hashlib
from pathlib import Path

from agent_benchmark.task_schema import TaskSpec


_IGNORED_PARTS = {"__pycache__", ".pytest_cache", ".DS_Store"}


def task_fingerprint(task: TaskSpec) -> str:
    """Hash the complete task contract used to judge an agent run.

    The task manifest, starting workspace, public/hidden tests, reference
    solution, and task-local evaluator files all affect score validity. A
    historical result is comparable only if this fingerprint matches.
    """
    digest = hashlib.sha256(b"agent-benchmark-task-fingerprint-v1\0")
    for path in sorted(task.root.rglob("*")):
        if not path.is_file() or any(part in _IGNORED_PARTS for part in path.parts):
            continue
        relative = path.relative_to(task.root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        contents = path.read_bytes()
        digest.update(len(contents).to_bytes(8, "big"))
        digest.update(contents)
    return digest.hexdigest()
