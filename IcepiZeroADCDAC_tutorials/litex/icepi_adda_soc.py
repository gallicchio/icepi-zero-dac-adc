#!/usr/bin/env python3
"""A LiteX SoC for the Icepi Zero with the ADC/DAC peripherals added.

    python3 icepi_adda_soc.py --build          # ~3 minutes
    python3 icepi_adda_soc.py --load           # into the FPGA's SRAM

Everything the stock LiteX Icepi Zero target has (VexRiscv CPU, 32 MB SDRAM,
serial port, BIOS, LED chaser) plus add_adda()'s three peripherals.
"""
from litex.build.parser import LiteXArgumentParser
from litex.soc.integration.builder import Builder
from litex_boards.platforms import icepi_zero as icepi_zero_platform
from litex_boards.targets import icepi_zero

from adda_litex import add_adda


class BaseSoC(icepi_zero.BaseSoC):
    def __init__(self, **kwargs):
        icepi_zero.BaseSoC.__init__(self, **kwargs)   # the stock SoC...
        add_adda(self)                                # ...plus our peripherals


def main():
    parser = LiteXArgumentParser(platform=icepi_zero_platform.Platform,
                                 description="Icepi Zero + ADC/DAC SoC.")
    parser.add_target_argument("--sys-clk-freq", default=50e6, type=float, help="System clock.")
    args = parser.parse_args()

    soc = BaseSoC(sys_clk_freq=args.sys_clk_freq, **parser.soc_argdict)
    builder = Builder(soc, **parser.builder_argdict)
    if args.build:
        builder.build(**parser.toolchain_argdict)
    if args.load:
        soc.platform.create_programmer().load_bitstream(builder.get_bitstream_filename(mode="sram"))


if __name__ == "__main__":
    main()
