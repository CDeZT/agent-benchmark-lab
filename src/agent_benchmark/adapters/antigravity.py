from __future__ import annotations

from agent_benchmark.adapters.command_base import ShellCommandAdapter


class AntigravityAdapter(ShellCommandAdapter):
    """Adapter for Google Antigravity CLI's non-interactive ``agy --print`` mode.

    The CLI's normal interactive surface is a TUI, but ``--print`` executes one
    prompt and writes its response to stdout.  The adapter deliberately uses
    the current CLI default for ``unspecified`` and only passes ``--model`` for
    an explicit benchmark request.  Antigravity 1.1.1 does not expose
    structured tool, token, cost, or default-model telemetry in print mode, so
    the parser keeps those fields unavailable instead of inferring them.
    """

    name = "antigravity"
    model_selection = "cli"
    command_env = "AGENT_BENCH_ANTIGRAVITY_COMMAND"
    timeout_env = "AGENT_BENCH_ANTIGRAVITY_TIMEOUT_SECONDS"
    default_command_template = (
        'if command -v agy >/dev/null 2>&1; then agy_bin="$(command -v agy)"; '
        'elif [ -x "$HOME/.local/bin/agy" ]; then agy_bin="$HOME/.local/bin/agy"; '
        'else echo "agy was not found on PATH or at ~/.local/bin/agy" >&2; exit 127; fi; '
        'if [ "$AGENT_BENCH_MODEL" = "unspecified" ]; then '
        '"$agy_bin" --dangerously-skip-permissions --print "$(cat {instruction_file})"; '
        "else "
        '"$agy_bin" --dangerously-skip-permissions --model "$AGENT_BENCH_MODEL" --print "$(cat {instruction_file})"; '
        "fi"
    )
