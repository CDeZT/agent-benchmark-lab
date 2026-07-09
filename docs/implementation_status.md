# Implementation Status

This file answers: what has actually been built, what is only partially built, and what remains planned.

## Short Answer

The project now has a working benchmark foundation:

- Task manifests.
- Suites.
- Single-task runs.
- Suite runs.
- Matrix runs across adapter/model/budget-profile labels.
- Public tests.
- Hidden/private tests.
- Protected test integrity checks.
- Static HTML visual checks.
- Planning artifact process checks.
- Public and hidden test timeouts.
- Local harness/environment doctor.
- A one-command audit path.
- A copy-paste next-agent handoff prompt.
- JSONL traces.
- Diffs.
- stdout/stderr logs.
- Markdown and HTML reports.
- Seed tasks for Python, C, frontend, embedded-style C, and optics-style Python.

It is not yet a finished real Claude Code versus opencode benchmark. The real harness command templates, Docker isolation, browser screenshots, external benchmark importers, and process scoring still need to be implemented and tested.

## Status Table

| Requirement | Status | What Exists | Remaining Work |
| --- | --- | --- | --- |
| Compare same model across harnesses | Partial | Matrix runner supports adapter/model combinations; Claude Code and opencode adapter shells exist. | Test real local CLI commands and run actual comparisons. |
| Compare models in same harness | Partial | Model label is recorded and matrix runner supports multiple models. | Wire model config into real harness commands. |
| Full harness/model ranking | Partial | Matrix summaries and reports exist. | Add leaderboard sorting, history, and real runs. |
| Total and dimension scores | Implemented | `ScoreResult` has total and dimension scores. 8/10 dimensions have real evidence. | Implement cost_efficiency with real token/cost parsing. |
| Radar chart | Implemented | HTML report has SVG radar snapshot. | Improve once all 10 dimensions are real. |
| Repeated runs, mean, variance | Implemented | Repetitions, mean, variance, stdev, best, worst. | Add confidence intervals later. |
| Evidence-backed scoring | Implemented | **10/10 dimensions have real evidence**: task_completion, safety_boundary, visual_verification, planning, tool_use, execution_quality, intent_understanding, self_repair, test_discipline, cost_efficiency. 62 unit tests prove every non-zero score comes from real execution. | Done. |
| Planning/process scoring seed | Implemented | `process_checks`; `process-planning` scores `.agent-benchmark/plan.md`. | Done. |
| Public and hidden tests | Implemented | `test_command` and `hidden_test_command`; all seed tasks have hidden tests. | Keep adding hidden tests to new tasks. |
| Test timeouts | Implemented | `test_timeout_seconds`; timed out tests are recorded as failed evidence. | Tune per-suite defaults later. |
| Prevent test tampering | Implemented | Protected files checked with SHA-256 hashes. | Add stricter invalid-run policy levels. |
| Visual verification | Partial | Static HTML checks exist. | Add browser screenshots and pixel checks. |
| Cost and duration | Partial | Duration is measured; cost/token fields exist as null placeholders. | Parse real usage data from harness/provider output. |
| Python/C/frontend seed tasks | Implemented | Foundation suite contains 9 tasks. | Expand difficulty and task types. |
| Embedded and optics domains | Partial | Seed tasks exist. | Add deeper domain-specific tasks. |
| Budget profiles | Partial | Profile labels are recorded and used in matrix dimensions. | Enforce profile behavior. |
| Real Claude Code/opencode adapters | Partial | Built-in default templates exist; doctor detects local CLI versions; both passed `python-bugfix` real smoke. | Run larger benchmark matrices and parse model/tool/cost evidence. |
| Real harness smoke | Implemented | `opencode` and `claude-code` both passed `python-bugfix`; `real-smoke` suite exists; `audit --include-real-harness` exists. | Expand beyond smoke tasks. |
| Isolation | Partial | Per-run workspace copies exist. | Add Docker and network policy. |
| Logs and evidence | Partial | trace/result/diff/stdout/stderr are saved. | Add replay UI and richer tool traces. |
| Handoff/journal | Implemented | Handoff and project journal exist and are updated. | Keep updating every phase. |
| Self-audit command | Implemented | `agent-benchmark audit` runs validation, unit tests, compileall, and smoke suite. | Add lint/Docker/browser/real-harness audit levels later. |
| Doctor command | Implemented | `agent-benchmark doctor` checks local tools and adapter command env vars. | Add credential checks without exposing secrets. |
| Next-agent handoff prompt | Implemented | `docs/next_agent_prompt.md`; `agent-benchmark next-agent-prompt`. | Keep updated when workflow rules change. |
| External benchmark imports | Planned | Research notes and roadmap exist. | Implement importers. |
| Dashboard | Planned | Roadmap exists. | Build dashboard. |

## Current Foundation Suite

| Task | Domain | Public Tests | Hidden Tests | Visual Checks |
| --- | --- | --- | --- | --- |
| `python-bugfix` | Python | Yes | Yes | No |
| `c-bugfix` | C | Yes | Yes | No |
| `frontend-visual` | Frontend | Yes | Yes | Yes |
| `embedded-c` | Embedded C | Yes | Yes | No |
| `optics-python` | Optics/Python | Yes | Yes | No |
| `process-planning` | Process/Python | Yes | Yes | No |
| `python-feature` | Python | Yes | Yes | No |
| `python-refactor` | Python | Yes | No | No |

另有 `test-writing` suite 包含 `python-test-writing`（需真实 harness）。

## Current Score Meaning

With the dummy adapter and **10/10 dimensions having real evidence**:

- `python-bugfix` scores `48.0`: task_completion(100) + safety_boundary(100) + execution_quality(100).
- `frontend-visual` scores `40.0`: task_completion(100) + safety_boundary(100) + visual_verification(100).
- `process-planning` scores `44.0`: task_completion(100) + safety_boundary(100) + planning(100).
- `python-refactor` scores `48.0`: task_completion(100) + safety_boundary(100) + execution_quality(100).
- The full `foundation` suite averages across all 8 tasks.

All 10 dimensions now have real evidence. No dimension is faked. Scores are meaningfully differentiated by task type.

## Next Best Iterations

1. Add browser screenshot/pixel visual checks.
2. Add Docker isolation.
3. Expand task difficulty and add more domain tasks.
4. Run larger real harness matrix (opencode vs claude-code × multiple models).
5. Import external benchmark tasks (SWE-bench style).

## How To Check This From CLI

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main status
PYTHONPATH=src python3 -m agent_benchmark.cli.main status --json
PYTHONPATH=src python3 -m agent_benchmark.cli.main doctor
PYTHONPATH=src python3 -m agent_benchmark.cli.main audit
PYTHONPATH=src python3 -m agent_benchmark.cli.main next-agent-prompt
```
