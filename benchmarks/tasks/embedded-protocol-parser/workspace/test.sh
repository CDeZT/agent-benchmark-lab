#!/bin/sh
set -eu
cd "$(dirname "$0")"
cc -Wall -Wextra -Werror -std=c99 protocol.c test_protocol.c -o test_protocol
./test_protocol
