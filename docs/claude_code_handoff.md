# Claude Code Continuation Guide

Read this after `docs/handoff.md`, `docs/corpus_strategy.md`, and `docs/next_agent_prompt.md`. This is the concrete route to a usable V1, not a request for another broad rewrite.

## Current Gate

The local corpus is now usable for preliminary comparisons: `audit-corpus` reports 15 local tasks with a failing baseline and passing reference solution; four dependency-heavy tasks are correctly `container_required`. `python-bugfix` is `smoke_only`, so it checks adapter wiring but must not influence rankings. Docker evaluator v1 is implemented; it needs a ready daemon before those four tasks can be exercised.

Before every change run:

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main audit
PYTHONPATH=src python3 -m agent_benchmark.cli.main audit-corpus
PYTHONPATH=src python3 -m agent_benchmark.cli.main calibrate-difficulty
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Do not bypass a failing corpus audit by changing a task role. Repair the baseline/reference/test contrast or keep the task out of comparative suites.

## Interruption and Resume Protocol

Every task experiment now writes `experiment_manifest.json` before the first harness call and updates `checkpoint.json` after every completed repetition. If an agent, network, or provider call is interrupted:

1. Do not delete the experiment directory under `runs/`.
2. Inspect `checkpoint.json` for completed and remaining repetitions.
3. Resume with `PYTHONPATH=src python3 -m agent_benchmark.cli.main resume --experiment-dir runs/<experiment-id>`.
4. The resume path reuses completed `result.json` files and runs only missing repetitions, then rebuilds summary and reports.

Commit meaningful code/documentation phases before starting expensive real harness matrices. `runs/` remains untracked evidence, so the manifest/checkpoint path must be included in any human handoff message if the work stops mid-matrix.

## Next Deliverable: Comparable Local Matrix

1. Run `doctor`; do not assume Docker exists. The current machine had no `docker` command in the last audit.
2. Select only `benchmark_role=comparative_candidate` tasks. Do not use `smoke_only` in rankings.
3. Run the same model through `opencode` and `claude-code` with the same task suite and budget profile. Use at least three repetitions per task.
4. Preserve raw run directories, model labels, detected model metadata, traces, diffs, test results, duration, and real token/cost output when available.
5. Run `calibrate-difficulty` after the matrix. Tasks with insufficient evidence, `too_easy`, or `too_hard` must be reported separately, not averaged into a public winner claim.
6. Report strict score, verified normalized score, verified coverage, per-axis scorecards, task success rate, variance, duration, and cost separately. Never substitute a tool-call count for cost.

This produces a preliminary personal answer to the harness question. It is not an authoritative public leaderboard yet.

## V1 Infrastructure: Docker Then External Benchmarks

Activate and validate the Docker runner before attempting external benchmarks. The four `container_required` tasks now use it automatically once `docker` is ready.

- Task environment contract: generated Dockerfile, exact Python dependency versions, image ID, timeout, no-network verifier policy, CPU/memory limits, and mounted workspace boundaries.
- Runner evidence: image tag/ID, Dockerfile, build log, command, exit status, stdout/stderr, and test output saved per repetition.
- The harness CLI remains on the host so it can use the user's existing login/provider configuration; its prompt includes a prebuilt public container-test helper. Do not mount credentials into images.
- Before a comparative claim, run a real container task and preserve its run directory. The current machine installed `docker` and Colima, but Colima VM image download timed out twice on 2026-07-10; `doctor` must be green before this gate is considered passed.
- Keep hidden tests outside the agent workspace and keep task fixtures read-only where appropriate.
- First validate Docker with project-owned Flask/NumPy tasks. Only then import a fixed, stratified SWE-bench Verified pilot; preserve upstream instance id, base commit, source version, license note, evaluator output, and upstream Fail-to-Pass/Pass-to-Pass result.
- Add Terminal-Bench after the SWE-bench bridge. Keep it as a separate terminal-agent axis rather than mixing its result into software-engineering resolution rate.

## Scoring Rules

- Strict total is intentionally conservative: unavailable dimensions remain zero.
- Always display strict total together with verified coverage and verified normalized score.
- `self_repair` and current `tool_use` trace signals are heuristic, not causal evidence.
- Browser screenshots/pixel checks and direct subagent/delegation evidence remain unfinished; leave them partial until an executable evaluator exists.
- Any subjective judge requires two independent judgments, saved rubrics/evidence, and a third adjudicator for material disagreement.

## Completion Checklist For Each Iteration

1. Add or update deterministic tests for new behavior.
2. Run `audit`, `audit-corpus`, relevant dummy smoke, and targeted real runs only when authorized.
3. Update README, implementation status, handoff, journal, and this guide when the route changes.
4. Check `git diff --check`, commit only related files, and leave the worktree clean.
