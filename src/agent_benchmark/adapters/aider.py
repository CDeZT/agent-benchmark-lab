from __future__ import annotations

from agent_benchmark.adapters.command_base import ShellCommandAdapter


class AiderAdapter(ShellCommandAdapter):
    """Adapter for Aider's one-message, non-interactive coding mode."""

    name = "aider"
    model_selection = "cli"
    command_env = "AGENT_BENCH_AIDER_COMMAND"
    timeout_env = "AGENT_BENCH_AIDER_TIMEOUT_SECONDS"
    default_command_template = (
        'if [ "$AGENT_BENCH_MODEL" = "unspecified" ]; then '
        'aider --yes-always --no-git --no-auto-commits --no-stream --message-file {instruction_file}; '
        "else "
        'aider --yes-always --no-git --no-auto-commits --no-stream --model "$AGENT_BENCH_MODEL" --message-file {instruction_file}; '
        "fi"
    )
