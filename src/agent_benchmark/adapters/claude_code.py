from __future__ import annotations

from agent_benchmark.adapters.command_base import ShellCommandAdapter


class ClaudeCodeAdapter(ShellCommandAdapter):
    """Adapter shell for the real Claude Code CLI.

    Configure with `AGENT_BENCH_CLAUDE_CODE_COMMAND`. The task instruction is
    passed on stdin from inside the isolated task workspace.
    """

    name = "claude-code"
    command_env = "AGENT_BENCH_CLAUDE_CODE_COMMAND"
    timeout_env = "AGENT_BENCH_CLAUDE_CODE_TIMEOUT_SECONDS"
    default_command_template = (
        'if [ "$AGENT_BENCH_MODEL" = "unspecified" ]; then '
        'claude -p --output-format json --dangerously-skip-permissions --no-session-persistence "$(cat {instruction_file})"; '
        "else "
        'claude -p --output-format json --dangerously-skip-permissions --no-session-persistence --model "$AGENT_BENCH_MODEL" "$(cat {instruction_file})"; '
        "fi"
    )
