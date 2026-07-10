#!/usr/bin/env bash
set -euo pipefail

# Run a three-repeat real harness matrix on the calibration suite.
# Requires: opencode and claude-code CLI tools available on PATH.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

PYTHONPATH=src python3 -m agent_benchmark.cli.main run-matrix \
  --suite calibration \
  --adapters opencode,claude-code \
  --models mimo-v2.5-pro,longcat-2.0 \
  --model-registry config/model_registry.json \
  --budget-profiles oneshot \
  --repetitions 3
