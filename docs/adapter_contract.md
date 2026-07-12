# Adapter Contract

Adapters connect Agent Benchmark Lab to real harnesses such as Codex, Aider, Claude Code, and opencode.

## Required Behavior

An adapter must:

- Receive a task instruction and isolated workspace path.
- Invoke the harness in a generic way.
- Capture stdout, stderr, exit code, and duration.
- Save enough trace events to explain what happened.
- Avoid task-specific shortcuts.
- Avoid reading secrets from repository files.

## Fairness Boundary

Adapters may be harness-specific because each harness has different natural usage. This is not considered cheating.

Adapters must not be task-specific. They must not:

- Detect task ids and apply custom fixes.
- Modify tests directly.
- Hide harness failures.
- Award scores.
- Delete evidence.

## Planned Adapters

### dummy

Implemented. It copies a task's `solution/` files into the workspace. This adapter exists only to validate the benchmark framework.

### opencode

Adapter shell implemented. Configure with `AGENT_BENCH_OPENCODE_COMMAND`. The task instruction is passed on stdin from inside the isolated workspace, and is also available through command placeholders. The exact command template should be refined after testing against the user's local opencode CLI.

### claude-code

Adapter shell implemented. Configure with `AGENT_BENCH_CLAUDE_CODE_COMMAND`. The task instruction is passed on stdin from inside the isolated workspace, and is also available through command placeholders. Permission and interaction handling must be refined after testing against the user's local Claude Code CLI.

### codex

Implemented. Built-in default uses Codex's non-interactive JSONL mode:

`codex exec --json --ephemeral --sandbox workspace-write --skip-git-repo-check -C {workspace}`

When `AGENT_BENCH_MODEL` is not `unspecified`, the template adds `-m "$AGENT_BENCH_MODEL"`. Codex command-execution/file-change JSON events and explicitly emitted usage fields are parsed; missing fields remain unavailable. Override with `AGENT_BENCH_CODEX_COMMAND`.

### aider

Implemented. Built-in default uses Aider's one-message scripting mode:

`aider --yes-always --no-git --no-auto-commits --no-stream --message-file {instruction_file}`

When `AGENT_BENCH_MODEL` is not `unspecified`, the template adds `--model "$AGENT_BENCH_MODEL"`. Aider's git integration is disabled because each benchmark run owns a disposable workspace. Only model/token/cost fields explicitly printed by Aider are parsed; a workspace diff alone is heuristic editing evidence, not verified tool telemetry. Override with `AGENT_BENCH_AIDER_COMMAND`.

### grok

Implemented. Built-in default uses Grok Build headless mode:

`grok --always-approve --output-format json --prompt-file {instruction_file}`

When `AGENT_BENCH_MODEL` is not `unspecified`, the template adds `-m "$AGENT_BENCH_MODEL"`. Override with `AGENT_BENCH_GROK_COMMAND`.

### generic-command

Implemented. A configurable adapter for experimental local harness commands. Configure it with `AGENT_BENCH_COMMAND`; the task instruction is passed on stdin from the isolated workspace, and is also available through command placeholders.

### Config registry (any headless CLI)

`config/harnesses.example.json` documents command templates for grok/gemini/opencode/claude-code. Copy to `config/harnesses.json` (gitignored) or set `AGENT_BENCH_HARNESSES_FILE` to register additional adapter names without writing Python. Built-in code adapters always win on name collision. CLI flag churn should be fixed by editing the command string, not the scoring system.

Command templates support these shell-quoted placeholders:

- `{task_id}`
- `{title}`
- `{workspace}`
- `{instruction_file}`
- `{prompt}`

The runner also injects these environment variables while the adapter command is built and executed:

- `AGENT_BENCH_MODEL`
- `AGENT_BENCH_CANONICAL_MODEL`
- `AGENT_BENCH_BUDGET_PROFILE`
- `AGENT_BENCH_LABEL`
- `AGENT_BENCH_BUDGET_MAX_ATTEMPTS`
- `AGENT_BENCH_BUDGET_MAX_SECONDS`

`AGENT_BENCH_MODEL` is the adapter-specific invocation identifier. `AGENT_BENCH_CANONICAL_MODEL` is the user-facing comparison identifier retained in reports; it is not necessarily valid CLI syntax for every harness.

`AGENT_BENCH_MODEL=unspecified` is intentional: it tells a built-in adapter to
use its current CLI default. The user changes those defaults over time, so this
mode must not be rewritten to a remembered DeepSeek, mimo, longcat, GPT, or
Gemini label. The runner records any actual identity exposed by saved harness
output. See `docs/model_modes.md` for the distinction between this practical
configuration comparison and an explicit same-model experiment.

An explicit adapter timeout environment variable takes precedence. Otherwise a profile with `AGENT_BENCH_BUDGET_MAX_SECONDS` supplies the subprocess timeout. `open_ended` intentionally has no timeout. A Ctrl-C interruption preserves `interruption.json`, `checkpoint.json`, and `run.interrupted` evidence; `resume` reruns repetitions that have no saved `result.json`.

Built-in default templates:

- opencode 1.17.15 always uses `opencode run --auto "$(cat {instruction_file})"`. Its `--model` flag currently crashes against this local CLI/provider setup, so the matrix command cannot select an opencode model; it intentionally uses the current opencode configured default and records any identity available from saved output.
- claude-code uses `claude -p --output-format json --dangerously-skip-permissions --no-session-persistence "$(cat {instruction_file})"` when `AGENT_BENCH_MODEL=unspecified`, otherwise it adds `--model "$AGENT_BENCH_MODEL"`.
- codex uses the JSONL `exec` template above; aider uses `--message-file` with git auto-commits disabled.

You can still override them with:

- `AGENT_BENCH_OPENCODE_COMMAND`
- `AGENT_BENCH_CLAUDE_CODE_COMMAND`
- `AGENT_BENCH_CODEX_COMMAND`
- `AGENT_BENCH_AIDER_COMMAND`

Claude Code's default template now uses `--output-format json`, so the runner can collect structured result metadata such as actual model identity, token usage, and cost when the configured provider exposes it.

## Evidence Events

Adapters should emit at least:

- `adapter.started`
- `adapter.command`
- `adapter.stdout`
- `adapter.stderr`
- `adapter.finished`
- `adapter.failed`
- `run.interrupted`

Long-running adapters should stream periodic progress events when possible.
