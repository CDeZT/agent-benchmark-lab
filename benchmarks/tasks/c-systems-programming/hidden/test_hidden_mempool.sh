#!/bin/sh
set -eu
out="${TMPDIR:-/tmp}/agent_bench_hidden_mempool_$$"
trap 'rm -f "$out"' EXIT
gcc -Wall -Wextra -std=c11 \
  "$AGENT_BENCH_WORKSPACE/mempool.c" \
  hidden_mempool_test.c \
  -I "$AGENT_BENCH_WORKSPACE" \
  -lm -o "$out"
"$out"
