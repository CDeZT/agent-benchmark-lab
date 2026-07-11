# Implementation Status

This file answers: what has actually been built, what is only partially built, and what remains planned.

## Short Answer

The project now has a usable early benchmark framework:

- Task manifests.
- Suites (foundation: 11 local tasks, calibration: 8 tasks, advanced: 3 tasks, plus a hard-to-easy selection ladder).
- Single-task runs.
- Suite runs.
- Matrix runs across adapter/model/budget-profile labels, including a first-class current-CLI-default mode.
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
- 125 unittest test functions, all expected to pass in the current tree.

It is not yet a finished real Claude Code versus opencode benchmark. Docker is now available through Colima, browser screenshots/pixel evidence work for local static pages, and a project-owned container task has run; external benchmark evaluator bridges and a multi-repeat real matrix with sufficient evidence remain unfinished. Model choices behind both CLIs are dynamic: the normal matrix compares their current defaults, while explicit same-model experiments remain a separate verified mode.
The current task corpus is custom seed/inspired work, not an imported authoritative benchmark set; see `docs/task_provenance.md`.

## Status Table

| Requirement | Status | What Exists | Remaining Work |
| --- | --- | --- | --- |
| Compare same model across harnesses | Partial | Matrix runner supports canonical model ids plus adapter-specific invocation ids through a model registry; reports expose requested/detected model identity status. | Run actual three-repeat comparisons where every comparable task reports `verified_match`. |
| Compare current CLI defaults | Implemented | `--models unspecified` is a first-class `cli_default_configurations` matrix: each CLI keeps its current configured model and reports any observed identity. | Run repeated real matrices after configuration changes and add historical comparison. |
| Compare models in same harness | Partial | Matrix runner supports multiple canonical models, model registry mappings, and identity evidence. | Create an explicit mapping only when the CLI can select the requested model, then run real comparisons. |
| Full harness/model ranking | Partial | Matrix reports separate raw suite aggregation from comparative-only ranking. Ranking uses task-level dimensions evidenced by every repetition in every combination; strict score remains diagnostic, and default-configuration versus explicit same-model evidence is visible. | Run a real three-repeat matrix and add historical cross-matrix comparison. |
| Total and dimension scores | Partial | `ScoreResult` has strict weighted total, per-dimension scores, verified evidence coverage, and verified-only normalized score. | Browser/subagent/causal self-repair evidence is still incomplete. |
| Radar chart | Implemented | HTML report has SVG radar snapshot. | Improve once all 10 dimensions are real. |
| Repeated runs, mean, variance | Implemented | Repetitions, mean, variance, stdev, best/worst, and task-level two-sided 95% Student-t confidence intervals for score, verified score, duration, and available cost. | Add paired significance tests once larger matched matrices exist. |
| Interrupted-run resume | Implemented | Task, suite, and matrix layers use manifests/checkpoints plus task-contract fingerprints; resume reuses saved work only when the current task content exactly matches the saved contract. | Add an optional historical recovery browser. |
| Evidence-backed scoring | Partial | Every non-zero score must come from saved execution evidence. Reports distinguish verified, heuristic, and unavailable dimensions; `cost_efficiency` uses parsed token/cost only; model identity distinguishes verified matches, explicit unverified/mismatched requests, and observed CLI defaults. Historical summaries with a missing/mismatched task fingerprint are excluded from selection statistics. 125 unittest tests cover framework and scoring behavior. | Replace weak trace heuristics and add direct subagent evidence. |
| Planning/process scoring seed | Implemented | `process_checks`; `process-planning` scores `.agent-benchmark/plan.md`. | Done. |
| Public and hidden tests | Partial | `test_command` and `hidden_test_command`; 16 of 19 tasks currently have hidden tests. | Add independent hidden tests to the remaining3 tasks. |
| Test timeouts | Implemented | `test_timeout_seconds`; timed out tests are recorded as failed evidence. | Tune per-suite defaults later. |
| Prevent test tampering | Implemented | Protected files checked with SHA-256 hashes. | Add stricter invalid-run policy levels. |
| Visual verification | Partial | Static HTML checks plus Playwright Chromium screenshots, rendered-selector visibility, and pixel statistics are saved per run. | Add server-backed pages, interactions, reference-image diffs, and mobile viewports. |
| Cost and duration | Partial | Duration is measured; parsed token/cost fields are carried into run summaries when harness output exposes them. | Improve provider-specific usage parsing and reporting. |
| Task corpus and difficulty ladder | Implemented | 19 manifests carry validated difficulty/provenance fields; easy=3, medium=9, hard=4, expert=3; the 8-task local `calibration` suite spans all four tiers. | Add task-quality negative controls and more domain tasks. |
| Selective screening gate | Implemented | `selection-ladder` runs expert to easy; `screening-report` admits only empirically discriminative, corpus-audited local tasks and labels smoke, under-sampled, too-easy/hard, and container-gated tasks separately. | Build enough real evidence to populate the first non-empty selection cohort. |
| Empirical difficulty calibration | Partial | `calibrate-difficulty` groups by actual observed model, excludes unidentified history, and refuses a discriminability conclusion without 3 combinations, 3 runs per combination, and 9 eligible runs. `python-bugfix` has been identified as too easy and marked smoke-only. | Run real matrices, then revise tasks that are too easy, too hard, or non-discriminative. |
| Outcome capability scorecard | Implemented | Suite reports aggregate separate software engineering, agent workflow, systems/embedded, scientific, web/UI, and security/reliability axes; all non-comparative tasks are excluded. | Add authoritative external tracks to each axis. |
| Embedded and optics domains | Partial | Seed tasks exist. | Add deeper domain-specific tasks. |
| Budget profiles | Partial | Profile labels are recorded and used in matrix dimensions. | Enforce profile behavior. |
| Real Claude Code/opencode adapters | Partial | Built-in default templates exist; doctor detects local CLI versions; both passed `python-bugfix` real smoke. Claude JSON output now yields actual `mimo-v2.5-pro[1m]`, tokens, and cost on this machine. | Run larger repeated current-default matrices; add an explicit registry only for a verified same-model experiment. |
| Real harness smoke | Implemented | `opencode` and `claude-code` both passed `python-bugfix`; `real-smoke` suite exists; `audit --include-real-harness` exists. | Expand beyond smoke tasks. |
| Isolation | Partial | Per-run workspace copies plus Docker evaluator v1: pinned dependency packages, image ID/build evidence, CPU/memory limits, and read-only hidden-test mount. Colima Docker is ready and `python-fullstack` has project-owned container evidence. Network behavior is intentionally task-specific rather than globally disabled. | Pin base-image digests before authoritative runs and add cache cleanup policy. |
| Logs and evidence | Partial | trace/result/diff/stdout/stderr are saved. | Add replay UI and richer tool traces. |
| Handoff/journal | Implemented | Handoff and project journal exist and are updated. | Keep updating every phase. |
| Self-audit command | Implemented | `agent-benchmark audit` runs validation, unit tests, compileall, and smoke suite. | Add lint/Docker/browser/real-harness audit levels later. |
| Doctor command | Implemented | `agent-benchmark doctor` checks local tools, Docker daemon readiness, and adapter command env vars. | Add credential checks without exposing secrets. |
| Next-agent handoff prompt | Implemented | `docs/next_agent_prompt.md`; `agent-benchmark next-agent-prompt`. | Keep updated when workflow rules change. |
| External benchmark imports | Planned | Source-aware manifests, catalog command, approved SWE-bench Verified/Terminal-Bench Core source registry, and import plan now exist. | Implement official-evaluator bridges for SWE-bench Verified and Terminal-Bench. |
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

另有 `test-writing` suite 包含 `python-test-writing`（需真实 harness）。
另有 `advanced` suite 包含 `python-swebench-style`、`c-systems-programming`、`python-fullstack`。

## Current Score Meaning

With the dummy adapter and current evidence-backed scoring:

- `python-bugfix` scores `58.0`: task_completion(100) + safety_boundary(100) + execution_quality(100) + intent_understanding(100).
- `frontend-visual` scores `50.0`: task_completion(100) + safety_boundary(100) + visual_verification(100) + intent_understanding(100).
- `process-planning` scores `54.0`: task_completion(100) + safety_boundary(100) + planning(100) + intent_understanding(100).
- `python-refactor` currently scores `36.0` with the dummy adapter because the dummy solution preserves behavior but does not satisfy the configured process checks.
- The full `foundation` suite averages across 11 locally runnable tasks. Container-required tasks are refused by the local runner until deterministic dependency provisioning exists.

No dimension should be assigned a non-zero score without execution evidence. Some process dimensions are still heuristic and should be treated as early evidence, not final scientific measurement.

## Next Best Iterations

1. Repair local model-registry mappings, then run `preflight-matrix` before any real harness matrix.
2. Run a three-repeat real harness matrix on the `calibration` suite (opencode vs claude-code × multiple models) and interpret only `verified_match` rows.
3. Import a stratified SWE-bench Verified pilot, then a Terminal-Bench pilot.
5. Build dashboard for historical results.

## How To Check This From CLI

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main status
PYTHONPATH=src python3 -m agent_benchmark.cli.main catalog
PYTHONPATH=src python3 -m agent_benchmark.cli.main status --json
PYTHONPATH=src python3 -m agent_benchmark.cli.main doctor
PYTHONPATH=src python3 -m agent_benchmark.cli.main audit
PYTHONPATH=src python3 -m agent_benchmark.cli.main next-agent-prompt
```
