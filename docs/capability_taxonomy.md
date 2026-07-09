# Capability Taxonomy

This taxonomy defines what the benchmark is trying to measure. Tasks should map to one or more capabilities.

## Core Agent Capabilities

| Capability | Meaning | Evidence Examples |
| --- | --- | --- |
| `intent_understanding` | Understands the user's real goal, constraints, and implied requirements. | Requirement checklist, final artifact match, missed-requirement detection. |
| `planning` | Creates and updates a realistic plan. | Plan events, plan updates, completed checklist, decomposition quality. |
| `execution` | Performs the actual engineering work. | Diffs, files created, commands run, passing tests. |
| `self_repair` | Detects failures and iterates without manual intervention. | Failed test followed by fix, repeated verification, reduced error count. |
| `tool_use` | Uses available shell, git, search, browser, visual, and subagent tools effectively. | Command trace, tool trace, screenshots, subtask records. |
| `test_discipline` | Runs relevant tests and adds appropriate tests. | Test logs, new tests, coverage evidence, no weakened tests. |
| `visual_verification` | Checks UI or image output visually when relevant. | Screenshots, pixel checks, browser automation traces. |
| `long_horizon` | Maintains context and progress over long tasks. | No drift, milestone completion, stable logs over time. |
| `safety_boundary` | Avoids damaging unrelated files or violating test integrity. | Diff audit, protected path checks, secret scan. |
| `cost_efficiency` | Uses time and tokens responsibly. | Duration, token count, API cost, command count. |

## Software Engineering Capabilities

| Capability | Meaning |
| --- | --- |
| `bugfix` | Finds and fixes defects. |
| `feature` | Adds requested behavior without regressions. |
| `refactor` | Improves structure while preserving behavior. |
| `test_writing` | Adds meaningful tests. |
| `ci_debugging` | Diagnoses and fixes failing CI-like checks. |
| `code_review` | Finds risks and actionable issues in code. |
| `large_repo_navigation` | Understands multi-file or multi-module codebases. |
| `project_generation` | Creates a working project from a high-level prompt. |

## Domain Capabilities

| Capability | Meaning |
| --- | --- |
| `python_engineering` | Python scripts, packages, tests, and data tooling. |
| `c_engineering` | C code, headers, build systems, memory and edge cases. |
| `fullstack_engineering` | Frontend, backend, API, and integration work. |
| `embedded_engineering` | Embedded-style C, protocols, buffers, timing, hardware-adjacent constraints. |
| `optics_engineering` | Optics, imaging, simulation, calibration, numerical processing. |

## Budget Profiles

| Profile | Purpose |
| --- | --- |
| `oneshot` | Measures first-attempt capability. |
| `bounded` | Measures practical completion under limits. |
| `open_ended` | Measures autonomous persistence and final reliability. |
| `human_like` | Measures normal development behavior with testing and repair. |
| `stress` | Measures long-horizon robustness. |
