from __future__ import annotations

from agent_benchmark.adapters.command_base import ShellCommandAdapter


class GenericCommandAdapter(ShellCommandAdapter):
    """Adapter for experimenting with a local harness command.

    Configure with:

    - `AGENT_BENCH_COMMAND`: shell command to run from the task workspace.
    - `AGENT_BENCH_TIMEOUT_SECONDS`: optional timeout.

    The task instruction is passed on stdin. The command may also use
    `{task_id}` and `{title}` placeholders.
    """

    name = "generic-command"
    command_env = "AGENT_BENCH_COMMAND"
    timeout_env = "AGENT_BENCH_TIMEOUT_SECONDS"
