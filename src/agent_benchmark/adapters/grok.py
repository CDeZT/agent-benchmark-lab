from __future__ import annotations

from agent_benchmark.adapters.command_base import ShellCommandAdapter


class GrokAdapter(ShellCommandAdapter):
    """Adapter for the Grok Build CLI (headless mode).

    Configure with ``AGENT_BENCH_GROK_COMMAND`` to override the template.
    Uses ``--prompt-file`` + ``--always-approve`` + JSON output so runs are
    non-interactive and leave parseable evidence when the CLI exposes it.
    """

    name = "grok"
    model_selection = "cli"
    command_env = "AGENT_BENCH_GROK_COMMAND"
    timeout_env = "AGENT_BENCH_GROK_TIMEOUT_SECONDS"
    default_command_template = (
        'if [ "$AGENT_BENCH_MODEL" = "unspecified" ]; then '
        "grok --always-approve --output-format json --prompt-file {instruction_file}; "
        "else "
        'grok --always-approve --output-format json -m "$AGENT_BENCH_MODEL" --prompt-file {instruction_file}; '
        "fi"
    )
