# Architecture

## Overview

Agent Benchmark Lab is organized around a small set of stable abstractions:

```text
ExperimentConfig + TaskSpec -> Adapter -> Runner -> Recorder -> Scorer -> Report
```

The first implementation uses Python and the standard library so the project can run on a clean machine. Third-party tools can be added later when they provide clear value.

## Core Concepts

### TaskSpec

A task specification describes:

- Task id, title, and domain.
- Prompt or instruction.
- Files and fixture path.
- Setup command.
- Test command.
- Protected paths.
- Capabilities measured.
- Budget profile.
- Scoring hints.

### Adapter

An adapter runs a real harness. Examples:

- `dummy`: deterministic local adapter for testing the framework.
- `claude-code`: future adapter for Claude Code CLI.
- `opencode`: future adapter for opencode CLI.

Adapters must not include task-specific shortcuts. Their job is only to invoke a harness in its natural mode, pass the task, and capture outputs.

Adapters are registered through a central adapter registry. CLI and runner code should not duplicate adapter-name lists.

### ExperimentConfig

An experiment configuration records:

- Adapter.
- Model label.
- Budget profile.
- Repetition count.
- Runs directory.
- Optional label.

This allows the project to grow into full matrix comparisons without changing every runner call.

### Runner

The runner:

- Creates a clean run directory.
- Copies or checks out the task workspace.
- Invokes the adapter.
- Runs scoring commands.
- Repeats the experiment as configured.
- Saves structured results.

### Recorder

The recorder writes trace events to JSONL. Every important action should be represented as an event:

- Run started.
- Prompt prepared.
- Adapter command started.
- Adapter output captured.
- Files changed.
- Test command run.
- Score computed.
- Run finished.

### Scorer

The scorer turns evidence into scores. It must keep raw evidence and explain each score.

Current scorer families:

- Test command scorer.
- Hidden/private test scorer.
- Protected path SHA-256 integrity scorer.
- Static HTML visual scorer.

Future scorer families should add evidence to existing dimensions where possible instead of inventing incompatible score surfaces.

Public tests run inside the isolated workspace. Hidden tests run from the task's `hidden/` directory and receive `AGENT_BENCH_WORKSPACE`, so hidden acceptance files are not copied into the agent workspace.

### Report

Reports summarize the run in human-readable form:

- Markdown report for review.
- HTML report with radar chart.
- JSON for machine processing.

### Implementation Status

`status/implementation_status.json` tracks which user requirements are implemented, partial, or planned. `agent-benchmark status` renders that file for quick review. This status file should be updated whenever a meaningful requirement changes state.

## Data Flow

1. Load task manifest.
2. Load experiment configuration.
3. Create run id and run directory.
4. Prepare isolated workspace.
5. Execute harness adapter.
6. Capture diff and logs.
7. Run tests and integrity checks.
8. Compute scores.
9. Repeat if requested.
10. Aggregate results.
11. Generate reports.

For suite and matrix runs, the same task-level pipeline is repeated and aggregated into suite-level or matrix-level summaries.

## External Benchmark Compatibility

The project should eventually include import layers for:

- SWE-bench-style issue tasks.
- Terminal-Bench-style task directories.
- WebArena-style browser tasks.
- OSWorld-style GUI tasks.

The internal schema should remain stable enough that imported tasks become normal TaskSpec objects.

## Initial Implementation Choices

- Python standard library CLI with `argparse`.
- JSON task manifests.
- JSONL traces.
- Markdown and HTML report generation.
- Temporary directory based isolation.
- Dummy adapter first, real harness adapters next.

These choices are intentionally conservative. They keep the first version inspectable and easy to replace.
