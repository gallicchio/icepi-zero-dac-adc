# IcePi Zero ADC DAC gateware

## Prompt 1

I made the adapter PCB from an IcePi Zero to the "AD9280 AD9708 Data Acquisition Board" 2x20 variant as described in `$HOME/OpticsPCBs/IcepiZeroADCDAC`. An IcePi Zero is currently plugged in to USB, with the adapter board and the "AD9280 AD9708 Data Acquisition Board" stacked on top of it. The open source toolchain is installed in `$HOME/openfpga` as described by `./README.md`.

Also plugged in to USB is an ADALM2000 (M2k). The Data Acquisition Board's:

* DAC is connected to the M2k's CH1
* ADC is connected to the M2k's W1

Your goal is to work as long as it takes on a series of tutorials geared toward a Junior-level Physics-major electronics lab class. These students will know the basics of analog and digital electronics, and they will have taken a class in fourier analysis, but they have never used FPGAs or Verilog. The tutorials should be self-contained in a new .md file in this directory. I'll list some things I'd like to see, but they can be rearranged, split, or combined for 

* First explain how to setup the ECP5 FPGA toolchain as simply as possible with a VScode extension that I hear makes this easy. This is the only part you will not test.
* Simple "bare" single-file verilog that creates a simple binary counter on the white LEDs --- a simplified version of what's in `./README.md`
* Simple "bare" verilog that outputs an interesting waveform like a sine out of the DAC.
* Simple verilog to capture a reasonable number samples from the ADC and somehow get them to the computer. If serial port is the best way, use that.
* Simple verilog that does a simple lock-in, where real and imaginary parts are reported over the serial port. If the student only get this far, they can run a series of these measurements on a filter or can do a measurement of the length of a cable.
* A LiteX peripheral that is a function generator, outputing at least a sine wave of a specified frequency. This probably needs to be driven by a bare-metal C program for vexriscv.
* A LiteX peripheral for doing an ADC capture.
* A LiteX peripheral for a lock-in measurement.
* The LiteX peripherals controlled under linux-on-litex-vexriscv in some very Linux-friendly way.

You should use the M2k to debug as you go along. Avoid stopping and asking me questions or changing the cabling unless absolutely necessary (or something is not working).

As you make the tutorial document, log your responses here in this document as a record of what I asked you to do and what you did.

Include some plots in the tutorial, with times and voltages and samples evident.

## Response 1 2026-09-28 21:53:00 - 2026-09-29 00:10:00 Claude Opus 5.5 Extra High

### Short version

The tutorial is [`IcepiZeroADCDAC_tutorials.md`](IcepiZeroADCDAC_tutorials.md): eight parts
plus two appendices, every source file printed in full, and seven figures made from live
ADALM2000 captures. The same files, tested, are in
[`IcepiZeroADCDAC_tutorials/`](IcepiZeroADCDAC_tutorials/). `tools/sync_md.py --check` confirms
that every code block in the `.md` is byte-identical to its file.

| part | what | tested on the hardware? |
| --- | --- | --- |
| 0 | OSS CAD Suite through VS Code + **Apio IDE** (`fpgawars.apio`, which knows `icepi-zero`), plus the by-hand way | no, as you asked |
| 1 | `counter.v`: binary counter on the 5 LEDs | builds and loads; LEDs not watched (I can't see them) |
| 2 | `sawtooth.v` (counter → DAC), `sine.v` (DDS, table computed by Yosys with `$sin`) | yes: M2k, 1 MHz measured 999,997 Hz, 3.84 V, harmonics ≤ −46 dBc |
| 3 | `capture.v` + `uart.v` + `capture.py`: 16384 samples, 25 MS/s ÷ 2^D, 1 Mbaud, 0.23 s per capture | yes: DC calibration sweep, sines at 1.1/3.3/10.1 MHz (ENOB ≈ 7), aliasing demo |
| 4 | `lockin.v` + `lockin.py`: coherent lock-in, 2^20-sample average, X/Y as hex text | yes, in simulation and against the M2k's W1; see "not tested" below |
| 5 | LiteX SoC (`icepi_adda_soc.py`) + function-generator peripheral + bare-metal C shell (`fg`) | yes: registers via BIOS `mem_write`, 4 waveforms, amplitude |
| 6 | capture peripheral: 16 kB Wishbone window, decimation, trigger (`cap`, `dump`, `cap_plot.py`) | yes, including triggered captures lining up |
| 7 | lock-in peripheral, referenced to the function generator's phase (`li`, `sweep`) | yes, down to 1 mV input |
| 8 | Linux 6.12 (Buildroot, musl) on VexRiscv-SMP; `/dev/mem`; a kernel driver `adda.ko` giving `funcgen/`, `capture/`, `lockin/` directories in sysfs | yes: every sysfs file, `sweep.sh`, `dump.sh`, `insmod`/`rmmod`, a module pasted over the console |

**Not tested, and the one thing I'd ask you to do:** Part 4's actual *measurements*, a
filter and a cable, need the DAC's output wired to the ADC's input. Your cabling has the
M2k in both paths, and you asked me not to change it, so I verified the lock-in two other
ways: in simulation, where a delayed, halved loopback gave the right amplitude and a phase
that is a pure delay; and on hardware against W1, which gave the right amplitude, the
rotating phasor, the sinc pass band with nulls at 23.8 Hz, and the crosstalk floor. A coax
from DAC to ADC, then a 1 kΩ/1 nF RC in the middle, is the one experiment in the document
that hasn't been run end to end. Appendix B lists this, and the other small untested items:
the LEDs, and booting Linux from an SD card.

### Measured, and now in the tutorial's hardware table

- DAC: V = 0.0307·code − 3.95 (−3.95 V … +3.88 V into 1 MΩ); ADC: code = 126.7 + 25.35·V (±5 V, 39.5 mV/code).
- The Icepi Zero's crystal is 2.8 ppm slow relative to the M2k's. The DAC and ADC measurements agree on that independently.
- DAC → ADC crosstalk seen by the lock-in: −99 dB at 10 kHz, −77 dB at 1 MHz, −48 dB at 12 MHz (bare `lockin.v`); 0.9 mV at 100 kHz in the LiteX SoC.

### Problems found along the way (all fixed, and most written into the tutorial)

1. **Opening `/dev/ttyUSB0` makes the FPGA receive a junk byte** (0xFF), which the first
   `capture.v` took as "capture with D = 15" (21 s). The command is now a hex digit.
2. **The M2k's AWG truncates cyclic buffers to a multiple of 4 samples**, which put a phase
   jump at every wrap and a one-sample glitch in about half the ADC captures.
3. **libm2k returns stale captures** unless `setKernelBuffersCount(1)` is set.
4. **The capture trigger fired immediately** on a re-arm, because it compared against the
   previous capture's last sample. Fixed in `adc_capture_core.v`.
5. **LiteX's default libc is minimal** (no `atoi`/`strtok`/libm): the SoC is built with
   `--libc-mode full`. Its compiler runtime also lacks `__floatdisf`, so the firmware
   shifts 64-bit sums down before converting to float.
6. **Buildroot 2026.02's glibc 2.42 crashes in its dynamic loader on VexRiscv** before
   `init` runs (kernel panic). The 2022 images' glibc 2.34 is fine. I switched to musl,
   which works and cut the compressed rootfs from 5.0 MB to 1.2 MB, together with dropping
   `pppd` and its 6 MB of OpenSSL. A serial boot is now 4 minutes at 460800.
7. **Buildroot's post-image script replaces `linux-on-litex-vexriscv/images/`** with
   symlinks to its own output, which silently replaces the stock images. My defconfig turns
   it off and uses `images_adda/` instead.
8. **The device tree records the rootfs size** (`linux,initrd-end`), taken from whatever was
   in `images/` at build time. `make_linux.py` now sizes it from `images_adda/`.
9. **kbuild's `make clean` deletes every `.ko` below the module directory**, including the
   rootfs overlay's copy, so the driver moved to `linux/driver/`.
10. **A driver bug (my own) oopsed the kernel**: bin-attribute callbacks get the *device's*
    kobject even inside a named group. Fixed, retested.
11. **BusyBox `awk` had no maths**: a BusyBox config fragment turns `CONFIG_FEATURE_AWK_LIBM` on.
12. **The 2021 kernel drops console characters** sent faster than a person types
    (most likely because it polls the UART's small receive FIFO; the 6.12 patch set adds
    RX interrupts). The helper scripts type in small pieces.

### Files

In `IcepiZeroADCDAC_tutorials/`:

- **Parts 1–4 (bare Verilog):** `icepi_adda.lpf` (one constraints file for all),
  `counter.v`, `sawtooth.v`, `sine.v`, `uart.v`, `capture.v`, `capture.py`, `lockin.v`,
  `lockin.py`, `capture_tb.v`, `lockin_tb.v`. The `Makefile` does `make load-NAME` and
  `make sim-NAME`.
- **Parts 5–7 (`litex/`):** four Verilog cores; `adda_litex.py` (the LiteX wrappers and
  `add_adda()`); `icepi_adda_soc.py`; `firmware/`; `cap_plot.py`; `make_linux.py`.
- **Part 8 (`linux/`):** a Buildroot external tree (`configs/icepi_adda_defconfig`, the
  kernel and BusyBox fragments, `rootfs_overlay/`) and `driver/adda.c`.
- **`tools/`** is the instructor's kit, not for students:
  - `m2k.py`, a libm2k wrapper with an exact-frequency AWG and a 4-parameter sine fit;
  - `fig_*.py`, one script per figure, with `--replot` to redraw from `data/`;
  - `serialboot.py`, `console.py`, `linux_shell.py` and `test_linux.py`, to script the
    BIOS, the firmware and Linux;
  - `sync_md.py`, which checks the document against the files.

### Changes outside this repository

- `~/.local`:
  - `swig` and `patchelf`, via `pip --user`;
  - **libiio 0.25** and **libm2k 0.9.1** with its Python bindings, built from source in
    `~/openfpga/libiio-0.25` and `~/openfpga/libm2k`. The system's libiio 0.23 is too old
    for libm2k and was left alone. `import libm2k` works from both `/usr/bin/python3` and
    this repo's `.venv`.
- `~/openfpga/buildroot`: a clone checked out at `2026.02.3`.
  `~/openfpga/buildroot-icepi/`: its output, 8.2 GB, deletable.
- `~/openfpga/linux-on-litex-vexriscv`:
  - new: `build/icepi_zero_adda/`, `images_adda/` (our Linux) and `images_stock_adda/`
    (the 2022 images plus our device tree, used to test `/dev/mem`);
  - `images/` was restored to the stock 2022 files after Buildroot's post-image script had
    turned them into symlinks. Restored means re-extracted from `linux_2022_03_23.zip`,
    `gzip -k`, and `rv32.dtb` copied back from `build/icepi_zero/`.
- `~/OpticsPCBs` is untouched. Nothing is committed.
- The board is currently running the Part 5–7 LiteX SoC (SRAM only), and W1 is idle.

## Prompt 2

There is an approximately 1-meter long SMA cable going from DAC to ADC. The M2k is out of the loop and off.

First, test the LED counter. I think I saw this working as you were writing it. The natural way to orient the Icepi Zero is with the USB connectors down, which is how it's oriented in nearly all photos online. Your binary counter may have its LSB on the left and MSB on the right in this configuration, which would not be satisfying to students. Set up the hardware as the counter and then pause. I'll tell you which one is the LSB and MSB. After I tell you the answer, make it count with the MSB on the left when you look at it with the USB ports down. If you change something, be sure to change it in both the files that will get checked in and inline in the tutorial. Check if changing the LED mapping for the counter will affect other sections in the tutorial.

Then do a lage number of tests to characterize the DAC -> ADC link through the SMA cable. I have no other filter to test today, so do what you can with the cable. I also have what looks like a 20cm SMA cable that I can swap for the 1-meter cable later. One part of the tutorial could be to take a careful sweep and measure the length or other properties of the cable. I'd also like to know the latency in the limit of a zero-length cable: low long does it take a new DAC value to show up at the ADC?

Finally, come up with other suggestions of things to test or things to add as extensions to this tutorial. If I have the hardware here, we do test those tonight, otherwise it will have to wait.

## Response 2 2026-09-29 20:25:00 - 2026-09-29 21:25:00 Claude Opus 5.5 Extra High

### Short version

- **LED counter:** fixed. You confirmed it ran LSB-left with the USB connectors down. I
  renumbered the LEDs in `icepi_adda.lpf` (E13, the leftmost, is now `led[4]`), and you
  confirmed it now counts MSB-left. `counter.v` itself is unchanged. The only other effect
  is which physical LED shows which indicator in `capture.v` and `lockin.v`; both sources'
  comments and the tutorial were updated. The LiteX parts use LiteX's own numbering (bit 0
  leftmost), and the Part 5 exercise now warns about that.
- **The cable:** 101.5 cm and 16.5 cm of RG-316. The lock-in gives **3.89 ns for the extra
  85.0 cm: 4.58 ns/m, velocity factor 0.73** (datasheet 0.695). It repeats to 0.05 ns
  between sweeps and drifted < 0.15 ns in 5 minutes. The details and the reasons for the
  5% are below, and in the tutorial's Part 4.
- **Latency, your direct question:** the *analog* path from the DAC latching a code to the
  ADC's sampling point is **32 ns at zero cable length**, plus 4.6 ns per metre of RG-316.
  But from the FPGA writing a DAC word to the FPGA reading the ADC's measurement of it is
  **5–6 samples (200–240 ns)**. Two thirds of that is the AD9280's 3-cycle pipeline, read
  on the 4th edge. Measured: a DAC step at sample 512 shows up at sample 518, on every
  edge, with both cables.
- **New in the tutorial:**
  - Part 3 gets "Closing the loop": `loopback.v` and `loopback.py`. The DAC plays a pattern
    locked to the capture, in four modes: square wave, the same shifted 20 ns for
    equivalent-time sampling, a staircase, and a pseudo-random m-sequence that gives the
    loop's impulse response.
  - Part 4's cable section is rewritten with real data and a figure. `lockin.py` gains
    `--linear` and prints the fitted delay.
  - New **Part 9: More experiments**: 10 designed experiments with `schemdraw` circuit
    diagrams, component values, predicted results and commands.
  - The module's connectors are now "SMA" throughout.

### The cable, and what the measurements say about the module

| | 101.5 cm | 16.5 cm |
| --- | --- | --- |
| lock-in group delay, 0.1–8 MHz (3 sweeps each) | 216.58 ns | 212.69 ns |
| amplitude at the ADC, 100 kHz | 3.89 V | 3.89 V |
| amplitude ratio, 1–9 MHz | 1.000 ± 0.006 | — |
| loopback step, "s" mode | sample 518 | sample 518 |
| staircase: ADC code vs DAC code | 0.776 × DAC + 27.5 | same |

- **The DAC is evidently series-terminated (~50 Ω) and the ADC is high-impedance.** An
  open-ended cable driven through its own Z₀ delivers a clean, delayed copy at full
  amplitude. That fits both cables giving the same amplitude, and the ADC seeing the
  3.9 V the DAC makes into 1 MΩ. With this arrangement the apparent delay is the true delay
  × (R_source/Z₀), so ±2 Ω tolerances on either end are worth ±4% each. That, not the
  lock-in, limits the velocity factor to about ±5%. Differences between cables of the same
  type are good to about ±1 cm.
- **The staircase slope (0.776) agrees within 0.2%** with the product of the two M2k
  calibrations from Prompt 1 (0.0307 V/code × 25.35 codes/V = 0.778).
- **Delay budget, zero-length cable** (lock-in, referenced to the DDS phase register):
  211.9 ns = 160 ns ADC pipeline and capture + 20 ns of FPGA registers + 10 ns zero-order
  hold (a sine rebuilt as a staircase lags by half a DAC sample) + 32 ns analog. The
  equivalent-time step response puts the 50% point ~35 ns after the DAC latch, which agrees
  once the ZOH term (present for a sine, absent for a step) is accounted for.
- **Above ~8 MHz the two cables disagree.** Most likely this is the DAC's image at
  50 MHz − f, which the 25 MS/s ADC folds *exactly* back onto f with conjugate phase, and
  whose phase depends on the cable. So delay fits stop at 8 MHz. This is an explanation,
  not a proven one. A test: run the ADC at a rate that isn't a submultiple of 50 MHz.
- **Above Nyquist** (to 24.9 MHz) the lock-in still works by undersampling: 3.7 V at 13 MHz,
  3.1 V at 20 MHz. Frequencies that are simple fractions of 25 MHz (10, 12.5, 20 MHz)
  scatter between runs.
- **Firmware lock-in (Part 7) through the cable:** same amplitudes, but a delay of 299 ns
  rather than 212.7. `funcgen_core`'s extra pipeline registers and `lockin_core` reading
  the phase one clock later explain 80 of the 86 ns. Now noted in Part 7.

### Extensions: tested tonight

- **Pseudo-random impulse response** (`loopback.py p`). One 0.66 ms capture gives
  h = 0.90 at 6 samples, then −0.18 of ringing; the taps sum to the DC gain. The FFT of h
  agrees with the lock-in below 1 MHz, but not near 12.5 MHz, because a sequence that
  changes every sample folds its 25 MHz − f content onto f. The tutorial explains this.
- **The loop oscillator.** Inverting feedback with gain 2 does *not* give one oscillation:
  with a pure 6-sample delay it is six independent interleaved oscillators (period 12
  samples). Averaging 4 samples in the loop locks them into one near-square wave at
  1.685 MHz (14.8 samples, against the 15 predicted). The "Try this" was rewritten to match.

### Extensions: designed, waiting for parts (Part 9)

The ADC's input impedance and the cable's C′ (and from it Z₀ = τ′/C′) with a 10 kΩ;
RC filters; a series LC; a 4 MHz crystal's Q (~16,600, a 240 Hz-wide peak, the parallel
resonance 6.4 kHz higher); a diode clipper's odd-only harmonics (the loop's own baseline,
≤ −46 dBc, was measured tonight); a quarter-wave stub (9.89 MHz for 5 m of RG-58); the
speed of sound with 40 kHz transducers (41.9°/mm); an LED/photodiode link (350 kHz vs
3.5 MHz with R_L = 10 kΩ vs 1 kΩ, and lock-in detection under room light); PI control of
an RC plant; and the Icepi's crystal against a GPS-disciplined 10 MHz to ppb.

### Files

- New: `loopback.v`, `loopback.py`; `tools/cable_sweep.py`, `tools/fig_cable.py`,
  `tools/fig_loopback.py`, `tools/fig_experiments.py`.
- New data and figures: `data/cable_{1m,16cm}.npz`, `data/loopback_{1m,16cm}.npz`; `img/cable.png`,
  `img/loopback_{step,stairs,prbs}.png`, `img/exp_*.png` (10 schematics).
- Changed: `icepi_adda.lpf` (LED order), `capture.v` and `lockin.v` (LED comments only),
  `lockin.py` (`--linear`, delay fit), `Makefile` (loopback). All bare designs rebuild and
  pass timing, and both simulations pass.
- Outside the repo: `pip install --user schemdraw` (for the schematics). The oscillator test
  designs are throwaway files in the session scratchpad.
- Nothing committed. The board is running the Part 5–7 LiteX SoC with the firmware. The
  16.5 cm cable is still in place.

## Prompt 3

When viewed in vscode's dark background, the circuit diagrams cannot be seen. They either need an explicit white background or they need some other way to be viewed both on github's white background and vscode's dark background.

Why are the DAC and ADC not run at the same rate? What sets their maximum sample rates? When you mention the 14.7ns with respect to the ADC, add a few more sentences discussing the maximum sampling rates of the ADC and DAC in this system. If, for example, the DAC can go faster, how would one set up a PLL within the FPGA to make that happen?

Can you write to the SD card through the USB connection that you have? Maybe through linux or LiteX? Or do I need to constantly remove the SD card, put it into an SD card reader, eject it, and put it back into the Icepi Zero? I have inserted a newly-formatted 64 GB microSD card into the Icepi Zero. One final tutorial would be to put the linux FPGA gateware into the FPGA flash and the linux filesystem on an SD card and show how quickly it can boot into a usable state.

## Response 3 2026-09-29 21:30:00 - 2026-09-29 23:34:00 Claude Opus 5.5 Extra High

### Short version

- **Schematics on a dark background:** fixed. `schemdraw` saves transparent PNGs, so the
  black lines vanished on VS Code's dark theme. `tools/fig_experiments.py` now flattens each
  one onto the same off-white (#fcfcfb) as the plots, with a margin. All 22 figures in
  `img/` are now opaque, so they read the same on GitHub's white and VS Code's dark.
- **Sample rates:** Part 3's "Clocking the ADC" gains a paragraph, "Why 25 MS/s in but
  50 MS/s out?". The AD9280 is rated for 32 MS/s (a 31.25 ns period, of which ≥ 14.7 ns
  high and low: its pipeline stages need that long to settle). The AD9708 is rated for
  100 MS/s (125 typical); it only latches data (2.0 ns setup, 1.5 ns hold). With one
  50 MHz oscillator, only 50/N is available: the DAC gets 50 and the ADC gets 25, the
  fastest it accepts. The whole-number ratio keeps them coherent, which Parts 3–4 rely on.
  The serial port is the other limit (25 MB/s against 100 kB/s), hence the block RAM.
- **A PLL:** new end of Part 2, "Faster clocks: a PLL". It covers what a PLL does,
  `ecppll -i 50 -o 100`, and `pll100.v` (the ECP5's `EHXPLLL`: VCO 600 MHz ÷ 6).
  `sine_pll.v` puts the DAC at 100 MS/s, and the section explains the DAC pin timing
  (5 ns each side of the latch edge: 3 ns of margin at 100 MHz, 2 ns at 125).
  Part 4 gets a matching section, "A faster DAC", with `lockin_pll.v`, **measured**
  (next section).
- **Writing the SD card: yes, over the USB cable, no card swapping.** The board's own Linux
  writes it. The files ride along with a serial boot: `make_sd_installer.sh` appends a
  second cpio archive to the initramfs, holding the card's files and `install-sd.sh`, which
  partitions (MBR from `make_mbr.py`), formats and fills the card. It took a 5½ minute
  upload plus 6 minutes of install. (LiteX's BIOS can't do it: its `sdcard_write` only
  writes test patterns.)
- **Booting from flash + SD (new Part 8.7):** the gateware is in the SPI flash (53 s to
  write), and the kernel and root file system are on the card. From reset to
  `buildroot login:` took **86.5 s**. After switching off five useless services and adding
  an `S90adda` script that loads the driver, it took **61 s, with the instruments ready**.
  Serial boot, for comparison, takes 5.0 min.

### The PLL, measured

The board's M2k was disconnected, so the 100 MS/s DAC was measured with the lock-in through
the 16.5 cm cable: `lockin_pll.v` (everything on clk100; ADC at 100/4 = 25 MS/s; UART
100 clocks/bit), next to 3 fresh `lockin.v` sweeps. The new 50 MS/s sweeps repeat Prompt 2's
to 0.2% and 0.13°. Figure: `img/pll.png`.

- **It works, to 50 MHz.** The lock-in undersamples (the reference aliases with the
  signal), so with the DAC at 100 MS/s it measures the module's analog response all the way
  to the DAC's Nyquist: 4.45 V peak near 15 MHz, 2.6 V at 25, 0.26 V at 40 MHz.
- **The image hypothesis from Response 2 is confirmed in magnitude.** Above ~8 MHz the
  50 MS/s readings differ from the 100 MS/s ones (sinc-corrected), and the difference is the
  size of the 50 MS/s DAC's image at 50 − f, whose amplitude the 100 MS/s sweep measures
  independently. They agree to 0.82–1.26× from 4 to 25 MHz. The image is 1% of the reading
  at 8 MHz, 4% at 12.4 MHz, and a quarter at 20 MHz. At 20 MHz the 50 MS/s design reads
  4.11 V where the tone alone gives 3.06 V. Its phase is conjugate-like but wanders ±50° from
  a simple model, so I claim only the magnitude.
- **A correction to Response 2:** the phase *bend* above 8 MHz is not the image. It's
  identical at both DAC rates, so it's the module's own analog phase (non-constant group
  delay near its cutoff). What the image does is make that bend cable-dependent, which is
  what broke the two-cable comparison. The tutorial now says both. The 100 MS/s two-cable
  comparison is left as a "Try this"; it needs the 1 m cable swapped back in.
- **Delay:** 9.75 ns shorter at 100 MS/s. That is one DAC clock (a half-clock latch plus a
  half-sample zero-order hold), predicted 10 ns.
- Timing: `sine_pll.v` 203 MHz, `lockin_pll.v` 139 MHz (both need 100). Not checked: the DAC
  pins' real skew, beyond "it works".

### The SD card and the boot, measured

| | time |
| --- | --- |
| RAM-disk serial boot (upload 3 min 56 s at 43.7 kB/s; kernel 19.4 s; init scripts 45 s) | 5.0 min |
| installer: `make_sd_installer.sh` 22 s; upload 15 MB 5 min 35 s; `install-sd.sh` 6 min 1 s | 12 min, once |
| flash + SD, stock Buildroot services | 86.5 s |
| flash + SD, 5 services off, `S90adda` | 61 s |

Where the 86.5 s goes: 2.8 s FPGA configuration + BIOS memory test; 14.4 s for the BIOS to
read the 9.1 MB `Image` (633 kB/s; it can't decompress); 9.3 s of kernel (half the
RAM-disk's 19 s, since there's no initramfs to unpack); 59 s of start-up scripts. The
scripts are CPU-bound: `time /bin/true` takes 0.37 s on this 50 MHz VexRiscv. Linux itself
reads the card at only 291 kB/s and writes at 213 kB/s (`dd`).

Things that went wrong on the way, now handled:

- BusyBox `fdisk` fed from a pipe wrote no partitions, and the old GPT made `mkdosfs`
  format all 59 GB. The fix is an MBR built on the PC (`make_mbr.py`), `dd`'d to the card,
  plus wiping both GPT copies.
- BusyBox `mke2fs` silently ignores `-N`, and 262,144 inodes took 5 min to write. It's now
  `-i 131072` (32,768 inodes), and the file systems take 89 s. The first full install took
  11 min; the final scripts take 6.
- Pasting files into the console with `base64` at full speed arrives corrupted, which is why
  the files travel in the serial boot's CRC-checked frames instead.
- Every hard reset leaves ext2 "unchecked" (no journal). The tutorial says to `sync` before
  unplugging.

The card layout is MBR, then p1 64 MiB FAT32 (Image, opensbi.bin, rv32.dtb, boot.json)
and p2 4 GiB ext2 root. The other 55 GB is unused.

### The tutorial as one flow

Every place that read like a changelog was rewritten as plain explanation: the intro, the
LED numbering, "why a hex digit", the cable and oscillator notes, the base64 "Try this", the
musl/pppd rationale, and Part 9's intro. The new material sits where a student meets it:
the rate limits in Part 3, the PLL at the end of Part 2, "A faster DAC" in Part 4 after
the cable, and 8.7 at the end of Part 8. 8.3's "Linux boots in about 20 s" was wrong (the
kernel takes 19 s, and login comes 45 s later); it now gives the measured numbers. 8.1's
resource numbers are updated for the native-SD SoC (51/56 block RAMs, 55% logic,
54.4 MHz). Appendix A gets five new troubleshooting rows, and Appendix B the new tests and
what's still untested.

### Files

- New: `pll100.v`, `sine_pll.v`, `lockin_pll.v`; `linux/make_mbr.py`, `linux/install-sd.sh`,
  `linux/make_sd_installer.sh`; `tools/fig_pll.py`; `data/cable_16cm_dac50.npz`,
  `data/cable_16cm_dac100.npz`, `data/cable_16cm_dac100_hi.npz`; `img/pll.png`.
- Changed: `Makefile` (PLL designs); `lockin.py` (`--fclk`); `tools/cable_sweep.py`
  (`--fclk`); `tools/fig_experiments.py` (opaque schematics, all `exp_*.png` regenerated);
  `litex/make_linux.py` (native 4-bit SD instead of SPI mode, `--images-dir=`,
  `--rootfs=` picks `boot.json`); the gateware was rebuilt with it.
- All code blocks match their files (`tools/sync_md.py --check`), and all internal links
  resolve.
- Nothing committed. **Board state:** the SPI flash holds the Linux SoC, and the card holds
  the trimmed system, so the board boots to a login with `adda.ko` loaded, by itself, in
  about a minute. The 16.5 cm cable is still DAC → ADC. To go back to bare-Verilog designs,
  load them to SRAM as before (`make load-...`); they're gone again at the next power-up.

## Prompt 4

I had JLCPCB manufacture the IcePi Zero designs in `~/OpticsPCBs/IcepiZeroADCDAC/jlcbuild` using the substitution parts that were selected there. One of these is plugged in and at `/dev/ttyUSB0`. Go through the `IcepiZeroADCDAC_tutorials.md` and test as much as you can. At the moment, there is no header soldered to it and no SD card. See if you can configure the LED counter and then stop. Then see if you can boot and test Linux. Then stop and I'll insert the SD card, which you should test. Then I'll solder on the header and plug in the ADC and DAC unit for you to test.

## Response 4 2026-09-30 15:50:00 - 2026-09-30 16:20:00 Claude Opus 5.5

The board under test: JLCPCB-built Icepi Zero (`jlcbuild/release_revA`), FT231X serial
`DP0525BU`, no 2x20 header, no SD card at first. Its big parts are the same as the original
board's (LFE5U-25F-6BG256C, FT231XQ, W25Q128JVSIQ, W9825G6KH-6I, SG-8018CG 50 MHz); the
substitutions are passives, connectors, and the TS-1088C buttons.

### 1. Part 1, the LED counter: works

- `openFPGALoader -b icepi-zero --detect`: LFE5U-25, IDCODE 0x41111043.
- The tutorial's four commands, verbatim: nextpnr reports `305.06 MHz (PASS at 50.00 MHz)`,
  the same number as the tutorial; the load takes 1.7 s. The user watched the LEDs: they
  count, MSB on the left.
- A throwaway test design (not in the tutorial) streamed both buttons over the UART at
  1 Mbaud and echoed a received byte: TX and RX both work, and both buttons (C4, C5) read 1
  when released. The line period, 2^19 clocks, came out at 10.5 ms, i.e. the 50 MHz
  oscillator runs.

### 2. Part 8, Linux from a serial boot: works, but 8.3's instructions don't, without a card

The gateware and images are the ones already built (`build/icepi_zero_adda`, `images_adda`).

- **Loading the SoC and pressing Enter gives no `litex>` prompt.** The BIOS runs (`Memtest OK`
  on 2 MiB, 14.6 MiB/s write, 20.2 MiB/s read, identical to the first board), offers serial
  boot for 0.25 s, then sits at `Booting from SDCard in SD-Mode... Booting from boot.json...`.
  LiteX's `add_sdcard()` gives the PHY a 1 s command timeout (`cmd_timeout=10e-1`) and the
  BIOS's `sdcard_init()` retries CMD8 1000 times, so an empty slot costs about 17 minutes
  (still waiting after 6 min here). The first board always had a card, so this was never seen.
  8.3's "press Enter for the litex> prompt, then serialboot" therefore only works with a card
  that has no `boot.json`; with an installed card the BIOS boots the card instead.
- **What works:** have the loader listening *before* the FPGA starts, and answer the BIOS's
  serial-boot request inside its 0.25 s window. The port comes back ~1 s before the request.
  (A script that reopens `/dev/ttyUSB0` must close the old handle when the port vanishes, or
  the FT231X comes back as `/dev/ttyUSB1`.)
- Upload 236 s (tutorial: 3 min 56 s), Liftoff to `/init` 19.2 s, then 44 s to `login:`.
- Checked without the module: `uname`, `cpuinfo` (rv32ima, sv32), `free` (22988 kB total), the
  device tree (`adda@f0002000`, `mmc@f0004000`), `time /bin/true` 0.35 s, 8 MB of
  `/dev/urandom` through tmpfs with matching `md5sum`s, `devmem` write/read-back of the tuning
  word, `insmod adda.ko`, every sysfs file (frequency reads `123455.992`), a free-running
  capture (16384 bytes in 0.39 s, all code 0: the ECP5's default pull-downs on the bare
  header), a triggered capture (`Operation timed out` after 60 s, as it should with no
  signal), the lock-in, `sweep.sh`, `dump.sh`, and `rmmod`/`insmod`.

### 3. The flash

- `openFPGALoader --detect -f`: JEDEC 0xef4018, Winbond W25Q128, blank, no protection bits.
- `openFPGALoader -f icepi_zero_adda.bit`: 53.0 s (tutorial: 53 s). The FPGA reloads from
  flash and the BIOS comes up the same as from SRAM.


## Prompt 5

I put the microSD card in while the Icepi Zero was on. It's the same card as before. Test that. Also, test the FPGA configuration flash and RAM. Have you tested everything that you can reasonably test without an HDMI display or USB peripherals?

With the PLLs on board, can the ADC achieve 32 MS/s?

I don't understand the phrase you've used at least twice: "The AD9708 is rated for 100 MS/s (125 typical)". Does this mean that all AD9708 chips are spec'd to do 100 MS/s, but a typical chip can be pushed up to 125 MS/s?

61 s to boot Linux seems to make this unusable as anything but a teaching tool for students simultaneously interested in Linux and with a lot of patience. Are other SoC's that boot linux much faster because they are not 50 MHz verilog designs running on an FPGA, because they can read and write faster to the SD card (perhaps using a different protocol), or because their Linux has had every extra second of boot time squeezed out of it?

For this stack of modules through 0.1 inch headers, how fast would you expect to be able to drive the DAC and ADC pins without issues? In the icepi_adda.lpf constraint file, you set DRIVE=4 SLEWRATE=SLOW for adc_clk, dac_clk, and dac_d. Why is this the right choice? Is this drive strength and speed good enough to go up to 100 MS/s on the DAC but not so strong or fast that it would cause excessive noise? What led to this choice? Why don't the LEDs and UART pins have DRIVE and SLEWRATE settings? Maybe their defaults are fine, but a sentence or two about this in the tutorial might be helpful for students who want to take this design as a starting point for their own.


## Response 5 2026-09-30 16:23:00 - 2026-09-30 17:20:52 Claude Opus 5.5

### Short version

- **SD card: works.** The BIOS was still retrying the empty slot 9½ minutes in when the
  card went in. It found the card and booted it by itself. Timed boot from flash + card,
  twice: login at 60.9 and 61.0 s, matching the first board to 0.1 s at every step.
- **Flash: works**, including the two data lines that one-bit configuration never uses.
  It reads back identical to the bitstream, and configures the FPGA in quad-SPI mode at
  62 MHz (3 of 3). Packing the Linux SoC that way gets to login 1.1–1.2 s sooner.
- **RAM: works.** BIOS `mem_test` over all 32 MiB passed twice (random data, so a stuck or
  shorted address line would have shown up). 14.6 MiB/s write, 20.2 MiB/s read.
- **Oscillator: 49,999,835.0 Hz, −3.30 ppm** against the PC's NTP clock.
- **Not tested yet:** pressing the buttons and pulling the card (each needs a finger), the
  40-pin header (not fitted), the two FPGA-side USB-C ports, HDMI, and the power rails'
  voltages. Details and a plan are below.
- **32 MS/s:** yes, the chip and a PLL can do it, but three things need care: an in-spec
  PLL frequency, the clock's duty cycle, and when to read the data. 31.25 MS/s is the easy
  version. I'll measure it when the module is on.
- **"100 MS/s (125 typical)":** your reading is right, and the tutorial now says it that
  way.
- **61 s:** all three of your reasons apply, in roughly this order: the CPU and memory
  (~37 s), the card path (~20 s, and it's the CPU, not the card or the protocol), and how
  much the system does at boot. Explained below and in a new paragraph in 8.7.
- **DRIVE/SLEWRATE:** the defaults are 8 mA and SLOW, so `SLEWRATE=SLOW` changes nothing
  and `DRIVE=4` is the only real change. The choice came from reasoning during the adapter
  design, not from measurement. It works at 100 MS/s. A paragraph now explains it in Part 1.

### The SD card (the same 64 GB card as before)

- Card: SanDisk (manfid 0x03) SC64G, SDXC, 59.5 GiB, made 10/2018. p1 64 MiB + p2 4 GiB,
  the trimmed system with `S90adda`. Linux found it at 7.0 s.
- 8 MB with `dd` (BusyBox's `dd` prints no rate, so timed with `time`): raw read 287 kB/s,
  file read 299 kB/s, write with `fsync` 215 kB/s (tutorial: ~290 and ~210).
- 4 MB of `/dev/urandom` written with `fsync`, caches dropped, read back: same MD5. The
  last 488 sectors of the card (sector 124,735,000) read fine.
- A marker file written and `sync`ed survived the hard reset (with the expected
  `mounting unchecked fs` warning).
- Timed boots from `openFPGALoader -r` (a logger opened the port 0.98 s earlier, which is
  subtracted):

| event | run 1 (s) | run 2 (s) | tutorial (s) |
| --- | ---: | ---: | ---: |
| BIOS tries serial boot | 2.8 | 2.8 | 2.8 |
| starts reading `Image` | 3.1 | 3.1 | 3.1 |
| `Image` loaded | 17.4 | 17.4 | 17.5 |
| OpenSBI starts Linux | 17.9 | 17.9 | 17.9 |
| `/sbin/init` | 27.2 | 27.2 | 27.2 |
| `adda` loaded | 59.5 | 59.5 | — |
| `login:` | 60.9 | 61.0 | 61 |

### The flash

- JEDEC 0xef4018, W25Q128, no protection bits.
- `--dump-flash` of the bitstream's length: identical to `icepi_zero_adda.bit` after its
  28-byte text header (`Part: LFE5U-25F-6CABGA256`), which openFPGALoader doesn't write.
- The LiteX build packs with ecppack's defaults: one-bit SPI at 2.4 MHz. So booting from
  flash had never used IO2/IO3 (M7, N7). The button/UART test design, packed with
  `--spimode qspi --freq 38.8` and then `62.0`, configured the FPGA from flash every time
  (1 + 1 at 38.8 MHz, 3 at 62 MHz). So all six flash wires work, and the flash's
  quad-enable (QE) bit must already be set, because nothing here set it.
- The Linux SoC packed with `--spimode qspi --freq 62.0`: `Memtest OK` 1.07 s after
  `-r`, instead of 2.51 s. Login at 59.7 and 59.9 s. Then I put the tutorial's bitstream
  back and verified it by reading it back. This is now a Try-this in 8.7.

### The RAM

The BIOS's own boot-time memtest covers 2 MiB. Its stack is in the 6 KiB on-chip SRAM
(0x10000000), so `mem_test 0x40000000 0x2000000` can cover all of main RAM. It ran twice,
both `Memtest OK`. Its address test only covers 32 KiB, but the random-data pass over 32 MiB
would catch aliasing from a stuck or shorted address line. The Linux tests of Response 4
(8 MB through tmpfs, the initrd at +16 MiB) agree.

### The oscillator

A throwaway design sends one byte every 2²² clocks (83.886 ms). The PC time-stamped 8584 of
them over 720 s (`time.monotonic()`, NTP-disciplined by timesyncd, offset −466 µs;
low-latency mode on the FT231X). A straight-line fit gives 49,999,834.99 Hz,
**−3.30 ppm ± 0.02 statistical**, with 0.30 ms rms residual. The PC clock's own error
adds perhaps a few tenths of a ppm. The first board was 2.8 ppm slow against the M2k.
Added to 9.10 as a reference-free way to measure your own board.

### What else is on the board, and what's been tested

| feature | status |
| --- | --- |
| JTAG, ECP5 configuration from SRAM and flash (x1 and x4) | tested |
| 50 MHz oscillator | tested, −3.30 ppm |
| 32 MiB SDRAM | tested, all of it |
| 16 MiB SPI flash | tested: ID, write, read-back, quad |
| micro-SD, native 4-bit | tested: boot, read, write, last sector, hot insertion |
| FT231X serial | tested: 1 Mbaud both ways, 460800 under the SoC |
| 5 white LEDs | tested by eye (the counter) |
| red LED D14 | the FT231X's RXLED: lights while the PC sends. Did you see it flicker during uploads? |
| buttons SW1 (C4, LiteX reset) and SW2 (C5) | both read 1 (released). Pressing not tested |
| card detect, `SD_DET` on M16 | reads 1 with a card in. Removal not tested. Nothing in LiteX uses it |
| two FPGA USB-C ports, J3 (`/USB/D0I`) and J4 (`/USB/D1I`) | not tested |
| HDMI (GPDI), its DDC through the PCA9306, hot-plug detect | not tested: needs a display |
| 40-pin header | not fitted. The module will exercise 18 of the 28 GPIOs and the 5 V pins |
| the three regulators | working, since everything else works. Voltages not measured |

What's reasonable to do while you're at the bench:

1. **Buttons and card detect: 1 minute.** `tools/boardtest/iotest.v` reports
   `B<C4><C5><SD_DET>` over the serial port every 10 ms. I'll load it, you press each
   button and pull the card, and I'll watch the bits change.
2. **The FPGA's USB ports: about 10 minutes**, needing only a second USB-C cable to the PC.
   LiteX's `icepi_zero` target can make `usb` 0 a USB serial device
   (`--uart-name=usb_acm`), so its BIOS would appear as `/dev/ttyACM0`. That tests one
   port's D+/D− and pull-up. J4 would need its pins swapped in the build.
3. HDMI needs a display, and the voltages need a meter.

### With the PLLs, can the ADC do 32 MS/s?

The AD9280 is specified at exactly that rate: a 32 MHz clock with a 50% duty cycle,
t<sub>CH</sub> and t<sub>CL</sub> ≥ 14.7 ns, and t<sub>OD</sub> = 25 ns *typical*, with no
min or max given. "Running the part at slightly faster clock rates may be possible, although
at reduced performance levels." Three things need care:

1. **An in-spec clock.** The ECP5 datasheet (Table 3.23) guarantees the PLL's jitter only
   when its phase-detector input is at least 10 MHz. From 50 MHz, that means a reference
   divider of 1–5 (PFD 50, 25, 16.7, 12.5 or 10 MHz). 32 MHz isn't a whole multiple of any
   of those, so `ecppll -i 50 -o 32` uses divider 14 (PFD 3.57 MHz) and gives 32.14 MHz:
   out of the jitter spec, and slightly over the ADC's rating. Two clean options:
   - **31.25 MS/s, 98% of the maximum:** a 62.5 MHz PLL clock (divider 4, PFD 12.5 MHz,
     VCO 625 MHz) toggling `adc_clk`, with the DAC at 62.5 MS/s, still in a whole-number
     ratio. The same VCO also gives 125 MHz for the DAC (its typical, not guaranteed,
     limit).
   - **Exactly 32 MS/s:** VCO 640 MHz = PFD 10 MHz × 64, with feedback taken from a
     secondary output at 80 MHz and CLKOP ÷ 20 = 32 MHz (or ÷ 10 = 64 MHz to toggle).
     That's a hand-written `EHXPLLL`, since `ecppll` only feeds back from CLKOP. The DAC
     could run at 128 MS/s (÷ 5, past even the typical limit) or 91.4, and only 128 is a
     whole-number ratio.
2. **The duty cycle.** At 32 MHz each half-period is 15.6 ns against the 14.7 ns minimum,
   so the clock must stay within 47–53% at the ADC's pin. Toggling a flip-flop at 64 MHz
   gives exactly 50% inside the FPGA. Unequal rise and fall times through the weak 4 mA
   driver and two connectors then eat into a 0.9 ns margin. The AD9280's datasheet asks
   for HC/AC-family clock drivers for exactly this reason. So `adc_clk` may want more drive
   at 32 MS/s.
3. **When to read the data.** With t<sub>OD</sub> ≈ 25 ns and a 31.25 ns period, the
   present rule ("read just before the next rising edge") would read data only ~6 ns after
   it settles, if t<sub>OD</sub> is typical, and t<sub>OD</sub> has no stated maximum. The
   middle of the valid window is ~9 ns *after* the next rising edge. With a PLL, the capture
   clock can be a second output with a phase shift, and the right phase can be found by
   sweeping it and watching where the codes go bad: an "eye scan".

Planned for when the module is on: capture at 31.25 MS/s with a phase sweep, and compare the
effective bits with the 7.1 measured at 25 MS/s. Part 3 now mentions the 31.25 MS/s option
and the timing problem. Part 2's PLL section has a short note on the 10 MHz rule.

### "The AD9708 is rated for 100 MS/s (125 typical)"

Yes. The datasheet's dynamic-specifications table has one row, "Maximum Output Update Rate
(f<sub>CLOCK</sub>)", with **Min 100, Typ 125 MSPS**. The minimum column is the guarantee:
every part keeps up at 100 MS/s. The typical column is what a typical part manages, but no
part is promised it. One more catch: the table's conditions are AVDD = DVDD = +5 V, and this
module's DVDD measured 3.3 V, so strictly the 100 MS/s guarantee doesn't cover this module.
It did run at 100 MS/s (Response 3). The tutorial now says this in plain words in both
places (Part 2's PLL section and Part 3). The phrase also appears in Response 3 above, which
I've left as written.

### Why does Linux take 61 s, and why are other SoCs faster?

All three of your reasons, and here is roughly how the 61 s divides:

- **About 3 s: FPGA configuration and the BIOS.** That's 1.5 s to load the bitstream at
  one bit and 2.4 MHz (quad SPI saves 1.4 s), then the memory test.
- **About 37 s: the CPU and memory.** The kernel takes 9.3 s, and the scripts 34 s minus
  their card reads. VexRiscv runs at 50 MHz, at most one instruction per clock, with 4 KiB
  direct-mapped I- and D-caches (the core's name has `Is4096Iy1` and `Ds4096Dy1`) and a 16-bit SDRAM at
  20 MiB/s. Starting any program (`/bin/true`) costs 0.35 s. A Pi Zero 2 W has 4 × 1 GHz
  Cortex-A53 with LPDDR2: very roughly 100× the single-thread speed and 100× the memory
  bandwidth. Process start-up there is about a millisecond.
- **About 20 s: the card path, though not the card or the protocol.** The BIOS clocks the
  standard 4-bit SD bus at 25 MHz (`SDCARD_CLK_FREQ`), good for 12.5 MB/s, and gets
  633 kB/s (5%), because the 50 MHz CPU does the per-block work and the copy. Linux gets
  290 kB/s. A Pi's SD host does 20–25 MB/s (high-speed mode), and the Pi 4/5 more with UHS
  1.8 V signalling. The 9.1 MB uncompressed `Image` costs 14.4 s here and a fraction of a
  second there.
- **Squeezing.** Raspberry Pi OS isn't squeezed: dozens of systemd services, and still
  ~10–30 s to login depending on the model. Systems tuned for boot time (a minimal kernel,
  the application as `init`, no udev) reach their application in about a second on ARM
  SoCs. On this board, the same ideas would give roughly: the application as `init` → ~28 s
  (the kernel starts `/sbin/init` at 27.2 s), a kernel stripped to this hardware → several
  seconds less loading, quad SPI → −1.4 s. That's a floor of perhaps 20 s. These are
  estimates, not tried.

So yes: Linux on a 50 MHz soft CPU is a teaching tool, or useful when you want Linux's
tooling and can wait a minute. For an instrument that has to be ready at power-up, the
bare-metal firmware of Parts 5–7 is the right model: no OS, and the BIOS that would start it
is running 2.5 s after power-up (1.1 s with quad SPI). This is now a short "Why does a
Raspberry Pi boot so much faster?" paragraph in 8.7.

### DRIVE=4 SLEWRATE=SLOW: why, and is it right?

**The defaults, and why the LEDs and UART have none.** Lattice's sysIO guide (FPGA-TN-02032
§4.11.2): "The software default for slew rate is SLEWRATE=SLOW." The default drive "depends
on the I/O standard". The Trellis bit database settles it: `OUTPUT_LVCMOS33` itself sets
the F4/F5/F6 fuses, which with F7/F8 clear is the **8 mA** pattern. nextpnr writes no DRIVE
or SLEWRATE for the LED pins in `counter.config`, so they run at 8 mA SLOW. In our `.lpf`,
`SLEWRATE=SLOW` therefore changes nothing, and `DRIVE=4` (half the default) is the only real
setting. For LEDs (DC) and a UART at ≤ 1 Mbaud on the Icepi Zero's own short traces, the
defaults are fine.

**What led to it.** It was decided on 2026-09-12 while designing the adapter
(`~/OpticsPCBs/IcepiZeroADCDAC/README.md` §4, and the `write_lpf()` docstring in
`adapters/make_boards.py`), by reasoning, not measurement. The 40–60 mm runs have ~0.3 ns
of flight time, and an edge several times longer than that makes the line electrically
short: no termination, no series resistors on the adapter. Slow, weak edges also limit
simultaneous-switching ground bounce through a connector with few ground pins. The "fast
≈ 1 ns, slow ≈ 3 ns" edge times quoted there were estimates. Lattice's datasheet doesn't
give edge times (the IBIS models do).

**Is it right?** For the DAC's data lines, yes, and the AD9708 datasheet agrees:
"the selection of the slowest logic family that satisfies the above conditions will result
in the lowest data feedthrough and noise", and it suggests 20–100 Ω series resistors
against ringing, a job the weak driver does instead. For the **DAC clock** the same
datasheet asks for the opposite: "Fast clock edges will help minimize any jitter that will
manifest itself as phase noise". The same goes for the **ADC clock**, where the duty cycle
matters at 32 MS/s (above). So the most defensible setting is probably weak and slow on the
eight data lines, and stronger and faster on the two clocks. That's a hypothesis to measure,
not a fact yet.

**How fast?** Measured: 100 MS/s works with these settings (Response 3, `lockin_pll.v`,
tones to 49.9 MHz). Lattice rates LVCMOS33 outputs to 150 MHz for all drives, characterized
at fast slew (Table 3.21). At 100 MS/s the data lines toggle at ≤ 50 MHz, and `dac_clk`, a
100 MHz square wave, is the hardest signal. So I'd expect 100 MS/s to be comfortable and
125 MS/s (the AD9708's typical limit) plausible, perhaps needing a faster clock edge. Above
that, the DAC itself isn't rated. The ADC side is limited by the AD9280 (32 MS/s), not the
pins.

Planned once the module is on, with the DAC cabled to the ADC: DAC at 50/100/125 MS/s ×
{4 mA SLOW, 8 mA SLOW, 8 mA FAST on the clock only, 16 mA FAST}, looking at the DAC output's
spurs and harmonics, and at the highest rate where codes still arrive correctly.

### Changes to the tutorial

- Part 1: a paragraph on `DRIVE` and `SLEWRATE`: the defaults, why the converter pins
  differ, and that the values were reasoned, not measured.
- Part 2: "Every AD9708 is guaranteed to run at 100 MS/s". The crystal error is now "2.8
  and 3.3 ppm slow" on the two boards. A note that `ecppll` doesn't enforce the PLL's
  10 MHz PFD minimum.
- Part 3: the AD9708's min/typ rating in plain words (and the 5 V caveat), the 31.25 MS/s
  option, and why reading the ADC at that rate needs a later sampling point.
- 8.3 and 8.7's installer: `openFPGALoader ... && litex_term ...` as one command, tested
  3 of 3. The old "press Enter for the litex> prompt, then serialboot" fails with an empty
  slot (no prompt) and with an installed card (it boots the card).
- 8.7: the "Why does a Raspberry Pi boot so much faster?" paragraph, and a quad-SPI Try-this
  with the measured saving.
- 9.10: measure your own crystal against NTP.
- Appendix A: the empty-slot BIOS stall (with the hot-insertion rescue), split from the
  "card with no `boot.json`" row.
- Appendix B: "On a second board", and two more not-tested items.
- `tools/sync_md.py --check`: all code blocks match their files. Nothing committed.

### New: `tools/boardtest/`, for the next new board

The tests above, kept so the second JLCPCB board can be checked the same way. None of them
needs the header, the module or a card:

- `iotest.v`: buttons and card detect, streamed over the serial port (`make load-iotest`).
- `tick.v` + `measure_osc.py`: the oscillator against NTP (`make load-tick`, then 12 min).
- `bootload.py`: a serial boot that answers the BIOS as the FPGA starts. `serialboot.py`
  needs the `litex>` prompt, which the Linux SoC never shows with an empty slot. It closes
  the port when it vanishes, so the port comes back as `/dev/ttyUSB0`.
- `boardtest.lpf`, `Makefile`.

Each was rerun from the repo copy: `iotest` (B111 with the card in), `tick` (a 20 s smoke
run), and `bootload.py` (request seen 8.46 s after the load started, upload begun, then
stopped).

**Board state:** flash holds the tutorial's `icepi_zero_adda.bit` (verified), and the card is
in, so it boots to a login in 61 s by itself.

## Prompt 6

You now have a second JLCPCB-produced Icepi Zero, this time with the ADC+DAC module attached. Do all of the tests on this board and add the ADC+DAC tests.

Are there enough available IO pins to make an adapter board that can accommodate 2 of these boards? 2*20 > 8*4+4, but I don't know how many pins are reserved for power, ground, or other special functions. If we combined the DAC clocks and ADC clocks to save 2 pins, would that then work?

## Response 6 2026-09-30 18:30:00 - 2026-09-30 19:39:12 Claude Opus 5.5

Names used here: **original** = the first Icepi Zero (Prompts 1–3), which made every
recording in `data/`; **JLC 1** = FT231X `DP0525BU` (Prompts 4–5, no header); **JLC 2** =
`DP051TLX`, this board, with the header, the same module, and the 16.5 cm cable DAC → ADC.
No M2k: the board's own ADC was the only instrument.

### Short version

- **JLC 2 passes everything that could be run, and with the module it reproduces the
  original board's recordings** to within their own repeat-to-repeat scatter.
- **Drive strength, measured:** at 100 MS/s the tutorial's 4 mA SLOW gives the least
  noise, by 0.3–3 dB depending on the measure. That's repeatable to 0.1 dB. A faster
  clock edge doesn't help. Every setting still converts correctly at 200 MS/s.
- **The ADC at 31.25 MS/s, measured:** the data is valid for all but about 4 ns of the
  32 ns period, and the quality at the best point equals 25 MS/s (7.0 effective bits).
- **New effect:** when the ADC samples while the DAC is switching, the noise rises by
  about 5 dB. That's a bigger effect than any drive setting.
- **Two modules on one Icepi Zero:** not as they are. The header has only 28 I/O, and
  sharing the clocks still needs 34. Sharing the DAC *data* bus does fit, in 27. Details
  below.

### The board itself (JLC 2)

| test | result |
| --- | --- |
| JTAG | LFE5U-25, IDCODE 0x41111043 |
| flash | W25Q128, blank, unprotected; Linux SoC written in 52.9 s, read back identical; quad SPI at 62 MHz configures the FPGA (3 of 3) |
| SDRAM | BIOS `mem_test` over all 32 MiB, twice, OK; 14.6 / 20.2 MiB/s |
| oscillator | 49,999,914.8 Hz, **−1.70 ppm** (12 min against NTP; JLC 1 was −3.30, the original −2.8 against the M2k) |
| buttons, card detect | both buttons read released. `SD_DET` read **0 with the slot empty**, and **1** once you had moved JLC 1's card across, so the switch works and 1 = card present |
| boot from flash + card | login at 61.2 s (JLC 1: 60.9, 61.0) |
| SD card | 8 MB raw read 285 kB/s, write with `fsync` 201 kB/s, MD5s match; the marker file written on JLC 1 was there |
| Linux | `uname`, `cpuinfo`, `free` (22992 kB), `/bin/true` 0.37 s, `devmem`, every sysfs file |
| Part 1 counter | builds (305.06 MHz, the tutorial's number) and loads. Nobody was watching the LEDs, so they're unverified on this board |

### Parts 2–8 with the module, against the original board's recordings

| part | on JLC 2 | compared with |
| --- | --- | --- |
| 2: `sawtooth`, `sine`, `sine_pll` | Each ran on the DAC while `capture.v` recorded the ADC: a wrapper instantiates both tutorial modules unchanged. Results: 195.3 kHz; 1,000,000.15 Hz at 3.859 V; 999,999.98 Hz at 3.852 V. Harmonics −40 to −58 dBc | the tutorial's 195.3 kHz and 3.82 V (M2k) |
| 3: `capture.py` | 16384 samples at 25 and 6.25 MS/s | — |
| 3: `loopback.v` s, t, r, p | mean difference 0.00, 0.01, 0.10 codes (s, t, r). Impulse response: main tap 0.910 vs 0.896 at the same 6-sample delay, DC gain 0.745 both. Staircase 0.7763 × DAC + 26.95 vs 0.7765 × DAC + 27.03 | `data/loopback_16cm.npz` |
| 4: `make sim-lockin` | runs | — |
| 4: `lockin.v`, 0.1–24.9 MHz | amplitude 0.17% rms, phase 0.08° rms, delay 214.48 vs 214.46 ns (both boards repeat to 0.18–0.28%) | `data/cable_16cm_dac50.npz` |
| 4: `lockin_pll.v`, 0.1–24.9 MHz | 0.06% rms, 0.08° rms (repeat 0.11%) | `data/cable_16cm_dac100.npz` |
| 4: `lockin_pll.v`, 25.1–49.9 MHz | 1.1% rms, 0.94° rms (repeat 1.6–1.7%) | `..._dac100_hi.npz` |
| 5: BIOS `mem_write`/`mem_read` | the same dump, byte for byte | the tutorial |
| 6–7: firmware `fg`, `cap`, `li`, `sweep`; `cap_plot.py` | `sweep 100000 8000000 6`: 3871.3 mV / −10.77° … 3965.2 mV / −125.61° | the transcript: 0.02% to 3.3 MHz, 0.2% at 8 MHz, ≤ 0.14° |
| 8: driver through the cable | lock-in at 100 kHz 3.873 V; `sweep.sh` 3.8270 V at 1 MHz; a 250 kHz triangle capture | 8.7's 3.83 V |

Sweeps excluded points within 0.35 MHz of 12.5, 25, 37.5 and 50 MHz, where a lock-in at
25 MS/s is degenerate. New raw data: `data/cable_16cm_jlc2_*.npz`, `data/loopback_16cm_jlc2.npz`.

### New measurement 1: drive strength and DAC speed

The DAC plays a DDS sine (1.1 or 10.1 MHz, on exact FFT bins) from a PLL at 50, 100,
125, 150 or 200 MS/s. Four settings went on `dac_d` / `dac_clk`: 4 SLOW / 4 SLOW (the
tutorial's), 8 SLOW / 8 SLOW (Lattice's default), 4 SLOW / 8 FAST, and 16 FAST / 16 FAST.
`capture.v` records each through the cable, 4 × 16384 samples. Results at 100 MS/s, which
repeat to 0.1 dB over 3 runs (total SNR counts the spurs; broadband SNR leaves out bins more
than 15 dB above the floor):

| `dac_d` / `dac_clk` | total SNR, 1.1 / 10.1 MHz | broadband SNR, 1.1 / 10.1 MHz |
| --- | --- | --- |
| 4 SLOW / 4 SLOW | **37.0 / 38.7** | **47.0 / 46.0** |
| 8 SLOW / 8 SLOW | 34.0 / 36.2 | 45.6 / 44.6 |
| 4 SLOW / 8 FAST | 36.7 / 38.5 | 45.2 / 45.5 |
| 16 FAST / 16 FAST | 36.2 / 36.7 | 44.8 / 44.1 |

- **4 mA SLOW is best or tied at every rate tried** (50, 100, 150 and 200; 125 is
  explained below). The margin is small, but it's real.
- **A faster DAC clock edge didn't help.** The AD9708 datasheet asks for fast clock edges
  for low jitter, but at these frequencies the effect doesn't show.
- **Speed:** every setting reproduced the sine with normal amplitude, harmonics and noise
  at **200 MS/s**, past the AD9708's typical 125 MS/s and the ECP5's 150 MHz LVCMOS33
  rating. At 200 MHz the data changes 2.5 ns before each clock edge (setup ≥ 2.0 ns).
  The 1.1 MHz DDS itself failed FPGA timing at 200 MHz (173.6 MHz achieved, 7 seeds
  tried), so that point is missing. That's a limit of the DDS logic, not of the pins.
- **The dominant "noise" is the DDS, not the pins:** spurs near −47 dBc from its 8-bit
  phase truncation (≈ −6 dB × 8 bits). Their frequencies move with the tuning word, so
  only settings at the same rate and tone compare fairly.
- **125 MS/s is bimodal.** The same bitstream gives ~44 or ~38 dB from one load to the
  next. 125 MHz is the only rate here where the PLL divides its 50 MHz input by 2, so the
  DAC clock can line up with either of two 50 MHz edges, and hence with the ADC's samples
  in two ways. Every other rate repeats exactly.

### New measurement 2: the ADC at 31.25 MS/s

`adceye.v` runs everything from one 125 MHz PLL clock: the DAC at 62.5 MS/s with a
1024-entry sine table, and the ADC clocked by a second PLL output at 31.25 MHz (or 25 MHz)
shifted by 0, 2, 4 or 6 ns. The ADC's pins are sampled on every 125 MHz edge, so each ADC
sample is seen at 4 (or 5) points 8 ns apart: 16 (or 20) points per period at 2 ns
spacing. Two loads of each, three captures per load.

- At every shift, all capture points read the same clean data except at most one, which
  lands on the transition (2,100–2,800 of its 3,276 or 4,096 samples wrong). Only 2 of the 16 points
  hit it at 31.25 MS/s, and 2 of 20 at 25 MS/s. **The data is valid for about 28 of every
  32 ns.**
- **The best SINAD is 43.7 dB at 31.25 MS/s (6.97 effective bits) and 42.9 dB at
  25 MS/s.** Both include the DAC chain's distortion, so this bounds the ADC from below.
  The 4 mA SLOW ADC clock causes no visible duty-cycle trouble at 31.25 MHz.
- **The same bitstream gives 37.9 or 43.4 dB from one load to the next.** The DAC's
  62.5 MHz toggle can start on either of two 125 MHz edges, so the ADC samples either
  while the DAC switches or between switchings. This is the same ~5 dB as at 125 MS/s:
  the converters share a module and a ground. The tutorial's designs derive everything
  from one 50 MHz clock with fixed flip-flops, so they are deterministic.
- **What it takes in a real design:** the PLL clock (62.5 MHz, reference divider 4, in
  spec), a capture point away from the ~4 ns transition (found by a scan like this one,
  since t<sub>OD</sub> is only "typical"), and a deterministic DAC/ADC phase.

Code: `tools/pinspeed/` (README there). Data: `data/pinspeed_drive.npz`,
`data/pinspeed_eye.npz`. Both analysis scripts reproduce the numbers above from those files.

### Two modules on one Icepi Zero?

The 40-pin header is a Raspberry Pi header. **28 pins are FPGA I/O** (GPIO0–27). On the
Icepi Zero each goes only to the header and an ECP5 ball (checked in the board file): no
pull-ups and no shared functions, unlike a Pi's GPIO2/3. The other 12 are 2 × 5 V,
2 × 3.3 V and 8 × GND. One module uses 18 (8 ADC data + ADC clock + 8 DAC data + DAC
clock), and leaves 10.

| | everything separate | shared ADC clock + shared DAC clock (your idea) | shared ADC clock + **shared DAC data bus** |
| --- | ---: | ---: | ---: |
| ADC data | 16 | 16 | 16 |
| ADC clocks | 2 | 1 | 1 |
| DAC data | 16 | 16 | **8** |
| DAC clocks | 2 | 1 | 2 |
| **total (of 28)** | 36 | **34: 6 short** | **27: fits, 1 spare** |

So sharing the clocks alone doesn't work. What does work is sharing the **DAC data bus**.
The AD9708 latches its data on the rising edge of *its own* clock, so two DACs can sit on
one 8-bit bus with separate clocks. The FPGA puts out DAC A's word and clocks A, then puts
out B's word and clocks B. The bus then runs at twice the per-DAC rate: 2 × 50 MS/s means
100 Mwords/s, which this stack runs today, and today's 200 MS/s result suggests headroom.
Sharing the **ADC clock** is natural, and useful: both ADCs then sample at the same instant,
for two-channel measurements such as a device's input and output together. With separate
ADC clocks the count is 28, with nothing spare. The ADCs can't share a data bus: the module's
connector brings out only the 18 signals, and the AD9280's three-state switching
(t<sub>DEN</sub> 25 ns, t<sub>DHZ</sub> 13 ns) is too slow at 25 MS/s anyway.

What the shared bus costs and needs:

- **More digital activity at each DAC.** The bus toggles at twice the rate, and each DAC
  sees the other's words. Today's measurements say switching *timing* relative to ADC
  sampling matters at the 5 dB level. So place both DAC clocks, and the ADC sampling
  instant, deliberately.
- **Two loads and a stub on each data line.** The edges get slower. 4 mA may need to
  become 8 mA, which costs ~1–2 dB by today's numbers. Keep the stubs short.
- **Power:** both modules from the header's two 5 V pins. The adapter README estimated
  ~250 mA worst case per module (never measured). Two, plus the Icepi Zero, could exceed a
  500 mA USB 2.0 port: use a USB-C supply that offers ≥ 1.5 A, or measure first.
- **Mechanics:** two modules don't fit over a 65 × 30 mm Icepi Zero. This would be a
  larger carrier board with two module sockets.
- **Ways I wouldn't use:** finding more pins elsewhere. The mini-HDMI connector's 8 TMDS
  lines and the USB-C data lines are FPGA pins, but reaching them takes adapters and cables.
  Dropping DAC or ADC bits is the other option, and it costs resolution.

### Traps found along the way

- **`PYTHONPATH` with an empty entry** (this PC's ends in `:`): running a LiteX tool
  from `IcepiZeroADCDAC_tutorials/` imports the tutorial's `litex/` folder as the
  `litex` package, giving `cannot import name 'RemoteClient'`. Added to Appendix A.
- On the board, `od -v | sort` over a 16 kB capture takes over a minute. That's the slow
  CPU again; my helper's 60 s timeout then desynchronised.
- My own mistakes, fixed: `pkill -f` with a pattern that matched its own shell (twice),
  and a first `adceye.v` that assigned the same registers from two `always` blocks.

### Changes

- Tutorial:
  - Part 1: the drive paragraph now gives the measurements.
  - Part 2: three crystals.
  - Part 3: the 31.25 MS/s paragraph is now measured, plus the DAC/ADC timing effect.
  - 9.10: the third board's crystal.
  - Appendix A: the `PYTHONPATH` row.
  - Appendix B: "On a third board, with the module", and the not-tested list updated.
- New: `tools/pinspeed/` (8 files + README), `data/pinspeed_drive.npz`,
  `data/pinspeed_eye.npz`, `data/cable_16cm_jlc2_{dac50,dac100,dac100_hi}.npz`,
  `data/loopback_16cm_jlc2.npz`.
- `tools/sync_md.py --check`: all code blocks match. Nothing committed.

### Still not tested on JLC 2

- The LEDs: the counter was loaded but nobody watched it.
- Pressing the buttons.
- The FPGA's USB-C ports and HDMI.
- The supply voltages, and the module's current draw. That draw matters for the
  two-module question.

**Board state:** JLC 2's flash holds `icepi_zero_adda.bit` (verified), and JLC 1's card is in
it, so it boots to a login with `adda.ko` loaded in 61 s.

## Prompt 7

The LEDs looked good. Test a 3rd JLCPCB board with the microSD card inserted, but no header soldered on (and therefore no ADC or DAC). When you've tested the hardware you can test, I'll give you the last one to test and we'll call our JLCPCB run a success.

## Response 7 2026-09-30 20:48:00 - 2026-09-30 21:22:46 Claude Opus 5.5

JLC 2's LEDs are confirmed: Appendix B now says its counter was watched. **JLC 3** is FT231X
`DP0525LR`, with no header and the same SD card (SanDisk SC64G, serial 0x08db0f22). It
passes everything testable without the header:

| test | JLC 3 | JLC 1 / JLC 2 |
| --- | --- | --- |
| JTAG | LFE5U-25, IDCODE 0x41111043 | same |
| buttons, card detect | both released; `SD_DET` = 1 (card in) | same |
| flash | blank W25Q128, unprotected; quad SPI at 62 MHz configures the FPGA (3 of 3); Linux SoC written in 52.2 s and read back identical | same |
| SDRAM | `mem_test` over all 32 MiB, twice, OK; 14.6 / 20.2 MiB/s | same |
| 8.3 serial boot, as now written (one command, under `script`) | request caught, 4 files at 42–44 kB/s, RAM-disk Linux to `buildroot login:` | JLC 1 by script |
| boot from flash + card | login at 61.3 and 61.1 s; card found at 7.0 s | 60.9, 61.0 / 61.2 |
| Linux | `uname`, `cpuinfo`, `free` (22992 kB), `/bin/true` 0.39 s, device tree, `devmem`, driver loaded at boot, sysfs files, a capture (all code 0: no module), lock-in and `sweep.sh` near zero | same |
| SD card | 8 MB raw read 285 kB/s, write with `fsync` 199 kB/s, MD5s match; marker file appended | 287 / 215, 285 / 201 |
| oscillator | 49,999,895.0 Hz, **−2.10 ppm** (12 min against NTP) | −3.30 / −1.70 |
| Part 1 counter | loaded at the end and left running for you to look at | watched on both |

Changes: Appendix B gets "On a fourth board". Part 2 and 9.10 list the fourth crystal.
Nothing committed.

**Board state:** JLC 3's flash holds `icepi_zero_adda.bit` (verified), and the card is in it.
The counter is running in SRAM right now; power-cycle the board (or `openFPGALoader -r`)
and it boots Linux from the card.

## Prompt 8

In addition to the one you just tested, there are 3 other JLCPCB Icepi Zeros connected to USB, each of which now has the header and the DAC+ADC module. You can finish testing the one with no header, but then focus on the other 3. The DAC+ADC module from before is still in the loopback configuration with the same 16.5 cm cable. The other two are connected to each other, with one's DAC connected to the other's ADC and vice versa. These are connected through two short 16.5 cm cables. The LEDs are all working and doing the LiteX "chase" pattern, so the additional 3 seem to be working.

Put these through their paces, testing the DAC+ADC modules and their communication with their Icepi Zeros as best you can. Each of the modules has a potentiometer onboard, and these have been left as they came.

Then, spend the night coming up with (and testing) interesting experiments or additions to the tutorial that could be accomplished with 2 boards connected to each other. Focus on both potentially interesting physics demonstrations and also on communication demonstrations or other demonstrations. These can be integrated into the openfpga/IcepiZeroADCDAC_tutorials.md document, but they should be self-contained enough to be cut out and pasted into a more advanced, second tutorial. I'll let you decide if raw verilog, LiteX, or LiteX+Linux is the best way to demonstrate each new interesting thing.

I hope to come back tomorrow morning to some fascinating ideas and results. I'm sure that some of these will be jumping off points for even more interesting demonstrations once additional hardware is added (hopefully things we already have or things that are easy to make or buy). Don't get stalled waiting indefinitely for something and don't stop unless something goes wrong that prevents you from continuing.

## Response 8 2026-09-30 22:05:00 - 2026-10-01 05:52:00 Claude Opus 5.5

Boards on the PC, by FT231X serial number (never by `ttyUSBn`, which moved during the night):

| name | serial | state |
| --- | --- | --- |
| JLC 1 | DP0525BU | header + a new module; cross-connected with JLC 2 |
| JLC 2 | DP051TLX | header + a new module; cross-connected with JLC 1 |
| JLC 3 | DP0525LR | header + the original module, looped back on itself (16.5 cm) |
| JLC 4 | DP0524FJ | no header; the SD card |

(The wiring was found, not assumed: each module board played a different frequency and
each ADC said whose it heard. The original module turned out to be on JLC 3.)

### Short version

- **JLC 4 (no header) is finished:** crystal −2.00 ppm against NTP. (A first attempt measured
  nothing: with several boards attached, a plain `openFPGALoader -b icepi-zero` loads
  *some* board. Everything since selects boards by FT231X serial number.)
- **The module boards and their modules all work.** On all three paths (JLC 3 looped back,
  JLC 1 → JLC 2, JLC 2 → JLC 1) the staircase is linear to 0.25 codes rms, and every ADC code
  between 29 and 225 appears, so no DAC or ADC bit is stuck. A 1.3 MHz sine gives a SINAD of
  40.4–40.5 dB on the new modules and 36.1 dB on the original. The new modules have 0.7% more
  gain (0.7815–0.7818 ADC codes per DAC code, against 0.7761); their potentiometers are a
  plausible cause.
- **A new Part 10, "Two boards"**, about 1,770 lines in the tutorial with its own folder
  `twoboard/`. It is self-contained enough to lift out as a second tutorial. Everything in it
  was run tonight, with the figures made from the data:

| | what | headline result |
| --- | --- | --- |
| 10.1 | two boards on one PC; the links checked | serial numbers, `/dev/serial/by-id`, the 4 kB read trap |
| 10.2 | two clocks (Part 4's `lockin.v` on both) | a beat of ±0.7591 Hz at 1 MHz, mirror-imaged; Allan deviation ≈ 1e-9 at 0.1–1 s, then drift; overnight the difference wandered +0.7 to +2.4 ppm, and the PC's NTP clock wandered by up to 3 ppm per 10 minutes |
| 10.3 | warming a crystal (`warmup.v`: a heater and the ECP5's DTR thermometer) | the crystal falls 3.0 ppm in 15 min of self-heating; two time constants; the PC as referee says it was A's crystal that moved |
| 10.4 | two-way time transfer (`awgcap.v`, `twoway.py`) | round trip 425.63 ± 0.15 ns; clock offset drifts 0.748 ppm, a third method agreeing with the beat and with NTP |
| 10.5 | coupled oscillators (`coupled.py`); a hardware PLL (`pll.v`) | lock range = K; slip rates follow Adler to 0.033 Hz rms, locked phase follows arcsin(Δ/K); hardware PLL: B a copy of A's clock to 0.07° (0.2 ns) |
| 10.6 | a real-time FSK modem in Verilog (`modem.v`), and Linux over it; its error rate against noise | 0 errors up to 2.5 Mbaud, full duplex; two FPGA Linux computers swap files (identical MD5), and with SLIP they `ping` each other (0% loss) and copy a file by TCP; with noise, the decisions follow ½ exp(−W·SNR/4), and a receiver with its own bit clock gains 10 dB |
| 10.7 | OFDM and Shannon (`ofdm.py`, `ber_curve.py`) | QAM-64 at 55.9 Mbit/s (0–17 errors in 366k bits); QAM-256 at 74.5 Mbit/s with BER 2e-3; the BER-vs-SNR points lie on the textbook QAM curves |
| 10.8 | ideas needing more hardware | antennas, light, sound, GPS, Johnson noise, a third board, PPP |

### Testing the module boards

`tools/twoboard/module_test.py` loads the tutorial's `loopback.v` into all three boards and
reads every board at once (one thread per port). JLC 3's record is its own pattern, and each of
JLC 1 / JLC 2 records the other's, from an arbitrary starting point, re-aligned at the
staircase's one big drop.

| path | ADC code per DAC code | offset | INL rms / worst | missing ADC codes | 1.3 MHz sine: H2, SINAD |
| --- | ---: | ---: | --- | --- | --- |
| JLC 3 → JLC 3 (the original module) | 0.7761 | 27.57 | 0.25 / 0.53 | none in 29–224 | −47.9 dBc, 36.1 dB |
| JLC 1 → JLC 2 | 0.7815 | 27.03 | 0.25 / 0.51 | none in 29–225 | −48.4 dBc, 40.4 dB |
| JLC 2 → JLC 1 | 0.7818 | 27.21 | 0.24 / 0.50 | none in 29–225 | −49.1 dBc, 40.5 dB |

All 8 DAC bits and 8 ADC bits work on all three modules. The potentiometers were not touched.
What they set is still unknown: turning one while `module_test.py` or a lock-in runs would
show it in a minute.

### IP between the two FPGA Linux computers

After the file transfers worked, I added `CONFIG_SLIP=y` to `linux/kernel_modules.config` and
`slattach`, `nc` to `linux/busybox.config`. The rebuild took 28.5 s, and the kernel grew 16 kB
to 9,129,904 bytes. Part 8 now notes that its quoted sizes predate these lines. Booted on both
boards of the pair (`tools/twoboard/linux_slip_test.py`):

- `ping` A → B 5/5 (43–51 ms), B → A 3/3 (49–61 ms), 0% loss; `ping -s 1000` 20/20 at
  259 ms. That's 178 ms of serialization at 115 200 baud, plus processing.
- TCP: `nc` carried a 32 kB random file A → B with an identical MD5 (`192d7b31…`). BusyBox's
  minimal `nc` has no `-w`, so the sender runs in the background and is stopped later.
- `sl0` counters: 147 packets out, 101 in, 0 errors.

### After midnight: the modem against noise (10.6)

The 10.6 "Try this" about noise became a worked experiment, on JLC 3 (looped back), so the
pair was free for the overnight clock log.

- **`twoboard/modem_noise.v`** is `modem.v` with three knobs: `NOISE` (white noise added
  before the DAC, the sum of the four bytes of a 32-bit xorshift generator, 0.577 × NOISE
  codes rms), `AMP` (tone amplitude) and `LOGWIN` (receiver window 2^LOGWIN samples). With the
  defaults it is `modem.v`. `twoboard/modem_ber.py` counts bit errors through one looped-back
  board and aligns what came back first (difflib), because a broken start bit loses or
  invents bytes. `make modem_noise NOISE=… AMP=… LOGWIN=…` builds a variant.
- **19 settings, 800,000 bits each** (`tools/twoboard/fsk_ber.py`). The SNR per ADC sample
  was measured, not assumed (a steady tone plus the noise, recorded with `capture.v`); it is
  within 0.6 dB of 1.5·(AMP/NOISE)². The same records, put through the receiver's arithmetic
  in numpy, give the error rate of the decisions alone.
- **The decisions follow non-coherent FSK theory, ½ exp(−W·SNR/4)**, for W = 16 and 128, and
  the 128-sample window gains the predicted 9 dB. Through the PC's UART, errors are 2–5×
  (W = 16) and 8–30× (W = 128) higher: a wrong decision at a start or stop bit misframes a
  byte, and a long window blurs the edges the UART times from. A simulation of the whole
  chain (`tools/twoboard/fsk_sim.py`) reproduces both within a factor of 2 over most of the
  range, and with perfect bit timing falls back onto theory.
- **The textbook receiver, built: `tools/twoboard/modem_sync.v`.** 216-sample sums and its
  own bit clock, kept centred by an early–late gate. Through the UART: BER 10⁻³ at −7.5 dB,
  1.7 dB better than the 128-sample window and 10 dB better than `modem.v` (theory 2.3 and
  11.3 dB). In the tutorial as a paragraph and a third curve in `img/tb_fskber.png`; the file
  itself stays in `tools/`.
- Student path checked by hand afterwards: `make modem_noise NOISE=86`, `make load-…`,
  `modem_ber.py` gave BER 2.82 × 10⁻⁴ (the sweep: 3.7 × 10⁻⁴); NOISE=61 AMP=25 LOGWIN=7 gave
  3.3 × 10⁻³ (sweep: 2.6 × 10⁻³).

### After midnight: which crystal moved in 10.3?

`warmup_run.py` already saved the PC arrival time of every lock-in result, and B sends one
every 2²⁰ of its own samples. So B's crystal against the PC's NTP clock was in the data all
along: B stayed within 0.3 ppm, while A fell 2.6 ppm and came back only 0.8. It was A. Now
in 10.3. The PC's clock is only a rough referee. `systemd-timesyncd` polls every 34 minutes
over a 139 ms network path (jitter 1.6 ms). A log of the kernel's clock discipline
(`adjtimex`, every 10 s from 02:24) shows each poll finding the clock up to 1.35 ms off,
changing its frequency correction by up to 0.33 ppm (−3.07 → −3.51 ppm by 04:18), and slewing
the offset away at up to 0.85 ppm. In the 15-minute beat run, the two boards' PC-timed
frequencies wandered together by ±1 ppm in 100 s blocks, while their difference stayed with
the beat.

### Overnight: two crystals for five hours (10.2)

`lockin_log.py` on JLC 1 and JLC 2 from 00:41 to 05:41 (`lockin.bit`, 1 MHz), started detached
with `setsid nohup` so it would outlive the session's 2-hour limit on background jobs:
429,153 results per board, none lost. `data/tb_beat_1M_overnight.npz` keeps every 4th result
(3 MB instead of 12 MB; the scripts read its `every` key). Results, now in 10.2 with
`img/tb_overnight.png` and a third curve in `img/tb_adev.png`:

- f_B − f_A wandered between +0.7 and +2.4 ppm, mostly slowly, with sudden steps of 0.3–0.5 ppm
  (01:05, 01:25, 03:52) that both lock-ins see identically. Their cause is unknown.
- Allan deviation: about 1 × 10⁻⁹ from 0.2 to 2 s (the shorter runs agree), then up to
  5 × 10⁻⁸ at 100 s, 1.5 × 10⁻⁷ at 1000 s and 3.5 × 10⁻⁷ at 1.7 h. It never turns down.
- Against the PC's clock (arrival times, 10-minute blocks), both boards moved together by up
  to 3 ppm, at the `timesyncd` polls. B − A averaged +1.527 ppm over the night, against the
  beat's +1.502 ppm. The kernel's frequency correction went from −3.07 to −4.00 ppm in six
  polls (`data/tb_pc_adjtimex.npz`, logged from 02:24), so the PC's own crystal drifted too.
- An averaging slip of mine: first I averaged groups of 8 results to shrink the file. With a
  beat of up to 1.5 Hz, 0.34 s groups are at the Nyquist limit, and the averaged phase aliased
  (the beat came out −0.15 instead of +1.51 ppm). Keeping every 4th raw result is safe up to
  3 Hz.

### Morning: every Part 10 script once more (`tools/twoboard/smoke_pair.sh`)

Run on the pair at 05:44, briefly, exactly as the tutorial prints the commands:

| section | script | result |
| --- | --- | --- |
| 10.2 | `lockin_log.py` + `beat.py`, 30 s | ±0.7550 ppm, mirror-imaged |
| 10.5 | `coupled.py`, one-way K_B = 1 Hz | locked: φ_A −27.3 ± 0.1°, B moved −0.774 Hz |
| 10.5 | `coupled.py`, mutual K = 0.5 Hz | not locked, as Adler says: the detuning (0.755 Hz) is outside K |
| 10.3 | `warmup_run.py`, 4 minutes | ran; heater on and off, DTR code reported |
| 10.5 | `pll_pair.py`, 10 s open, 20 s closed | open beat 2.078 Hz (A just heated), locked to 0.107° rms |
| 10.4 | `twoway.py`, 20 s | round trip 425.4–426.0 ns |
| 10.7 | `ofdm.py` QAM-64 A → B, QAM-16 B → A | 6.8 × 10⁻⁵ (10 errors, EVM 3.8%); 0 errors, but EVM 5.1% |
| 10.6 | `modem_test.py` at 1 Mbaud and 115,200 baud | 0 wrong in 20,000 / 5,000 bytes, both ways at once |

The 5.1% EVM didn't recur: four repeats of QAM-16 each way gave 3.0–3.5%, and QAM-64
B → A gave 0 errors at 3.2%. It was probably taken while A's crystal was still recovering
from the short heating run just before. Earlier, `pll_test.py --test-offset 100` on JLC 3
locked at +100 Hz with a 0.5–0.6° phase error, and `ofdm.py` looped back on JLC 3 gave
QAM-64 with 0 errors (EVM 3.0%) and a sounded capacity of 169 Mbit/s. All the figure scripts
regenerate their figures from `data/`.

### Things that went wrong, and what they taught

- **`openFPGALoader -b icepi-zero` with several boards attached picks one** (not necessarily
  the one you mean). My first JLC 4 oscillator run listened to the wrong board and got nothing.
  Fix: `--usb-serial-num`, and `/dev/serial/by-id/` names. Now in 10.1, and in
  `tools/boardtest/Makefile` (`SERIAL=`).
- **Reading several serial ports one after the other loses data.** The kernel keeps about
  4 kB per port, and a 16 kB record overflowed it while I was reading another board. Fix:
  a thread per port (`awgcap.record_many`, `module_test.py`, `modem_test.py`).
- **Channel sounding across boards first said 25 dB SNR**, then 18, then 40. The first was a
  bug of mine: I divided by the number of records twice. The second came from comparing
  *different* records, whose DAC images fold back with a phase that rotates every ~27 ms
  as the two sample clocks slide. Comparing the two loops *within* a record gives the real
  noise, about 40 dB per bin.
- **`pll.v` first jumped by 48.8 kHz whenever Q went negative.** In
  `tw0 + (Q >>> 10) + integ`, unsigned `tw0` makes Verilog treat the whole expression as
  unsigned, and `>>>` then becomes a logical shift. Now a `signed` wire. It's in the tutorial
  as a lesson.
- **Linux refused the second LiteX UART** (`error -22`): `CONFIG_SERIAL_LITEUART_MAX_PORTS`
  defaults to 1. `linux/kernel_modules.config` now sets 2. The kernel and rootfs rebuilt in
  35 s, the `Image` is the same size, and `images_adda/` (Part 8) was not touched.
- **At 1 Mbaud with 64-byte FIFOs, Linux lost 97% of a file**: the receive FIFO overflows in
  0.64 ms. The modem SoC now uses 115 200 baud and 512-byte FIFOs. The very first file after a
  board booted still lost 6% while the start-up scripts ran. After that, 4 of 4 were perfect.
- **A serial-boot upload stalled** when I loaded bitstreams into *other* boards during it.
  Since then, boards serial-boot one at a time with no other USB activity, and no stall has
  recurred.
- **The FSK error-rate sweep hung** at −10.5 dB with the 128-sample window. With that much
  noise, the idle MARK tone makes false start bits, garbage bytes never stop, and "read until
  the line is quiet for 0.5 s" never ended. Now there is a deadline.
- **The first noise source was four 16-bit LFSRs**, which are shifted copies of one sequence
  that repeats every 1.3 ms. Its sweep matched the xorshift one except at the two
  highest-SNR settings of the 128-sample window, where it gave fewer errors. Replaced, to be
  safe.
- **The FT231X can't make 115,200 baud.** It sends 3 MHz / 26 = 115,385 baud: 216.67
  samples a bit, not 217. `modem_sync.v`'s first version got 11% of the bits wrong without
  any noise, until its bit length became fractional. No UART notices 0.16%.
- **An integrate-and-dump receiver that restarts at each start edge** is hopeless at the SNRs
  where it would help: in simulation, below −8 dB, its 16-sample edge detector is wrong a
  quarter of the time. A bit clock that averages over many edges works.
- My own scripting errors, twice each: `pgrep -f`/`pkill -f` patterns that matched the
  shell running them (fix: `'name[.]py'`-style patterns, and no kill in the same command
  line), and wait loops that could never end for the same reason.

### Not done, or not tested

- The new modules' potentiometers (see above), and the ADC's full range (the DAC only reaches
  codes 29–225).
- 10.8's ideas: they need parts.
- Noise from a physical source (a noise diode, a hot resistor). The noise of 10.6 and 10.7 is
  made digitally and added before the DAC, so it does cross the analog path, but it isn't
  independent of the transmitter.
- Remote login across the cable. IP works (see above), but `telnetd` isn't in BusyBox here,
  and adding `CONFIG_FEATURE_TELNETD_STANDALONE` makes Buildroot start `telnetd` at every
  boot, which would change Part 8's images. Left as a 10.8 idea.

### Files

- New folder `IcepiZeroADCDAC_tutorials/twoboard/`: `awgcap.v`, `awgcap.py`, `twoway.py`,
  `coupled.py`, `lockin_log.py`, `beat.py`, `warmup.v`, `warmup_run.py`, `pll.v`,
  `pll_test.py`, `pll_pair.py`, `modem.v`, `modem_test.py`, `make_modem_linux.py`,
  `ofdm.py`, `ber_curve.py`, `modem_noise.v`, `modem_ber.py`, `Makefile` (with a
  `modem_noise` rule), `.gitignore`.
- New `tools/twoboard/` (instructor): `boards.py`, `module_test.py`, `sine_quality.py`,
  `linux_modem_test.py`, `fig_beat.py`, `fig_adev.py`, `fig_warmup.py`, `fig_twoway.py`,
  `fig_adler.py`, `fig_pllpair.py`, `fig_ofdm.py`, `fig_ber.py`; after midnight
  `fsk_ber.py`, `fsk_build.sh`, `mn_measure.v`, `fsk_sim.py`, `modem_sync.v`,
  `fsk_sync_ber.py`, `fsk_sync_run.py`, `fig_fskber.py`, `fig_overnight.py`, `smoke_pair.sh`.
- New data `data/tb_*.npz` and figures `img/tb_*.png`.
- Changed: `linux/kernel_modules.config` (two LiteX UARTs, `CONFIG_SLIP`), `linux/busybox.config`
  (`slattach`, `nc`), `tools/boardtest/Makefile`
  (`SERIAL=`), `tools/boardtest/measure_osc.py` (port argument), `tools/boardtest/bootload.py`
  (`--port`); the tutorial: Part 10, Contents, Appendix B, and one caveat in 9.10 about the
  PC's clock.
- `tools/sync_md.py --check`: all code blocks match. Nothing committed.

**Board state (06:00):** all four boards still have the Part 8 Linux SoC in flash, and JLC 4
has the SD card. JLC 1, JLC 2 and JLC 3 run `awgcap.bit` (SRAM) from the last tests; JLC 4 was
not touched overnight. A power cycle returns all of them to the flash SoC. Nothing is
committed.

## Prompt 9

All 5 Icepi Zeros are connected to USB. 3 have DAC+ADC boards. All 5 have new SD cards that should format and put your final version of linux on. Make sure they boot and talk to the computer reliably.

## Response 9 2026-10-01 18:57:42 - 2026-10-01 20:01:43 Claude Opus 5.5

**All five boards now boot Part 8's Linux from their new cards, and passed 35 boots with no failure.**

| board | serial | module | SD card | boots tested | reset → `login:` | 1 MHz at the ADC |
| --- | --- | --- | --- | ---: | --- | --- |
| original | DK0GFLAW | none | 14.6 GiB | 7 | 57.5–60.1 s | 0.005 V (no module) |
| JLC 1 | DP0525BU | new, cross-connected to JLC 2 | 14.6 GiB | 7 | 57.5–60.1 s | 3.827 V (JLC 2's DAC) |
| JLC 2 | DP051TLX | new, cross-connected to JLC 1 | 14.6 GiB | 7 | 57.5–60.1 s | 3.829 V (JLC 1's DAC) |
| JLC 3 | DP0525LR | original, looped back | 14.6 GiB | 7 | 57.5–60.1 s | 3.820 V (its own DAC) |
| JLC 4 | DP0524FJ | none | 14.6 GiB | 7 | 57.5–60.1 s | 0.006 V (no module) |

(The boot-time range is over all five boards' boots. Every card reported itself as 14.6 GiB in the
installer's log (`mmcblk0: mmc0:0001 USD 14.6 GiB`).)

### What is on them

The "final version": the Buildroot build from 2026-10-01 00:24 (kernel 6.12.0, 9,129,904-byte
`Image`, with Part 10's `CONFIG_SLIP`, two LiteX UARTs, and BusyBox's `slattach` and `nc`),
installed exactly as 8.7 describes:

- **SPI flash:** `build/icepi_zero_adda/gateware/icepi_zero_adda.bit` (Part 8's SoC, built
  09-29), rewritten on all five with `openFPGALoader -f --verify` (70–77 s each), so all five are
  known to hold the same gateware.
- **SD card:** partition 1, 64 MiB FAT32 with `Image`, `opensbi.bin`, `rv32.dtb`
  (`root=/dev/mmcblk0p2`) and `boot.json`; partition 2, 4 GiB ext2 with the root file system.
  `make_sd_installer.sh` rebuilt `images_sd/` and `images_install/` from that Buildroot build.
- **8.7's tuning, on every card:** `S01syslogd S02klogd S02sysctl S40network S50crond` moved to
  `/etc/init.d/off`, and `S90adda` loads `/root/adda.ko` at boot. `adda.ko` was rebuilt against
  the current kernel first: it came out bit-identical to the one already in the root file system.

### How (`tools/boardtest/sd_provision.py`, new)

Five boards, one process each, all at once. Each one:

1. types `reboot` at the board's `litex>` prompt (where the BIOS ends up after power-up with a
   card that has no `boot.json`), and answers the serial-boot request with `images_install/`.
   It never calls `openFPGALoader`, because last night a bitstream load on one board stalled
   another board's upload. Five uploads at once each ran at full speed: 15 MB in about 5½ min.
2. logs in, runs `install-sd.sh` (320–347 s), and does the tuning on the card;
3. boots from the card several times. After each boot it logs in and checks: the kernel command
   line says `root=/dev/mmcblk0p2`, `/` is mounted from it, the driver printed `ADC/DAC
   peripherals ready` during boot, and `/sys/bus/platform/devices/f0002000.adda/` exists. It
   also checks the serial link both ways: 32 kB of random bytes from the board as base64,
   checked against the board's md5, and 4 kB typed into the board as a base64 here-document,
   checked by its md5.

Boots: round 1, three by `reboot` on each board; round 2, one by `reboot` and three by
`openFPGALoader -r` on each board (the FPGA reloads from flash, as at power-up; those resets
were done one board at a time). **35 boots, all from the card, all checks passed every time.**
From reset to `login:` took 57.5–60.1 s. 8.7's table says 61 s, and its 86.5 s untuned.
`tools/boardtest/adda_check.py` (new) then set every DAC to 1 MHz and read every lock-in and
one capture.

### Things that went wrong (all mine, in the test scripts; none in the boards)

- **The first install command was cut short.** My console helper typed the command right after
  logging in, before the board's shell had run `stty -echo`, so it saw the next prompt and
  returned early. The queued command ran anyway, and the script gave up. Fix: after login, wait
  for a marker that only the board can print (`echo "SY""NC"` → `SYNC`). The install was then
  rerun cleanly on all five, without a second upload (`--skip-upload`).
- **"No BIOS banner", twice.** This BIOS prints `BIOS CRC passed`, not `BIOS built on`, so my
  second marker, `LiteX SoC`, matched the kernel's `LiteX SoC Controller` line instead. The first
  15 boots were marked "PROBLEM" for that reason only: their logs show `Booting from SDCard`,
  and every real check passed. Then my reader searched only the last 400 bytes of each read, and
  the banner arrives in one burst with the memory test after it. Both fixed.

### Board state (20:01)

All five are logged in as root on their card-booted Linux, with every DAC playing 1 MHz (from
`adda_check.py`). Power them off whenever you like: type `sync` first if you have changed
files (8.7). Each will boot from its card at the next power-up. Nothing is committed.

## Prompt 10

Split Part 5 in three:
* The first should be getting a RISC-V processor on the chip, and having it boot into LiteX where you enter some terminal commands like directly writing to memory to toggle the LEDs
* Then running a simple C program (maybe search for prime numbers like in openfpga-icebreaker.md).
* Then getting the peripheral to work within the LiteX framework.

Similarly, Part 8 should be split in two:
* Getting linux up and running