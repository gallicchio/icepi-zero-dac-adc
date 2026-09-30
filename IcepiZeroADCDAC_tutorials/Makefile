# Build and load the bare-Verilog tutorials.
#
#   make counter.bit        synthesize, place & route, pack   (any NAME.v -> NAME.bit)
#   make load-counter       ...and load it into the FPGA (SRAM: gone at power-off)
#   make sim-lockin         run lockin_tb.v in the Icarus Verilog simulator
#   make clean
#
# Each .v file here is a complete design whose top module has the file's name.
# The three steps are exactly the commands in the tutorial:

LPF = icepi_adda.lpf

%.json: %.v
	yosys -q -p "synth_ecp5 -top $* -json $@" $^

# designs that also use the serial port, or the PLL
capture.json lockin.json loopback.json lockin_pll.json: uart.v
sine_pll.json lockin_pll.json: pll100.v

%.config: %.json $(LPF)
	nextpnr-ecp5 --25k --package CABGA256 --speed 6 --json $< --lpf $(LPF) \
	    --textcfg $@ 2> $*.pnr.log || (tail -20 $*.pnr.log; false)
	@grep -E "Max frequency for clock" $*.pnr.log | tail -n +1

%.bit: %.config
	ecppack --compress $< $@

load-%: %.bit
	openFPGALoader -b icepi-zero $<

sim-%: %_tb.v %.v uart.v
	iverilog -g2005 -o $*_tb.vvp $^ && vvp $*_tb.vvp

clean:
	rm -f *.json *.config *.bit *.pnr.log *.vcd *.vvp

.PRECIOUS: %.json %.config %.bit
