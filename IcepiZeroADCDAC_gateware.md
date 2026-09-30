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
