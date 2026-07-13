# Requirements

This document is the source of truth for the user's goals. It intentionally includes long-term requirements that may not be implemented in the first version.

## Project Purpose

Build a personal, long-term benchmark system for quantifying the real capabilities of coding agents and model/harness combinations. The core unit of comparison is:

```text
harness x model x task x environment x budget profile
```

The benchmark must support all of these comparison modes:

- Same model, different harnesses, such as DeepSeek in Claude Code versus opencode.
- Same harness, different models, such as Claude Code with DeepSeek, mimo, longcat, GPT, or Gemini.
- Full combination ranking across harness/model pairs.
- Current CLI default configuration comparison: Claude Code and opencode may be reconfigured by the user at any time, so the default experiment must use each CLI's live default rather than assuming a fixed model label. It must record observed identity and clearly distinguish this practical configuration comparison from a same-model claim.

The project exists because public model leaderboards often do not answer the user's actual question: which real local tool and model combination is better for their own work.

Model-selection rule: a registry or CLI argument is configuration metadata, not
proof of actual model identity. Explicit same-model conclusions require saved
post-run identity evidence; the ordinary CLI-default mode must remain usable
without pinning a model or maintaining a registry.

## User Priorities

The benchmark should measure more than task success. Harness strength is multi-dimensional and should include:

- Understanding the user's intent, including informal and incomplete requirements.
- Producing a complete and realistic plan.
- Updating the plan while working.
- Splitting work across subagents or subtasks when the harness supports it.
- Implementing a demo or final artifact.
- Running automated tests.
- Performing visual checks for UI tasks.
- Detecting bugs and iterating without being asked.
- Continuing until the result matches the original target.
- Avoiding unrelated or destructive changes.
- Recording enough evidence to explain the score.

The user prefers reliability and completeness over speed or low cost. Time, token use, and money should still be measured, but they are not the primary optimization target.

## Output Expectations

The benchmark should eventually produce:

- Overall score.
- Per-dimension scores.
- Radar chart.
- Leaderboards.
- Mean and variance across repeated runs.
- Cost and duration reports.
- Live task/repetition progress, elapsed time, and a clearly labeled ETA once
  enough completed work exists to estimate it.
- Failure reason classification.
- Raw evidence and replayable traces.
- Practical recommendations for which combination is best for which kind of task.

Scores must not be fake. Each score should be backed by observable evidence such as tests, hidden tests, diffs, logs, screenshots, command traces, or structured evaluator output.

Progress is operational evidence, not a benchmark score: it must distinguish a
currently running harness, scoring/verification work, a completed attempt, and
a prerequisite failure. An ETA must be derived from completed attempt durations
and shown as unavailable until it has a real basis.

## Product Usability And Delivery

The current command-line workflow is a useful intermediate delivery path, not the
final user experience. The user should eventually be able to select or create an
empty result directory and begin a benchmark with one obvious action, without
having to understand environment variables, Python/Node dependencies, Docker,
Playwright, or harness-specific setup.

The future product must:

- Diagnose prerequisites before a paid run: local runtime versions, project
  dependencies, browser runtime, Docker/Colima availability, adapter binary and
  version, non-secret authentication readiness, writable result directory, and
  available disk space.
- Automatically perform safe, explainable repairs where practical: install
  project-owned dependencies, install the browser runtime, start a supported
  local Docker runtime, and install/update the project launcher. Operations
  requiring network access, administrator privileges, provider login, or a
  choice that can affect the user's system must ask for confirmation and show a
  plain-language next step rather than exposing a raw stack trace.
- Keep normal operation free of required environment-variable knowledge. Power
  users may retain overrides, but they must not be the primary onboarding path.
- Present clear readiness, progress, recoverability, and failure explanations;
  a failed prerequisite must not look like a failed benchmark result.
- Ultimately ship as a standalone native macOS desktop application, not a
  browser-only page. It should provide guided setup, harness readiness,
  result-folder selection, run configuration, live progress/logs, resume and
  history, and automatic opening of the completed dashboard. Terminal commands
  remain an advanced/debugging interface.

This is an intentional deferred requirement: do not claim the current
`benchmark` launcher already installs or repairs the environment merely because
it runs `doctor` and `preflight`.

## Task Coverage

The benchmark should eventually cover:

- Bug fixing.
- Feature implementation.
- Refactoring.
- Test writing.
- Frontend UI implementation.
- Backend API implementation.
- Full-stack work.
- Data processing scripts.
- CI debugging.
- Large repository understanding.
- Project generation from scratch.
- Code review.
- Long-running autonomous work.
- Visual/browser-based tasks.
- GUI and desktop tasks.

Technology coverage should eventually include:

- Python.
- C.
- JavaScript/TypeScript.
- Full-stack applications.
- Additional mainstream stacks as the project grows.

The user's personal domains must be represented over time:

- Embedded engineering: C, memory safety, protocol handling, device-like constraints, timing, low-level interfaces.
- Optics and imaging: numerical simulation, image formation, calibration, signal processing, optical data analysis.

The first version may only include seed tasks for these areas, but future iterations must keep expanding them.

## Task Sources

The system should mix:

- Custom tasks designed around the user's workflow.
- SWE-bench-style real repository issue tasks.
- Terminal-Bench-style terminal and environment tasks.
- WebArena-style web tasks.
- OSWorld-style desktop or GUI tasks.
- GitHub-derived realistic engineering tasks.

The project should support external benchmark importers over time. It should not be locked into a single public benchmark format.

## Evaluation Modes

The benchmark must support multiple budget profiles:

- `oneshot`: one attempt, measuring first-response capability.
- `bounded`: limited time or limited iterations, measuring practical efficiency.
- `open_ended`: generous limits, measuring autonomous completion ability.
- `human_like`: allows normal testing and repair loops, matching everyday coding use.
- `stress`: long-horizon tasks with larger codebases and complex objectives.

The user's default preference is open-ended reliability, but oneshot and bounded modes are still important for scientific comparison.

Each serious comparison should run at least three repetitions and report mean and variance. More repetitions should be supported.

## Fairness Rules

The benchmark should use each harness in its natural mode rather than forcing every harness into an unnatural wrapper. Fairness should come from:

- Same task specification.
- Same initial state.
- Same allowed resources.
- Same scoring rubric.
- Same repetition count.
- Same budget profile.
- Same evidence requirements.

Harness-specific adapters are allowed and necessary. They must not contain task-specific shortcuts.

## Test Integrity

By default, agents must not modify benchmark tests or scoring files. The system should detect:

- Modified tests.
- Deleted tests.
- Modified scoring scripts.
- Suspicious changes outside the task workspace.

Adding new tests may be allowed for engineering quality, but it should not replace or weaken benchmark tests.

## Network And Search

Network access can be part of the task profile. Web search ability is itself a harness capability and should eventually be measured. Some suites should run without network access; others should allow or require documentation lookup.

## Isolation

Each run should start from a clean state. Preferred long-term isolation is Docker or equivalent sandboxing. The first implementation may use temporary directories and git worktree-like copies on macOS, then add Docker later.

## Logs And Handoff

The project must maintain:

- `docs/project_journal.md`: development decisions and actions.
- `docs/handoff.md`: current state, unfinished work, and next-agent instructions.
- `runs/<run_id>/trace.jsonl`: benchmark execution trace.

The handoff document must be updated after each meaningful phase, especially when a module is incomplete or future work is implied.

## Non-Goals For Early Versions

Early versions do not need to perfectly solve every benchmark family. They must instead preserve the long-term requirements and provide a framework that can grow without rewriting the whole project.
