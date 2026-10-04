<!-- nav -->
[← 3.02 A driver](3_02_a_driver.md#302-a-driver) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)** &emsp;&emsp;&emsp; [3.04 Booting from an SD card →](3_04_booting_from_sd.md#304-booting-from-an-sd-card)

# 3.03 Building Linux yourself

![How the Linux system is built: the CPU from SpinalHDL; the bitstream from LiteX; the device tree from LiteX's csr.json and make_linux.py, through dtc; the kernel and root file system from Buildroot; the driver from kbuild. Each output is coloured by where it ends up: the FPGA's SPI flash, the SD card's FAT partition, or its ext2 partition](img/linux_build.png)

Everything in [`src/linux/prebuilt/`](../src/linux/prebuilt/) can be rebuilt
from source. You need this when you change the gateware (a new peripheral), the
kernel (a new option) or the driver. It takes a Linux computer (or WSL), about
5 GB of disk, and the better part of an hour the first time.

## Tools

On top of [1.00](1_00_circuits_from_code.md#100-circuits-from-code) and [2.00](2_00_a_processor_on_the_fpga.md#200-a-processor-on-the-fpga):

```bash
sudo apt install build-essential device-tree-compiler bc cpio rsync unzip file \
                 libncurses-dev openjdk-17-jdk-headless
cd $ADDA/tools
wget https://github.com/sbt/sbt/releases/download/v2.0.6/sbt-2.0.6.tgz
tar xzf sbt-2.0.6.tgz && rm sbt-2.0.6.tgz   # Scala's build tool: generates the VexRiscv CPU
echo 'export PATH="$ADDA/tools/sbt/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
git clone https://github.com/litex-hub/linux-on-litex-vexriscv.git
git clone https://gitlab.com/buildroot.org/buildroot.git
cd buildroot && git checkout 2026.02.3
```

The VexRiscv CPU is written in SpinalHDL, a hardware language embedded in
Scala, and `sbt` turns the exact configuration LiteX asks for (one core, 4 kB
caches, an MMU) into Verilog. That happens once; the result is cached. A
hardware description in a language embedded in a language that runs on a
virtual machine: it works, and you only wait for Java once.

## 1. The SoC, and the device tree

linux-on-litex-vexriscv's `make.py` builds a Linux-capable SoC for a named
board. [`make_linux.py`](../src/linux/make_linux.py) adds one more board,
`icepi_zero_adda`: the stock `icepi_zero` plus `add_adda()` from
[2.03](2_03_function_generator_peripheral.md#203-a-function-generator-peripheral), with the micro-SD slot driven in
its fast native 4-bit mode. Then it adds nodes for our peripherals and the
LEDs to the [device tree](https://en.wikipedia.org/wiki/Devicetree).

<details>
<summary>The whole file: <code>make_linux.py</code></summary>

<!-- file: src/linux/make_linux.py -->
```python
#!/usr/bin/env python3
"""Build linux-on-litex-vexriscv's Icepi Zero SoC with the ADC/DAC peripherals.

Run it from the linux-on-litex-vexriscv directory, like that project's make.py:

    cd $ADDA/tools/linux-on-litex-vexriscv
    python3 $ADDA/src/linux/make_linux.py --board=icepi_zero_adda --build --uart-baudrate=460800

It registers one extra board, "icepi_zero_adda": the stock icepi_zero plus
add_adda() from ../riscv, with the SD card in its native 4-bit mode and no HDMI
terminal.  It runs make.py, then writes a device tree with a node for the
peripherals -- so a Linux driver can find them -- and one for the five LEDs,
to <images-dir>/rv32.dtb.

    --images-dir=images_adda   (default) the root file system is an initramfs,
                               images_adda/rootfs.cpio.gz, whose size the device
                               tree records -- put it there first
    --rootfs=mmcblk0p2 --images-dir=images_sd
                               the root file system is partition 2 of the SD card

Without --build it only regenerates the device tree (seconds).
"""
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "riscv"))       # adda_litex.py
sys.path.insert(0, os.getcwd())

import make      # linux-on-litex-vexriscv's make.py
import boards
from litex_boards.targets import icepi_zero
from adda_litex import add_adda

IMAGES = "images_adda"
for a in list(sys.argv):
    if a.startswith("--images-dir="):
        IMAGES = a.split("=", 1)[1]
        sys.argv.remove(a)


class IcepiZeroAddaSoC(icepi_zero.BaseSoC):
    def __init__(self, **kwargs):
        icepi_zero.BaseSoC.__init__(self, **kwargs)
        add_adda(self)


class Icepi_zero_adda(boards.Icepi_zero):
    def __init__(self):
        boards.Board.__init__(self, IcepiZeroAddaSoC, soc_capabilities={
            "serial", "sdcard", "leds",
        })


make.supported_boards["icepi_zero_adda"] = Icepi_zero_adda    # make.py's list of boards


MARK = "\n/* ---- added by make_linux.py ---- */\n"
DTS_NODE = """
/ {{
    soc {{
        adda: adda@{funcgen:x} {{
            compatible = "hmc,icepi-adda";
            reg = <0x{funcgen:x} 0x100>, <0x{capture:x} 0x100>,
                  <0x{lockin:x} 0x100>, <0x{buf:x} 0x{bufsize:x}>;
            reg-names = "funcgen", "capture", "lockin", "buffer";
            clock-frequency = <{clk}>;
            status = "okay";
        }};
    }};
}};

/* The five white LEDs, as files in /sys/class/leds/.  LiteX's GPIO driver
   drives the SoC's LED register (5 bits, bit 0 = the leftmost LED); named here
   as in Chapter 1, led0 = the rightmost.  led4 starts with Linux's heartbeat. */
&leds {{
    litex,ngpio = <5>;
}};

/ {{
    gpio-leds {{
        compatible = "gpio-leds";
        led0 {{ label = "led0"; gpios = <&leds 4 0>; }};
        led1 {{ label = "led1"; gpios = <&leds 3 0>; }};
        led2 {{ label = "led2"; gpios = <&leds 2 0>; }};
        led3 {{ label = "led3"; gpios = <&leds 1 0>; }};
        led4 {{ label = "led4"; gpios = <&leds 0 0>; linux,default-trigger = "heartbeat"; }};
    }};
}};
"""


def write_dtb(board_name):
    build = os.path.join("build", board_name)
    csr = json.load(open(os.path.join(build, "csr.json")))
    dts_file = os.path.join(build, board_name + ".dts")
    dts = open(dts_file).read()
    for old in [MARK, "\n/ {\n    soc {\n        adda: adda@"]:   # without what an earlier run added
        dts = dts.split(old)[0]

    # make.py sized the initrd from images/rootfs.cpio.gz; use ours instead
    m = re.search(r"linux,initrd-start = <(0x[0-9a-f]+)>", dts)
    if m:
        end = int(m.group(1), 16) + os.path.getsize(os.path.join(IMAGES, "rootfs.cpio.gz"))
        dts = re.sub(r"linux,initrd-end   = <0x[0-9a-f]+>", "linux,initrd-end   = <0x%x>" % end, dts)

    dts += MARK + DTS_NODE.format(
        funcgen=csr["csr_bases"]["funcgen"],
        capture=csr["csr_bases"]["capture"],
        lockin=csr["csr_bases"]["lockin"],
        buf=csr["memories"]["capture_buf"]["base"],
        bufsize=csr["memories"]["capture_buf"]["size"],
        clk=csr["constants"]["config_clock_frequency"],
    )
    open(dts_file, "w").write(dts)
    subprocess.check_call(["dtc", "-O", "dtb", "-o", os.path.join(IMAGES, "rv32.dtb"), dts_file])
    rootfs = [a.split("=", 1)[1] for a in sys.argv if a.startswith("--rootfs=")] or ["ram0"]
    shutil.copy(os.path.join("images", "boot_%s.json" % rootfs[0]), os.path.join(IMAGES, "boot.json"))
    print(f"Device tree with the hmc,icepi-adda and LED nodes: {IMAGES}/rv32.dtb (from {dts_file})")


if __name__ == "__main__":
    os.makedirs(IMAGES, exist_ok=True)
    stock_dtb = os.path.join("images", "rv32.dtb")
    saved = open(stock_dtb, "rb").read() if os.path.exists(stock_dtb) else None
    try:
        make.main()                 # (also writes images/rv32.dtb: put it back below)
    finally:
        if saved is not None:
            open(stock_dtb, "wb").write(saved)
    board = [a.split("=", 1)[1] for a in sys.argv if a.startswith("--board=")][0]
    write_dtb(board)
```

</details>

The **device tree** is how Linux learns what hardware exists on a board with
no plug-and-play bus. LiteX generates most of it from `csr.json` (the serial
port, the timer, the interrupt controller...). The addresses in our nodes
come from the same `csr.json`, so they're right even if LiteX moves things
around.

```bash
cd $ADDA/tools/linux-on-litex-vexriscv
mkdir -p images_adda
python3 $ADDA/src/linux/make_linux.py --board=icepi_zero_adda --build --uart-baudrate=460800
```

The result is
`build/icepi_zero_adda/gateware/icepi_zero_adda.bit` and
`images_adda/rv32.dtb`. This SoC fills 51 of the 56 block RAMs and 55% of
the logic, and only just passes timing at 50 MHz (nextpnr reports 50–54 MHz,
depending on the run). The serial port runs at 460,800 baud, the fastest
that serial boot handles reliably.

## 2. Linux, with Buildroot

[Buildroot](https://buildroot.org) builds a whole small Linux system from
source: a cross-compiler first, then the kernel (Linux 6.12, with
linux-on-litex-vexriscv's LiteX patches), OpenSBI, [BusyBox](https://en.wikipedia.org/wiki/BusyBox) and the root file
system. linux-on-litex-vexriscv provides the board support; our changes live
in [`src/linux/`](../src/linux/), a [Buildroot](https://en.wikipedia.org/wiki/Buildroot) *external tree*:

<details>
<summary><code>configs/icepi_adda_defconfig</code>: the whole Buildroot configuration</summary>

<!-- file: src/linux/configs/icepi_adda_defconfig -->
```
# Target options
BR2_riscv=y
BR2_RISCV_32=y

# Instruction Set Extensions
BR2_riscv_custom=y
# Backward compat (buildroot 2023.02.5 LTS).
BR2_RISCV_ISA_CUSTOM_RVM=y
BR2_RISCV_ISA_CUSTOM_RVA=y
BR2_RISCV_ISA_CUSTOM_RVC=n
# make.py enables FPU/hard-float options in the generated board defconfig.
#BR2_RISCV_ISA_CUSTOM_RVF=y
#BR2_RISCV_ISA_CUSTOM_RVD=y
# Since commit cbd91e89e4 (2023-08-18 / 2023.11).
BR2_RISCV_ISA_RVM=y
BR2_RISCV_ISA_RVA=y
BR2_RISCV_ISA_RVC=n
# make.py enables FPU/hard-float options in the generated board defconfig.
#BR2_RISCV_ISA_RVF=y
#BR2_RISCV_ISA_RVD=y
BR2_RISCV_ABI_ILP32=y

# Patches
BR2_GLOBAL_PATCH_DIR="$(BR2_EXTERNAL_LITEX_VEXRISCV_PATH)/patches"

# GCC
BR2_GCC_VERSION_13_X=y

# System
BR2_TARGET_GENERIC_GETTY=y
BR2_TARGET_GENERIC_GETTY_PORT="console"

# Filesystem
BR2_TARGET_ROOTFS_CPIO=y
BR2_TARGET_ROOTFS_CPIO_GZIP=y
BR2_TARGET_ROOTFS_EXT2=y
BR2_TARGET_ROOTFS_EXT2_4=y

# Image

# Kernel header version
# Kernel header version. MUST track BR2_LINUX_KERNEL_CUSTOM_VERSION_VALUE below.
# BR2_KERNEL_HEADERS_AS_KERNEL=y (the kconfig default) builds the headers package
# at the kernel's version, while this symbol declares the series the toolchain is
# built against. support/scripts/check-kernel-headers.sh compares the two and
# aborts the build if they disagree.
BR2_PACKAGE_HOST_LINUX_HEADERS_CUSTOM_6_12=y

# Kernel (mainline + patches set)
BR2_LINUX_KERNEL=y
BR2_LINUX_KERNEL_CUSTOM_VERSION=y
BR2_LINUX_KERNEL_CUSTOM_VERSION_VALUE="6.12"
BR2_LINUX_KERNEL_USE_CUSTOM_CONFIG=y
BR2_LINUX_KERNEL_CUSTOM_CONFIG_FILE="$(BR2_EXTERNAL_LITEX_VEXRISCV_PATH)/board/litex_vexriscv/linux.config"
BR2_LINUX_KERNEL_IMAGE=y

# Bootloader (opensbi)
BR2_TARGET_OPENSBI=y
BR2_TARGET_OPENSBI_CUSTOM_GIT=y
BR2_TARGET_OPENSBI_CUSTOM_REPO_URL="https://github.com/litex-hub/opensbi.git"
BR2_TARGET_OPENSBI_CUSTOM_REPO_VERSION="1.3.1-linux-on-litex-vexriscv"
BR2_TARGET_OPENSBI_PLAT="litex/vexriscv"
BR2_TARGET_OPENSBI_INSTALL_DYNAMIC_IMG=n

# Rootfs customisation

# Required tools to create the SD image
BR2_PACKAGE_HOST_DOSFSTOOLS=y
BR2_PACKAGE_HOST_GENIMAGE=y
BR2_PACKAGE_HOST_MTOOLS=y

# Extra packages
#BR2_PACKAGE_DHRYSTONE_OPT=y
#BR2_PACKAGE_MICROPYTHON=y
#BR2_PACKAGE_SPIDEV_TEST=y
#BR2_PACKAGE_MTD=y
#BR2_PACKAGE_MTD_JFFS_UTILS=y

# Crypto
#BR2_PACKAGE_LIBATOMIC_OPS_ARCH_SUPPORTS=y
#BR2_PACKAGE_LIBATOMIC_OPS=y
#BR2_PACKAGE_OPENSSL=y
#BR2_PACKAGE_LIBRESSL=y
#BR2_PACKAGE_LIBRESSL_BIN=y
#BR2_PACKAGE_HAVEGED=y
# make.py enables hardware AES options in the generated board defconfig.
#BR2_PACKAGE_VEXRISCV_AES=y

# ---- added for the Icepi Zero ADC/DAC tutorials ----
# Loadable modules, so the adda driver can be insmod'ed:
BR2_LINUX_KERNEL_CONFIG_FRAGMENT_FILES="$(BR2_EXTERNAL_ICEPI_ADDA_PATH)/kernel_modules.config"
# Upstream's overlay plus ours (adda.ko and sweep.sh in /root):
BR2_ROOTFS_OVERLAY="$(BR2_EXTERNAL_LITEX_VEXRISCV_PATH)/board/litex_vexriscv/rootfs_overlay $(BR2_EXTERNAL_ICEPI_ADDA_PATH)/rootfs_overlay"
# No post-image script: upstream's replaces linux-on-litex-vexriscv/images/
# with links to these files.  Copy them to images_adda/ instead (see 3.03, step 4).
# awk with maths, for /root/sweep.sh:
BR2_PACKAGE_BUSYBOX_CONFIG_FRAGMENT_FILES="$(BR2_EXTERNAL_ICEPI_ADDA_PATH)/busybox.config"
# musl instead of glibc: glibc 2.42's dynamic loader (Buildroot 2026.02) crashes
# on this CPU before init's main(), while glibc 2.34 (the 2022 images) did not.
# musl works (tested), and is smaller too.
BR2_TOOLCHAIN_BUILDROOT_MUSL=y
# (BR2_PACKAGE_PPPD removed: it pulls in 6 MB of OpenSSL that every serial boot would have to upload)
# MicroPython (about 0.6 MB, 0.36 MB compressed): a Python prompt on the board,
# with machine.mem32[] for reading and writing the peripherals' registers (3.01)
BR2_PACKAGE_MICROPYTHON=y
```

</details>

<details>
<summary><code>kernel_modules.config</code> and <code>busybox.config</code>: what we add to the kernel and to BusyBox</summary>

<!-- file: src/linux/kernel_modules.config -->
```
# Added to linux-on-litex-vexriscv's kernel configuration (Chapter 3).
#
# Loadable modules, so that drivers can be loaded with insmod instead of
# rebuilding the kernel each time.
CONFIG_MODULES=y
CONFIG_MODULE_UNLOAD=y
# Room for a second LiteX UART (5.05's modem SoC gives Linux /dev/ttyLXU1).
# With the default of 1, the driver rejects the second port with error -22.
CONFIG_SERIAL_LITEUART_MAX_PORTS=2
# SLIP, so two boards can run IP over that second port (5.05).
CONFIG_SLIP=y
# The LEDs as files in /sys/class/leds (3.01), with triggers that let the kernel
# blink them: a heartbeat, a timer, and SD-card activity (mmc0).
CONFIG_NEW_LEDS=y
CONFIG_LEDS_CLASS=y
CONFIG_LEDS_GPIO=y
CONFIG_LEDS_TRIGGERS=y
CONFIG_LEDS_TRIGGER_HEARTBEAT=y
CONFIG_LEDS_TRIGGER_TIMER=y
CONFIG_LEDS_TRIGGER_DEFAULT_ON=y
```

<!-- file: src/linux/busybox.config -->
```
# Added to Buildroot's BusyBox configuration: floating-point maths in awk
# (sqrt, atan2, exp, log), for sweep.sh.
CONFIG_FEATURE_AWK_LIBM=y
# slattach and nc, for IP between two boards over the modem (5.05).
CONFIG_SLATTACH=y
CONFIG_NC=y
CONFIG_NC_SERVER=y
```

</details>

```bash
cd $ADDA/tools/buildroot
make O=$ADDA/tools/buildroot-icepi \
     BR2_EXTERNAL=$ADDA/tools/linux-on-litex-vexriscv/buildroot:$ADDA/src/linux \
     icepi_adda_defconfig
make O=$ADDA/tools/buildroot-icepi          # 15-30 minutes, the first time
```

The results are in `$ADDA/tools/buildroot-icepi/images/`.

<details>
<summary><b>Detail:</b> two changes from linux-on-litex-vexriscv's own configuration, and why</summary>

- **musl instead of glibc.** With Buildroot 2026.02's glibc 2.42, the kernel
  boots, but the first program crashes inside glibc's dynamic loader, before
  `main()` (`init[1]: unhandled signal 11 ... in ld-linux-riscv32-ilp32.so.1`,
  then `Kernel panic - not syncing: Attempted to kill init!`). Older images
  built with glibc 2.34 work on the same CPU. The musl C library works, and
  makes the root file system much smaller.
- **No `pppd`.** It pulls in 6 MB of OpenSSL, which takes the compressed root
  file system from about 1.5 MB to 5 MB, and every serial boot has to push
  that through the serial port.

</details>

## 3. The driver

A module must be built from the same source, configuration and compiler as
the kernel that loads it. This `Makefile` hands the job to the kernel's own
build system (*kbuild*), in Buildroot's copy of the kernel:

<!-- file: src/linux/driver/Makefile -->
```makefile
# Build adda.ko against the kernel Buildroot built (3.03):
#     make
# The module must be built by the same compiler, from the same kernel source
# and configuration, as the kernel it will be loaded into.
obj-m := adda.o

# Buildroot's output folder (3.03): this repository's tools/buildroot-icepi
BR    ?= $(abspath $(CURDIR)/../../../tools/buildroot-icepi)
KDIR  ?= $(BR)/build/linux-6.12
# the same compiler Buildroot built the kernel with (riscv32-buildroot-linux-musl-gcc)
CROSS ?= $(patsubst %gcc,%,$(firstword $(wildcard $(BR)/host/bin/riscv32-buildroot-linux-*-gcc)))

all:
	$(MAKE) -C $(KDIR) M=$(CURDIR) ARCH=riscv CROSS_COMPILE=$(CROSS) modules

clean:
	$(MAKE) -C $(KDIR) M=$(CURDIR) ARCH=riscv CROSS_COMPILE=$(CROSS) clean
```

```bash
cd $ADDA/src/linux/driver
make                                   # -> adda.ko
cp adda.ko ../rootfs_overlay/root/     # into the root file system...
cd $ADDA/tools/buildroot && make O=$ADDA/tools/buildroot-icepi    # ...repacked in seconds
```

Everything in `rootfs_overlay/` appears in the board's file system.

## 4. Put it together

```bash
cd $ADDA/tools/linux-on-litex-vexriscv
B=$ADDA/tools/buildroot-icepi/images
cp $B/Image $B/rootfs.cpio.gz images_adda/
cp $B/fw_jump.bin images_adda/opensbi.bin
python3 $ADDA/src/linux/make_linux.py --board=icepi_zero_adda --images-dir=images_adda   # the device tree again
```

The device tree records where the root file system ends in memory, so
`make_linux.py` must run again whenever `rootfs.cpio.gz` changes size. Without
`--build` it only regenerates the device tree, in seconds (the baud rate
matters only with `--build`). Then boot it as in
[3.01](3_01_booting_linux.md#301-booting-linux), with your files instead of the prebuilt ones:

```bash
openFPGALoader -b icepi-zero build/icepi_zero_adda/gateware/icepi_zero_adda.bit && \
litex_term --speed=460800 --images=images_adda/boot.json /dev/ttyUSB0
```

**Try this:**

- Getting a new `adda.ko` onto the board doesn't need a new root file system
  and a 4-minute reboot. Run `base64 adda.ko` on the laptop, type
  `base64 -d > /tmp/adda.ko` on the board, paste the text, press Ctrl-D, then
  `rmmod adda; insmod /tmp/adda.ko`. Paste slowly: the board's serial port
  receives into a small buffer. At 8 characters every 10 ms, the 14 kB module
  takes about 30 s, and arrives with an identical `md5sum`. Pasted at full
  speed, it arrives garbled.
- The kernel includes drivers this board will never use. Remove some with
  `make O=$ADDA/tools/buildroot-icepi linux-menuconfig` (IPv6 and PPP, for
  a start), rebuild, and see how much smaller `Image` gets.

<!-- nav -->
[← 3.02 A driver](3_02_a_driver.md#302-a-driver) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)** &emsp;&emsp;&emsp; [3.04 Booting from an SD card →](3_04_booting_from_sd.md#304-booting-from-an-sd-card)

<!-- author -->
<sub>Jason Gallicchio, jason@hmc.edu, Harvey Mudd College</sub>
