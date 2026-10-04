#!/usr/bin/env python3
"""A Linux SoC whose second serial port is modem.sv: two FPGA Linux computers, talking
through their DACs, ADCs and the cables.

Run it from the linux-on-litex-vexriscv directory, like ../linux/make_linux.py (3.03):

    cd $ADDA/tools/linux-on-litex-vexriscv
    python3 $ADDA/src/twoboard/make_modem_linux.py --board=icepi_zero_modem --build --uart-baudrate=460800

The SoC is the stock icepi_zero (as in Chapter 3) plus a second LiteX UART at 115200 baud
with 512-byte FIFOs.  (At 1 Mbaud, with 64-byte FIFOs, Linux on this 50 MHz CPU could not
empty the receive FIFO in time and lost most of a 32 kB file; the modem itself carries
2.5 Mbaud.)
Inside the FPGA, that UART's transmit line drives modem.sv's transmitter and modem.sv's
receiver drives the UART's receive line, so Linux sees /dev/ttyLXU1, and whatever is
written to it on one board can be read from it on the other.  The device tree goes to
images_modem/rv32.dtb (copy Image, rootfs.cpio.gz and opensbi.bin there from images_adda).
"""
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "litex"))
sys.path.insert(0, os.getcwd())

from migen import ClockSignal, Instance, Record, Signal
from litex.soc.cores.uart import RS232PHY, UART
import make      # linux-on-litex-vexriscv's make.py
import boards
from litex_boards.targets import icepi_zero
from adda_litex import adda_pins

IMAGES = "images_modem"


def add_modem(soc, baudrate=115_200, fifo=512):
    soc.platform.add_extension(adda_pins)
    soc.platform.add_source(os.path.join(HERE, "modem.sv"))
    pins = soc.platform.request("adda")
    line = Record([("tx", 1), ("rx", 1)])          # a serial line that never leaves the chip
    soc.uart1_phy = RS232PHY(line, soc.sys_clk_freq, baudrate=baudrate)
    soc.uart1 = UART(soc.uart1_phy, tx_fifo_depth=fifo, rx_fifo_depth=fifo)
    soc.irq.add("uart1", use_loc_if_exists=True)
    soc.specials += Instance("modem",
        i_clk=ClockSignal("sys"),
        i_uart_rx=line.tx,                         # what Linux sends -> tones
        o_uart_tx=line.rx,                         # tones from the other board -> Linux
        o_dac_d=pins.dac_d, o_dac_clk=pins.dac_clk,
        i_adc_d=pins.adc_d, o_adc_clk=pins.adc_clk,
        o_led=Signal(5))


class IcepiZeroModemSoC(icepi_zero.BaseSoC):
    def __init__(self, **kwargs):
        icepi_zero.BaseSoC.__init__(self, **kwargs)
        add_modem(self)


class Icepi_zero_modem(boards.Icepi_zero):
    def __init__(self):
        boards.Board.__init__(self, IcepiZeroModemSoC, soc_capabilities={"serial", "sdcard", "leds"})


make.supported_boards["icepi_zero_modem"] = Icepi_zero_modem

DTS_NODE = """
/ {{
    soc {{
        liteuart1: serial@{base:x} {{
            compatible = "litex,liteuart";
            reg = <0x{base:x} 0x100>;
            interrupts = <{irq}>;
            status = "okay";
        }};
    }};
}};
"""


def write_dtb(board_name):
    build = os.path.join("build", board_name)
    csr = json.load(open(os.path.join(build, "csr.json")))
    dts_file = os.path.join(build, board_name + ".dts")
    dts = open(dts_file).read()
    import re
    m = re.search(r"linux,initrd-start = <(0x[0-9a-f]+)>", dts)
    if m:
        end = int(m.group(1), 16) + os.path.getsize(os.path.join(IMAGES, "rootfs.cpio.gz"))
        dts = re.sub(r"linux,initrd-end   = <0x[0-9a-f]+>", "linux,initrd-end   = <0x%x>" % end, dts)
    dts += DTS_NODE.format(base=csr["csr_bases"]["uart1"], irq=csr["constants"]["uart1_interrupt"])
    open(dts_file, "w").write(dts)
    subprocess.check_call(["dtc", "-O", "dtb", "-o", os.path.join(IMAGES, "rv32.dtb"), dts_file])
    shutil.copy(os.path.join("images", "boot_ram0.json"), os.path.join(IMAGES, "boot.json"))
    print(f"Device tree with a second liteuart: {IMAGES}/rv32.dtb")


if __name__ == "__main__":
    os.makedirs(IMAGES, exist_ok=True)
    stock_dtb = os.path.join("images", "rv32.dtb")
    saved = open(stock_dtb, "rb").read() if os.path.exists(stock_dtb) else None
    try:
        make.main()
    finally:
        if saved is not None:
            open(stock_dtb, "wb").write(saved)
    write_dtb([a.split("=", 1)[1] for a in sys.argv if a.startswith("--board=")][0])
