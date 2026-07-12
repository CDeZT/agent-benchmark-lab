#!/bin/sh
cd "$(dirname "$0")"
gcc -Wall -Wextra -std=c11 -pthread -o test_thread_pool test_thread_pool.c thread_pool.c && ./test_thread_pool
