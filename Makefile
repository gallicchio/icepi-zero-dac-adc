# The repository's top level.  Each folder under src/ has its own Makefile, used by the
# tutorial's pages; this one runs them all, and checks the tutorial.
#
#   make check       the tutorial's integrity (dev/tools/check_tutorial.py): the code on
#                    every page matches the file in src/, every link and picture exists,
#                    every section named in the text is a link, ...
#   make sync        copy the files from src/ into the pages, and redo the navigation
#   make bitstreams  every design of Chapters 1, 4 and 5 (needs the OSS CAD Suite, 1a)

VERILOG  = counter sawtooth sine adc_leds adc_stream capture loopback lockin \
           sine_pll lockin_pll fft am_radio
TWOBOARD = awgcap modem pll warmup radio

.PHONY: check sync bitstreams
check:
	python3 dev/tools/check_tutorial.py
sync:
	python3 dev/tools/sync_md.py
bitstreams:
	$(MAKE) -C src/verilog $(addsuffix .bit,$(VERILOG))
	$(MAKE) -C src/twoboard $(addsuffix .bit,$(TWOBOARD))
