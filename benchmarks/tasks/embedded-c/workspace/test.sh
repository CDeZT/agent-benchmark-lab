#!/bin/sh
set -eu
cc -Wall -Wextra -Werror packet.c test_packet.c -o test_packet
./test_packet
