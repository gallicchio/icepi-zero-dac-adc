#!/usr/bin/env python3
# Bare-metal GPIO demo target for the Colorlight i9 (v7.2): stock BaseSoC
# from litex_boards.targets.colorlight_i5, plus the 8-LED PMOD (pmodk) and
# 4-button+4-switch PMOD (pmodl) wired to LiteX's stock GPIOOut/GPIOIn,
# following the "Bare-metal C on a LiteX SoC" section of openfpga.md.
#
# No PMODs need to be physically attached to build/boot this -- the
# switch/button inputs are pulled up in gpio_pmods.py so they read a safe
# idle value, and the LED outputs simply drive pins that go nowhere.
#
#   python3 colorlight_i9_gpio.py --build
#   python3 colorlight_i9_gpio.py --load   # after board is up

from migen import Signal
from litex.build.parser import LiteXArgumentParser
from litex.soc.cores.gpio import GPIOOut, GPIOIn
from litex.soc.integration.builder import Builder

from litex_boards.platforms import colorlight_i5
from litex_boards.targets.colorlight_i5 import BaseSoC

from gpio_pmods import _gpio_pmod_io


def main():
    parser = LiteXArgumentParser(
        platform=colorlight_i5.Platform,
        description="Bare-metal GPIO demo on Colorlight i9 (v7.2)."
    )
    parser.add_target_argument("--board",        default="i9",  help="Board type (i9).")
    parser.add_target_argument("--revision",     default="7.2", help="Board revision (7.2).")
    parser.add_target_argument("--sys-clk-freq", default=60e6, type=float, help="System clock frequency.")
    args = parser.parse_args()

    soc = BaseSoC(board=args.board, revision=args.revision,
        toolchain    = args.toolchain,
        sys_clk_freq = args.sys_clk_freq,
        **parser.soc_argdict
    )

    platform = soc.platform
    platform.add_extension(_gpio_pmod_io)

    # LEDs are active-low -- invert between the raw pin and GPIOOut so a CSR
    # write of 1 means "on" (matches the raw-Verilog GPIO demo's convention).
    led_pads  = platform.request("user_leds8")
    led_logic = Signal(8)
    soc.comb += led_pads.eq(~led_logic)
    soc.leds8 = GPIOOut(led_logic)

    # Switches are idle-high too, but "up" is already the natural 1 -- no
    # invert needed here, unlike buttons below.
    soc.switches = GPIOIn(platform.request("user_switches4"))

    # Buttons are idle-high/actuated-low -- invert so a CSR read of 1 means "pressed".
    btn_logic = Signal(4)
    soc.comb += btn_logic.eq(~platform.request("user_buttons4"))
    soc.buttons = GPIOIn(btn_logic)

    builder = Builder(soc, **parser.builder_argdict)
    if args.build:
        builder.build(**parser.toolchain_argdict)

    if args.load:
        prog = soc.platform.create_programmer()
        prog.load_bitstream(builder.get_bitstream_filename(mode="sram"))


if __name__ == "__main__":
    main()
