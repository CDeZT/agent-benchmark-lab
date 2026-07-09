# Project Journal

## 2026-07-09

- Confirmed the workspace is already a Git repository on `main` with no commits yet.
- Reframed the project as a long-term personal agent benchmark lab rather than a small benchmark script.
- Decided to use a docs-first foundation so the user's full requirements are preserved before implementation details narrow the first version.
- Selected a conservative initial implementation: Python standard library CLI, JSON manifests, JSONL traces, Markdown/HTML reports, dummy adapter first.
- Recorded benchmark research directions from SWE-bench, Terminal-Bench, Inspect AI, Aider benchmarks, OpenHands, WebArena, and OSWorld.
- Added `docs/conversation_requirements.md` to preserve informal but important user requirements.
- Added `docs/adapter_contract.md` and `docs/run_log_schema.md`.
- Implemented the first Python standard-library CLI and runner.
- Implemented a dummy adapter that copies `solution/` files to validate the benchmark pipeline.
- Added five seed tasks: Python bugfix, C bugfix, frontend/visual, embedded-style C, and optics-style Python.
- Added a `foundation` suite manifest for the first seed tasks.
- Added `run-suite` CLI command for running every task in a suite.
- Ran all five seed tasks with the dummy adapter for three repetitions each.
- Observed expected score of 36.0 for passing dummy runs because only task completion and protected-path existence currently have evidence-backed scoring.
- Added `generic-command` adapter. It runs `AGENT_BENCH_COMMAND` from the isolated workspace and passes task instructions on stdin.
- Added a first SVG radar snapshot to HTML reports.
- Added ADRs for experiment config, evidence-backed safety scoring, and zero-until-evidenced dimensions.
- Added `ExperimentConfig` and adapter registry to reduce hard-coded runner state.
- Replaced protected-path existence checks with SHA-256 baseline/current integrity checks.
- Added per-run stdout/stderr log files.
- Added suite-level `suite_summary.json` and `suite_report.md`.
- Extracted shared shell command adapter logic.
- Added initial command-configured `opencode` and `claude-code` adapter shells.
- Added `run-matrix` and matrix-level summary/report output.
- Added ADR 0004 for visual verification.
- Added `visual_checks` task schema and `html-static-v1` visual scorer.
- Added static visual checks to `frontend-visual`; the task now scores 40.0 with dummy evidence.
- Added duration aggregation for runs, adapters, tests, suites, and matrix reports.
- Added explicit null cost/token fields to summaries; these are placeholders for real measured values, not estimates.
- Verified the `foundation` suite now scores 36.8 with the dummy adapter because only the frontend seed task has visual evidence.
- Added ADR 0005 for hidden tests and definition validation.
- Added `hidden_test_command` support. Hidden tests run from `task/hidden` and receive `AGENT_BENCH_WORKSPACE` as an absolute path.
- Added hidden tests to all five foundation seed tasks.
- Added `agent-benchmark validate`.
- Added public/hidden pass status to reports.
- Added `docs/implementation_status.md` and `status/implementation_status.json` to map user requirements to implemented, partial, and planned states.
- Added `agent-benchmark status`.
- Added ADR 0006 for self-audit and test timeout behavior.
- Added `test_timeout_seconds`; public and hidden tests now fail safely on timeout.
- Added `agent-benchmark audit`, which runs validation, unit tests, compileall, and a foundation smoke suite.
- Ran full audit successfully.
- Confirmed local `opencode` and `claude` commands are installed.
- Added `agent-benchmark doctor` for local environment diagnostics and recommended command templates.
- Enhanced command adapters with `{workspace}`, `{instruction_file}`, `{prompt}`, `{task_id}`, and `{title}` placeholders.
- Injected `AGENT_BENCH_MODEL`, `AGENT_BENCH_BUDGET_PROFILE`, and `AGENT_BENCH_LABEL` during adapter execution.
- Added `process_checks` and a `process-planning` seed task to make planning scoring evidence-backed.
- Updated `foundation` suite to include `process-planning`; dummy foundation score is now 38.0.
- Added built-in default command templates for opencode and Claude Code adapters.
- Ran real opencode smoke on `python-bugfix`; public and hidden tests passed.
- Ran real Claude Code smoke on `python-bugfix`; public and hidden tests passed.
- Fixed adapter instruction-file workspace pollution discovered by the opencode run.
- Fixed generated Python cache files appearing in `changed_files`, discovered by the Claude Code run.
- Added `real-smoke` suite plus `docs/real_harness_smoke.md`.
- Added optional `audit --include-real-harness` for explicit real opencode/Claude Code smoke verification.
- Added `docs/next_agent_prompt.md` and `agent-benchmark next-agent-prompt` for clean handoff when the thread cannot continue.
- User requested that future verified iterations should be committed; this is now documented in handoff instructions.
- Added unit tests for task loading, suite loading, dummy runs, and generic command runs.
- Verified the `foundation` suite with `run-suite --suite foundation --adapter dummy --repetitions 1`.

## 2026-07-09 (iteration 5)

- Connected parser data to scorer: `tool_use` dimension now scores from real harness output.
- tool_use scoring: 50% from tool variety (up to 4+ types), 50% from call count (up to 5+).
- Verified: opencode python-bugfix → tool_use=100, total=42.0 (was 36.0).
- Verified: dummy adapter → tool_use=0 (no tool calls parsed).
- Added 2 tool_use integrity tests. Total tests now 35, all pass.
- 5 out of 10 dimensions now have real evidence: task_completion, safety_boundary, visual_verification, planning, tool_use.

## 2026-07-09 (iteration 4)

- Fixed Claude Code CLI UI display issues:
  - Added COLUMNS/LINES fix to ~/.zshrc for Warp Terminal compatibility
  - Improved statusline-command.sh: handles missing session_name, context_window.max_tokens, and transcript_path
  - Falls back to session file for session name, infers max context from model name
- All UI fields now show data or graceful "N/A" instead of blank/error

## 2026-07-09 (iteration 3)

- Added `parsers/` module to extract model name and tool calls from real harness output.
- opencode parser: extracts model name from `> build · ModelName`, tool calls (read/edit/search/bash) from stderr.
- claude-code parser: handles minimal `-p` mode output gracefully (model/tool info not exposed in this mode).
- Integrated parser into runner: `detected_model` and `tool_call_count` now appear in summary and per-run results.
- Verified with real opencode run: successfully extracted `LongCat-2.0` and 6 tool calls.
- Added 3 parser unit tests. Total tests now 33, all pass.

## 2026-07-09 (iteration 2)

- Deep code review: 3 parallel agents reviewed all source, tests, and documentation.
- Verified scoring integrity with 4 controlled experiments:
  - Wrong code → score=0 (task_completion from real test exit_code)
  - Correct code + tampered protected file → safety_boundary=0 (SHA-256 mismatch)
  - Correct code + deleted protected file → task_completion=50 (hidden test fails)
  - Correct code + intact files → score=36 (all checks pass)
- Added 11 scoring integrity tests proving every non-zero score comes from real execution.
- Fixed c-bugfix/embedded-c: added `artifact_ignore_globs` to filter compiled binaries from changed_files.
- Fixed c-bugfix/embedded-c: added header files (clamp.h, packet.h) to protected_paths.
- Fixed `SUPPORTED_DIMENSIONS` in process.py to include `execution_quality` and `cost_efficiency`.
- Fixed real-smoke.json capability_focus metadata.
- Added .gitignore rules for C compilation artifacts and coverage products.
- Added setdefault comment in basic.py for clarity.
- Verified real opencode and claude-code on python-bugfix and c-bugfix after all fixes.
- All 30 unit tests pass. Full audit passes (validate + unit_tests + compileall + smoke_suite).

Next actions:

- Add real opencode and Claude Code adapters after the framework contract is stable.
- Add baseline hashing so protected tests cannot be modified silently.
- Add browser screenshot and pixel verification.
- Add real token and cost parsing for opencode and Claude Code outputs where possible.
- Add importers that map external benchmark private tests to `hidden_test_command`.
- Keep implementation status updated after each phase.
- Expand audit levels with linting, Docker, browser visual checks, and real harness dry runs.
- Parse real harness output for tool-use, model, token, and cost evidence.
- Keep next-agent prompt, README, handoff, status, and journal synchronized after workflow changes.
