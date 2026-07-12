# Mixed Local And Official Reporting

`run-suite` can now schedule local tasks and selected SWE-bench Verified instances in one resumable command:

```bash
PYTHONPATH=src python3 -m agent_benchmark.cli.main run-suite \
  --suite comprehensive-screening-v1 \
  --adapter claude-code --model unspecified --repetitions 3
```

This is one **execution campaign**, not one synthetic score scale.

- Local tasks retain the project ten-dimension strict score, verified coverage, verified-normalized score, variance, CI, and domain axes.
- SWE-bench tasks are scored only by the upstream official evaluator. A resolved task contributes to the official resolution track; `not_resolved` is a valid official failure; evaluator infrastructure errors are excluded rather than forced to zero.
- The hard ranking candidates determine official resolution rate. The easy diagnostic tail is retained for inspection but excluded from that rate.
- Official resolution outcomes never become invented planning, intent, execution-quality, or safety scores, and they are not averaged into local strict totals.

`unified-hard` remains a smaller mixed smoke/cross-check cohort. Prefer `comprehensive-screening-v1` for the fixed full personal screening group. Terminal-Bench remains an independent official track because its terminal sandbox and evaluator mean something different from repository-issue resolution.
