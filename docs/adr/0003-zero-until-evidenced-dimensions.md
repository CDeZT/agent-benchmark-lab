# ADR 0003: Zero Until Evidenced Dimensions

Date: 2026-07-09

## Status

Accepted.

## Context

The benchmark has many target dimensions: planning, intent understanding, self-repair, visual verification, tool use, cost efficiency, and more. Some are not yet implemented.

Filling these dimensions with optimistic placeholder scores would make reports look better but violate the user's requirement that every score be real.

## Decision

Unimplemented dimensions remain scored as 0 until there is evidence-backed scoring logic.

Reports and handoff documents must explain this clearly so low early scores are not mistaken for failed tasks.

## Consequences

- Early scores are conservative.
- Radar charts reveal missing measurement infrastructure.
- Future agents have a clear checklist of dimensions to implement.
