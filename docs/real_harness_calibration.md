# Real Hard-Task Calibration

This document records individual real harness runs without turning them into a comparative leaderboard claim. The raw evidence stays in ignored `runs/` directories.

All entries below predate task-contract fingerprints and are therefore retained
only as debugging and implementation evidence. They must not enter current
difficulty calibration, selection, or harness/model winner claims. New real
calibration must be rerun from the current fingerprinted task contracts.

## 2026-07-11: Embedded Protocol Parser

- Task: `embedded-protocol-parser` (`hard`, project-owned embedded-domain seed).
- Harness/model request: `claude-code` with `deepseek-v4-pro`.
- Budget: `bounded`; explicit adapter timeout `180` seconds.
- Evidence directory: `runs/live-20260711-claude-embedded/20260711T021119Z-8af7b912`.
- Outcome: adapter timeout after `180.01s`; no workspace changes; public tests `4/8`, hidden tests `9/22`; strict score `6.0`; verified normalized score `13.04`; verified coverage `46%`.
- Identity: `requested_unverified`; the timed-out CLI produced no detectable model/token/cost/tool trace.

Interpretation: this is one complete failure sample for a hard embedded task, not a DeepSeek-versus-LongCat or Claude Code-versus-opencode conclusion. At least three verified repeated combinations are still required for a discriminability or same-model claim.

## Interrupted OpenCode Attempt

- Task: `embedded-protocol-parser`.
- Harness/model request: `opencode` with `longcat-2.0`.
- Evidence directory: `runs/live-20260711-opencode-embedded/20260711T020412Z-f1523161`.
- Outcome: before hard timeout enforcement was added, the adapter produced no workspace changes or output after five minutes and was manually interrupted. This older run remains `in_progress` and must not be scored or used for calibration.

## 2026-07-11: Current CLI Default Configuration, C Clamp Bugfix

- Task: `c-bugfix` (`easy`, now `smoke_only` after this calibration).
- Configuration A: opencode with its current CLI default, observed as `LongCat-2.0`.
- Configuration B: Claude Code with its current CLI default, observed as `mimo-v2.5-pro[1m]`.
- Budget: `real_smoke`; three independent repetitions per configuration.
- Evidence directories: `runs/20260711T110820Z-71d005cd`, `runs/20260711T111029Z-942be9ce`, `runs/20260711T110840Z-3a9c40f0`, and `runs/20260711T111119Z-e12d8875`.

| Current configuration | Public/hidden pass | Mean strict score | Strict stdev | Mean verified normalized score | Mean verified coverage | Mean duration | Mean recorded cost |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| opencode + LongCat-2.0 | 3/3 | 50.45 | 0.35 | 100.00 | 46% | 16.16s | not exposed |
| Claude Code + mimo-v2.5-pro[1m] | 3/3 | 52.43 | 0.22 | 94.87 | 50% | 21.85s | $0.128317 |

Interpretation at the time was that both configurations completed this smoke task, but the run contracts are now legacy and invalid for current comparison. `c-bugfix` remains `smoke_only` by task policy and excluded from comparative leaderboards. The observed models differ, and the 1.98 strict-score gap was additionally telemetry-sensitive because Claude Code exposed token/cost telemetry while opencode did not. Rerun a fingerprinted, three-repeat multi-task default-configuration matrix before making any practical tool recommendation.
