<!-- nav -->
[← 7.07 Bigger ideas: NMR, MRI and qubits](7_07_bigger_ideas.md) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)** &emsp;&emsp;&emsp; [Appendix B. Troubleshooting →](B_troubleshooting.md)

# Appendix A. Why this hardware?

<img src="img/photo_stack.png" alt="The Icepi Zero, the adapter and the ADC/DAC module, stacked, with a short coax cable from the DAC to the ADC" width="320">

The goals:

* an FPGA with an open-source toolchain that runs on every laptop;
* open-hardware boards;
* a fast ADC and DAC that are easy to drive, for physics and communications
  experiments;
* and enough FPGA to boot Linux.

The hardware chosen:

* the [Icepi Zero](https://github.com/cheyao/icepi-zero): a Lattice ECP5 FPGA,
  SDRAM, and USB-C programming built in;
* an [AD9280](https://www.analog.com/en/products/ad9280.html) ADC (8 bits, up
  to 32 MS/s) and an [AD9708](https://www.analog.com/en/products/ad9708.html)
  DAC (8 bits, up to 125 MS/s), on an
  [AD9280 AD9708 data acquisition board](https://www.amazon.com/dp/B0C8D6JQSC)
  that adds an op-amp front end to each;
* and a custom PCB between them, [the adapter](../adapter_board/). (Sorry
  that this is one more thing to order.)

**Why the Icepi Zero?** Lattice makes the FPGAs that work best with the
open-source toolchains, which run on Linux, macOS and Windows. The ECP5 is big
enough to hold an open-source RISC-V processor as a customizable system on a
chip that boots Linux, via
[linux-on-litex-vexriscv](https://github.com/litex-hub/linux-on-litex-vexriscv).
The Icepi Zero is in stock for $79 at
[Elecrow](https://www.elecrow.com/icepi-zero.html) and
[Mouser](https://www.mouser.com/).

FPGA boards considered and rejected:

* [Radiona ULX3S](https://github.com/ulx3s): the flagship, and similar, but
  $140–275.
* [OrangeCrab](https://github.com/orangecrab-fpga/orangecrab-hardware): more
  powerful, with faster DDR3 RAM, but more expensive, and hard to buy.
* [Colorlight](https://github.com/wuxx/Colorlight-FPGA-Projects) boards: not
  enough RAM for Linux, and a flaky serial loader. This project started here.
* [iCESugar-Pro](https://github.com/wuxx/icesugar-pro), $72: probably the same
  flaky Muse Lab boot loader.
* [Sipeed Tang Primer 20K](https://github.com/sipeed/TangPrimer-20K-example),
  $53: LiteX-Boards' own target for it refuses the open `apicula` toolchain
  whenever the DRAM is used (`assert not (toolchain == "apicula" and with_dram)`
  in `litex_boards/targets/sipeed_tang_primer_20k.py`), so Linux on it needs
  Gowin's proprietary tools.

**Why the AD9280 and AD9708?** These modules are everywhere, cheap ($30–50),
fast, and easy to drive from an FPGA: a parallel bus and a clock. They are only
8 bits.

The next step up would be two 12-bit 65 MS/s ADC channels (a dual AD9238)
and two 14-bit 125 MS/s DAC channels (a dual AD9767, the DAC of the Red
Pitaya below), on one PCB with the FPGA. That board is drawn and, since
October 2026, ordered: [Appendix D](D_coming_soon.md).

Fancier alternatives to this whole system, open source but relying on
proprietary Xilinx tools:

* [ADALM2000](https://wiki.analog.com/university/tools/m2k) ("M2k"): $100
  used, $260 new.
* [Red Pitaya](https://redpitaya.com/), the flagship open FPGA + ADC + DAC
  board, with 2 × 14 bits at 125 MS/s: $200 used, $500 new.
* [Digilent Eclypse Z7](https://digilent.com/shop/eclypse-z7) ($524) with a
  [Zmod Scope](https://digilent.com/reference/zmod/scope/start) ($262) and a
  [Zmod AWG](https://digilent.com/shop/zmod-awg-1411-2-channel-14-bit-arbitrary-waveform-generator-awg-module/)
  ($104): a fancier module approach, but $900.

## Open, all the way down: good for learning with an AI

Every layer of this system can be read but one: the FPGA's toolchain
(Yosys, nextpnr, and the ECP5's bitstream as Project Trellis documented
it), the CPU (VexRiscv, in SpinalHDL), the SoC (LiteX), Linux, the
Icepi Zero's and the adapter's KiCad files, the converters' datasheets,
and every design and script in this repository. The one is the converter
module's own schematic, which its maker doesn't publish
([Appendix D](D_coming_soon.md#open-to-the-copper-hardware-an-ai-can-read)
says why that matters).

Being able to read it all matters more now that students learn with an
AI assistant beside them. An assistant can only reason about what it can read. Here it can
follow a symptom from a Python script through the Verilog to the pin and
the datasheet, as [Appendix C](C_how_it_was_tested.md) describes it doing
while this tutorial was written. It can also run the tools itself: synthesize,
simulate, load a board and measure, then change the design and try again.
A closed toolchain or a closed board puts a wall in that loop at the point
where it gets interesting. [Appendix D](D_coming_soon.md)'s board is open to
the copper, which takes the loop one step further.

<!-- nav -->
[← 7.07 Bigger ideas: NMR, MRI and qubits](7_07_bigger_ideas.md) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)** &emsp;&emsp;&emsp; [Appendix B. Troubleshooting →](B_troubleshooting.md)

<!-- author -->
<sub>Jason Gallicchio, jason@hmc.edu, Harvey Mudd College</sub>
