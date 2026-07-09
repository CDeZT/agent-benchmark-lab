#!/bin/sh
cd "$(dirname "$0")"
gcc -Wall -Wextra -std=c11 -o test_mempool test_mempool.c mempool.c -lm && ./test_mempool
