#!/bin/bash
# Instructor's builds for fsk_ber.py:  fsk_build.sh OUTDIR NOISE AMP LOGWIN
#   OUTDIR/mn_NOISE_AMP_LOGWIN.bit  twoboard/modem_noise.sv (the modem with noise)
#   OUTDIR/mm_NOISE_AMP_LOGWIN.bit  mn_measure.v (steady MARK tone + noise, capture.sv on the ADC)
# e.g.  for m in 0 43 61 70 78 86 95 104 113 139; do echo "$m 100 4"; done | xargs -P 4 -L 1 ./fsk_build.sh /tmp/fsk
set -e
HERE=$(cd "$(dirname "$0")" && pwd); T=$HERE/../../../src
OUT=$1; tag=$2_$3_$4
P="chparam -set NOISE $2 -set AMP $3 -set LOGWIN $4"
mkdir -p $OUT
cd $T/twoboard
yosys -q -p "$P modem_noise; synth_ecp5 -top modem_noise -json $OUT/mn_$tag.json" modem_noise.sv > $OUT/mn_$tag.ylog 2>&1
nextpnr-ecp5 --25k --package CABGA256 --speed 6 --json $OUT/mn_$tag.json --lpf ../verilog/icepi_adda.lpf --textcfg $OUT/mn_$tag.config > $OUT/mn_$tag.log 2>&1
ecppack --compress $OUT/mn_$tag.config $OUT/mn_$tag.bit
yosys -q -p "$P mn_measure; synth_ecp5 -top mn_measure -json $OUT/mm_$tag.json" $HERE/mn_measure.v modem_noise.sv ../verilog/capture.sv ../verilog/uart.sv > $OUT/mm_$tag.ylog 2>&1
nextpnr-ecp5 --25k --package CABGA256 --speed 6 --json $OUT/mm_$tag.json --lpf ../verilog/icepi_adda.lpf --textcfg $OUT/mm_$tag.config > $OUT/mm_$tag.log 2>&1
ecppack --compress $OUT/mm_$tag.config $OUT/mm_$tag.bit
grep "Max frequency" $OUT/mn_$tag.log | tail -1
