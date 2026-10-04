# Prebuilt Linux for Chapter 3

Everything Chapter 3 boots, built exactly as
[3.03](../../../tutorial/3_03_building_linux.md#303-building-linux-yourself) describes, so that you can run
Linux without building it.

| file | what | used in |
| --- | --- | --- |
| `icepi_zero_adda.bit` | the SoC: VexRiscv-SMP CPU, SDRAM, SD-card slot, serial port at 460,800 baud, the LEDs, and the function generator, capture unit and lock-in of [2.03](../../../tutorial/2_03_function_generator_peripheral.md#203-a-function-generator-peripheral)–[2.05](../../../tutorial/2_05_lockin_peripheral.md#205-a-lock-in-peripheral) | [3.01](../../../tutorial/3_01_booting_linux.md#301-booting-linux), [3.04](../../../tutorial/3_04_booting_from_sd.md#304-booting-from-an-sd-card) |
| `images/` | Linux, booted over the serial port into a RAM disk: `Image` (the kernel), `rootfs.cpio.gz` (the root file system, with the driver in `/root`), `opensbi.bin`, `rv32.dtb` (the device tree) and `boot.json` | [3.01](../../../tutorial/3_01_booting_linux.md#301-booting-linux), [3.02](../../../tutorial/3_02_a_driver.md#302-a-driver) |
| `install/` | the same Linux, plus the files for an SD card and `install-sd.sh` to write them, in `/boot/sd` and `/root`. Uses the kernel from `images/` | [3.04](../../../tutorial/3_04_booting_from_sd.md#304-booting-from-an-sd-card), without a card reader |
| `sdcard.img.xz` | a whole SD card: partition 1 (64 MiB, FAT32) holds the boot files, partition 2 (512 MiB, ext2) the root file system. Write it with any card-writing program | [3.04](../../../tutorial/3_04_booting_from_sd.md#304-booting-from-an-sd-card), with a card reader |
| `legal-info-manifest.csv` | every package in the images, with its version, licence and source archive: Buildroot's `make legal-info` | [the licences](../../../LICENSE) |

Built 2026-10-04 from this repository with LiteX `fad9b3759`,
linux-on-litex-vexriscv `05fc5e4`, Buildroot 2026.02.3 and Linux 6.12, and
tested on an Icepi Zero by serial boot (`images/`, `install/`) and from a card
written by `install-sd.sh`.

The images contain GPL software (the Linux kernel and BusyBox) and other
open-source packages, each under its own licence: [`LICENSE`](../../../LICENSE) says
which, and [`../legal/`](../legal/README.md) says how to collect their complete source.
