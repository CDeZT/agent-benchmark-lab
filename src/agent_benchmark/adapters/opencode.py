from __future__ import annotations

from agent_benchmark.adapters.command_base import ShellCommandAdapter


class OpencodeAdapter(ShellCommandAdapter):
    """Adapter shell for the real opencode CLI.

    Configure with `AGENT_BENCH_OPENCODE_COMMAND`. The task instruction is
    passed on stdin from inside the isolated task workspace.
    """

    name = "opencode"
    model_selection = "configured_default_only"
    command_env = "AGENT_BENCH_OPENCODE_COMMAND"
    timeout_env = "AGENT_BENCH_OPENCODE_TIMEOUT_SECONDS"
    default_command_template = (
        # opencode 1.17.15 --model flag triggers server errors. Run without --model;
        # the harness uses its own configured default model.
        'opencode run --auto "$(cat {instruction_file})"'
    )
