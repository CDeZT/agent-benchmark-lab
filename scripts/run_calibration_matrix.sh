#!/usr/bin/env bash
set -euo pipefail

# Run a three-repeat real harness matrix on the calibration suite.
# Requires: opencode and claude-code CLI tools available on PATH.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Default mode compares each CLI's current configured model (not a same-model claim).
# Observed identities are recorded after execution. For a deliberate same-model matrix,
# pass an explicit --models value plus --model-registry config/model_registry.json.
PYTHONPATH=src python3 -m agent_benchmark.cli.main preflight-matrix \
  --suite calibration \
  --adapters opencode,claude-code \
  --models unspecified \
  --budget-profiles oneshot \
  --repetitions 3

PYTHONPATH=src python3 -m agent_benchmark.cli.main run-matrix \
  --suite calibration \
  --adapters opencode,claude-code \
  --models unspecified \
  --budget-profiles oneshot \
  --repetitions 3
