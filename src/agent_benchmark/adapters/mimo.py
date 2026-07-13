from __future__ import annotations

from agent_benchmark.adapters.command_base import ShellCommandAdapter


class MimoAdapter(ShellCommandAdapter):
    """Adapter for MimoCode's headless JSONL runner.

    MimoCode's standard macOS installer keeps the binary in
    ``~/.mimocode/bin/mimo`` without necessarily adding it to PATH. The
    built-in template accepts a normal PATH installation first and otherwise
    uses that documented local location. ``AGENT_BENCH_MIMO_COMMAND`` remains
    the explicit escape hatch for custom launchers.
    """

    name = "mimo"
    model_selection = "cli"
    command_env = "AGENT_BENCH_MIMO_COMMAND"
    timeout_env = "AGENT_BENCH_MIMO_TIMEOUT_SECONDS"
    default_command_template = (
        'if command -v mimo >/dev/null 2>&1; then mimo_bin="$(command -v mimo)"; '
        'elif [ -x "$HOME/.mimocode/bin/mimo" ]; then mimo_bin="$HOME/.mimocode/bin/mimo"; '
        'else echo "mimo was not found on PATH or at ~/.mimocode/bin/mimo" >&2; exit 127; fi; '
        'if [ "$AGENT_BENCH_MODEL" = "unspecified" ]; then '
        '"$mimo_bin" run --format json --dangerously-skip-permissions "$(cat {instruction_file})"; '
        "else "
        '"$mimo_bin" run --format json --dangerously-skip-permissions -m "$AGENT_BENCH_MODEL" "$(cat {instruction_file})"; '
        "fi"
    )
