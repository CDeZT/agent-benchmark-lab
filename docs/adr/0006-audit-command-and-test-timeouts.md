# ADR 0006: Audit Command And Test Timeouts

Date: 2026-07-09

## Status

Accepted.

## Context

The user expects every iteration to include self-checking, code review, real local tests, and bug fixing. Relying on a remembered list of commands is fragile.

Public and hidden tests also need timeout protection so malformed or adversarial task solutions cannot hang the benchmark runner indefinitely.

## Decision

Add `agent-benchmark audit`.

The audit command runs:

- Task and suite validation.
- Unit tests.
- Python compile check.
- Foundation smoke suite with the dummy adapter.

The command writes `audit_summary.json` and `audit_report.md` under `runs/audit-*`.

Add `test_timeout_seconds` to task manifests. Public and hidden test commands time out and are recorded as failed evidence when they exceed the limit.

## Consequences

- New iterations have a one-command self-check path.
- Audit results become saved evidence, not just terminal output.
- Long-running or stuck tests fail safely.

## Follow-Up

Future audit levels can add linting, real harness dry runs, Docker smoke runs, browser screenshot checks, and status-file consistency checks.
