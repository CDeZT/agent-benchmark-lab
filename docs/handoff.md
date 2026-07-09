# Handoff

This document must be updated after every meaningful phase or whenever unfinished work is left for a future agent.

## Current Phase

Phase 0 foundation is complete. The project has entered early Phase 1: minimal working benchmark.

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
- Implemented `cost_efficiency` scoring from token/cost data or tool call efficiency proxy.
- Extended opencode parser to extract token counts and cost.
- **10/10 dimensions now have real evidence**.
- 62 unit tests pass. Full audit passes.

## In Progress

- Framework hardening.
- Real harness adapter planning.

## Not Yet Implemented

- Larger real Claude Code/opencode benchmark runs beyond smoke tests.
- Docker isolation.
- External benchmark importers.
- Visual browser automation.
- Optional LLM judge adjudication.
- Dashboard.
- Browser screenshot and pixel-based visual verification.
- External benchmark importers for SWE-bench/Terminal-Bench-style private tests.

## Known Scoring Limitation

All 10 dimensions now have real evidence-backed scoring:

- `task_completion`: 100 when the test command passes.
- `safety_boundary`: 100 when protected paths match the baseline SHA-256 hashes.
- `visual_verification`: 100 only for tasks that declare passing `visual_checks`.
- `planning`: 100 when planning artifacts exist and pass content checks.
- `tool_use`: 100 when parsed harness output shows diverse tool calls.
- `execution_quality`: 100 when the agent's workspace file differs from baseline.
- `intent_understanding`: 100 when the agent modified the correct files.
- `self_repair`: 100 when stdout/stderr shows retry/fix/correct patterns (3+ indicators).
- `test_discipline`: 100 when agent-created test files have sufficient test functions and assertions.
- `cost_efficiency`: scored from token/cost data (if available) or tool call efficiency proxy.

No dimension is faked. All scores come from real execution evidence.

Protected paths are now checked with SHA-256 hashes against the baseline workspace. Missing or modified protected paths set `safety_boundary` to 0.

`python-bugfix` scores 48.0 with the dummy adapter (task_completion + safety + execution_quality). `frontend-visual` scores 40.0 (task_completion + safety + visual). `process-planning` scores 44.0 (task_completion + safety + planning). The full `foundation` suite averages across all 8 tasks.

## Verified Commands

The following commands passed on 2026-07-09:

```bash
PYTHONPATH=src python3 -m pytest tests/ -q                    # 43 tests, all pass
PYTHONPATH=src python3 -m agent_benchmark.cli.main list-tasks
PYTHONPATH=src python3 -m agent_benchmark.cli.main list-suites
PYTHONPATH=src python3 -m agent_benchmark.cli.main list-adapters
PYTHONPATH=src python3 -m agent_benchmark.cli.main validate
PYTHONPATH=src python3 -m agent_benchmark.cli.main status
PYTHONPATH=src python3 -m agent_benchmark.cli.main doctor
PYTHONPATH=src python3 -m agent_benchmark.cli.main audit      # 4 checks, all pass
PYTHONPATH=src python3 -m agent_benchmark.cli.main next-agent-prompt
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-suite --suite foundation --adapter dummy --repetitions 1
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-matrix --suite foundation --adapters dummy --models smoke-a,smoke-b --budget-profiles oneshot,open_ended --repetitions 1
PYTHONPATH=src python3 -m compileall -q src tests
```

All foundation seed tasks also passed with the dummy adapter for three repetitions earlier in this phase.

## Recommended Next Phase

1. Add a larger real harness matrix suite beyond `real-smoke`.
2. Add browser screenshot and pixel-based visual verification for `frontend-visual`.
3. Add Docker isolation.
4. Import external benchmark tasks (SWE-bench style).
5. Add more domain-specific tasks (embedded, optics, full-stack).

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
