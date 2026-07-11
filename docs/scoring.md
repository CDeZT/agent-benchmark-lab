# Scoring Model

The scoring system must be evidence-backed. A score without an observable evidence source is not allowed.

## Score Layers

1. Task-level metrics: raw observations from one run.
2. Capability scores: normalized scores for dimensions such as planning, execution, and self-repair.
3. Aggregate score: weighted score for one run.
4. Experiment score: mean, variance, and confidence summaries across repetitions.

## Strict Total And Measurement Coverage

The strict weighted total keeps unavailable dimensions at zero. This prevents missing telemetry from improving a score, but it must not be read as a direct task-success percentage.

Every run also records:

- `verified_coverage_percent`: how much of the weight has deterministic, task-specific evidence.
- `verified_normalized_score`: the weighted result normalized over only verified dimensions.
- Per-dimension status: `verified`, `heuristic`, or `unavailable`.

Reports must display the strict total and coverage together. Heuristic trace signals such as keyword-based self-repair and tool-call patterns remain visible, but are excluded from the verified normalized score.

## Default Capability Weights

These weights are an initial default and should be versioned when changed.

| Capability | Weight |
| --- | ---: |
| Task completion | 30 |
| Intent understanding | 10 |
| Planning | 8 |
| Execution quality | 12 |
| Self-repair | 10 |
| Test discipline | 10 |
| Tool use | 6 |
| Visual verification | 4 |
| Safety boundary | 6 |
| Cost efficiency | 4 |

Total: 100.

Domain-specific suites may add bonus or replacement dimensions such as embedded correctness or optics numerical accuracy.

## Evidence Sources

| Evidence | Use |
| --- | --- |
| Exit codes | Test and command success. |
| Test logs | Pass/fail details and regression evidence. |
| Hidden tests | Stronger completion evidence where available. |
| Diffs | Scope, quality, and safety audit. |
| File checksums | Test integrity and protected file detection. |
| Screenshots | Visual and UI verification. |
| Static HTML checks | Early visual verification for no-browser seed tasks. |
| JSONL traces | Process, planning, commands, and iteration. |
| Static checks | Lint, type checking, compile checks, complexity. |
| Cost records | Cost efficiency and budget comparison. |

## Automatic First

Automatic tests and deterministic checks should be preferred over subjective judging.

LLM-as-judge may be used only when:

- The task cannot be fully scored with deterministic tests.
- The judge prompt and rubric are versioned.
- The judge output is saved as evidence.
- Disagreement handling is explicit.

For subjective scoring, use a high-exam-style process:

- Two independent judges score the same evidence.
- If scores differ beyond a configured threshold, a third judge adjudicates.
- The final report records the disagreement.

## Public And Hidden Tests

Task manifests can define both `test_command` and `hidden_test_command`.

- Public tests run from the isolated workspace.
- Hidden tests run from `task/hidden` and receive `AGENT_BENCH_WORKSPACE` as an absolute path.
- Hidden files are not copied into the agent workspace.
- `task_completion` is the average of all configured test evidence sources.

This lets public tests provide normal feedback while hidden tests act as private acceptance checks.

## Test Integrity

The scorer must detect test or scoring-file modification. Recommended handling:

- Modified benchmark tests: major penalty or invalid run.
- Deleted benchmark tests: invalid run.
- Added tests: allowed, recorded as engineering quality evidence.
- Modified task instructions: invalid run.

Current implementation snapshots protected files from the baseline workspace and compares SHA-256 hashes after adapter execution. Missing or modified protected paths set `safety_boundary` to 0.

## Visual Verification

Current implementation supports static HTML checks plus `browser_screenshot` checks. Browser checks use Playwright Chromium to capture an actual page PNG, verify required selectors have visible rendered boxes, and verify non-background pixels plus channel standard deviation. Screenshots are saved as run artifacts and their paths/statistics are recorded in score evidence.

Static local pages are covered now. Server-backed apps, interaction flows, reference-image diffs, and mobile viewport matrices remain future visual work. See `docs/browser_visual_verification.md`.

## Repetition Statistics

For each harness/model/task/profile combination, report:

- Number of repetitions.
- Mean score.
- Variance and standard deviation.
- Best and worst score.
- Success rate.
- Mean duration.
- Mean cost if available.

Cost fields remain `null` when harness output does not expose token or provider usage data. When parsers extract `cost_usd`, `input_tokens`, or `output_tokens`, those values are preserved in per-run summaries and aggregated into mean fields. Adapters should fill these fields from structured provider output where available, never by guessing.

At least three repetitions are recommended for meaningful comparison.
