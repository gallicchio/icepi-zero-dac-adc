# The XY show on two Icepi Zeros (5.08).  The tables in rtl/ are made by make_show.py and committed, so building
# needs only the OSS CAD Suite (1.00); changing the show needs Python with numpy.
#   make            build/x.bit and build/y.bit: the X board (ROLE 0) and the Y board (ROLE 1), a few minutes each
#   make flash      write them into the two boards' flash, X into the board with the lower FT231X serial number
#                   (flash.py; make flash X=DK0GFLAW Y=DP051TLX to choose)
#   make load       the same into the FPGAs' RAM: quicker, and gone at power-off
#   make tables     python3 make_show.py: rtl/'s tables again, from make_show.py's constants (then make)
#   make movie      python3 make_show.py --movie: the show as the boards will draw it, renders/show_movie.mp4
#   make sim        the two boards simulated through a modelled cable (iverilog, a few minutes):
#                   renders/icepi_show_sheet.png, a frame of every mode and finale
RTL    = top_icepi.v sync_link.v vec3d.v matrix_unit.v show_seq.v lorenz.v chua.v regbus.v uart.v
TABLES = scene_xy.hex scene_z.hex persp.hex sincos.hex matrix_prog.hex regs_init.hex \
         scene_layout.vh matrix_prog.vh show_params.vh show_finales.vh
SRC    = $(addprefix rtl/,$(RTL) $(TABLES))
SEED  ?= 1
BUILD_ID := $(shell date +%Y%m%d)
CHOOSE  = $(if $(X),--x $(X)) $(if $(Y),--y $(Y))

all: build/x.bit build/y.bit

build/%.json: $(SRC)
	@mkdir -p build
	cd rtl && yosys -q -l ../build/$*_yosys.log -p "read_verilog -sv -defer $(RTL); \
	    chparam -set ROLE $(if $(filter x,$*),0,1) -set BUILD_ID 32'h$(BUILD_ID) top_icepi; \
	    synth_ecp5 -top top_icepi -json ../build/$*.json"
build/%.config: build/%.json rtl/icepi_adda.lpf
	nextpnr-ecp5 --25k --package CABGA256 --speed 6 --seed $(SEED) --json $< --lpf rtl/icepi_adda.lpf \
	    --textcfg $@ 2> build/$*.pnr.log || (tail -20 build/$*.pnr.log; false)
	@grep -E "Max frequency for clock" build/$*.pnr.log | tail -n 1
build/%.bit: build/%.config
	ecppack --compress $< $@

flash: build/x.bit build/y.bit
	python3 flash.py $(CHOOSE)
load: build/x.bit build/y.bit
	python3 flash.py --sram $(CHOOSE)
tables:
	python3 make_show.py
movie:
	python3 make_show.py --movie
sim:
	@mkdir -p renders
	cp rtl/*.hex sim/
	cd sim && iverilog -g2012 -I ../rtl -o tb_icepi.vvp tb_icepi.v $(addprefix ../rtl/,$(RTL)) \
	    && vvp -n tb_icepi.vvp | tail -4 && python3 render_icepi.py
clean:
	rm -rf build sim/*.hex sim/*.vvp sim/icepi_samples.txt

.PRECIOUS: build/%.json build/%.config
.PHONY: all flash load tables movie sim clean
