<!-- nav -->
[← Appendix B. Troubleshooting](B_troubleshooting.md#appendix-b-troubleshooting) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)**

# Appendix C. How this tutorial was tested

<img src="img/photo_stack.png" alt="The stack that every measurement in this tutorial was made on" width="280">

Every figure, transcript and number in the tutorial comes from the hardware,
except where this appendix says otherwise: the last section lists what was
not tested, and a figure's caption says "computed" or "simulated" when it
is.
The scripts that made the figures, the raw data, and the board-test tools are
in [`dev/`](../dev/), and [`dev/CLAUDE_CODE_CHAT.md`](../dev/CLAUDE_CODE_CHAT.md)
is the log of the Claude Code sessions that wrote and tested it all, prompt by
prompt.

## The instruments

The development setup had an ADALM2000 ("M2k") USB instrument wired to the
stack: the DAC output to scope channel 1, and the M2k's signal generator W1 to
the ADC input. Everything was driven from Python through ADI's `libm2k`. The
scripts that made the figures from live captures are in
[`dev/tools/`](../dev/tools/) (`m2k.py` is the instrument wrapper, `fig_*.py`
one per figure), and the raw data is in [`dev/data/`](../dev/data/).

- **DAC calibration**: the sawtooth, averaged over many periods at 100 MS/s and
  fitted with a straight line against code.
- **ADC calibration**: W1 stepped from −5 V to +5 V in 0.5 V steps, 16384
  samples averaged at each.
- **ADC quality**: sine captures at 1.1, 3.3 and 10.1 MHz, each fitted with a
  four-parameter least-squares sine. The residual was 0.46–0.62 codes rms, 5
  captures out of 5 at each frequency.
- **Lock-in**: the pass-band sweep of [1.08](1_08_lockin.md#108-a-lock-in-amplifier), and a 1 MHz ↔ 2.5 MHz frequency
  switch in simulation.

<details>
<summary>Three traps for anyone scripting an M2k</summary>

(1) The M2k's arbitrary waveform generator silently truncates a cyclic buffer
to a multiple of 4 samples, which leaves a phase jump each time it wraps. That
showed up as a one-sample glitch in about half of the ADC captures until the
buffer lengths were rounded to a multiple of 8. (2) By default `libm2k` queues
captures in kernel buffers, so `getSamples()` can return data from *before*
your last change; `setKernelBuffersCount(1)` fixes it. Before that fix, an
amplitude sweep appeared to lag by two steps. (3) `libm2k` is not on PyPI for
Linux, and its current version needs libiio ≥ 0.24 (Ubuntu 22.04 ships 0.23).
Both were built from source (libiio v0.25, then libm2k v0.9.1 with
`-DENABLE_PYTHON=ON -DINSTALL_UDEV_RULES=OFF`, swig from `pip install swig`).

</details>

The LiteX and Linux chapters were tested the same way, with the helpers in
`dev/tools/`: `serialboot.py` (litex_term's upload code without its keyboard
console, so it runs from a script), `console.py` (the [BIOS](https://en.wikipedia.org/wiki/BIOS) and firmware
prompts), `linux_shell.py` (logs in and runs commands on the board) and
`test_linux.py` (the Linux checks, with the M2k measuring the DAC).

- **LiteX peripherals**: every register through the BIOS's `mem_write` and
  `mem_read`; the amplitude register stepped 255 → 0 and checked on the M2k to
  within 1% of full scale; the four waveforms; free-running and triggered
  captures; lock-in readings against a 2 V input and down to 1 mV.
- **Linux**: `/dev/mem`; every [sysfs](https://en.wikipedia.org/wiki/Sysfs) file; `sweep.sh` and `dump.sh`; a module
  reloaded over the serial console.
- **Flash and SD card** ([3.04](3_04_booting_from_sd.md#304-booting-from-an-sd-card), a 64 GB SDXC card): the installer, end to end,
  twice; the boot from flash and card timed from the serial log three times,
  with `openFPGALoader -r` as t = 0, and the RAM-disk boot timed the same way;
  the trimmed start-up, and the driver and `sweep.sh` on the card-booted
  system.

**With a cable from the DAC to the ADC** (two RG-316 cables, 101.5 cm and
16.5 cm, and the M2k disconnected): `loopback` in all four modes with both
cables; lock-in sweeps from 100 kHz to 24.9 MHz in 100 kHz steps, 3 times with
each cable (the delays repeat to 0.05 ns); a 5-minute drift run (< 0.15 ns);
the firmware's `li` and `sweep` through the cable; and the oscillator exercise.
Then, for [4.01](4_01_a_faster_dac.md#401-a-faster-dac-plls), with the 16.5 cm cable: 3 new sweeps at 50 MS/s, which repeat
the earlier ones to 0.2% in amplitude and 0.13° in phase; 3 with
`lockin_pll` to 24.9 MHz; and 3 more from 25.1 to 49.9 MHz.

## Five boards

The tutorial was written on one Icepi Zero, and then repeated on four more,
built by JLCPCB from the same design with substitute passives, connectors and
buttons. Each passed: JTAG; the BIOS's `mem_test` over all 32 MB of SDRAM,
twice; a flash read-back, and configuration in quad mode at 62 MHz (3 of 3);
an SD card written and read back with matching checksums (190–215 kB/s write,
274–287 kB/s read); the serial boot of [3.01](3_01_booting_linux.md#301-booting-linux); and the boot from flash and card
(login at 60.9–61.7 s). Their crystals measured 2.8, 3.3, 1.7, 2.1 and 2.0 ppm
slow against [NTP](https://en.wikipedia.org/wiki/Network_Time_Protocol). The board-test designs and scripts are in
[`dev/tools/boardtest/`](../dev/tools/boardtest/).

Three of the JLCPCB boards then got headers and modules. On the first,
everything in Chapters 1–3 was repeated against the original board's
recordings, with only the ADC as an instrument: the counter (watched);
`sawtooth`, `sine` and `sine_pll` through the cable (195.3 kHz, and 1 MHz at
3.86 V); `loopback` in all four modes, identical to the original board's to
0.00–0.10 codes on average; lock-in sweeps at 50 and 100 MS/s, matching to
0.06–0.17% rms and 0.08° rms below 25 MHz; the firmware's `sweep`, matching to
0.02% up to 3.3 MHz; and the driver, `sweep.sh` and captures under Linux. Two
more measurements came from that board: the DAC from 50 to 200 MS/s under four
drive settings, and the ADC's data window at 31.25 and 25 MS/s
([`dev/tools/pinspeed/`](../dev/tools/pinspeed/)).

**Chapter 5** was done with three module boards: one pair cross-connected
(16.5 cm cables), and one looped back as a check. Every number and figure in
Chapter 5 comes from those runs; the raw data is in `dev/data/tb_*.npz`, and
the figure scripts are in `dev/tools/twoboard/`. Each experiment ran once, as
described, apart from these repeats: the 100 and 125 MS/s drive tests three
times; the two-clock beat at 60 s, at 15 minutes and for 5 hours overnight;
OFDM [QAM-64](https://en.wikipedia.org/wiki/Quadrature_amplitude_modulation) four times board to board; the modem at four baud rates both ways,
plus a text exchange; and the Linux modem twice on one board and once across
the pair. The modem's error rate against noise ([5.06](5_06_modem_and_noise.md#506-the-modem-against-noise)) was measured on the
looped-back board, all nineteen settings in one run. `modem_sync.v` was
measured once at eight noise levels (`dev/tools/twoboard/fsk_sync_run.py`),
each time after 400 bytes of 0x55 for its bit clock to lock to. The next
morning every Chapter 5 script was run once more, briefly, on the pair
(`dev/tools/twoboard/smoke_pair.sh`), and all of them still worked as printed.

**Five cards at once.** Finally, all five boards got new 16 GB cards with the
same Linux build, installed by `dev/tools/boardtest/sd_provision.py`, one
process per board. Each board then booted from its card seven times. After
every boot the script checked the root device, that the driver had loaded, and
the serial link both ways, with 32 kB of random data from the board and 4 kB
typed in, each compared by MD5. All 35 boots passed, 57.5–60.1 s from reset to
`login:`.

## Moving to SystemVerilog, and to this repository

The tutorial was first written in Verilog, as one long page. When it moved
here, every design was converted to SystemVerilog, and each conversion was
checked against the Verilog that had been tested on the hardware:

- **Proven equivalent** with Yosys's formal equivalence checker
  (`equiv_make`, `equiv_simple`, `equiv_induct`): `counter`, `sawtooth`,
  `sine`, `sine_pll` (with the PLL replaced by a model), both halves of
  `uart`, `capture`, `loopback`, `lockin`, `lockin_pll`, the four LiteX cores
  and `awgcap`. (The designs with 16 kB memories were proven with the memory
  shrunk to 16 entries, the same way in both versions.) A deliberately
  altered design failed the check, as it should.
- **Simulated side by side** with the same random inputs for 300,000 clocks,
  every output compared on every clock: `modem`, `modem_noise` (three sets of
  parameters), `pll` and `warmup`, whose arithmetic was too big for the
  formal check. No output differed. A deliberately altered `modem` differed on
  64% of clocks.
- **The testbenches** print exactly what the Verilog ones printed.
- **On the hardware** (one board, through a 101.5 cm cable): `capture`;
  `loopback` in all four modes (the step returns 6 samples later, as before);
  `lockin` (216.73 ns through the long cable, against 216.6 ns before) and
  `lockin_pll` (9.5 ns less); the LiteX SoC rebuilt with the SystemVerilog
  cores, with the firmware's `fg`, `li`, `sweep` and `cap`; the Linux SoC,
  rebuilt; and OFDM and the lock-in beat on one looped-back board ([6.07](6_07_ofdm.md#607-ofdm-the-triumph-of-physics-over-math), [5.01](5_01_two_clocks.md#501-two-clocks)).

New in this version, and tested on the hardware: `adc_stream.sv` and
`stream.py` ([1.05](1_05_adc_to_python.md#105-adc-samples-to-python)); the figures of [1.08](1_08_lockin.md#108-a-lock-in-amplifier)'s "The idea", from samples that
`awgcap.sv` recorded through the 101.5 cm cable (three records of each
waveform, which agree to 0.1%); the stock LiteX SoC, its BIOS and `primes` ([2.01](2_01_a_cpu_and_its_bios.md#201-a-cpu-and-its-bios), [2.02](2_02_c_on_the_cpu.md#202-c-on-the-cpu)); and a
new Linux build with the LEDs in `/sys/class/leds`, built from this
repository's files with a fresh [Buildroot](https://en.wikipedia.org/wiki/Buildroot) output folder and a fresh clone of
linux-on-litex-vexriscv. Its files in `src/linux/prebuilt/` were serial-booted
(`images/` and `install/`), and the LEDs, the driver, `sweep.sh` and a capture
were checked. The LEDs were checked by reading the LED register back with
`devmem`, not by watching them.

## Added later, and how each was checked

All on JLC 2, looped back through the 101.5 cm cable:

- **The lock-in's cosine convention ([1.08](1_08_lockin.md#108-a-lock-in-amplifier)).** Only names and comments changed
  in `lockin.sv`, `lockin_pll.sv` and `lockin_core.sv`: with the comments
  removed and the old names put back, each file is token for token the one
  that was tested. `lockin_tb.sv` prints what it did before. The figures were
  redrawn from the same recorded samples, and give the same numbers.
- **GPS's G1 in `loopback.sv` ([1.07](1_07_closing_the_loop.md#107-closing-the-loop-the-dac-talks-to-the-adc)).** G1 combined with GPS's G2 register
  reproduces the published first ten chips of the C/A codes of PRN 1 to 4.
  In simulation the DAC plays G1 chip for chip; on the board, the impulse
  response was measured four times (h[6] = 0.74, the same 6-sample delay).
- **`spectrum.py` ([1.09](1_09_spectrum_analyzer.md#109-a-spectrum-analyzer))**, on 64 records of `loopback.sv`'s square wave.
- **`fft.sv` ([1.09](1_09_spectrum_analyzer.md#109-a-spectrum-analyzer)).** In simulation, `fft_check.py`'s eight signals give
  exactly the numbers of a numpy model of the same integer arithmetic. On the
  board, its own square wave, with the harmonics compared against their
  [Fourier series](https://en.wikipedia.org/wiki/Fourier_series).
- **`radio.sv` ([5.07](5_07_radio_link.md#507-a-radio-link))**, simulated at 9600 and 19,200 baud, then on the board
  with `modem_ber.py`: 0 errors in 80,000 bits at 4800, 9600 and 19,200 baud,
  and at 9600 baud with the transmitter at 8, 2 and 1 DAC codes.
- **[5.03](5_03_time_transfer.md#503-what-time-is-it-over-there)'s figures:** one board measuring its own loop, five times
  (217.596 ± 0.005 ns).
- **The [1.01](1_01_led_counter.md#101-a-counter-on-the-leds) and [1.04](1_04_adc_on_the_leds.md#104-the-adc-on-the-leds) animations** are Verilator simulations of `counter.sv`
  and `adc_leds.sv`, drawn on a 3D render of the Icepi Zero's own KiCad
  design.
- **The tools in `$ADDA/tools/` ([1.00](1_00_circuits_from_code.md#100-circuits-from-code), [2.00](2_00_a_processor_on_the_fpga.md#200-a-processor-on-the-fpga), [3.03](3_03_building_linux.md#303-building-linux-yourself)):** only the driver's
  Makefile was tried with the new default path, against the existing
  Buildroot output; it built an `adda.ko` identical to the one in the root
  file system.

Later still:

- **`stream.py --play`** ([1.05](1_05_adc_to_python.md#105-adc-samples-to-python)): music from a phone, played back through the
  laptop's speaker, by the tutorial's author.
- **`fft.sv`'s `q` command** ([1.09](1_09_spectrum_analyzer.md#109-a-spectrum-analyzer)): `fft_check.py`'s eight signals still match
  the numpy model exactly; on the board, with the DAC quiet the biggest peak
  through the cable fell from +11.4 to −79 dB re 1 V.
- **`am_radio.sv`** ([1.10](1_10_am_radio.md#110-an-am-radio)): in simulation, `am_check.py` compared every receiver output
  sample of 50 runs with a numpy model of the same arithmetic: all equal.
  On the board, through the 101.5 cm cable: the carrier arrives at 53.7 ADC
  codes, the test tone at 1000.0 Hz and 56.2% of the carrier, the melody's
  31 notes in the right order (the spectrogram at the top of [1.10](1_10_am_radio.md#110-an-am-radio)), 59 dB
  less of it tuned 10 kHz away, and the selectivity of a bare carrier from
  −30 to +30 kHz. Not tried: a real AM radio, and an antenna.
- **The section names and links.** When the sections were renumbered (`1.8`
  became `1i`, then `1.06`, with files `1_06_fast_capture.md`), every reference to a section in the text, the code and the scripts
  was listed and checked by hand before it was changed, so that times like
  "1.7 s" stayed numbers. `dev/tools/check_tutorial.py` (`make check`) now
  checks every link, anchor and picture on every page.
- **The [UART](https://en.wikipedia.org/wiki/Universal_asynchronous_receiver-transmitter) bridge** ([2.06](2_06_registers_from_the_laptop.md#206-the-registers-from-the-laptop)): built with `--uart-name=crossover+uartbone` (69 s) and run on
  one board through the 101.5 cm cable: `litex_cli --ident` and `--regs`,
  `remote.py` (3.850 V at 1 MHz, against the firmware's 3.85 V; the 16 kB
  capture read back in 1.5 s), and `litex_term crossover` reaching the BIOS
  (`mem_read` of `ctrl_scratch`: 0x12345678).
- **The LFSR figures** ([1.07](1_07_closing_the_loop.md#107-closing-the-loop-the-dac-talks-to-the-adc)) are computed, not measured: `fig_lfsr.py` steps
  `loopback.sv`'s own expression, checks it against `loopback.py`'s copy, and
  checks that the register visits all 1023 non-zero states once per cycle.
- **MicroPython** ([3.01](3_01_booting_linux.md#301-booting-linux), [3.02](3_02_a_driver.md#302-a-driver)): Buildroot added it in 2 minutes, and
  `rootfs.cpio.gz` grew from 1.18 to 1.54 MB. Serial-booted on two boards. On
  the one with the converters, through the 101.5 cm cable, the REPL's
  `machine.mem32` set the function generator to 2 MHz (the driver read back
  2000000.001 Hz), and `micropython sweep.py` agreed with `sweep.sh` to the
  fourth digit up to 3 MHz.
- **`install-sd.sh` with the current build** (with MicroPython), on the second
  board's 15 GB card: serial-booted from `install/` (upload 5 min 53 s), the
  installer took 5 min 54 s, and the card then booted to `login:` 86.4 s
  after the bitstream loaded. (That board's kernel didn't find the card at
  first, a timeout, and found it when asked again: Appendix B has the fix.)
- **Chapter 6, the first night** ([6.01](6_01_eye_diagrams.md#601-eye-diagrams-and-pulse-shaping), [6.02](6_02_psk_and_qpsk.md#602-psk-and-qpsk-finding-the-clock-and-the-carrier) and [6.06](6_06_spread_spectrum.md#606-spread-spectrum-the-gps-way)): every script and figure was first checked on
  `channel.py`'s model, then run on one board through the 101.5 cm cable:
  `psk.py` ([QPSK](https://en.wikipedia.org/wiki/Phase-shift_keying#Quadrature_phase-shift_keying_(QPSK)), BPSK, differential, and with the carrier and symbol-rate
  offsets of `--cfo 3000 --sro 2000`, found to within 7 Hz and 3 ppm: 0
  errors in each), the bit-error-rate sweep (within about 1 dB of theory from
  0 to 8 dB), `eye.py`, `cdma.py` (the two users' delays 300.42 chips apart,
  against 300.40 sent; 0 errors), and the detector characteristics (Gardner's
  slope 1.08 per symbol, against 1.07 per symbol). Only `comms_eye_slow.png` (it needs a low-pass
  filter in the cable) and the model comparison `comms_channel.png` are not
  measurements of the board.

- **Chapter 6, the second night** ([6.03](6_03_qam.md#603-qam-more-bits-per-symbol), [6.04](6_04_msk_and_gmsk.md#604-msk-and-gmsk-constant-envelope), [6.05](6_05_the_channel.md#605-the-channel-sounding-it-and-equalizing-it), [6.08](6_08_shannons_limit.md#608-shannons-limit-and-how-far-from-it-you-are)–[6.12](6_12_on_the_air.md#612-on-the-air-whispers-and-how-far-they-carry)): the
  same way, model first, then one board through the cable. [6.02](6_02_psk_and_qpsk.md#602-psk-and-qpsk-finding-the-clock-and-the-carrier)'s
  frequency-locked loop pulled in offsets of 100 kHz and 24 kHz at 6 dB;
  `qam.py` read MERs of 38.2, 34.9 and 34.5 dB for 8PSK, 16-QAM and 64-QAM,
  and the error-rate sweep (20 records a point) crossed 10<sup>−4</sup> at 8.5,
  12.6 and 17.5 dB against the theory's 8.4, 12.2 and 16.5; `msk.py`'s coherent
  receiver sat on BPSK's curve (4.38 dB at 10<sup>−2</sup> against 4.32), and the
  plain run that once showed 130 errors passed three times out of three
  afterwards; `sound.py` found the cable's main tap at 0.786 and 0.760 from
  the step and the [m-sequence](https://en.wikipedia.org/wiki/Maximum_length_sequence), `equalize.py` cleared the simulated echo;
  `ecc.py`'s sweep (100 records a point) gave coding gains at 10<sup>−4</sup> of
  −0.1, 1.1, 2.4 and 4.8 dB with the uncoded points on theory, and the 40-symbol dropout 0 errors with the
  interleaver against 15 to 17 without (the first receiver did not acquire
  the carrier phase feed-forward and read 21.7 dB on the cable; with the
  fourth-power estimate added it reads 42.2 dB, and the sweep was re-run); `capacity.py` is theory plus
  [6.07](6_07_ofdm.md#607-ofdm-the-triumph-of-physics-over-math)'s numbers, and `fig_capacity.py` measured QPSK's MER of 38.3 dB.
  [6.10](6_10_chirps_and_lora.md#610-chirps-zadoffchu-and-lora-ranging-and-radar-on-a-cable)'s `chirp.py` and `lora.py` and their figures were run on the board
  after the model (`comms_radar.png` stays simulated: there is no T and
  stub). [6.11](6_11_the_modem_in_the_fpga.md#611-the-modem-in-the-fpga)'s `qpsk_modem.sv` passed its bit-for-bit check against the
  model in iverilog (5624 symbols, 2000 ppm and 3 kHz off); its first board
  run lost one byte in 250 (the output serial port two clocks slower than
  the input: found and fixed in simulation, [6.11](6_11_the_modem_in_the_fpga.md#611-the-modem-in-the-fpga) tells the story); the
  fixed bitstream then carried 20,000 and 200,000 bytes through the cable
  with no errors. [6.12](6_12_on_the_air.md#612-on-the-air-whispers-and-how-far-they-carry)'s `ft8.py` decoded through the cable
  at both speeds; `ddc.sv` passed its testbench before the board. Only the
  diagrams (`comms_d_*.png`), `comms_pulses.png`, `comms_capacity.png`'s left
  panel and `comms_modem_fpga.png` (the FPGA's loops can't be read out from
  the board) are computed rather than measured.

- **Chapter 7** ([7.01](7_01_fir_filters.md#701-fir-filters-the-sliding-dot-product)–[7.07](7_07_bigger_ideas.md#707-bigger-ideas-nmr-mri-and-qubits), the morning of 2026-10-04): the bench
  had changed to the ADALM2000 (its W1 into ADC IN, DAC OUT on its scope
  channel 1, no loopback cable), so everything in this chapter was measured
  that way, through libm2k. Every design was simulated in iverilog against
  a Python model first (`make sim-fir`, `sim-iir`, `sim-filter`, `sim-control`,
  `make sim` for the delta-sigma gateware; `filter_core_tb.sv` for [7.04](7_04_the_filter_as_a_litex_peripheral.md#704-the-filter-as-a-litex-peripheral);
  bit-exact where a model exists), then built, then run: [7.01](7_01_fir_filters.md#701-fir-filters-the-sliding-dot-product)'s and
  [7.02](7_02_iir_filters.md#702-iir-filters-feedback-and-an-rc-in-one-line)'s fixed bitstreams on a 300 kHz square wave (the scope traces);
  [7.03](7_03_a_filter_you_can_load.md#703-a-filter-you-can-load)'s `filter.py --m2k` sweeps for the moving average, the low-pass,
  the edge detector and the one-pole (0.25, 0.91, 0.12 and 0.06 dB rms from
  scipy) and its `--impulse`; [7.04](7_04_the_filter_as_a_litex_peripheral.md#704-the-filter-as-a-litex-peripheral)'s SoC over LiteX's bridge, loading
  three filters and reading the DAC on the scope (seven points, all within
  0.5 dB of the design); [7.05](7_05_trading_speed_for_bits.md#705-trading-speed-for-bits)'s `sigma_delta.py --m2k --table` and
  `oversample_adc.py --m2k` (both `--dc` too), and the gateware's four modes
  on the scope. Not measured: [7.03](7_03_a_filter_you_can_load.md#703-a-filter-you-can-load)'s `--measure` loopback path, [7.04](7_04_the_filter_as_a_litex_peripheral.md#704-the-filter-as-a-litex-peripheral)'s
  firmware and MicroPython loaders (built, not run: the firmware's expected
  codes are predictions, and the filter is not in the prebuilt Linux
  bitstream), the two-board VNA, [7.05](7_05_trading_speed_for_bits.md#705-trading-speed-for-bits)'s CIC readback and everything the
  loopback cable would allow, and [7.06](7_06_control.md#706-control-at-the-speed-of-the-cable)'s mode 0 (the cable as the plant: the
  loop-delay measurement that is the page's point); its modes 1 and 2 were
  measured on the M2k bench (critical gain 4.25 at 1.10 MHz against the
  model's 4.39, 16.5 against 16 without the extra delay, −18 dB of
  rejection at 5 kHz, the sensitivity function on the model's curve),
  after a first bitstream that did nothing: Yosys synthesized a negated
  size cast with the wrong sign, which every RTL testbench had evaluated
  correctly; a gate-level replay of the laptop's bytes found it (the page
  tells the story). [7.07](7_07_bigger_ideas.md#707-bigger-ideas-nmr-mri-and-qubits) is priced, not built.

## Not tested

- **The instructions for macOS and Windows (WSL)**, and the Apio / VS Code
  route of [1.00](1_00_circuits_from_code.md#100-circuits-from-code). Everything here was done on Linux (Ubuntu 22.04).
- **`sdcard.img.xz` written to a card.** Its partition table and both file
  systems were checked on the laptop, and its files are the ones the serial
  boot tested, but no card has been written from it and booted.
- **`adc_leds.sv`'s LEDs** were not watched. Its ADC logic is the same as
  `adc_stream.sv`'s, which was tested.
- **Measuring a filter** ([1.08](1_08_lockin.md#108-a-lock-in-amplifier)): no filter was at hand. The cable measurement
  uses the same code and procedure.
- **The LED indicators of [1.06](1_06_fast_capture.md#106-fast-captures) and [1.08](1_08_lockin.md#108-a-lock-in-amplifier).** Only the [1.01](1_01_led_counter.md#101-a-counter-on-the-leds) counter was watched (it
  runs MSB-left with the USB connectors down).
- **`sine_pll` on a scope** (the M2k was disconnected by then). The same PLL,
  DDS and DAC timing were measured through `lockin_pll`.
- **A true power-on boot.** The boot times start at `openFPGALoader -r`,
  which makes the FPGA reload itself from flash as it does at power-up.
- **The open-ended "Try this" suggestions**, except the loop oscillator, the
  lock-in above 12.5 MHz, and the quad-SPI bitstream, which were.
- **The DAC above 200 MS/s, the ADC above 31.25 MS/s**, and drive settings
  other than the four in `dev/tools/pinspeed/`. Nor were the faster rates
  built into the tutorial's designs.
- **A fresh install into `$ADDA/tools/`**, following [1.00](1_00_circuits_from_code.md#100-circuits-from-code), [2.00](2_00_a_processor_on_the_fpga.md#200-a-processor-on-the-fpga) and [3.03](3_03_building_linux.md#303-building-linux-yourself) from
  the start. The tools used here were installed earlier, in another folder.
- **`stream.py`'s `--bits`, `--keep` and `--reverse`** ([1.05](1_05_adc_to_python.md#105-adc-samples-to-python)) were checked on a
  computed test tone (the aliased tone lands where it should), not yet by ear.
- **Chapter 6 with two boards** ([6.07](6_07_ofdm.md#607-ofdm-the-triumph-of-physics-over-math)'s OFDM was run board to board, above), and
  the RF parts of [6.00](6_00_digital_communications.md#600-digital-communications-hardware-defined-radio). For every other script, two boards were only simulated
  (`--sim --ppm`).
- **HDMI and the USB host** ([3.04](3_04_booting_from_sd.md#a-computer-of-its-own)): described from linux-on-litex-vexriscv's
  configurations for other boards, not built for this one.
- **[5.07](5_07_radio_link.md#507-a-radio-link)'s antennas.** The loops, the range and the field-strength estimates
  are calculations; `radio.sv` was tested only through a cable.
- **[7.03](7_03_a_filter_you_can_load.md#703-a-filter-you-can-load)'s `--measure` path** through the loopback cable: the impulse
  mode returns the taps to the ADC's resolution but one tap late, and the
  step and noise modes return zeros; the alignment code is wrong and the
  `--m2k` sweeps are the measurements the pages use.
- **[7.04](7_04_the_filter_as_a_litex_peripheral.md#704-the-filter-as-a-litex-peripheral)'s firmware and MicroPython loaders**, and the Linux SoC with the
  filter (not rebuilt).
- **[7.07](7_07_bigger_ideas.md#707-bigger-ideas-nmr-mri-and-qubits)**: nothing on it has been built; the TeachSpin connections are
  read from its manual.
- **[6.12](6_12_on_the_air.md#612-on-the-air-whispers-and-how-far-they-carry)'s air.** Every rung of the antenna ladder is a calculation
  (`air.py`), the frame has only gone through the cable, and the ADC module's
  input impedance, which the [near-field](https://en.wikipedia.org/wiki/Near_and_far_field) rungs depend on, has not been
  measured.
- **[6.10](6_10_chirps_and_lora.md#610-chirps-zadoffchu-and-lora-ranging-and-radar-on-a-cable)'s radar.** The stub's echo is modelled (there is no T); the
  [chirp](https://en.wikipedia.org/wiki/Chirp), Zadoff–Chu and ranging figures are measured through the plain cable.
- **The experiments of [4.02](4_02_rc_and_lc_circuits.md#402-rc-and-lc-circuits)–[4.09](4_09_your_crystal.md#409-your-crystal-against-a-reference).** Their numbers are calculations, not
  measurements, except the crystal-against-NTP timing of [4.09](4_09_your_crystal.md#409-your-crystal-against-a-reference) and the baseline
  of [4.04](4_04_harmonics.md#404-harmonics-a-diode-clipper) (the loop's own harmonics).

<!-- nav -->
[← Appendix B. Troubleshooting](B_troubleshooting.md#appendix-b-troubleshooting) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)**

<!-- author -->
<sub>Jason Gallicchio, jason@hmc.edu, Harvey Mudd College</sub>
