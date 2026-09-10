# New IO entries for the 8-LED PMOD (pmodk) and 4-button + 4-switch PMOD
# (pmodl) from the raw-Verilog GPIO demo section of openfpga.md, now
# addressed from software via LiteX's stock GPIOOut/GPIOIn instead of
# hand-written HDL. Bit order matches the verified .lpf from that section
# (index 0 = rightmost physical LED/button/switch, the LSB) -- NOT
# pmodk/pmodl's raw connector-pin order -- since Pins() token position
# *is* bit index with no way to reverse it afterward.
from litex.build.generic_platform import Pins, IOStandard, Misc

_gpio_pmod_io = [
    # led[0..7]->pmodk index: R3(0) N4(4) M4(1) L4(5) L5(2) P16(6) J16(3) J18(7)
    ("user_leds8", 0,
        Pins("pmodk:0 pmodk:4 pmodk:1 pmodk:5 pmodk:2 pmodk:6 pmodk:3 pmodk:7"),
        IOStandard("LVCMOS33")),
    # sw[0..3]->pmodl index: T1(4) Y2(5) W1(2) M1(3)
    ("user_switches4", 0,
        Pins("pmodl:4 pmodl:5 pmodl:2 pmodl:3"),
        IOStandard("LVCMOS33"), Misc("PULLMODE=UP")),
    # btn[0..3]->pmodl index: R1(0) U1(1) V1(6) N2(7)
    ("user_buttons4", 0,
        Pins("pmodl:0 pmodl:1 pmodl:6 pmodl:7"),
        IOStandard("LVCMOS33"), Misc("PULLMODE=UP")),
]
