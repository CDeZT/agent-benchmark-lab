# Adapter Contract

Adapters connect Agent Benchmark Lab to real harnesses such as Claude Code and opencode.

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

### generic-command

Implemented. A configurable adapter for experimental local harness commands. Configure it with `AGENT_BENCH_COMMAND`; the task instruction is passed on stdin from the isolated workspace, and is also available through command placeholders.

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

`AGENT_BENCH_MODEL` is the adapter-specific invocation identifier. `AGENT_BENCH_CANONICAL_MODEL` is the user-facing comparison identifier retained in reports; it is not necessarily valid CLI syntax for every harness.

Built-in default templates:

- opencode uses `opencode run --auto "$(cat {instruction_file})"` when `AGENT_BENCH_MODEL=unspecified`, otherwise it adds `--model "$AGENT_BENCH_MODEL"`.
- claude-code uses `claude -p --dangerously-skip-permissions --no-session-persistence "$(cat {instruction_file})"` when `AGENT_BENCH_MODEL=unspecified`, otherwise it adds `--model "$AGENT_BENCH_MODEL"`.

You can still override them with:

- `AGENT_BENCH_OPENCODE_COMMAND`
- `AGENT_BENCH_CLAUDE_CODE_COMMAND`

Claude Code's default template now uses `--output-format json`, so the runner can collect structured result metadata such as actual model identity, token usage, and cost when the configured provider exposes it.

## Evidence Events

Adapters should emit at least:

- `adapter.started`
- `adapter.command`
- `adapter.stdout`
- `adapter.stderr`
- `adapter.finished`
- `adapter.failed`

Long-running adapters should stream periodic progress events when possible.
