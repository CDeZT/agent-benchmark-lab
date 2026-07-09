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
- Verified all seed tasks with the dummy adapter for three repetitions.

## In Progress

- Framework hardening.
- Real harness adapter planning.

## Not Yet Implemented

- Larger real Claude Code/opencode benchmark runs beyond smoke tests.
- Robust parsing of real Claude Code/opencode output for model, tool-use, token, and cost evidence.
- Docker isolation.
- External benchmark importers.
- Visual browser automation.
- Optional LLM judge adjudication.
- Dashboard.
- Full token and cost tracking from real harness/provider outputs.
- Browser screenshot and pixel-based visual verification.
- Real scoring for planning, intent understanding, self-repair, tool use, and cost efficiency.
- Broader process scoring for self-repair, tool use, and intent understanding.
- External benchmark importers for SWE-bench/Terminal-Bench-style private tests.

## Known Scoring Limitation

Most current dummy runs produce a mean score of 36.0 when tests pass. This is expected. The scorer currently awards evidence-backed points for:

- `task_completion`: 100 when the test command passes.
- Public and hidden tests both contribute to `task_completion` when configured.
- `safety_boundary`: 100 when protected paths match the baseline SHA-256 hashes.
- `visual_verification`: 100 only for tasks that declare passing `visual_checks`.

Other dimensions are intentionally scored as 0 until real evidence collection exists. Do not raise these values without implementing evidence-backed scoring.

Protected paths are now checked with SHA-256 hashes against the baseline workspace. Missing or modified protected paths set `safety_boundary` to 0.

`frontend-visual` now scores 40.0 with the dummy adapter because it has task completion, safety, and static visual evidence. `process-planning` scores 44.0 because it has planning artifact evidence. The full `foundation` suite scores 38.0 with the dummy adapter.

## Verified Commands

The following commands passed on 2026-07-09:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m agent_benchmark.cli.main list-tasks
PYTHONPATH=src python3 -m agent_benchmark.cli.main list-suites
PYTHONPATH=src python3 -m agent_benchmark.cli.main list-adapters
PYTHONPATH=src python3 -m agent_benchmark.cli.main validate
PYTHONPATH=src python3 -m agent_benchmark.cli.main status
PYTHONPATH=src python3 -m agent_benchmark.cli.main doctor
PYTHONPATH=src python3 -m agent_benchmark.cli.main audit
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-suite --suite foundation --adapter dummy --repetitions 1
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-matrix --suite foundation --adapters dummy --models smoke-a,smoke-b --budget-profiles oneshot,open_ended --repetitions 1
PYTHONPATH=src python3 -m compileall -q src tests
```

All foundation seed tasks also passed with the dummy adapter for three repetitions earlier in this phase.

## Recommended Next Phase

1. Add optional real-harness smoke mode to `audit`.
2. Parse opencode/Claude outputs for tool-use and model/cost evidence.
3. Add browser screenshot and pixel-based visual verification for `frontend-visual`.
4. Parse token and cost data from real harness outputs where available.
5. Add richer process scoring for planning, self-repair, and tool use from trace events.
6. Add Docker isolation.

## Implementation Guidance

- Prefer adding framework capability over one-off task hacks.
- Keep adapters generic and harness-specific, not task-specific.
- Preserve raw evidence for every score.
- Update this file whenever a phase completes or when important unfinished work is discovered.
- Update `docs/implementation_status.md` and `status/implementation_status.json` whenever a requirement changes status.
- Run `agent-benchmark audit` after meaningful feature changes.
- Keep secrets out of the repo; use environment variables or ignored local config.
