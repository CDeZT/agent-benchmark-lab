# Conversation-Derived Requirements

This document preserves user ideas that came from discussion rather than formal specification. Future agents must treat these as real product requirements unless they are explicitly superseded.

## Core User Questions

The benchmark should answer:

- With the same model, is Claude Code or opencode the stronger harness?
- With the same harness, which model is stronger: DeepSeek, mimo, longcat, GPT, Gemini, or another model?
- Which full harness/model pair is best for the user's own real work?

## User's Meaning Of A Strong Harness

The user considers a strong harness to be one that can:

- Understand the user's intent even when requirements are informal.
- Make a complete plan.
- Assign subagents or subtasks when available.
- Build a demo or working artifact.
- Automatically run tests.
- Automatically inspect visual output for UI tasks.
- Find bugs.
- Iterate until the result matches the original request.

## Measurement Preferences

- The user wants total scores, per-dimension scores, and radar charts.
- The user wants repeated runs with mean and variance. Three repetitions is the minimum; more should be supported.
- Cost and runtime should be recorded, but reliability and completeness matter more.
- Oneshot ability matters, but it should not be the only mode.
- Open-ended autonomous completion is important.

## Coverage Requirements

The user wants broad task coverage over time:

- Bugfix.
- Feature work.
- Refactoring.
- Test writing.
- Frontend UI.
- Backend API.
- Full-stack projects.
- CI debugging.
- Code review.
- Large repository understanding.
- From-scratch project generation.

The user wants broad stack coverage over time:

- C.
- Python.
- Full-stack web.
- More stacks in later iterations.

The user specifically wants embedded engineering and optics to be represented where suitable because these match their learning direction.

## Fairness And Realism

- Use real harnesses in their natural mode.
- Do not overfit adapters to tasks.
- Do not fake scoring dimensions.
- If a dimension is not implemented yet, show it as missing or zero rather than pretending it was measured.
- Web search and browser ability can be part of harness capability.
- Agents generally must not modify benchmark tests. Added tests can be allowed, but weakening official tests should be penalized or invalidated.

## Long-Term Maintenance

- The project cannot be completed in one pass.
- Requirements that are not implemented yet must remain documented.
- `docs/handoff.md` must be updated after each meaningful phase.
- Development actions and reasoning should be recorded in `docs/project_journal.md`.
- Future coding agents should be able to continue from the documents without re-asking the user for technical decisions.
