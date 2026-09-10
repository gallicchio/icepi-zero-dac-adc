#!/usr/bin/env bash
# Build (and optionally flash) uart_stress_test.v with a given baud rate,
# burst length, and pattern, via the raw yosys/nextpnr-ecp5/ecppack flow.
#
# Usage: ./build.sh <baud> <burst_limit> <pattern:0|1> <out_name> [--load]
#   burst_limit 0 = transmit forever
#   pattern 0 = monotone 0x55, 1 = cycling printable ASCII
set -euo pipefail
cd "$(dirname "$0")"

BAUD="${1:?baud rate, e.g. 115200}"
BURST="${2:?burst limit, 0 for infinite}"
PATTERN="${3:?pattern 0 or 1}"
OUT="${4:?output basename, e.g. burst_600_115200}"
LOAD="${5:-}"

# Bake literal parameter values directly into a per-build copy of the source
# instead of relying on yosys `chparam` post-hierarchy re-elaboration of the
# baud-derived localparam, which was found to silently miscompute the divider.
TMP_V="${OUT}.gen.v"
sed \
  -e "s/parameter integer BAUD_RATE   = 115200,/parameter integer BAUD_RATE   = ${BAUD},/" \
  -e "s/parameter integer BURST_LIMIT = 600,/parameter integer BURST_LIMIT = ${BURST},/" \
  -e "s/parameter integer PATTERN     = 0/parameter integer PATTERN     = ${PATTERN}/" \
  uart_stress_test.v > "${TMP_V}"

yosys -p "
  read_verilog ${TMP_V};
  synth_ecp5 -top uart_stress_test -json ${OUT}.json
"
nextpnr-ecp5 --45k --package CABGA381 --json "${OUT}.json" --lpf colorlight_i9_uart_stress.lpf --textcfg "${OUT}.config"
ecppack --compress "${OUT}.config" "${OUT}.bit"

echo "Built ${OUT}.bit (baud=${BAUD} burst=${BURST} pattern=${PATTERN})"

if [ "${LOAD}" = "--load" ]; then
    openFPGALoader -b colorlight-i9 "${OUT}.bit"
fi
