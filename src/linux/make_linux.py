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
