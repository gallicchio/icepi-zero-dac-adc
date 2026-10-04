# Board-test designs for a new Icepi Zero (no header, module or card needed).
#   make load-iotest    buttons and card detect, streamed over the serial port
#   make load-tick      then: python3 measure_osc.py   (the oscillator, 12 min)
#   SERIAL=DP0525BU make load-iotest   picks one board when several are plugged in
UART = ../../../src/verilog/uart.sv
LPF  = boardtest.lpf

%.json: %.v $(UART)
	yosys -q -p "synth_ecp5 -top $* -json $@" $< $(UART)
%.config: %.json $(LPF)
	nextpnr-ecp5 --25k --package CABGA256 --speed 6 --json $< --lpf $(LPF) --textcfg $@ --lpf-allow-unconstrained
%.bit: %.config
	ecppack --compress $< $@
load-%: %.bit
	openFPGALoader -b icepi-zero $(if $(SERIAL),--usb-serial-num $(SERIAL)) $<
clean:
	rm -f *.json *.config *.bit
.PRECIOUS: %.json %.config
