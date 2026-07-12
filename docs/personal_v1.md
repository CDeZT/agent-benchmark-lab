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
| Domain-weighted suite total (C/embedded/optics axes) | Done | `evaluation_axis_scorecard.domain_weighted_total` on suite summaries |
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

# 2) sampled multi-harness probe (4 tasks, one harness at a time)
bash scripts/run_personal_probe.sh claude-code,opencode,grok 1
# results: latest suite-* under runs/, plus regenerate dashboard

# 3) history + radar gallery
PYTHONPATH=src python3 -m agent_benchmark.cli.main dashboard
open runs/dashboard/index.html
```

If Claude Code fails in <1s with `Unsupported model`, fix the **Claude Code default model** in its own settings; the adapter is fine.

## First personal probe snapshot (2026-07-12)

Sampled suite `personal-probe`, 1 repetition, not a statistical leaderboard.

| Harness | Observed model | Mean strict (4 tasks) | Domain-weighted total* | Comparative pass % |
| --- | --- | ---: | ---: | ---: |
| claude-code | LongCat-2.0[1m] | 59.42 | **57.87** | 66.7 |
| opencode | LongCat-2.0 | 55.54 | 52.60 | 33.3 |
| grok | unverified identity | 55.5 | 54.59 | 66.7 |

\*Domain-weighted total renormalizes over axes present in the probe (optics axis missing). Recomputed with the domain-weight feature after the probe run.

Full tables: `runs/personal-probe-comparison.md` (local, gitignored under `runs/`).

Claude multi-model note: if all Claude Code aliases map to the same provider model ID, separate `--model` runs will not produce a true multi-model comparison until distinct accepted model IDs are configured.

## What "external full import" means (and does NOT mean)

**Local scoring is already complete** for project-owned tasks: public/hidden tests + 10 process dimensions + domain axes + domain-weighted suite total.

**External benchmarks (SWE-bench / Terminal-Bench)** are different:

| State | Meaning | Can enter local leaderboard? |
| --- | --- | --- |
| `external_frozen` | Metadata frozen (issue id, commit). No official Docker result yet. | No |
| Official bridge result (`resolved` / `not_resolved`) | Official evaluator finished with an instance report | Separate external track only |
| `evaluator_error` | Infrastructure/image/network failed before a score | No (not a model score) |

So "满分导入" was a shorthand for "official external tasks fully scored by upstream evaluators and allowed into rankings." That is **optional depth**, not required for personal harness scoring. Without that import, **local tasks still score fully** via tests.

## Grok Build CLI is real (not a stub)

Evidence from real runs (workspace files actually changed; tests executed):

- `python-bugfix`: fixed `stats.py`, public+hidden pass, strict 58
- `process-planning`: wrote plan + code, pass
- `embedded-protocol-parser`: modified `protocol.c`, pass
- suite mean ~55.5 on personal-probe

If it were a fake adapter, tests would not go green after real file edits.
