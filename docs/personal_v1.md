# Personal V1: When This Project Is "Complete Enough" For You

This project will never be "done" in the absolute sense (new harnesses, new models, more domains). For **personal use and open-source v1**, treat the following as complete.

## Personal V1 checklist (use this as the finish line)

| Item | Status target | How to verify |
| --- | --- | --- |
| Run one harness on one task | Done | `run --task python-bugfix --adapter grok` (or claude-code/opencode) |
| See score + evidence | Done | `runs/<id>/summary.json` |
| See **radar chart** | Done | `open runs/<id>/report.html` → section "Radar Snapshot" |
| Historical browser | Done | `agent-benchmark dashboard` → `runs/dashboard/index.html` |
| Add a new CLI without rewriting scoring | Done | `config/harnesses.example.json` / `generic-command` |
| Single-harness real smoke | Done when public+hidden pass | grok smoke already passed; claude-code needs a valid default model |
| Multi-task single-harness calibration | Optional next | `run-suite --suite calibration --adapter <one> --repetitions 3` |
| Official SWE-bench score | Later | needs working Docker instance image + network |
| Dual-harness ranking | Later / optional | only when you deliberately compare two CLIs |

## What "complete" does **not** mean

- Not "every dimension always non-zero" — missing telemetry stays 0 by design.
- Not "every external benchmark imported" — those are separate tracks.
- Not "selection_ready > 0 forever without re-running" — CLI/model changes invalidate old evidence.

## Why it felt endless

Work mixed three layers:

1. **Usable now** (run → score → radar → dashboard) — this is Personal V1.
2. **Evidence-rich ranking** (multi-repeat calibration, screening gate) — takes real runs, not more architecture.
3. **Authoritative external tracks** (SWE-bench/Terminal-Bench) — infrastructure + network + cost.

Only layer 1 blocks "I can use this myself today." Layers 2–3 are depth, not entry.

## Recommended personal workflow

```bash
# 1) one task
PYTHONPATH=src python3 -m agent_benchmark.cli.main run \
  --task python-bugfix --adapter grok --repetitions 1
open runs/<experiment-id>/report.html   # radar is here

# 2) small suite (still one harness)
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-suite \
  --suite real-smoke --adapter grok --repetitions 1

# 3) history
PYTHONPATH=src python3 -m agent_benchmark.cli.main dashboard
open runs/dashboard/index.html
```

If Claude Code fails in <1s with `Unsupported model`, fix the **Claude Code default model** in its own settings; the adapter is fine.
