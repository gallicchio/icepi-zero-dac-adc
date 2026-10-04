#!/bin/sh
# dump.sh -- take one capture and print it as hex, 64 samples per line: the
# same format as the bare-metal firmware's "dump" (2.04), so the same laptop-side
# parser reads either.
A=$(echo /sys/bus/platform/devices/*.adda)
hexdump -v -e '64/1 "%02x" "\n"' "$A/capture/data"
