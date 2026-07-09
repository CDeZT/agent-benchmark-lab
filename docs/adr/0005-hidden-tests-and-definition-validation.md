# ADR 0005: Hidden Tests And Definition Validation

Date: 2026-07-09

## Status

Accepted.

## Context

Public tests are useful for normal engineering feedback, but agents can overfit to visible tests. The benchmark needs private acceptance checks that are not copied into the agent workspace.

As task count grows, the project also needs a validation command so broken manifests and suite references are caught before long benchmark runs.

## Decision

Task manifests may define:

- `test_command`: public tests run from the agent workspace.
- `hidden_test_command`: private acceptance tests run from `task/hidden`.

Hidden tests receive `AGENT_BENCH_WORKSPACE` as an absolute path to the isolated workspace. The hidden directory is not copied into the workspace.

`task_completion` is computed from all configured test evidence sources. With public and hidden tests configured, each contributes equally.

Add `agent-benchmark validate` to check task and suite definitions.

## Consequences

- Agents can receive public feedback while still being evaluated by private acceptance checks.
- Reports can show public and hidden pass/fail separately.
- Future SWE-bench or Terminal-Bench importers can map their private test phases into `hidden_test_command`.
