# Screening Exam Policy

This project is building a selective engineering-agent exam, not a
qualification checklist. A task that nearly every configuration passes does
not strengthen a leaderboard, even if its verifier is correct.

## Ladder

The local `selection-ladder` suite is ordered `expert -> hard -> medium ->
easy`. Difficult tasks are encountered first to expose a configuration's
ceiling. Easy tasks remain for diagnosis and CLI wiring, but `smoke_only` tasks
are excluded from selection rankings.

Use the executable gate before interpreting a local ranking:

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main screening-report
PYTHONPATH=src python3 -m agent_benchmark.cli.main screening-report --json
```

`selection_ready_local_seed` requires all of the following:

1. The task is a `comparative_candidate`, not a smoke check.
2. Its baseline/reference contrast passes `audit-corpus`.
3. Identified real-harness evidence contains at least three
   adapter/observed-model/profile configurations with at least three runs each.
4. Every contributing summary carries the exact current task-contract
   fingerprint. Missing or mismatched fingerprints are historical/debugging
   evidence only, never ranking evidence.
5. Empirical calibration calls it `discriminative_candidate`: neither
   universally easy nor universally impossible, with a material success-rate
   spread.

`awaiting_real_evidence` is not a failure label. It means a task may be a good
candidate but has not earned selection weight yet. `retune_or_replace` means
the measured task is too easy or too hard and should not be rescued by simply
changing its declared difficulty. `corpus_gate_pending` means the task has not
yet passed the baseline/reference contrast gate (including a
container-required task without a recorded container audit), so it cannot
enter selection even if its observed pass rate later looks promising.

External pilots use the same selective rule before official evaluator results
exist: `ranking_candidate` instances appear first and may later receive track
weight; `diagnostic_tail` instances may only diagnose floor behavior. A pilot
needs at least three ranking candidates, and no ranking candidate may appear
after its diagnostic tail. This prevents a short or explicitly easy upstream
task from diluting a difficult screening track.

## Authoritative Tracks

Project-owned tasks are essential for embedded and optics work, but source
provenance stays separate from public benchmarks.

- [SWE-bench](https://github.com/SWE-bench/SWE-bench) provides real GitHub
  issue-resolution tasks; its Verified subset contains 500 engineer-confirmed
  solvable problems, and its official evaluation is Docker based.
- [Terminal-Bench](https://github.com/laude-institute/terminal-bench) provides
  terminal environments with task verifiers and oracle solutions. The source
  registry currently records Core v0.1.1 as the first planned pilot.
- The [Terminal-Bench task rubric](https://github.com/harbor-framework/terminal-bench-science/blob/main/rubrics/task-implementation.toml)
  reinforces this project's rule that verifiers should be deterministic and
  behavioral, not source-keyword matching.

`config/authoritative_corpora.json` records the approved source/evaluator
contracts. It does not mean these datasets have been imported yet. An imported
task can receive `provenance.type=external_imported` only after preserving the
upstream instance id, version, license note, Docker/evaluator evidence, and raw
result.
