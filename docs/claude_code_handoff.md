# Claude Code Continuation Guide

Read this after `docs/handoff.md`, `docs/corpus_strategy.md`, and `docs/next_agent_prompt.md`. This is the concrete route to a usable V1, not a request for another broad rewrite.

## Current Gate

The local corpus is now usable for preliminary comparisons: `audit-corpus` reports 15 local tasks with a failing baseline and passing reference solution; four dependency-heavy tasks are correctly `container_required`. `python-bugfix` is `smoke_only`, so it checks adapter wiring but must not influence rankings.

Before every change run:

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main audit
PYTHONPATH=src python3 -m agent_benchmark.cli.main audit-corpus
PYTHONPATH=src python3 -m agent_benchmark.cli.main calibrate-difficulty
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Do not bypass a failing corpus audit by changing a task role. Repair the baseline/reference/test contrast or keep the task out of comparative suites.

## Next Deliverable: Comparable Local Matrix

1. Run `doctor`; do not assume Docker exists. The current machine had no `docker` command in the last audit.
2. Select only `benchmark_role=comparative_candidate` tasks. Do not use `smoke_only` in rankings.
3. Run the same model through `opencode` and `claude-code` with the same task suite and budget profile. Use at least three repetitions per task.
4. Preserve raw run directories, model labels, detected model metadata, traces, diffs, test results, duration, and real token/cost output when available.
5. Run `calibrate-difficulty` after the matrix. Tasks with insufficient evidence, `too_easy`, or `too_hard` must be reported separately, not averaged into a public winner claim.
6. Report strict score, verified normalized score, verified coverage, per-axis scorecards, task success rate, variance, duration, and cost separately. Never substitute a tool-call count for cost.

This produces a preliminary personal answer to the harness question. It is not an authoritative public leaderboard yet.

## V1 Infrastructure: Docker Then External Benchmarks

Implement a Docker runner before attempting the four `container_required` tasks or any external benchmark.

- Task environment contract: immutable image/Dockerfile reference, setup steps, dependency lock, timeout, network policy, CPU/memory limits, and mounted workspace boundaries.
- Runner evidence: image digest, command, exit status, stdout/stderr, test output, and cleanup outcome saved per repetition.
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
