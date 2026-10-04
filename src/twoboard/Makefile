# Two-board designs (Chapter 5).  Uses uart.sv, sine.sv, pll100.sv and
# icepi_adda.lpf from ../verilog, where lockin.bit is built too.
#   make awgcap.bit
#   make load-awgcap SERIAL=DP0525LR       (pick the board by its FT231X serial number)
#   make modem_noise NOISE=78 AMP=100 LOGWIN=4   ->  modem_noise_78_100_4.bit (5.06)
#   make radio_amp4.bit                          ->  radio.sv with AMP = 4 (5.07)
V    = ../verilog
LPF  = $(V)/icepi_adda.lpf
UART = $(V)/uart.sv

%.json: %.sv $(UART)
	yosys -q -p "synth_ecp5 -top $* -json $@" $^
warmup.json: $(V)/sine.sv $(V)/pll100.sv

%.config: %.json $(LPF)
	nextpnr-ecp5 --25k --package CABGA256 --speed 6 --json $< --lpf $(LPF) --textcfg $@ 2> $*.pnr.log || (tail -20 $*.pnr.log; false)
	@grep -E "Max frequency for clock" $*.pnr.log | tail -n 1
%.bit: %.config
	ecppack --compress $< $@

NOISE ?= 0
AMP ?= 100
LOGWIN ?= 4
MN = modem_noise_$(NOISE)_$(AMP)_$(LOGWIN)
modem_noise: $(MN).bit
$(MN).json: modem_noise.sv
	yosys -q -p "chparam -set NOISE $(NOISE) -set AMP $(AMP) -set LOGWIN $(LOGWIN) modem_noise; synth_ecp5 -top modem_noise -json $@" $<

# radio.sv with a weaker transmitter (5.07): make radio_amp4.bit  (AMP = 4 DAC codes)
radio_amp%.json: radio.sv
	yosys -q -p "chparam -set AMP $* radio; synth_ecp5 -top radio -json $@" $<

load-%: %.bit
	openFPGALoader -b icepi-zero $(if $(SERIAL),--usb-serial-num $(SERIAL)) $<
clean:
	rm -f *.json *.config *.bit *.pnr.log
.PRECIOUS: %.json %.config %.bit
.PHONY: modem_noise clean
