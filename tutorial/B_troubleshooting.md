<!-- nav -->
[← Appendix A. Why this hardware?](A_why_this_hardware.md#appendix-a-why-this-hardware) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)** &emsp;&emsp;&emsp; [Appendix C. How this tutorial was tested →](C_how_it_was_tested.md#appendix-c-how-this-tutorial-was-tested)

# Appendix B. Troubleshooting

<img src="img/stack_loopback.png" alt="Seen from above, USB connectors at the bottom: ADC IN is the left SMA, DAC OUT the right one" width="340">

The most common problem of all: the wrong SMA connector. With the USB
connectors toward you, **ADC IN is on the left and DAC OUT on the right**.

## Connecting to the board

| symptom | cause and fix |
| --- | --- |
| The ADC reads a constant (about 127, or nothing changes), or the DAC's signal doesn't arrive | the wrong SMA. With the USB connectors toward you, **ADC IN is the left-hand SMA and DAC OUT the right-hand one** ([0.00](0_00_the_hardware.md#which-sma-is-which)) |
| `openFPGALoader` can't find the board, or `Permission denied` | Linux and WSL: the udev rule and group membership of [1.00](1_00_circuits_from_code.md#100-circuits-from-code); unplug and replug the board afterwards, and log out and back in |
| WSL: no `/dev/ttyUSB0`, or `openFPGALoader` sees nothing | the board isn't attached to WSL: `usbipd attach --wsl --busid ...` in PowerShell, again after every replug. If `lsusb` shows the board but there's still no `/dev/ttyUSB0`, `sudo modprobe ftdi_sio` |
| macOS: `openFPGALoader` can't open the FTDI device | another program has the serial port open (close it). If it still fails, try `sudo openFPGALoader ...` (untested on a Mac) |
| `/dev/ttyUSB0` vanishes while loading a bitstream | normal: the same FT231X chip does both jobs. Close serial programs before loading; the port comes back afterwards |
| with several boards, the wrong one answers | `ttyUSB` numbers change. Use serial numbers: [5.00](5_00_two_boards.md#500-two-boards-on-one-laptop) |
| a Python script gets no bytes back | the wrong bitstream is loaded, or a terminal program still has the port open |

## Chapter 1

| symptom | cause and fix |
| --- | --- |
| nextpnr: `IO 'x' is unconstrained in LPF` | a port name in your design has no `LOCATE` line in `icepi_adda.lpf` (check the spelling and the `[n]` indices) |
| nextpnr: `FAIL at 50.00 MHz` | some path has too much logic for 20 ns: register an intermediate result (pipeline it), as `lockin.sv` does |
| Yosys: `syntax error` on a line that looks fine | the file must end in `.sv` for Yosys to read SystemVerilog; and `logic x = a & b;` is a one-time initial value, not a connection: write `logic x; assign x = a & b;` |
| the DAC output sits at full scale before loading, or with `capture.sv` loaded | normal: FPGA pins that nothing drives float high |
| captures show a flat line at code ~127 | nothing connected to the ADC input (it reads 0 V) |
| captures show codes stuck at 0 or 255 | an input beyond ±5 V, or the module not powered or plugged in the wrong way round |
| a PLL design does nothing | the logic waits for `locked`. Check the `ecppll` numbers, and that the VCO is within 400–800 MHz |

## Chapter 2

| symptom | cause and fix |
| --- | --- |
| LiteX build: `No module named 'litex'` | the Python virtual environment of [1.00](1_00_circuits_from_code.md#100-circuits-from-code) isn't active (`source $ADDA/tools/venv/bin/activate`), or you sourced the OSS CAD Suite's `environment` script, which puts its own Python first. Put only its `bin/` on your `PATH`, as in [1.00](1_00_circuits_from_code.md#100-circuits-from-code) |
| `ImportError: cannot import name ... from 'litex' (unknown location)` | you ran a LiteX tool from inside `$ADDA/tools/litex`, where the `litex/` clone hides the real package. Run it from anywhere else |
| firmware: `undefined reference to 'atoi'` (or `sqrtf`, `strtok`) | the SoC was built without `--libc-mode full` |
| firmware: `undefined reference to '__floatdisf'` | converting a 64-bit integer to `float`, which LiteX's runtime library can't do. Shift down to 32 bits first, as `main.c` does |
| `litex_term` exits with `Lost connection to the device` | a bitstream was loaded while it was running. Load first, then start `litex_term` |
| `serialboot` loads, but the program crashes or prints nothing | the program was built against a different SoC's build folder (`BUILD_DIR` in its `Makefile`) |

## Chapter 3

| symptom | cause and fix |
| --- | --- |
| no `litex>` prompt after loading the Linux SoC; the [BIOS](https://en.wikipedia.org/wiki/BIOS) sits at `Booting from SDCard in SD-Mode... Booting from boot.json...` | the SD slot is empty. The BIOS tries 1000 times to wake a card and waits up to 1 s for each answer, so it's stuck for about 17 minutes. Load the bitstream and start `litex_term` in one command ([3.01](3_01_booting_linux.md#301-booting-linux)), or insert a card |
| Linux: `unhandled signal 11 ... in ld-linux-riscv32-ilp32.so.1`, then `Attempted to kill init!` | a glibc root file system from [Buildroot](https://en.wikipedia.org/wiki/Buildroot) 2026.02; use the musl `icepi_adda_defconfig` of [3.03](3_03_building_linux.md#303-building-linux-yourself) |
| Linux can't unpack its root file system, or can't find `/init` | `rv32.dtb` still records an old `rootfs.cpio.gz`'s size. Re-run `make_linux.py` |
| `insmod: ... Invalid module format` | `adda.ko` was built against a different kernel from the one running. Rebuild it in `src/linux/driver/` |
| characters go missing when you paste into the board's console | its serial receive buffer is small. Paste slowly, or a line at a time |
| `install-sd.sh` says `missing /boot/sd/mbr.bin` | the board was booted from `images/`, not `install/` ([3.04](3_04_booting_from_sd.md#304-booting-from-an-sd-card)) |
| the BIOS can't boot from a card that's in the slot | no `boot.json` on its first (FAT) partition. Write the card as in [3.04](3_04_booting_from_sd.md#304-booting-from-an-sd-card) |
| Linux stops at `Waiting for root device /dev/mmcblk0p2...` | the card has no second partition, or isn't seated. From a serial-booted system, `ls /dev/mmcblk0*` shows what Linux sees |
| `install-sd.sh` says `no SD card`, and `dmesg` shows `litex-mmc ... Command (cmd 55) error, status -110` | Linux tried the card once at boot, and it didn't answer in time (seen on one board out of five). Ask again: `echo f0004000.mmc > /sys/bus/platform/drivers/litex-mmc/unbind`, then the same into `.../bind`. `ls /dev/mmcblk0` should then show the card |
| the flashed board boots the RAM-disk system instead of the card | `litex_term` was started with `--images`, so it answered the BIOS's serial-boot request. Start it without |

## Chapters 5 and 6

| symptom | cause and fix |
| --- | --- |
| `python3 psk.py` says `No Icepi Zero found` | the scripts look for the FTDI FT231X (USB 0403:6015) with pyserial (`pip install pyserial`) and [1.00](1_00_circuits_from_code.md#100-circuits-from-code)'s udev rule; or give the port, or `--sim` |
| the constellation is a ring, or the eye is shut, with no noise asked for | the wrong SMA, or `awgcap.sv` isn't loaded: `make load-awgcap` in `src/twoboard` |
| `psk.py` reports offsets unlike what `--cfo` and `--sro` asked for | they are rounded to the loop's grid: steps of 3051.76 Hz and 1953 ppm |
| two boards: hundreds of errors, unique words at odd places | A's DAC OUT must go to B's ADC IN, and B's port comes second on the command line |
| `ofdm.py --sound` or `--qam` with two boards gives nothing but errors | the same cabling rule; with one board, give no ports at all and it loops back |

<!-- nav -->
[← Appendix A. Why this hardware?](A_why_this_hardware.md#appendix-a-why-this-hardware) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)** &emsp;&emsp;&emsp; [Appendix C. How this tutorial was tested →](C_how_it_was_tested.md#appendix-c-how-this-tutorial-was-tested)

<!-- author -->
<sub>Jason Gallicchio, jason@hmc.edu, Harvey Mudd College</sub>
