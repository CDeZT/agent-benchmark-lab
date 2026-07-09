#!/bin/sh
set -eu
cc -Wall -Wextra -Werror clamp.c test_clamp.c -o test_clamp
./test_clamp
