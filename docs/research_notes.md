# Research Notes

This project borrows ideas from established benchmarks without copying any single one completely.

## SWE-bench

SWE-bench evaluates systems on real GitHub issues. The important lessons for this project are:

- Use real engineering tasks where possible.
- Apply agent changes to a clean environment.
- Score with tests instead of verbal claims.
- Preserve patches and logs.

References:

- https://github.com/swe-bench/SWE-bench
- https://www.swebench.com/SWE-bench/reference/harness/

## Terminal-Bench

Terminal-Bench focuses on terminal tasks in controlled environments. Useful ideas:

- Task instructions plus isolated environment.
- Oracle or test-based verification.
- Final state matters more than explanation.
- Docker-style reproducibility is important.

References:

- https://github.com/harbor-framework/terminal-bench
- https://www.tbench.ai/

## Inspect AI

Inspect AI provides a useful conceptual model:

- Dataset.
- Solver or agent.
- Scorer.
- Sandbox.
- Logs and log viewer.

The project should borrow this abstraction style while still supporting real local coding harnesses.

References:

- https://inspect.aisi.org.uk/
- https://inspect.aisi.org.uk/tutorial.html

## Aider Benchmarks

Aider's benchmark work is relevant because it measures coding changes through realistic file edits and tests.

Useful ideas:

- Track pass rate.
- Track cost.
- Track edit behavior and failures.
- Compare models under repeated coding tasks.

References:

- https://aider.chat/docs/leaderboards/
- https://github.com/Aider-AI/aider/blob/main/benchmark/README.md

## OpenHands Benchmarks

OpenHands and related benchmark runners are relevant for tracing agent actions and comparing agent systems.

References:

- https://github.com/OpenHands/benchmarks
- https://github.com/All-Hands-AI/OpenHands

## WebArena And OSWorld

These benchmarks are relevant for future browser, visual, and desktop-agent tasks.

References:

- https://github.com/web-arena-x/webarena
- https://github.com/xlang-ai/osworld

## Project-Specific Takeaway

The user's benchmark needs to be broader than a public leaderboard. It must preserve:

- Real harness behavior.
- Model comparison.
- Process evidence.
- Long-running autonomy.
- Visual and GUI evaluation.
- Embedded and optics domain tasks.
- Repetition statistics.
- Practical recommendations.
