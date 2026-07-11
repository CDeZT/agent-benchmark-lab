# ADR 0004: Visual Verification Pipeline

Date: 2026-07-09

## Status

Accepted.

## Context

The user explicitly wants UI tasks to be checked visually when relevant. A final system should support browser screenshots and pixel-level checks, but the project should not wait for a browser dependency before adding evidence-backed visual scoring.

## Decision

Introduce a `visual_checks` field in task manifests and a `visual_verification` scorer.

The first engine is `html-static-v1`, which supports deterministic checks against HTML files:

- Required text in an HTML file.
- Forbidden placeholder text.
- Exact text for simple selectors: `tag`, `#id`, and `.class`.

The initial browser screenshot engine now writes evidence into the same `visual_verification` dimension: Playwright Chromium captures PNGs, checks selector visibility, and computes pixel evidence. It remains intentionally limited to static local pages.

## Consequences

- Frontend tasks can now earn visual verification points when evidence exists.
- The first visual system remains dependency-free and easy to run in CI.
- Browser screenshots, Playwright, pixel checks, and visual artifacts now preserve the same task-level score semantics.
- Dynamic pages and interaction/reference-image evaluators remain future work.
