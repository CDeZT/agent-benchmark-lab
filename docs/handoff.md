# Handoff

This document must be updated after every meaningful phase or whenever unfinished work is left for a future agent.

## Current Phase

Phase 1 framework foundation is usable, but the benchmark is not finished. The project currently has 19 task definitions, 6 suites, 92 unittest test functions, real harness smoke support, model identity evidence, Docker evaluator v1 code, recoverable task/suite/matrix runs, and evidence-backed scoring rules that keep dimensions at 0 when evidence is absent.

Important boundary: the current task corpus is custom seed/inspired work, not an imported authoritative benchmark set. See `docs/task_provenance.md`.

## User Intent Summary

The user wants a long-term benchmark system for evaluating real coding-agent combinations, especially harness/model pairs such as Claude Code or opencode with DeepSeek, mimo, longcat, GPT, Gemini, and future models.

The benchmark must measure more than final pass/fail. It should quantify intent understanding, planning, execution, subagent or task decomposition, self-testing, visual checking, self-repair, safety, cost, speed, and stability.

The user values reliable results over low cost or short runtime. Repeated runs, mean, and variance are expected.

Embedded engineering and optics should be preserved as long-term domain requirements.

## Completed

- Created foundational documentation structure.
- Captured requirements, taxonomy, scoring model, architecture, research notes, roadmap, and journal.
- Added `.gitignore`.
- Added conversation-derived requirements so informal user ideas are preserved.
- Added adapter contract and run log schema documents.
- Built a minimal Python CLI and runner.
- Added a dummy adapter for framework validation.
- Added a generic command adapter for experimental local CLI harness integration.
- Added seed tasks for Python, C, frontend/visual, embedded-style C, and optics-style Python.
- Added the `foundation` suite to group the first seed tasks.
- Added `run-suite` CLI command.
- Added SHA-256 protected path integrity scoring.
- Added per-run `stdout.log` and `stderr.log`.
- Added suite-level `suite_summary.json` and `suite_report.md`.
- Added command-based adapter shells for `opencode` and `claude-code`.
- Added `run-matrix` for suite x adapter x model x budget-profile experiments.
- Added static HTML visual checks through `visual_checks` and `visual_verification`.
- Added run, adapter, and test duration aggregation.
- Added explicit null cost/token fields so future adapters can fill real usage data without guessing.
- Added hidden/private test support through `hidden_test_command`.
- Added `agent-benchmark validate` for task and suite definition checks.
- Added public/hidden pass status to task reports.
- Added implementation status tracking through `docs/implementation_status.md` and `status/implementation_status.json`.
- Added `agent-benchmark status` for a quick completion snapshot.
- Added `test_timeout_seconds`; timed out public/hidden tests fail safely and are recorded.
- Added `agent-benchmark audit`; it runs validation, unit tests, compileall, and a foundation smoke suite, then saves audit evidence under `runs/audit-*`.
- Added `agent-benchmark doctor` for local tool and harness environment diagnostics.
- Added command template placeholders: `{workspace}`, `{instruction_file}`, `{prompt}`, `{task_id}`, `{title}`.
- Injected `AGENT_BENCH_MODEL`, `AGENT_BENCH_BUDGET_PROFILE`, and `AGENT_BENCH_LABEL` into adapter command execution.
- Added `process_checks` and `process-planning` to provide evidence-backed planning scoring.
- Added built-in default command templates for `opencode` and `claude-code`.
- Ran real opencode and Claude Code smoke tests on `python-bugfix`; both passed public and hidden tests.
- Fixed workspace pollution from adapter instruction files.
- Added generated artifact filtering for Python cache files.
- Added `real-smoke` suite and real harness smoke documentation.
- Added optional `audit --include-real-harness` to run real opencode/Claude Code smoke checks explicitly.
- Added `docs/next_agent_prompt.md` and `agent-benchmark next-agent-prompt`.
- Verified all seed tasks with the dummy adapter for three repetitions.
- Added 11 scoring integrity tests that prove every non-zero score comes from real execution evidence.
- Fixed C tasks (`c-bugfix`, `embedded-c`): added `artifact_ignore_globs` to filter compiled binaries from changed_files.
- Fixed C tasks: added header files (`clamp.h`, `packet.h`) to `protected_paths` to prevent agent from bypassing constraints.
- Fixed `SUPPORTED_DIMENSIONS` in `process.py` to include `execution_quality` and `cost_efficiency`, matching the placeholder list in `basic.py`.
- Fixed `real-smoke.json` `capability_focus` metadata: replaced `public_hidden_tests` with `test_discipline`.
- Added `.gitignore` rules for C compilation artifacts (`*.o`, `*.so`, `*.dylib`) and coverage products.
- Added `setdefault` comment in `basic.py` clarifying that placeholders don't overwrite process_check evidence.
- Verified real opencode and claude-code on `python-bugfix` and `c-bugfix` after all fixes.
- Added `parsers/harness_output.py` to extract model name and tool calls from real harness output.
- Integrated parser into runner: `detected_model` and `tool_call_count` now in summary/run results.
- Verified opencode parser extracts `LongCat-2.0` model name and tool calls from stderr.
- Added 3 parser unit tests. Total tests now 33, all pass.
- Connected parser to scorer: `tool_use` now scores from real harness output (tool variety + count).
- Verified opencode python-bugfix → tool_use=100, total=42.0 (was 36.0).
- Added 2 tool_use integrity tests. Total tests now 35, all pass.
- 5/10 dimensions now have real evidence: task_completion, safety_boundary, visual_verification, planning, tool_use.
- Enhanced reports: detected_model, tool call counts, per-run tools column in Markdown and HTML.
- Added `python-feature` task (feature implementation: merge_sorted). Foundation suite now has 7 tasks.
- Full manual code review of all 35 source files — no bugs found.
- Added `test_file_quality` process check type for evidence-backed test_discipline scoring.
- Added `file_changed` process check type for evidence-backed execution_quality scoring.
- Created `python-test-writing` task: agent writes tests for buggy stats.py (5 demonstrable bugs).
- verify_tests.py runs agent's tests against buggy code; tests that FAIL prove they caught bugs.
- Added `test-writing` suite for meta-tasks requiring real harness.
- Added `file_changed` checks to python-bugfix and python-feature tasks.
- 6/10 dimensions now have real evidence: task_completion, safety_boundary, visual_verification, planning, tool_use, execution_quality.
- 43 unit tests pass. Full audit passes.
- Added `instruction_match` process check for `intent_understanding` scoring (checks if agent modified correct files).
- Added `self_repair` scoring from stdout/stderr log analysis (retry/fix/correct/debug patterns).
- Created `python-refactor` task: refactor data_processor.py while preserving behavior.
- Added `instruction_match` process checks to all 9 tasks.
- Fixed audit logic: `hidden_test_passed=None` no longer treated as failure.
- 8/10 dimensions now have real evidence: task_completion, safety_boundary, visual_verification, planning, tool_use, execution_quality, intent_understanding, self_repair.
- 56 unit tests pass. Full audit passes.
- Implemented `cost_efficiency` scoring from token/cost data.
- Extended opencode parser to extract token counts and cost.
- All non-zero dimensions must now be backed by saved evidence; dimensions without evidence remain 0.
- 62 unit tests pass. Full audit passes.
- Added complex engineering tasks: SWE-bench style, fullstack, C systems, optics, embedded, data pipeline.
- Added `advanced` suite for complex tasks.
- Added new process check types: code_quality, performance_check, documentation_check.
- 75 unit tests passed at that point. Later audit work added one usage aggregation test, bringing the unittest function count to 76.
- Added `docs/task_provenance.md` to make task-source claims explicit.
- Tightened `cost_efficiency`: tool-call count no longer acts as a cost proxy. Only parsed token/cost evidence can produce a non-zero cost score.
- Carried parsed `cost_usd`, `input_tokens`, and `output_tokens` into per-run and mean summary fields.
- Added validated task-corpus metadata: every manifest now declares difficulty, rationale, and provenance; `agent-benchmark catalog` makes the 3 easy / 9 medium / 4 hard / 3 expert distribution inspectable.
- Added the local 8-task `calibration` suite spanning all difficulty tiers for repeatable real-harness comparisons.
- Found task-validity issues: Flask/NumPy/SciPy/pandas tasks could not run reproducibly on this Mac. Marked those tasks `container_required`; the runner now refuses them locally and `project-generation` was removed from the default local foundation suite rather than treating dependency failures as benchmark success.
- Added `docs/corpus_strategy.md`: external imports must follow Docker isolation and preserve upstream evaluator/provenance evidence; custom embedded and optics tasks remain first-class.
- Added strict-score measurement coverage: every result now distinguishes the all-dimension strict total from verified evidence coverage and a verified-only normalized score. Do not present either number without the other.
- Added `calibrate-difficulty`, which requires real non-dummy results across at least 3 combinations and 9 runs before a task can be called a discriminative candidate.
- Applied the first live calibration result: `python-bugfix` is 100% successful across four non-dummy combinations and twelve recorded runs, so its manifest is now `smoke_only`; never use it as a differentiating leaderboard task.
- Added outcome capability scorecards to suite summaries. These aggregate software engineering, agent workflow, systems/embedded, scientific computing, web/UI, and security/reliability separately; smoke-only tasks are excluded from these comparisons.
- Added `audit-corpus`, which proves baseline/reference contrast, and made it a mandatory default `audit` check. Fixed `code-review`, `repo-understanding`, and `python-test-writing`; the current corpus result is 15 local tasks passing and 4 container-required tasks skipped.
- Added interruption-safe task and suite persistence: task manifests/checkpoints plus `resume --experiment-dir` reuse completed repetitions; suite manifests/checkpoints plus `resume-suite --suite-run-dir` reuse completed task summaries and only run missing tasks. Matrix-level resume is still pending.
- Added matrix persistence and `resume-matrix --matrix-run-dir`: each combination gets a stable summary and nested suite checkpoint, so interruption inside a combination or between combinations resumes without redoing completed work. Matrix reports now have a comparative-only ranking that excludes `smoke_only` and reports strict score, verified score, coverage, pass rate, variance, duration, and cost side by side.
- Re-audited feasibility with a full audit and a real harness smoke: both opencode and Claude Code passed the smoke-only task. Claude's structured JSON output now provides actual model identity (`mimo-v2.5-pro[1m]` in the latest local smoke), token usage, and cost. Added canonical-model to adapter-model registry support plus `verified_match`/`requested_unverified`/`mismatch` identity status so a same-model claim cannot rely on a label alone.
- Implemented Docker evaluator v1 for `container_required` tasks: exact-version Python dependencies, generated Dockerfile/image evidence, CPU/memory limits, read-write workspace mount, read-only hidden tests, and a public test helper injected into the real harness prompt. The host harness keeps its local credentials instead of putting them in the container. The evaluator does not impose a blanket no-network policy because network/tool use needs its own task-specific measurement.
- Installed the `docker` CLI and Colima without sudo. Colima VM image download timed out multiple times. OrbStack installation initiated as alternative (in progress). No daemon-backed container task has been claimed as tested; `doctor` reports this honestly.
- Added hidden tests to ci-debugging, code-review, python-refactor, python-test-writing, and repo-understanding. 16/19 tasks now have hidden tests.
- Implemented budget profile enforcement: BudgetProfile dataclass with max_attempts, max_duration_seconds, max_tool_caps across 5 user-facing profiles (oneshot/bounded/open_ended/human_like/stress) plus audit/real_smoke internal profiles. Profiles now inject instruction suffixes and env vars into adapter execution.
- Created `config/model_registry.json` with 5 canonical models + adapter-specific mappings. `scripts/run_calibration_matrix.sh` is ready for real harness matrix execution.
- Standardized all 19 task.json files to consistent formatting. Added missing process_checks and hidden_test_command to python-refactor.
- 99 unit tests pass. Full audit passes.

## In Progress

- Docker daemon activation (OrbStack downloading).
- Real harness matrix preparation (model registry + calibration script ready).

## Not Yet Implemented

- Larger real Claude Code/opencode benchmark runs beyond smoke tests.
- Docker daemon activation and a real container-task smoke run (Docker evaluator code exists).
- Docker-backed external evaluator bridges (SWE-bench Verified, Terminal-Bench).
- Visual browser automation.
- Optional LLM judge adjudication.
- Dashboard.
- Browser screenshot and pixel-based visual verification.

## Known Scoring Limitation

All non-zero scores must have saved evidence. Several dimensions are still early heuristic evidence and should not be described as final scientific measurement:

- `task_completion`: 100 when the test command passes.
- `safety_boundary`: 100 when protected paths match the baseline SHA-256 hashes.
- `visual_verification`: 100 only for tasks that declare passing `visual_checks`.
- `planning`: 100 when planning artifacts exist and pass content checks.
- `tool_use`: 100 when parsed harness output shows diverse tool calls.
- `execution_quality`: 100 when the agent's workspace file differs from baseline.
- `intent_understanding`: 100 when the agent modified the correct files.
- `self_repair`: currently heuristic; it uses stdout/stderr retry/fix/correct patterns and is not causal proof of a repair loop.
- `test_discipline`: 100 when agent-created test files have sufficient test functions and assertions.
- `cost_efficiency`: scored only from token/cost data when available; otherwise 0.

No dimension should be faked. Tool-call count belongs to `tool_use`, not `cost_efficiency`.

Protected paths are now checked with SHA-256 hashes against the baseline workspace. Missing or modified protected paths set `safety_boundary` to 0.

`python-bugfix` scores 58.0 with the dummy adapter in the current implementation because task completion, safety, execution quality, and intent-understanding evidence are present. The full `foundation` suite averages across 11 locally runnable tasks.

## Verified Commands

The following commands should pass before handoff:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v       # 92 tests
PYTHONPATH=src python3 -m agent_benchmark.cli.main list-tasks
PYTHONPATH=src python3 -m agent_benchmark.cli.main catalog
PYTHONPATH=src python3 -m agent_benchmark.cli.main calibrate-difficulty
PYTHONPATH=src python3 -m agent_benchmark.cli.main taxonomy
PYTHONPATH=src python3 -m agent_benchmark.cli.main list-suites
PYTHONPATH=src python3 -m agent_benchmark.cli.main list-adapters
PYTHONPATH=src python3 -m agent_benchmark.cli.main validate
PYTHONPATH=src python3 -m agent_benchmark.cli.main status
PYTHONPATH=src python3 -m agent_benchmark.cli.main doctor
PYTHONPATH=src python3 -m agent_benchmark.cli.main audit      # 5 checks, all pass
PYTHONPATH=src python3 -m agent_benchmark.cli.main next-agent-prompt
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-suite --suite foundation --adapter dummy --repetitions 1
PYTHONPATH=src python3 -m agent_benchmark.cli.main resume --experiment-dir runs/<experiment-id>
PYTHONPATH=src python3 -m agent_benchmark.cli.main resume-suite --suite-run-dir runs/<suite-run-id>
PYTHONPATH=src python3 -m agent_benchmark.cli.main resume-matrix --matrix-run-dir runs/<matrix-run-id>
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-matrix --suite foundation --adapters dummy --models smoke-a,smoke-b --budget-profiles oneshot,open_ended --repetitions 1
PYTHONPATH=src python3 -m compileall -q src tests
```

The local `foundation` suite has 11 tasks. Do not claim any container-required dependency task has passed locally until `doctor` reports a ready Docker daemon and a saved container run exists.

## Recommended Next Phase

1. Restore network access for Colima (or start another Docker daemon), then smoke-test the implemented Docker evaluator on project-owned Flask/NumPy tasks.
2. Create a local model registry from `config/model_registry.example.json`, then run a three-repeat real harness matrix on `calibration` (opencode vs claude-code × multiple models). Only interpret rows with verified model identity.
3. Add browser screenshot and pixel-based visual verification for `frontend-visual`.
4. Bridge to a fixed SWE-bench Verified pilot, then Terminal-Bench, preserving upstream evaluators.
5. Add more domain-specific tasks (embedded, optics, full-stack).
6. Build dashboard for historical results.

For the exact Claude Code continuation route, read `docs/claude_code_handoff.md`. It defines the comparative local-matrix gate, Docker/external-benchmark ordering, and non-negotiable evidence rules.

## Implementation Guidance

- Prefer adding framework capability over one-off task hacks.
- Keep adapters generic and harness-specific, not task-specific.
- Preserve raw evidence for every score.
- Update this file whenever a phase completes or when important unfinished work is discovered.
- Update `docs/implementation_status.md` and `status/implementation_status.json` whenever a requirement changes status.
- Update `README.md`, `docs/handoff.md`, `docs/project_journal.md`, and `docs/next_agent_prompt.md` whenever workflow or handoff rules change.
- Run `agent-benchmark audit` after meaningful feature changes.
- Commit after each verified iteration.
- Keep secrets out of the repo; use environment variables or ignored local config.
