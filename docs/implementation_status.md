# Implementation Status

This file answers: what has actually been built, what is only partially built, and what remains planned.

## Short Answer

The project now has a fully functional benchmark framework:

- Task manifests.
- Suites (foundation: 12 tasks, advanced: 3 tasks).
- Single-task runs.
- Suite runs.
- Matrix runs across adapter/model/budget-profile labels.
- Public tests.
- Hidden/private tests.
- Protected test integrity checks (SHA-256).
- Static HTML visual checks.
- Planning artifact process checks.
- Public and hidden test timeouts.
- Local harness/environment doctor.
- A one-command audit path.
- A copy-paste next-agent handoff prompt.
- JSONL traces.
- Diffs.
- stdout/stderr logs.
- Markdown and HTML reports (with radar chart).
- 19 task definitions covering many major capability areas.
- Evidence-backed scoring with explicit zero scores when evidence is absent.
- 76 unittest test functions, all expected to pass in the current tree.

It is not yet a finished real Claude Code versus opencode benchmark. Docker isolation, browser screenshots, and external benchmark importers still need to be implemented and tested.
The current task corpus is custom seed/inspired work, not an imported authoritative benchmark set; see `docs/task_provenance.md`.

## Status Table

| Requirement | Status | What Exists | Remaining Work |
| --- | --- | --- | --- |
| Compare same model across harnesses | Partial | Matrix runner supports adapter/model combinations; Claude Code and opencode adapter shells exist. | Test real local CLI commands and run actual comparisons. |
| Compare models in same harness | Partial | Model label is recorded and matrix runner supports multiple models. | Wire model config into real harness commands. |
| Full harness/model ranking | Partial | Matrix summaries and reports exist. | Add leaderboard sorting, history, and real runs. |
| Total and dimension scores | Implemented | `ScoreResult` has total and dimension scores. Dimensions without evidence stay at 0. | Keep refining weak heuristic dimensions. |
| Radar chart | Implemented | HTML report has SVG radar snapshot. | Improve once all 10 dimensions are real. |
| Repeated runs, mean, variance | Implemented | Repetitions, mean, variance, stdev, best, worst. | Add confidence intervals later. |
| Evidence-backed scoring | Implemented | Every non-zero score must come from saved execution evidence. `cost_efficiency` now scores only from parsed token/cost usage, not tool-call proxies. 76 unittest tests cover scoring integrity. | Keep strengthening heuristic dimensions and provenance checks. |
| Planning/process scoring seed | Implemented | `process_checks`; `process-planning` scores `.agent-benchmark/plan.md`. | Done. |
| Public and hidden tests | Implemented | `test_command` and `hidden_test_command`; all seed tasks have hidden tests. | Keep adding hidden tests to new tasks. |
| Test timeouts | Implemented | `test_timeout_seconds`; timed out tests are recorded as failed evidence. | Tune per-suite defaults later. |
| Prevent test tampering | Implemented | Protected files checked with SHA-256 hashes. | Add stricter invalid-run policy levels. |
| Visual verification | Partial | Static HTML checks exist. | Add browser screenshots and pixel checks. |
| Cost and duration | Partial | Duration is measured; parsed token/cost fields are carried into run summaries when harness output exposes them. | Improve provider-specific usage parsing and reporting. |
| Python/C/frontend seed tasks | Implemented | Repository contains 19 task definitions; foundation suite contains 12 tasks. | Expand difficulty and task types. |
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
| External benchmark imports | Planned | Research notes, roadmap, and task provenance document exist. | Implement importers and annotate task provenance metadata. |
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
| `ci-debugging` | CI/Python | Yes | No | No |
| `code-review` | Security/Python | Yes | No | No |
| `repo-understanding` | Python | Yes | No | No |
| `project-generation` | Python/Web | Yes | No | No |

另有 `test-writing` suite 包含 `python-test-writing`（需真实 harness）。
另有 `advanced` suite 包含 `python-swebench-style`、`c-systems-programming`、`python-fullstack`。

## Current Score Meaning

With the dummy adapter and current evidence-backed scoring:

- `python-bugfix` scores `58.0`: task_completion(100) + safety_boundary(100) + execution_quality(100) + intent_understanding(100).
- `frontend-visual` scores `50.0`: task_completion(100) + safety_boundary(100) + visual_verification(100) + intent_understanding(100).
- `process-planning` scores `54.0`: task_completion(100) + safety_boundary(100) + planning(100) + intent_understanding(100).
- `python-refactor` currently scores `36.0` with the dummy adapter because the dummy solution preserves behavior but does not satisfy the configured process checks.
- The full `foundation` suite averages across 12 tasks.

No dimension should be assigned a non-zero score without execution evidence. Some process dimensions are still heuristic and should be treated as early evidence, not final scientific measurement.

## Next Best Iterations

1. Run real harness matrix (opencode vs claude-code × multiple models).
2. Add browser screenshot/pixel visual checks.
3. Add Docker isolation.
4. Import external benchmark tasks (SWE-bench, Terminal-Bench).
5. Build dashboard for historical results.

## How To Check This From CLI

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main status
PYTHONPATH=src python3 -m agent_benchmark.cli.main status --json
PYTHONPATH=src python3 -m agent_benchmark.cli.main doctor
PYTHONPATH=src python3 -m agent_benchmark.cli.main audit
PYTHONPATH=src python3 -m agent_benchmark.cli.main next-agent-prompt
```
