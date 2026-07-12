#!/usr/bin/env sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"

evaluator_python=".agent-benchmark-evaluators/swebench/bin/python"
uv venv --python 3.11 .agent-benchmark-evaluators/swebench
uv pip install --python "$evaluator_python" swebench
uv tool install --python 3.13 terminal-bench

PYTHONPATH=src python3 -m agent_benchmark.cli.main preflight-authoritative
