# Delivery Plan

## Current Delivery Form

The right first delivery form is a local CLI benchmark lab, not a desktop app.

Why:

- The benchmark needs to run local harnesses such as Claude Code and opencode.
- It needs repeated runs, matrix runs, logs, diffs, traces, and reports.
- CLI workflows are easier to automate, audit, and run overnight.
- A dashboard is more useful after real benchmark data exists.

Current deliverable:

- CLI commands under `agent-benchmark`.
- Task and suite definitions under `benchmarks/`.
- Evidence and reports under `runs/`.
- Human docs under `docs/`.
- Machine-readable status under `status/`.

## Planned Delivery Layers

1. CLI benchmark lab.
2. HTML/Markdown reports.
3. Historical result store and comparison tools.
4. Local dashboard.
5. Optional packaged app if the dashboard becomes central.

## Important Commands

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main doctor
PYTHONPATH=src python3 -m agent_benchmark.cli.main audit
PYTHONPATH=src python3 -m agent_benchmark.cli.main audit --include-real-harness
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-suite --suite foundation --adapter dummy --repetitions 1
PYTHONPATH=src AGENT_BENCH_OPENCODE_TIMEOUT_SECONDS=180 python3 -m agent_benchmark.cli.main run --task python-bugfix --adapter opencode --model unspecified --budget-profile real_smoke --repetitions 1
PYTHONPATH=src AGENT_BENCH_CLAUDE_CODE_TIMEOUT_SECONDS=180 python3 -m agent_benchmark.cli.main run --task python-bugfix --adapter claude-code --model unspecified --budget-profile real_smoke --repetitions 1
```

## Real Harness Smoke Status

On 2026-07-09, both local harnesses completed `python-bugfix` successfully:

- opencode: public and hidden tests passed; changed `stats.py`.
- Claude Code: public and hidden tests passed; changed `stats.py`.

This proves the adapter path can launch real local harnesses. It does not yet prove the benchmark is complete.
