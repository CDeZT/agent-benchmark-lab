# Corpus Strategy

## Purpose

This benchmark must answer two different questions without confusing their evidence:

1. Which harness/model combination is best for this user's actual work, including embedded engineering and optics?
2. How does that combination perform on broadly recognized public benchmarks?

The first needs maintained project-owned tasks. The second needs upstream tasks evaluated with their official or compatible harnesses. A single undifferentiated score would hide both kinds of evidence, so reports must always preserve corpus source and difficulty stratum.

## Current Corpus

The repository has 19 project-owned tasks, all tagged with a difficulty tier and provenance. The current distribution is:

| Tier | Count | Intended role |
| --- | ---: | --- |
| Easy | 3 | Smoke tests and basic harness correctness |
| Medium | 9 | Planning, visual, review, and ordinary engineering workflows |
| Hard | 4 | Multi-step embedded, optics, data, and cross-module work |
| Expert | 3 | Systems memory work and dependency-isolated full-stack work |

`calibration` is the local, runnable progression suite. It covers all four tiers without relying on third-party Python packages. Run it with at least three repetitions before a larger harness/model matrix. `python-fullstack`, `project-generation`, `optics-imaging-pipeline`, and `python-data-pipeline` are intentionally tagged `container_required`; this Mac currently has neither Docker nor the required packages, so treating their skipped or import-failed local tests as valid comparative results would be incorrect. The runner refuses these tasks before a local run begins.

## External Corpus Plan

External imports begin in two layers once Docker isolation exists. This order is deliberate: reliable environments and provenance are more valuable than importing many tasks that cannot be reproduced.

1. **SWE-bench Verified pilot**: import a fixed, stratified subset of real issue-resolution tasks, preserve the upstream instance id, repository base commit, data release, license note, and evaluator output. Use its containerized evaluator rather than rewriting expected patches.
2. **Terminal-Bench pilot**: run a small fixed subset through the upstream Docker task environment and verifier. Keep terminal-agent scores separate from repository-issue scores.
3. **WebArena and OSWorld**: add these later as separate web/desktop tracks, not to the coding grand score. They evaluate different interaction surfaces and require browser/VM infrastructure.

For every external task, the importer must emit a manifest with `provenance.type=external_imported` and all required source fields. The project must retain the raw upstream evaluator result beside its normalized report.

The implementation should follow the upstream projects rather than a third-party reimplementation: [SWE-bench's evaluation guide](https://github.com/SWE-bench/SWE-bench/blob/main/docs/guides/quickstart.md), [Terminal-Bench's announcement and harness description](https://www.tbench.ai/news/announcement), [WebArena](https://github.com/web-arena-x/webarena), and [OSWorld](https://github.com/xlang-ai/OSWorld).

## Project-Owned Task Policy

Continue adding custom tasks; they are necessary for embedded and optics work that generic public corpora will not cover well. Each new task needs:

- A declared tier and rationale.
- A source classification.
- A deterministic environment declaration.
- A public acceptance test and, whenever feasible, an independent hidden test.
- A reference solution only for framework smoke validation, never exposed to a real harness.
- A negative control proving an incorrect solution does not pass.

Tasks whose dependencies cannot be reproduced locally must be marked `container_required` and excluded from default local comparison suites until the container runner is implemented.

## Scoring and Reporting Rule

Do not report one global number across custom, SWE-bench, Terminal-Bench, web, and desktop tasks without a published weighting policy. First report per-corpus, per-tier success rates, mean score, variance, duration, and actual cost/token evidence. A future composite score may be added only after its weights, exclusions, and confidence intervals are documented.
