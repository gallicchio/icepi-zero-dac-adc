# Chapter 7 DSP designs.  Uses uart.sv and icepi_adda.lpf from ../verilog.
#   make sigma_delta.bit                     7.05: the delta-sigma DAC and CIC decimator
#   make sim                                 simulate sigma_delta_tb.sv (iverilog), no board
#   make fir_set1.bit                        fir.sv with SET = 1 (0 average, 1 low-pass, 2 edge, 3 band-pass)
#   make iir_k4.bit iir_k6.bit iir_k6_g0.bit iir_peak.bit    iir.sv: one-pole with K, GUARD = 0, the resonator
#   make iir_peak F0=1000000 Q=20            ->  iir_peak_1000000_20.bit
#   make filter.bit control.bit
#   make sim-filter                          filter_tb.sv in Icarus Verilog (also sim-fir, sim-iir, sim-control)
#   make load-sigma_delta SERIAL=DP0525LR    (pick the board by its FT231X serial number)
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

# fir.sv and iir.sv, with their parameters (7.02, 7.04)
fir_set%.json: fir.sv
	yosys -q -p "chparam -set SET $* fir; synth_ecp5 -top fir -json $@" $<
iir_k%_g0.json: iir.sv
	yosys -q -p "chparam -set MODE 0 -set K $* -set GUARD 0 iir; synth_ecp5 -top iir -json $@" $<
iir_k%.json: iir.sv
	yosys -q -p "chparam -set MODE 0 -set K $* iir; synth_ecp5 -top iir -json $@" $<
iir_peak.json: iir.sv
	yosys -q -p "chparam -set MODE 1 iir; synth_ecp5 -top iir -json $@" $<
F0 ?= 2000000
Q  ?= 10
iir_peak: iir_peak_$(F0)_$(Q).bit
iir_peak_$(F0)_$(Q).json: iir.sv
	yosys -q -p "chparam -set MODE 1 -set F0 $(F0) -set Q $(Q) iir; synth_ecp5 -top iir -json $@" $<

# any NAME_tb.sv with NAME.sv: make sim-NAME
sim-%: %_tb.sv %.sv $(UART)
	iverilog -g2012 -o $*_tb.vvp $^ && vvp -n $*_tb.vvp

# sigma_delta.sv's testbench (7.05)
sim: sigma_delta_tb.vvp
	vvp $<
sigma_delta_tb.vvp: sigma_delta_tb.sv sigma_delta.sv $(UART)
	iverilog -g2012 -o $@ $^

load-%: %.bit
	openFPGALoader -b icepi-zero $(if $(SERIAL),--usb-serial-num $(SERIAL)) $<
# control.sv through its pins only, replaying the bytes control.py sends (control.py --dump-bytes
# control_script.txt), against the RTL and against the gates Yosys makes of it; the two logs
# must agree.  The first build of control.sv passed every RTL test and failed on the board:
# Yosys drops the minus sign of a negated size cast ("-22'(YMAX)").  This catches that class.
#   make sim-control-gl
YOSYS_DAT := $(shell yosys-config --datdir)
# -nobram: Yosys's DP16KD simulation "model" is an empty black box, so the capture memory is
# built from LUT RAM here (the real bitstream keeps its block RAM; the board's dumps proved it)
control_gl.v: control.sv $(UART)
	yosys -q -p "read_verilog -sv $^; chparam -set LOGN 7 control; synth_ecp5 -top control -nobram; write_verilog -noattr $@"
control_script.txt: control.py
	python3 control.py --mode 1 --K 4 --L 5 --kp 2 --ki 0.05 --step 40 --N 9 --dump-bytes $@
# Yosys's ecp5/cells_sim.v includes cells_ff.vh and cells_io.vh twice (once itself, once
# through common_sim.vh), which Icarus rejects; this copy drops the direct includes.
ecp5_cells_sim.v: $(YOSYS_DAT)/ecp5/cells_sim.v
	sed -e '/^`include "cells_ff.vh"/d' -e '/^`include "cells_io.vh"/d' $< > $@
sim-control-gl: control_gl_tb.sv control.sv control_gl.v control_script.txt mult18x18d_sim.v ecp5_cells_sim.v
	iverilog -g2012 -o control_gl_rtl.vvp control_gl_tb.sv control.sv $(UART) && vvp -n control_gl_rtl.vvp +script=control_script.txt > control_gl_rtl.log
	iverilog -g2012 -DGATES -I $(YOSYS_DAT)/ecp5 -o control_gl_gates.vvp control_gl_tb.sv control_gl.v ecp5_cells_sim.v mult18x18d_sim.v && vvp -n control_gl_gates.vvp +script=control_script.txt > control_gl_gates.log
	@diff control_gl_rtl.log control_gl_gates.log && echo "RTL and gates agree:" && cat control_gl_gates.log

clean:
	rm -f *.json *.config *.bit *.pnr.log *.vvp *_trace.txt control_gl.v control_gl_*.log
.PRECIOUS: %.json %.config %.bit
.PHONY: iir_peak sim clean
