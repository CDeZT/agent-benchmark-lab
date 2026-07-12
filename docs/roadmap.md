# Roadmap

## Phase 0: Foundation

Status: complete.

Goals:

- Capture requirements.
- Define capability taxonomy.
- Define scoring model.
- Define architecture.
- Create handoff and journal documents.
- Build minimal CLI skeleton.
- Validate the pipeline with a dummy adapter.

Progress:

- Foundational documents created.
- Minimal CLI and runner created.
- Dummy adapter created.
- Seed tasks created and validated.
- Basic tests added.
- Generic command adapter added.
- Suite runner added.

## Phase 1: Minimal Working Benchmark

Goals:

- Support task discovery.
- Support repeated runs.
- Support JSONL traces.
- Support Markdown and HTML reports.
- Support basic test scoring.
- Support protected path checks.
- Include seed tasks:
  - Python bugfix.
  - C bugfix.
  - Frontend/visual task.
  - Embedded-style C task.
  - Optics-style Python task.

Progress:

- Task discovery implemented.
- Suite discovery implemented.
- Single-task repeated runs implemented.
- Suite runs implemented.
- Matrix runs implemented for adapter/model/profile combinations.
- Requirement implementation status tracking added.
- Audit command added.
- Test timeout support added.
- Doctor command added.
- Process planning scorer and task added.
- Built-in opencode and Claude Code command templates added.
- Real opencode and Claude Code smoke tests passed on `python-bugfix`.
- JSONL traces implemented.
- Markdown reports implemented.
- HTML reports with radar snapshot implemented.
- Basic test scoring implemented.
- Protected path existence check implemented.
- Protected path SHA-256 integrity implemented.
- Static HTML visual checks implemented.
- Duration aggregation implemented.
- Explicit null cost/token fields added.
- Seed tasks implemented.

Remaining:

- Strong protected file hashing.
- Real harness adapters.
- Better aggregation across model/harness combinations.
- Browser screenshot checks.
- Real token/cost parsing.

## Phase 2: Real Harness Adapters

Goals:

- Add opencode adapter.
- Add Claude Code adapter.
- Support model configuration through environment variables and local config.
- Capture harness stdout/stderr and exit codes.
- Detect interaction or permission failures.

## Phase 3: Stronger Isolation

Goals:

- Add Docker runner.
- Add deterministic dependency setup.
- Add task-level network policy.
- Add clean workspace restoration.

## Phase 4: Scoring Expansion

Goals:

- Add richer code quality checks.
- Add visual screenshot checks.
- Add LLM-as-judge as optional adjudication.
- Add mean, variance, and confidence reporting.
- Add failure taxonomy.
- Add safety and test-integrity penalties.

## Phase 5: External Benchmark Imports

Goals:

- Build a Docker-backed external evaluator bridge before importing any task.
- Import a fixed, stratified SWE-bench Verified pilot with upstream instance, release, commit, license, and evaluator evidence preserved.
- Add a small Terminal-Bench pilot through its upstream Docker environment and verifier.
- Keep external coding, terminal, web, and desktop tracks separate in reports.
- Add browser task support inspired by WebArena only after browser isolation exists.
- Add desktop task support inspired by OSWorld only after VM/desktop isolation exists.

Current readiness:

- Docker is available and project-owned container evaluation records image identifiers. `preflight-authoritative` validates the official source registry and the local `swebench` / `tb` toolchain without claiming an import. The next blocker is a frozen upstream pilot and its official evaluator bridge, not local tool installation.

## Phase 6: Dashboard

Goals:

- Local dashboard for historical results.
- Radar charts and leaderboards.
- Harness/model/task comparison views.
- Failure case browser.

## Permanent Requirements

These requirements must stay visible across all phases:

- Do not discard user ideas because they are not in the first version.
- Keep embedded engineering and optics as long-term first-class domains.
- Keep open-ended autonomy and oneshot capability both measurable.
- Keep all scores tied to evidence.
- Update `docs/handoff.md` after meaningful phases.
