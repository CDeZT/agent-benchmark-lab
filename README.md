# Agent Benchmark Lab

Agent Benchmark Lab is a long-term benchmark project for measuring real coding-agent combinations:

```text
harness x model x task x environment x budget profile -> evidence-backed scores
```

The project is intentionally broader than a model leaderboard. It is designed to answer practical questions such as:

- Which harness is stronger when using the same model?
- Which model works best inside the same harness?
- Which harness/model pair best matches a user's real engineering workflow?
- How well does an agent understand intent, plan, use tools, test, inspect visuals, repair bugs, and continue autonomously?

## Current Status

This repository is in foundation mode. The first implementation focuses on:

- Requirements and benchmark design documents.
- A minimal Python CLI with no mandatory third-party dependencies.
- A task manifest schema.
- A dummy adapter for validating the runner, recorder, scorer, and report pipeline.
- Seed tasks for Python, C, frontend/visual, embedded-style, and optics-style evaluation.
- Matrix runs across adapter/model/budget-profile combinations.
- Static HTML visual checks for early frontend evidence.
- Public and hidden test commands.
- Task and suite validation.
- Test timeout protection.
- Local harness/environment doctor.
- One-command project audit.
- Real opencode and Claude Code smoke path.

See `docs/roadmap.md` and `docs/handoff.md` before extending the system.

## Quick Start

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main list-tasks
PYTHONPATH=src python3 -m agent_benchmark.cli.main list-suites
PYTHONPATH=src python3 -m agent_benchmark.cli.main validate
PYTHONPATH=src python3 -m agent_benchmark.cli.main status
PYTHONPATH=src python3 -m agent_benchmark.cli.main doctor
PYTHONPATH=src python3 -m agent_benchmark.cli.main audit
PYTHONPATH=src python3 -m agent_benchmark.cli.main audit --include-real-harness
PYTHONPATH=src python3 -m agent_benchmark.cli.main next-agent-prompt
PYTHONPATH=src python3 -m agent_benchmark.cli.main run --task python-bugfix --adapter dummy --model smoke --budget-profile oneshot --repetitions 3
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-suite --suite foundation --adapter dummy --model smoke --budget-profile open_ended --repetitions 3
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-matrix --suite foundation --adapters dummy --models smoke-a,smoke-b --budget-profiles oneshot,open_ended --repetitions 1
```

Run outputs are written under `runs/` by default.

## Safety

API keys, provider credentials, and local harness configuration must be supplied through environment variables or local files excluded by `.gitignore`. This repository should never store secrets.

## Handoff

For context transfer to another agent, use:

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main next-agent-prompt
```

The source file is `docs/next_agent_prompt.md`.
