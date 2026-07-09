#!/bin/sh
cd "$AGENT_BENCH_WORKSPACE"
gcc -Wall -Wextra -std=c11 -o test_hidden_mempool hidden/hidden_mempool_test.c mempool.c -lm && ./test_hidden_mempool
