from __future__ import annotations

from agent_benchmark.adapters.command_base import ShellCommandAdapter


class CodexAdapter(ShellCommandAdapter):
    """Adapter for the local Codex CLI's non-interactive execution mode."""

    name = "codex"
    model_selection = "cli"
    command_env = "AGENT_BENCH_CODEX_COMMAND"
    timeout_env = "AGENT_BENCH_CODEX_TIMEOUT_SECONDS"
    default_command_template = (
        'if [ "$AGENT_BENCH_MODEL" = "unspecified" ]; then '
        'codex exec --json --ephemeral --sandbox workspace-write --skip-git-repo-check -C {workspace} "$(cat {instruction_file})"; '
        "else "
        'codex exec --json --ephemeral --sandbox workspace-write --skip-git-repo-check -C {workspace} -m "$AGENT_BENCH_MODEL" "$(cat {instruction_file})"; '
        "fi"
    )
