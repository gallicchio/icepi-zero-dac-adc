# Build and load the SystemVerilog designs of Chapters 1 and 4.
#
#   make counter.bit        synthesize, place & route, pack   (any NAME.sv -> NAME.bit)
#   make load-counter       ...and load it into the FPGA (SRAM: gone at power-off)
#   make sim-lockin         run lockin_tb.sv in the Icarus Verilog simulator (also sim-capture, sim-fft)
#   make clean
#
# Each .sv file here is a complete design whose top module has the file's name.
# The three steps are exactly the commands in the tutorial:

LPF = icepi_adda.lpf

%.json: %.sv
	yosys -q -p "synth_ecp5 -top $* -json $@" $^

# designs that also use the serial port, or the PLL
adc_stream.json capture.json lockin.json loopback.json lockin_pll.json fft.json am_radio.json: uart.sv
sine_pll.json lockin_pll.json: pll100.sv

%.config: %.json $(LPF)
	nextpnr-ecp5 --25k --package CABGA256 --speed 6 --json $< --lpf $(LPF) \
	    --textcfg $@ 2> $*.pnr.log || (tail -20 $*.pnr.log; false)
	@grep -E "Max frequency for clock" $*.pnr.log | tail -n +1

%.bit: %.config
	ecppack --compress $< $@

load-%: %.bit
	openFPGALoader -b icepi-zero $<

sim-%: %_tb.sv %.sv uart.sv
	iverilog -g2012 -o $*_tb.vvp $^ && vvp -n $*_tb.vvp

clean:
	rm -f *.json *.config *.bit *.pnr.log *.vcd *.vvp

.PRECIOUS: %.json %.config %.bit
