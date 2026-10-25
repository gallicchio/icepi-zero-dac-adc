# 4.06's design.  Uses uart.sv and icepi_adda.lpf from ../verilog.
#   make awgcap_slow.bit
#   make load-awgcap_slow
#   make sim-awgcap_slow       (awgcap_slow_tb.sv in Icarus Verilog)
V    = ../verilog
LPF  = $(V)/icepi_adda.lpf
UART = $(V)/uart.sv

%.json: %.sv $(UART)
	yosys -q -p "synth_ecp5 -top $* -json $@" $^
%.config: %.json $(LPF)
	nextpnr-ecp5 --25k --package CABGA256 --speed 6 --json $< --lpf $(LPF) --textcfg $@ 2> $*.pnr.log || (tail -20 $*.pnr.log; false)
	@grep -E "Max frequency for clock" $*.pnr.log | tail -n 1
%.bit: %.config
	ecppack --compress $< $@
load-%: %.bit
	openFPGALoader -b icepi-zero $<
sim-%: %_tb.sv %.sv $(UART)
	iverilog -g2012 -o $*_tb.vvp $^ && vvp -n $*_tb.vvp
clean:
	rm -f *.json *.config *.bit *.pnr.log *.vvp
.PRECIOUS: %.json %.config %.bit
