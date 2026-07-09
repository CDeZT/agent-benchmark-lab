# Real Harness Smoke Results

Date: 2026-07-09

## Environment

- opencode: `1.17.15`
- Claude Code: `2.1.205`
- Python: `3.14.3`
- C compiler: Apple clang `21.0.0`

## Task

`python-bugfix`

Instruction: fix `average(values)` so non-empty inputs return arithmetic mean and empty input returns `0.0`.

## Results

| Harness | Model Label | Score | Public | Hidden | Changed Files | Notes |
| --- | --- | ---: | --- | --- | --- | --- |
| opencode | `unspecified` | 36.0 | pass | pass | `stats.py` | stderr indicated LongCat-2.0 in this local configuration. |
| claude-code | `unspecified` | 36.0 | pass | pass | `stats.py` | Initial run produced `__pycache__`; framework now filters Python cache artifacts. |

## Bugs Found And Fixed

- The adapter instruction file was originally written into the task workspace and appeared in `changed_files`. Fixed by writing the instruction file to the run directory instead.
- Python cache files could appear in `changed_files` after real harness execution. Fixed by filtering common generated artifacts such as `__pycache__/*` and `*.pyc`.

## Follow-Up

- Add explicit real-harness smoke audit mode.
- Parse harness traces for tool-use scoring.
- Parse model/cost/token data where harness output exposes it.
- Run the `real-smoke` suite with both harnesses when cost is acceptable.
