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

The project exists because public model leaderboards often do not answer the user's actual question: which real local tool and model combination is better for their own work.

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
- Failure reason classification.
- Raw evidence and replayable traces.
- Practical recommendations for which combination is best for which kind of task.

Scores must not be fake. Each score should be backed by observable evidence such as tests, hidden tests, diffs, logs, screenshots, command traces, or structured evaluator output.

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
