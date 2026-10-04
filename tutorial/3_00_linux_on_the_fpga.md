<!-- nav -->
[← 2.06 The registers from the laptop](2_06_registers_from_the_laptop.md#206-the-registers-from-the-laptop) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)** &emsp;&emsp;&emsp; [3.01 Booting Linux →](3_01_booting_linux.md#301-booting-linux)

# 3.00 Linux on the FPGA

![The whole 4 GB address space of the Linux SoC, not to scale (ROM, SRAM, the SDRAM, the capture buffer, the CSRs, CLINT and PLIC), with the 32 MB of SDRAM zoomed in to scale: the files the BIOS loads before Linux starts, each with its first and last address; Tux the Linux penguin beside it](img/linux_files.png)

<sub>Tux: Larry Ewing (lewing@isc.tamu.edu) and The GIMP; SVG by Simon Budig and Garrett LeSage, via [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Tux.svg).</sub>

**What you need first:** to *run* Linux, only [1.01](1_01_led_counter.md#101-a-counter-on-the-leds) (loading a bitstream) and [2.00](2_00_a_processor_on_the_fpga.md#200-a-processor-on-the-fpga)'s
tool install: [3.01](3_01_booting_linux.md#301-booting-linux) boots prebuilt images. To understand the driver ([3.02](3_02_a_driver.md#302-a-driver)), the registers
of [2.03](2_03_function_generator_peripheral.md#203-a-function-generator-peripheral)–[2.05](2_05_lockin_peripheral.md#205-a-lock-in-peripheral); to build it all yourself ([3.03](3_03_building_linux.md#303-building-linux-yourself)), Chapter 2.

The top of the ladder is Linux on the FPGA, controlling the hardware the way
Linux controls any hardware: through files. By the end of this chapter,
you'll be able to set up a function generator under Linux, which is running on
the FPGA itself, by typing the following commands (at the board's own shell,
logged in as root: a `#` prompt means that throughout Chapter 3;
[0.01](0_01_how_to_use_this_tutorial.md#where-does-this-run) has the table of
prompts):

```console
# echo 123456 > /sys/bus/platform/devices/f0002000.adda/funcgen/frequency
# echo triangle > /sys/bus/platform/devices/f0002000.adda/funcgen/waveform
```

and take a 16384-sample capture and a lock-in measurement with these:

```console
# cat /sys/bus/platform/devices/f0002000.adda/capture/data > samples.bin
# cat /sys/bus/platform/devices/f0002000.adda/lockin/result
```

## What's different about Linux

The CPU of Chapter 2 runs one program, which can touch any address it likes.
Linux runs many programs at once and keeps them from trampling on each other
and on the hardware. For that it needs a CPU with a **[memory-management unit](https://en.wikipedia.org/wiki/Memory_management_unit)**
(MMU), which gives each program its own private addresses. So the Linux SoC
uses **VexRiscv-SMP**, a bigger version of Chapter 2's CPU, with an MMU. It
comes from the [linux-on-litex-vexriscv](https://github.com/litex-hub/linux-on-litex-vexriscv)
project, which knows how to build a Linux-capable SoC for the Icepi Zero.

Booting Linux takes five files. The [BIOS](https://en.wikipedia.org/wiki/BIOS) (or, over the serial port,
`litex_term`) reads `boot.json` to learn where the other four go, copies them
into the SDRAM, and jumps to OpenSBI:

| file | what | size |
| --- | --- | ---: |
| `Image` | the [Linux kernel](https://en.wikipedia.org/wiki/Linux_kernel), version 6.12 | 9.2 MB |
| `rootfs.cpio.gz` | the *root file system*: every program and file Linux will see, unpacked into RAM at boot. Here, [BusyBox](https://en.wikipedia.org/wiki/BusyBox) (one small program that is `ls`, `cat`, `sh` and 300 other commands), the musl C library and MicroPython | 1.5 MB |
| `opensbi.bin` | OpenSBI, the RISC-V firmware between the hardware and the kernel | 264 kB |
| `rv32.dtb` | the *[device tree](https://en.wikipedia.org/wiki/Devicetree)*: tells the kernel what hardware exists, and at which addresses | 3 kB |
| `boot.json` | tells the BIOS (and `litex_term`) where each file goes in memory | 130 bytes |

plus the SoC's bitstream, `icepi_zero_adda.bit`, which is Chapter 2's
peripherals around the Linux CPU, with the SD-card slot added.

## Prebuilt, or build it yourself

Building all of that takes a Linux computer the better part of an hour the
first time, and about 5 GB of tools ([Buildroot](https://en.wikipedia.org/wiki/Buildroot), Java and Scala for the
CPU). So the bitstream and the Linux
files are in [`src/linux/prebuilt/`](../src/linux/prebuilt/), built exactly as
[3.03](3_03_building_linux.md#303-building-linux-yourself) describes, and [3.01](3_01_booting_linux.md#301-booting-linux) and [3.02](3_02_a_driver.md#302-a-driver) use them. They need
nothing beyond what you installed in [1.00](1_00_circuits_from_code.md#100-circuits-from-code) and [2.00](2_00_a_processor_on_the_fpga.md#200-a-processor-on-the-fpga) (`openFPGALoader` and
`litex_term`), so they work on every laptop. [3.03](3_03_building_linux.md#303-building-linux-yourself)
shows how to build them on your laptop, on Linux or in WSL.

| piece | built by | time | prebuilt |
| --- | --- | --- | --- |
| gateware: the SoC, as a bitstream | `make_linux.py` (LiteX) | 5 min | `icepi_zero_adda.bit` |
| device tree | `make_linux.py` | seconds | `images/rv32.dtb` |
| kernel, root file system, OpenSBI | Buildroot | 15–30 min the first time, then seconds | `images/` |
| the driver, `adda.ko` | the kernel's build system | seconds | inside `rootfs.cpio.gz`, in `/root` |
| an SD card that boots by itself | [3.04](3_04_booting_from_sd.md#304-booting-from-an-sd-card) | 6 min | `sdcard.img.xz` |

<!-- nav -->
[← 2.06 The registers from the laptop](2_06_registers_from_the_laptop.md#206-the-registers-from-the-laptop) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)** &emsp;&emsp;&emsp; [3.01 Booting Linux →](3_01_booting_linux.md#301-booting-linux)

<!-- author -->
<sub>Jason Gallicchio, jason@hmc.edu, Harvey Mudd College</sub>
