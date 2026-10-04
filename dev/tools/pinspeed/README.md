# pinspeed: how fast the converter pins go (Prompt 6, second JLCPCB board)

Two experiments with the DAC cabled to the ADC (16.5 cm RG-316), no other instrument.

**Drive strength** (`drive_*.py`): the DAC plays a DDS sine (1.1 or 10.1 MHz) from a PLL at
50/100/125/150/200 MS/s, with four `DRIVE`/`SLEWRATE` settings on `dac_d` and `dac_clk`;
the tutorial's `capture.sv` records it at 25 MS/s.  `drive_build.py` writes and builds every
variant (one bitstream each), `drive_run.py` loads each and captures 4 x 16384 samples,
`drive_rerun.py` repeats a subset, `drive_analyze.py` prints SNR/THD/spurs from
`../../data/pinspeed_drive.npz`.

**ADC eye** (`adceye.v`, `eye_*.py`): one 125 MHz PLL domain; DAC at 62.5 MS/s; the ADC clocked
at 31.25 or 25 MHz by a second PLL output shifted by 0/2/4/6 ns; the ADC pins sampled on every
125 MHz edge, so each ADC sample is seen at 4 (or 5) points 8 ns apart.  `eye_analyze.py`
scores each point (SINAD, samples more than 8 codes off) from `../../data/pinspeed_eye.npz`.

The build/run scripts write into the current directory and expect the tutorial's
`capture.sv`, `uart.sv` and `icepi_adda.lpf` two levels up.  Results: `IcepiZeroADCDAC_gateware.md`,
Response 6.
