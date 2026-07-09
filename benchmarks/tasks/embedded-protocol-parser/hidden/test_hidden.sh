#!/bin/sh
set -eu
out="${TMPDIR:-/tmp}/agent_bench_hidden_protocol_$$"
trap 'rm -f "$out"' EXIT
cc -Wall -Wextra -Werror -std=c99 \
  "$AGENT_BENCH_WORKSPACE/protocol.c" \
  hidden_protocol_test.c \
  -I "$AGENT_BENCH_WORKSPACE" \
  -o "$out"
"$out"
