# Evidence Strength And Harder Corpora

## Why some dimensions looked "unable to enable strong evidence"

They were not disabled on purpose for the user. The scorer separates:

| Status | Meaning |
| --- | --- |
| `verified` | Deterministic or structured telemetry tied to this run |
| `heuristic` | Useful but weaker (e.g. keyword self-repair) |
| `unavailable` | No evidence at all for this task/harness (score stays 0) |

### Before the fix

- **tool_use** from Claude/opencode structured output was always marked `heuristic`, even when `num_turns` / tool events were real.
- **cost_efficiency** already became `verified` when token/cost JSON existed (Claude).
- **planning** / **test_discipline** stay `unavailable` unless the **task** defines process checks (e.g. require `.agent-benchmark/plan.md`).
- **visual_verification** only applies to visual tasks.
- **Grok** often exposes little tool/cost JSON → those dimensions stay 0 (honest), not "broken".

### After the fix

- Structured harness tool telemetry (`read`/`edit`/`bash`/`agent_turn`/JSON turns) marks **tool_use = verified**.
- Hard tasks in `hard-discrimination` require a planning artifact (≥40 bytes plan.md) so **planning** can become verified when the agent actually plans.

## Why the local bank felt too easy / too small

- Many seed tasks are intentionally medium smoke/calibration.
- Personal probe used only 4–5 tasks for cost control.
- External banks exist as **frozen pilots + bridges**, not fully scored imports yet.

## Authoritative banks (how scoring works)

| Source | What exists | How it scores |
| --- | --- | --- |
| Local hard suite | `hard-discrimination` | Project public/hidden tests + 10 dimensions |
| SWE-bench Verified pilot | 6 frozen instances + `swebench-bridge` | Official Docker evaluator only; no local fake pass |
| Terminal-Bench pilot | 6 frozen tasks + `terminal-bench-bridge` | Official `tb run` only |

Prefer overall **harder** local discrimination first; use official bridges for external tracks without inventing local scores.

## Recommended personal hard run

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-suite \
  --suite hard-discrimination --adapter claude-code --repetitions 1
```
