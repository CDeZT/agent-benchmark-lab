# Real Hard-Task Calibration

This document records individual real harness runs without turning them into a comparative leaderboard claim. The raw evidence stays in ignored `runs/` directories.

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
