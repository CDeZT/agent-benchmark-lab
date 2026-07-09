#!/bin/sh
set -eu
out="${TMPDIR:-/tmp}/agent_bench_hidden_packet_$$"
trap 'rm -f "$out"' EXIT
cc -Wall -Wextra -Werror \
  "$AGENT_BENCH_WORKSPACE/packet.c" \
  hidden_packet_test.c \
  -I "$AGENT_BENCH_WORKSPACE" \
  -o "$out"
"$out"
