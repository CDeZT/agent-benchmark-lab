from __future__ import annotations

from agent_benchmark.adapters.command_base import ShellCommandAdapter


class OpencodeAdapter(ShellCommandAdapter):
    """Adapter shell for the real opencode CLI.

    Configure with `AGENT_BENCH_OPENCODE_COMMAND`. The task instruction is
    passed on stdin from inside the isolated task workspace.
    """

    name = "opencode"
    model_selection = "cli"
    command_env = "AGENT_BENCH_OPENCODE_COMMAND"
    timeout_env = "AGENT_BENCH_OPENCODE_TIMEOUT_SECONDS"
    default_command_template = (
        'if [ "$AGENT_BENCH_MODEL" = "unspecified" ]; then '
        'opencode run --auto --format json "$(cat {instruction_file})"; '
        "else "
        'opencode run --auto --format json -m "$AGENT_BENCH_MODEL" "$(cat {instruction_file})"; '
        "fi"
    )
