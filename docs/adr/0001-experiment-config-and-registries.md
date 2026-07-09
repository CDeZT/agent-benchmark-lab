# ADR 0001: Experiment Config And Registries

Date: 2026-07-09

## Status

Accepted.

## Context

The benchmark must grow from a dummy runner into a long-term system that compares:

```text
harness x model x task x environment x budget profile
```

The first implementation hard-coded adapter names and passed only a few primitive arguments through the runner. That is acceptable for a smoke test, but it does not scale to real Claude Code, opencode, model configuration, budget profiles, Docker, or future scorers.

## Decision

Introduce an `ExperimentConfig` object and adapter registry.

`ExperimentConfig` should carry:

- Adapter name.
- Model name.
- Budget profile.
- Repetition count.
- Runs directory.
- Optional label.

The adapter registry should be the only place that maps adapter names to adapter classes. CLI code and runner code should not duplicate adapter lists.

## Consequences

- New adapters can be added in one place.
- Reports can record model and budget profile even before model-specific adapters are implemented.
- Future matrix runs can reuse the same config object.
- The runner becomes easier to test.

## Non-Goals

This ADR does not require implementing full model-provider configuration. That should come after real harness adapters exist.
