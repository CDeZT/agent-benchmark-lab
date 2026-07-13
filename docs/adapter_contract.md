# Adapter Contract

Adapters connect Agent Benchmark Lab to real harnesses such as Codex, Aider, Antigravity CLI, Claude Code, opencode, Grok, and MimoCode.

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

Implemented. Built-in default uses OpenCode's structured non-interactive mode:

`opencode run --auto --format json "$(cat {instruction_file})"`

When `AGENT_BENCH_MODEL` is not `unspecified`, the template adds `-m "$AGENT_BENCH_MODEL"`. The current local CLI successfully accepted `-m longcat/LongCat-2.0`. OpenCode's JSONL step events provide token/cost telemetry; its probe creates one temporary JSON session, then reads `opencode export <session-id>` to obtain the actual default model before task 1. Override with `AGENT_BENCH_OPENCODE_COMMAND`.

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

### antigravity

Implemented. This adapter targets Google Antigravity CLI's official `agy`
command:

`agy --dangerously-skip-permissions --print "$(cat {instruction_file})"`

It first uses `agy` from PATH, then falls back to the standard macOS/Linux
installation location `~/.local/bin/agy`. When `AGENT_BENCH_MODEL` is not
`unspecified`, the template adds `--model "$AGENT_BENCH_MODEL"`. AGY 1.1.1
has a usable non-interactive invocation but its print output is natural
language, not a stable telemetry schema. Do not parse text that mentions a
model, token count, cost, command, or tool as harness evidence; default model
identity is also pending without a paid probe. Override with
`AGENT_BENCH_ANTIGRAVITY_COMMAND`.

### grok

Implemented. Built-in default uses Grok Build headless mode:

`grok --always-approve --output-format streaming-json --prompt-file {instruction_file}`

When `AGENT_BENCH_MODEL` is not `unspecified`, the template adds `-m "$AGENT_BENCH_MODEL"`. The parser reads only explicit JSON/JSONL model, usage, cost, and tool fields. Override with `AGENT_BENCH_GROK_COMMAND`.

### mimo

Implemented. This adapter targets MimoCode's actual local command, `mimo`:

`mimo run --format json --dangerously-skip-permissions`

It first uses `mimo` from PATH, then falls back to the normal macOS installer
location `~/.mimocode/bin/mimo`. The runner's isolated workspace is the
process working directory. When `AGENT_BENCH_MODEL` is not `unspecified`, the
template adds `-m "$AGENT_BENCH_MODEL"`. Its JSONL parser records explicit
input/output token counts, cost, and tool events. MimoCode's observed default
JSONL output does not necessarily contain a model identifier, so the adapter
must leave model identity pending rather than treating the request as evidence.
Override with `AGENT_BENCH_MIMO_COMMAND`.

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

- opencode uses `opencode run --auto --format json`; its current local CLI accepts `-m provider/model` for an explicit model experiment. In `unspecified` mode, the adapter uses the present OpenCode default and the startup probe records `opencode export <session-id>` metadata before task 1.
- claude-code uses `claude -p --output-format json --dangerously-skip-permissions --no-session-persistence "$(cat {instruction_file})"` when `AGENT_BENCH_MODEL=unspecified`, otherwise it adds `--model "$AGENT_BENCH_MODEL"`.
- codex uses the JSONL `exec` template above; aider uses `--message-file` with git auto-commits disabled.
- antigravity uses `agy --dangerously-skip-permissions --print`; its current plain response is evidence-free until AGY publishes a stable machine-readable protocol.

You can still override them with:

- `AGENT_BENCH_OPENCODE_COMMAND`
- `AGENT_BENCH_CLAUDE_CODE_COMMAND`
- `AGENT_BENCH_CODEX_COMMAND`
- `AGENT_BENCH_AIDER_COMMAND`
- `AGENT_BENCH_ANTIGRAVITY_COMMAND`

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
