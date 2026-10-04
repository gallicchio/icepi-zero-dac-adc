#!/bin/bash
# Instructor's smoke test: every Part 10 student script, briefly, on the cross-connected
# pair (JLC 1 = A, JLC 2 = B), exactly as the tutorial runs them.  Outputs go to $OUT.
#   tools/twoboard/smoke_pair.sh /tmp/smoke
set -x
OUT=${1:-/tmp/smoke}; mkdir -p $OUT
SA=DP0525BU; SB=DP051TLX
A=/dev/serial/by-id/usb-FTDI_FT231X_USB_UART_${SA}-if00-port0
B=/dev/serial/by-id/usb-FTDI_FT231X_USB_UART_${SB}-if00-port0
cd "$(dirname "$0")/../../../src/twoboard"
load() { openFPGALoader -b icepi-zero --usb-serial-num $1 $2 2>&1 | grep -c DONE; sleep 1; }
(cd ../verilog && make -s lockin.bit) | tail -1; make -s awgcap.bit warmup.bit pll.bit modem.bit | tail -3
# 10.2  two clocks
load $SA ../verilog/lockin.bit; load $SB ../verilog/lockin.bit
python3 lockin_log.py $OUT/beat.npz 30 1e6 $A $B && python3 beat.py $OUT/beat.npz
# 10.5  coupled oscillators: B follows A (one-way), then mutual coupling
python3 coupled.py $A $B --KA 0 --KB 1 --seconds 20 -o $OUT/coupled_pll.npz | tail -3
python3 coupled.py $A $B --KA 0.25 --KB 0.25 --seconds 20 -o $OUT/coupled_mutual.npz | tail -3
# 10.3  warming a crystal (short)
load $SA warmup.bit
python3 warmup_run.py $A $B --on 60 --off 180 --end 240 -o $OUT/warm.npz | tail -4
# 10.5  hardware PLL: B runs pll.sv, A runs the lock-in
load $SA ../verilog/lockin.bit; load $SB pll.bit
python3 pll_pair.py $A $B --open 10 --closed 20 -o $OUT/pll_pair.npz
# 10.4  two-way time transfer
load $SA awgcap.bit; load $SB awgcap.bit
python3 twoway.py $A $B --seconds 20 -o $OUT/twoway.npz | tail -6
# 10.7  OFDM, both directions
python3 ofdm.py $A $B --qam 64 --records 4 | tail -4
python3 ofdm.py $B $A --qam 16 --records 4 | tail -4
# 10.6  the modem, both ways at once
load $SA modem.bit; load $SB modem.bit
python3 modem_test.py $A $B --baud 1000000
python3 modem_test.py $A $B --baud 115200 --bytes 5000
