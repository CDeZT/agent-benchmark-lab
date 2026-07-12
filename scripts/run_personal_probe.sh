#!/usr/bin/env bash
# Sampled personal comparison: one harness at a time, 4 tasks, 1 rep by default.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
ADAPTERS="${1:-claude-code,opencode,grok}"
REPS="${2:-1}"
IFS=',' read -r -a items <<< "$ADAPTERS"
for adapter in "${items[@]}"; do
  echo "=== personal-probe adapter=$adapter reps=$REPS ==="
  PYTHONPATH=src python3 -m agent_benchmark.cli.main run-suite \
    --suite personal-probe \
    --adapter "$adapter" \
    --model unspecified \
    --budget-profile open_ended \
    --repetitions "$REPS"
done
PYTHONPATH=src python3 -m agent_benchmark.cli.main dashboard
echo "Dashboard: runs/dashboard/index.html"
echo "Tip: open each experiment report.html for radar charts."
