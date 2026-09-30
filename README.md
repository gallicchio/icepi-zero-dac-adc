# Open-Source FPGA synthesis, RISC-V, and Linux

The goal is to "live my undergraduate dreem" of building a completely open-source processor and peripherals (network, USB) with completely open-source synthesis tools and compilers that runs a fairly stock linux and python. I've given up on writing all of the source code myself, but I do want to end up with a clear picture, from low to high level, of how everything fits together. Starting with an FPGA on a PCB:

* What each of the pins on the PCB/FPGA doies and how they map into the HDL and ultimately into linux.
* How all of the board-level "what is connected to each FPGA pin" and gets described and used in a design.
* How the clocking works on the board and in the FPGA. What are the options? How are each configured on the FPGA? What PLLs are available and what frequencies can the FPGA run at? How many different clock domains can there be?
* How the I/O pins are chosen and configured on the FPGA (voltage level, speed, drive current)
* How the RISC-V processor works, is configured, and is built.
* How the SoC-type peripherals are configured, built, and actually talk to the processor (both memory maps and interrupts)
* How the device tree is configured along with the HDL
* How the entire boot process works, from fetching the initial instructoins, through Uboot (if applicable), and on to the kernel.
* How the kernel is configured appropriately and compiled from source
* How the filesystem (bulidroot?) is configured and compiled from source and eventually loaded
* How the addresses of all of the peripherals bookkept semi-automatically and propagate themselves into the device tree and ultimately into python objects
* How to do basic GPIO (buttons switches LEDs), serial, and fast I/O for LFSR, DAC, ADC, radio.
* How to connect a screen (HDMI or tiny LCD), keyboard, and ethernet to the thing to turn it into a little computer that still has buttons, LEDs, and some interesting fast I/O.
* How to do interesting radio communication with it: either SDR or low-latency direct OOK or PSK/QPSK from the pins (with a plugin PCB or by making a new PCB with the FPGA and memory directly on it).

At the end, it would be great to "type `make` and it builds everything, flashes the FPGA, and boots linux flawlessly." However, I don't *just* want to download and build. I want to actually understand all of the above things at a level beyond just typing commands to get it to work. In particular, I want to know (by example) where to intervene at all of these levels to add, remove, or modify stuff.

The best order for the tutorial would be:

* Discuss the choices made at every level, which would be background information, but could be skipped if people just wanted to get going. Include a brief description of how, when the processor reads or writes to memory addresses, they either go to RAM or to a "CSR". Define what those are and how they affect actual hardware.
* Install the tools and get a simple Verilog design (like a Gray Code counter or Linear Feedback Shift Register) onto a Lattice ECP5 FPGA board like the Colorlight i9 (with an optional simulation step).
* Install the tools to get the VexRiscv soft core RISC-V processor, the LiteX SoC peripheral description and address map maker, and a bootable Linux.
* Make the simple Verilog design into a LiteX peripheral that is accessable from Linux and python. (Both python running under Linux on the RISC-V soft core and python running on the laptop).

## Design Choices: Why this particular stack of hardware and softare?

For hardware, it seems Lattice ECP5 is the FPGA family that best supported by open source tools and is capable of reasinably running Linux. This tutorial also uses the VexRiscv RISC-V soft processor core, the LiteX SoC peripheral definitions, the Wishbone bus, Linux, and the LiteX python hardware-interface framework.

Toolchain:

```
  +-------------------------------------------------------+
  | 4. SOFTWARE STACK: Buildroot -> Linux Kernel -> SBI  |
  +-------------------------------------------------------+
  | 3. SOFT CPU CORE: VexRiscv-SMP (with MMU)             |
  +-------------------------------------------------------+
  | 2. HARDWARE GENERATOR: LiteX (Builds SoC & Buses)     |
  +-------------------------------------------------------+
  | 1. FPGA TOOLCHAIN: Yosys -> nextpnr -> Project Trellis |
  +-------------------------------------------------------+
```

### Why Lattice ECP5 over other FPGA families?

Three requirements had to be met simultaneously: enough logic for a soft Linux-capable SoC, fully supported by *open-source* synthesis and place-and-route tools, and available at reasonable cost. Here are the alternatives:

* **Lattice ECP5**: The most mature open-source FPGA toolchain for a logic-rich device. Yosys + nextpnr-ecp5 + Project Trellis fully support all ECP5 primitives including SERDES (for 1 GbE), PLLs, BRAM, and DSP blocks. The ECP5-45F (Colorlight i9) is the minimum size for a comfortable Linux SoC. The 85F (ULX3S, ECPIX-5) has headroom for more complex designs. We chose this.
* **Lattice iCE40** (also fully open-source via Yosys + nextpnr + icestorm): The largest iCE40 (HX8K) has only ~7,000 LUTs — too small for VexRiscv + LiteDRAM. Good for blinky and custom peripherals as standalone projects, not for a Linux SoC.
* **Lattice MachXO / CrossLink**: Not supported by nextpnr. Closed Lattice toolchain required.
* **Gowin** (Tang Nano, Tang Primer): Growing open-source support via the Apicula project, but community size and documentation depth lag the ECP5 significantly. Look at these again in the future.
* **Xilinx 7-series** (Artix-7, the PL side of Zynq-7000): Yosys can synthesize to 7-series, and the `nextpnr-xilinx` / Project X-Ray toolchain can place-and-route some 7-series designs, but it remains experimental. For LiteX specifically: when you target an Artix-7 board (e.g., `digilent_arty`, `xilinx_kc705`), LiteX automatically selects Vivado as the backend — there is no open place and route path for a production LiteX SoC on 7-series. The board support file sets `platform.toolchain = "vivado"` explicitly. So if open-source tools are the requirement, Xilinx 7-series is ruled out.
* **Intel/Altera** (Cyclone V, the core of the DE10-Nano and many PYNQ-style boards): No mature open-source place-and-route tool exists. The official tool is Quartus Prime (also closed-source, also free for some devices).

### ECP5 Development Board Selection

As for dev boards, the best ones seem to be out of stock or expensive. In order:

* gsd_orangecrab / gsd_butterstick: Built by Greg Davill. **Both confirmed unavailable (correction, 2026-08-17):** OrangeCrab is Obsolete -- DigiKey's `ORANGECRAB-R0D2-85` listing explicitly says "no longer manufactured." **ButterStick is also not actually purchasable** -- an earlier pass of this document reported it as available on Amazon/Ubuy based on search-result listings still existing, but Jason confirmed directly that it is not actually available anywhere; those listing pages are stale, not live inventory. Retracting that claim entirely -- don't trust the Amazon/Ubuy listing pages for this board without confirming an actual add-to-cart succeeds. For the record, `linux-on-litex-vexriscv/boards.py`'s `class ButterStick` does exist as a supported Linux target (dual-rank DDR3L, 256 MB or 1 GB per the GroupGets hardware spec, $179.99 at its original 2021-era GroupGets campaign price) -- the software support is real, only the hardware is not currently buyable.
* radiona_ulx3s: Developed by Radiona. One of the most mature, community-backed open-source hardware ECP5 boards available, packed with onboard peripherals and standard video out. Only the 45F and 85F variants have enough LUTs to fit the full VexRiscv-SMP (with MMU) + LiteDRAM + Ethernet + SD card + video-framebuffer SoC that `linux-on-litex-vexriscv/boards.py`'s `ULX3S` profile builds by default  Current Mouser pricing/stock:
  * `CS-ULX3S-01` (ECP5 **12F**, 12K LUT): **$158.27**, 18 in stock. Too few LUTs for a Linux-capable RISC-V.
  * `CS-ULX3S-02` (ECP5 **45F**, 44K LUT): **$175.01**, Non-stocked (not orderable right now). 32 MiB and 44K LUTs could run Linux.
  * `CS-ULX3S-03` (ECP5 **85F**, 84K LUT): **$275.09**, 12 in stock. 32 MiB and 84K LUTs will work with linux.
* lattice_ecp5_evn / lattice_versa_ecp5: These are **two different physical boards**, each with its own separate `litex_boards` platform/target file — resolved from an earlier "is versa different?" TODO in this doc:
  * **`lattice_ecp5_evn`** = ($152 LFE5UM5G-85F-EVN from Mouser) **No onboard SDRAM/DDR of any kind**  — 8 LEDs, 3 buttons, mostly unpopulated holes including for SMAs, matching this board's own product listing (178 GPIO, 20 diff-pair I/O, four 5G SERDES channels, SPI boot flash).
  * **`lattice_versa_ecp5`** ($466) = a genuinely different, more populated board (device family `LFE5UM5G`/`LFE5UM`). Its target file (`litex_boards/targets/lattice_versa_ecp5.py`) *does* wire up real DDR3: `module = MT41K64M16(sys_clk_freq, "1:2")` via `ECP5DDRPHY`. It *is* a supported target in `linux-on-litex-vexriscv/boards.py` (`class VersaECP5`). This is the board that's actually "pre-tested" for Linux, not the EVN. **RAM: 128 MiB.** `MT41K64M16` is `nbanks=8, nrows=8192, ncols=1024` at native 16-bit width -- `8 × 8192 × 1024 × 16 bits ÷ 8 = 128 MiB` -- a single 1 Gbit DDR3 chip (Micron's naming: "64M x16" = 64 Mega-word × 16-bit = 1 Gbit = 128 MiB). Confirmed at the pinout level too: `litex_boards/litex_boards/platforms/lattice_versa_ecp5.py`'s `"sdram"` connector lists exactly 16 `dq` pins and a single `cs_n` -- one chip, native x16, not doubled up the way Colorlight's two parallel x16 chips are. It also routes 2 `dm` (byte-mask/DQM) pins, so -- unlike the Colorlight i9 -- this board does *not* need the `--with-wishbone-memory` workaround; VexRiscv's native LiteDRAM path with sub-word writes works directly. 128 MiB is comfortably in "32+ MB is a comfortable environment" territory from the Linux-vs-Zephyr section later in this document -- this board would *not* need any of the 8 MB-specific patching the Colorlight i9 section above requires.
* colorlight_5a_75x / colorlight_i5 / colorlight i9 (i5 target has support for i9, but i9+ is Xilinx and requires Vivado): Budget-friendly LED control cards repurposed by the community into incredibly low-cost Linux FPGA development targets. (I bought a Colorlight i9 module+holder from AliExpress for $80) Resolved: yes, 8 MB is tight and doesn't comfortably run Linux in RAM -- see "Making Linux actually fit in the i9's real 8 MB SDRAM" further down for exactly what has to change (OpenSBI offset patch, and switching to SD card or NFS rootfs instead of RAM). Resolved: the I/O pins are directly connected with no protection at all -- see "I/O pin protection" below.
* lambdaconcept_ecpix5: A high-performance ECP5 board designed explicitly for deep evaluation and processing using open toolchains. Re-checked (2026-08-17) directly on the lambdaconcept shop: €151 (~$165, both the 45F and 85F variants), which would clear the ≥32 MB / under-$200 bar easily -- it has 512 MB DDR3L per the vendor spec, by far the most RAM of any board on this list -- but it is **currently "Out-of-Stock"** on the only official storefront found, "Notify me when available" only. Worth watching, not buyable today. I'd want the ECPIX-5 85F version anyway.

OrangeCrab, ButterStick, ULX3S, ECPIX-5: So many of the most interesting boards (for this tutorial) were created a few years ago and are no longer available. I feel like I'm late to the party and everyone in this community has moved on, leaving me to work with hardware scraps. Where have they all gone? Where are the new open-hardware boards that take advantage of the open-synthesis tools?

**Answered (2026-08-17, corrected same day):** re-checking all four, OrangeCrab and ButterStick are both confirmed genuinely unavailable -- OrangeCrab's DigiKey listing says "no longer manufactured" outright, and ButterStick's Amazon/Ubuy listing pages that an earlier pass of this document took as evidence of availability turned out to be stale, not live inventory (Jason confirmed this directly -- see the correction above). ECPIX-5 is out of stock at its only official storefront today, but that's a "notify me when available" restock message, not a discontinuation notice. ULX3S is actually in stock and buyable *right now* (see the corrected pricing above) -- it was this document's own stale "$600" note, not the board's real unavailability, that made it look dead.

**Why this pattern happens at all:** every one of these (OrangeCrab, ButterStick, ULX3S, ECPIX-5) is a small-batch board from an individual maker or tiny team (Greg Davill / Good Stuff Department for OrangeCrab and ButterStick, LambdaConcept for ECPIX-5, Radiona / Zagreb Makerspace for ULX3S), funded and sold in batches through Crowd Supply-style crowdfunding rather than mass-manufactured with continuously replenished retail inventory. Restocking is discretionary, unfunded work for whoever runs the project -- there's no company obligated to keep making more. The 2021-2023 global chip shortage hit this category especially hard, squeezing already-thin margins on both the ECP5 FPGAs themselves and the DDR3/SDRAM chips these boards need. Colorlight's boards avoid all of this specifically *because* they were never "for us" -- they're mass-produced for the LED video-wall signage industry at industrial scale, and the FPGA hobbyist community is just repurposing surplus/production units from a much larger, unrelated, more resilient supply chain. That's the real reason Colorlight stays cheap and in stock while purpose-built hobbyist ECP5 boards cycle in and out of availability.

**Where the new boards are:** one genuinely new one exists as of this check -- the **[Icepi Zero](https://www.crowdsupply.com/icy-electronics/icepi-zero)** (Icy Electronics), a Raspberry Pi Zero-form-factor ECP5 board that finished its Crowd Supply campaign and shipped to backers around January 2026. Specs: ECP5-25F (24K LUTs, the same size class as the Colorlight i5), 256 Mbit (**32 MB**) SDRAM at 166 MHz -- the same speed grade as ULX3S's SDRAM, comfortably clearing the ≥32 MB bar this document has been using -- 128 Mbit (16 MB) QSPI flash, 3× USB-C, a GPDI (mini-HDMI) video connector, and a 40-pin Raspberry Pi-compatible GPIO header. It's *currently in stock at Mouser* (part `ICEPI-ZERO-QTY-1`, tens to low hundreds of units depending on region, ship-immediately) at a crowdfunding price of $69/unit -- comfortably under this document's $100-200 budget, check Mouser directly for current retail price.

**Correction (2026-08-17, same day): the "no `litex_boards` support" claim above was wrong -- checked the actual repos, not just the vendor's own example list, and support genuinely exists.** `linux-on-litex-vexriscv/boards.py` has had a real `class Icepi_zero(Board)` entry since commit `db4a1266`/`f612fefb` ("Added Icepi Zero support"), dated 2026-06-19 -- two months before this research, not something that appeared afterward. `litex_boards/litex_boards/targets/icepi_zero.py` and `litex_boards/litex_boards/platforms/icepi_zero.py` both exist and are complete: `device="LFE5U-25F"`, `toolchain="trellis"` (the same fully open Yosys + nextpnr-ecp5 + Project Trellis flow as every other ECP5 board in this document, not a proprietary tool), default `sdram_module_cls="W9825G6KH6"`. Verified the RAM figure two ways, the same standard applied to every other board in this document: geometry math (`nbanks=4, nrows=8192, ncols=512` × 16-bit = 32 MiB) and the platform file's actual `"sdram"` pin block (16 `dq` + 2 `dm` pins -- single chip, native x16, DQM routed, so no `--with-wishbone-memory` workaround needed, same as ULX3S). The `Icepi_zero` `boards.py` profile is `serial`, `spisdcard`, `leds`, `video_terminal` -- no Ethernet required; the SD card capability is present but, with 32 MiB of RAM (4× the Colorlight i9's 8 MiB), a RAM-only (`ram0`) rootfs the way this whole document does it for Colorlight looks very plausible without actually wiring up a physical SD card, and this is now confirmed working on real hardware (2026-08-27) -- see "Confirmed working: full Linux boot on real Icepi Zero hardware" further down.

**Revised verdict: Icepi Zero is a legitimate, appropriate candidate for this tutorial** -- it has real, pre-existing, tested board support in exactly the same repos this document already uses, not a project to bootstrap from scratch. This reverses the earlier "not appropriate" call.

### Survey: every open-toolchain board with native `linux-on-litex-vexriscv` support (2026-08-17)

Requested (2026-08-17): re-examine Gowin Tang Nano/Primer and any other options, cross-check `litex_boards`/`linux-on-litex-vexriscv` support, and find the most open, least expensive boards with native working support that don't need a lot of external components (Ethernet, SD cards). Went through every `class X(Board)` entry in `linux-on-litex-vexriscv/boards.py`, kept the ones on a genuinely open toolchain (Yosys + nextpnr-* + an open place-and-route backend -- excludes anything defaulting to Vivado, Quartus, or Efinity), and verified RAM the same way as every other board above: `litedram` module geometry cross-checked against actual `dq`/`dm` pin counts in the platform file, not vendor naming alone.

| Board | Toolchain | RAM (verified) | Price | Stock (2026-08-17) | External HW for Linux? |
|---|---|---|---|---|---|
| **Icepi Zero** | `trellis` (fully open) | 32 MiB (`W9825G6KH6`, DQM routed) | $69 | ✅ In stock, Mouser | No Ethernet; SD card available but likely avoidable given RAM |
| **CologneChip GateMate A1 EVB** (Olimex) | `peppercorn` (fully open -- vendor's own native flow, not reverse-engineered) | 8 MB HyperRAM | €50 (~$54) | ✅ In stock, Olimex direct | Inherits every 8 MB Colorlight-style RAM constraint documented above |
| **ULX3S 85F** | `trellis` (fully open) | 32 MiB | $275.09 | ✅ In stock (12 units), Mouser | No Ethernet; SD card available but likely avoidable |
| ULX3S 45F | `trellis` (fully open) | 32 MiB | $175.01 | ❌ Non-stocked | -- |
| ULX3S 12F | `trellis` (fully open) | 32 MiB | $158.27 | ✅ In stock (18 units) | Too few LUTs to fit the Linux SoC at all (see above) |
| Sipeed Tang Primer 20K | `gowin` **required** for DRAM -- `assert not (toolchain == "apicula" and with_dram)` directly in `litex_boards/targets/sipeed_tang_primer_20k.py` | 256 MiB (`IMD128M16R39CG8GNF`) | ~$30-50 | ✅ Widely stocked (Amazon, AliExpress, Sipeed's own store) | Needs SD card (`spisdcard` in its `boards.py` profile); DRAM path is not open |
| Sipeed Tang Nano 20K | `gowin` (default); `apicula` listed as a toolchain option but no confirmed working DRAM path -- the SDRAM module choice is marked `# FIXME.` directly in the target file | 8 MiB (`M12L64322A`) | Cheap, widely stocked | ✅ | Needs SD card (`sdcard` in profile); same tight-RAM problem as Colorlight, on a toolchain that's less open than ECP5's |
| Machdyne Noir | `trellis` (fully open) | 256 MB (`MT41K128M16`, configurable up to 1 GB) | €139.95 | ❌ Out of stock (machdyne.com) | No Ethernet by default |
| Machdyne Kölsch | `colognechip` (fully open) | 64 MB (`W989D6DBGX6`) | €99.95 | ❌ Out of stock, **and** vendor's own listing warns "has not yet been fully tested successfully and may contain hardware bugs that limit functionality" | -- |
| `lattice_versa_ecp5` | `trellis` (fully open) | 128 MiB | $372-500+ | ✅ but far over budget | -- |
| `lambdaconcept_ecpix5` | `trellis` (fully open) | 512 MB | ~$165 | ❌ Out of stock | -- |
| TrellisBoard | `trellis` (fully open) | 1 GiB (32-bit-wide DDR3, confirmed via 32 `dq` pins) | -- | Not a commercial retail product -- open-hardware GitHub project (gatecat/TrellisBoard), no confirmed vendor selling assembled units | -- |
| ULX4M-LD | `trellis` (fully open) | 1 GiB | -- | NLnet-funded Crowd Supply campaign; couldn't confirm current retail purchasability | -- |
| ButterStick | `trellis` (fully open) | 256 MB/1 GB | -- | **Confirmed not actually available** (see correction above) | -- |
| OrangeCrab | `trellis` (fully open) | DDR3 | -- | Confirmed discontinued | -- |
| Colorlight i5/i9 | `trellis` (fully open) | 4-8 MiB (see the whole first half of this document) | $80 | ✅ In stock | This document's own subject -- included for reference |

**Direct answer to "most open, least expensive, native support, minimal external components":**

1. **Icepi Zero ($69) is the strongest match.** Fully open `trellis` toolchain -- the same mature, well-documented flow this entire document already uses for Colorlight, not a different or less-proven one. 32 MiB RAM, 4× the Colorlight i9's 8 MiB, so it should sidestep this document's entire "Making Linux actually fit" ordeal rather than repeat it. No Ethernet dependency. Genuinely in stock today. **Confirmed (2026-08-27): the RAM-only (`ram0`) rootfs build works end-to-end on real hardware, no troubleshooting needed beyond a shared-USB-device serial-console ordering gotcha** -- see "Default target: Icepi Zero" and "Confirmed working: full Linux boot on real Icepi Zero hardware" further down. This document's default target has been switched to the Icepi Zero as a result.
2. **GateMate A1 EVB (~$54) is the most philosophically open pick**, since CologneChip ships their own native open-source place-and-route as the primary toolchain rather than relying on a reverse-engineered third party (Trellis for ECP5, Apicula for Gowin, both excellent but both started as unofficial efforts the vendor didn't originally support). But its 8 MB HyperRAM means picking it buys straight back into every constraint this document spent the last several sections solving for Colorlight -- worth it only if toolchain purity matters more than convenience.
3. **Avoid the Gowin Tang boards if "most open" is a hard requirement.** Tang Primer 20K's own `litex_boards` source explicitly blocks the open `apicula` toolchain whenever DRAM is used -- Linux on it requires Gowin's proprietary tool, full stop. Tang Nano 20K's DRAM path through `apicula` is unverified (literally flagged `# FIXME` in the source) and its RAM (8 MiB) doesn't improve on Colorlight anyway.
4. **Everything else with meaningfully more RAM (Machdyne Noir/Kölsch, TrellisBoard, ULX4M-LD) is currently out of stock, not a real retail product, or both** -- interesting to watch, not buyable today.

The broader trend is real, though: some of the hobbyist energy that used to go into "the next OrangeCrab" has diffused elsewhere -- toward Gowin/Tang Nano boards (different vendor, cheaper silicon, the Apicula open-toolchain still maturing, mentioned in the "Why Lattice ECP5" section above) and toward cheap hard-silicon RISC-V Linux SBCs, which sidestep the FPGA-soft-core exercise entirely for people who just want "cheap open Linux on RISC-V" rather than this document's specific goal of understanding the whole stack down to the FPGA fabric. That diffusion, more than any lack of interest, is probably why this niche keeps producing occasional crowdfunded bursts (like Icepi Zero) rather than a steady retail lineup.

### Why the Colorlight i9 Board Specifically?

The Colorlight i9 is small tweak of the i5:

* <https://github.com/wuxx/Colorlight-FPGA-Projects>
* <https://github.com/wuxx/Colorlight-FPGA-Projects/blob/master/schematic/i5_v6.0-extboard.pdf>
* <https://github.com/wuxx/Colorlight-FPGA-Projects/blob/master/doc/i5_extboard_v1.2_pinout.png>

Colorlight boards were designed as LED video wall controllers — they have fast SDRAM, Gigabit Ethernet, and clean schematics because LED wall controllers need deterministic timing and reliable signal integrity. The community discovered these properties and repurposed the boards for FPGA development.

* **Price**: $80 (module + carrier) vs. $275.09 for the ULX3S 85F -- the only ULX3S variant confirmed both in-stock and large enough to actually run this Linux stack (corrected from an earlier, stale "$600" figure in this doc — see the board-selection section above for the full per-variant pricing/LUT breakdown) — or $152 for the Lattice EVN board (which, per the board-selection section, has no SDRAM and can't run Linux at all).
* **SDRAM**: 8 MB (confirmed by hardware boot log and by `litex_boards` source — see "Confirmed root cause" note below; an earlier draft of this document incorrectly said 32 MB). Enough to boot a *minimal* Linux, but tight — see the SDRAM-size debugging section below for what has to change to make it fit. By comparison: ULX3S and Icepi Zero are 32 MiB, `lattice_versa_ecp5` is 128 MiB, ECPIX-5 is 512 MB — see the board-selection section above and the open-toolchain board survey below for sourcing on each (and for why ButterStick, despite having comparable RAM on paper, isn't included: it's not actually buyable).
* **Gigabit Ethernet**: The i9 module has two RTL8211F Gigabit Ethernet PHYs without onboard magnetics. The Muse Lab carrier board has a USB and HDMI, not RJ45. The module only contains the transceivers, not the Ethernet transformers or RJ45 connectors. The 2x 4 differentials pairs are routed to the SODIMM pins. A third addon board can plug into the header pins and break the PHYs out to two standard RJ45 jacks. This enables `litex_server` remote register access over a real network cable and eventual network-boot Linux. See <https://tomverbeure.github.io/2021/01/22/The-Colorlight-i5-as-FPGA-development-board.html> Resolved: not a single standard product, but several independent open-hardware designs exist for exactly this -- [DaveBerkeley/colorlight-eth](https://github.com/DaveBerkeley/colorlight-eth) (GitHub, KiCad files), kazkojima's `i5ether` design (in the same [colorlight-i5-tips](https://github.com/kazkojima/colorlight-i5-tips) repo already cited elsewhere in this document), and a smaller commercially-manufactured version from WIDE SERVIS. None is "the" canonical addon board the way the DAPLink extension board is -- expect to fab-your-own from one of these KiCad projects rather than buy one off a shelf.
* **STM32 DAPLink on carrier**: The extension board has an onboard STM32 running DAPLink firmware, providing CMSIS-DAP JTAG/SWD access to the FPGA without any external debug probe. `openFPGALoader` communicates with it natively via USB. By contrast, the PYNQ-Z2 has an FTDI FT232HQ chip that provides both JTAG programming (no separate probe needed — Vivado can "Open Target → Auto Connect" over USB directly) and a USB UART bridge. Additionally, within PYNQ's Jupyter environment, `Overlay('new_design.bit')` loads a new bitstream at runtime without rebooting — more convenient than the power-cycle-and-reflash cycle required for the Colorlight during development. This is a genuine advantage of the PYNQ approach for iterative hardware development.
* **Open schematic**: The carrier board schematic is publicly available. Resolved -- it's the same `wuxx/Colorlight-FPGA-Projects` repo already linked at the top of this section: <https://github.com/wuxx/Colorlight-FPGA-Projects/blob/master/schematic/i5_v6.0-extboard.pdf> (extension/carrier board) and the `colorlight_i9_v7.2.md` file in the same repo for the i9 module itself.
* **I/O pin protection**: The Colorlight carrier I/O pins are directly connected to FPGA I/O bank pins with no protection — 3.3V logic only, and a wiring mistake can damage the FPGA. The PYNQ-Z2 is more forgiving: its PMOD connectors include 200 Ω series resistors between the Zynq I/O pins and the connector, limiting fault current and providing some protection at the cost of ~2 ns of added RC delay (inconsequential below ~100 MHz). This makes the PYNQ-Z2 more appropriate for classroom use where students routinely miswire things.

Limitation: The i9's 32-bit SDRAM PHY does not route byte-mask (DQM) pins to the FPGA package balls — this is a PCB design choice, not a configurable parameter. DQM signals tell the SDRAM chip which byte lanes to write and which to mask off, enabling sub-word writes. Without DQM wired up, the SDRAM chip always writes all four bytes of a 32-bit word simultaneously, so any sub-word write would corrupt the other bytes in that word.

To force VexRiscv to use full-word wwrite, you need to build it with  `--with-wishbone-memory`. Without this, `vexriscv_smp`'s native LiteDRAM path issues byte-masked writes directly and would corrupt memory. The `--with-wishbone-memory` flag reroutes main RAM through the Wishbone/L2 cache, which pads every write to a full word by reading-then-writing, sidestepping DQM entirely. The penalty is reduced write throughput (every sub-word write becomes a read-modify-write cycle at the Wishbone level).

Boards that do route DQM and can use the native LiteDRAM path with `vexriscv_smp` (no flag needed): OrangeCrab (DDR3 with full DM/DQS signals), ULX3S (32-bit SDRAM with DQM routed — verify per revision), and ECPIX-5 (DDR3 with DM). In general, any board with a DDR3/LPDDR4 interface routes DM as part of the standard DDR spec. Budget boards with SDR SDRAM sometimes omit DQM to save PCB routing complexity.

Resolved for the two official Lattice boards, checked directly against their `litex_boards` platform files (same standard applied everywhere else in this document -- actual `dm` pin presence, not assumption): `lattice_ecp5_evn` has no SDRAM at all (see the board-selection section above), so the question doesn't apply. `lattice_versa_ecp5` **does** route DQM -- its `"sdram"` connector has 2 `dm` pins alongside 16 `dq` pins, confirmed in the board-selection section above -- so it uses the native LiteDRAM path with no `--with-wishbone-memory` workaround needed, same as ULX3S and Icepi Zero (also confirmed with `dm` pins present). Every DQM-routed board checked in this document so far has 2 `dm` pins for a 16-bit-wide chip; the Colorlight i9 is the one exception with zero.

### Why VexRiscv soft-core processor and LiteX SoC generator? The Fundamental Split: Hard CPU vs. Soft CPU

This is the most important architectural choice, and it separates the entire ECP5 + LiteX world from the Xilinx Zynq world you may already be familiar with.

**The Xilinx Zynq approach (PYNQ-Z2, Brain-1):** A Zynq 7000 device contains a *hard-wired* dual-core ARM Cortex-A9 directly on the silicon die — custom transistor layout, not configurable logic. The ARM boots from on-chip ROM, loads a First Stage Bootloader (FSBL) from QSPI flash, which launches U-Boot, which launches Linux. The FPGA fabric (Xilinx calls it the PL — Programmable Logic) is an accelerator attached to the ARM via AXI4 high-speed interconnects. From a Linux perspective, the FPGA is just a peripheral with memory-mapped registers. The 512 MB DDR3 on the PYNQ-Z2 is wired directly to the hard ARM's DDR controller — again, not the configurable logic.

The Xilinx tools for this world:

* **Vivado**: Synthesis and place-and-route. Closed-source; no-cost for 7-series and Zynq under WebPACK license (requires Xilinx account registration, ~30 GB download). Constraint files are `.xdc` format: `set_property PACKAGE_PIN AY15 [get_ports clk]` — the Xilinx equivalent of the ECP5's `.lpf`.
* **AXI Bus**: Resolved. AXI4 (part of ARM's AMBA family) is the standard on-chip interconnect for Zynq/Xilinx designs. Every transaction splits into up to 5 independent channels with their own valid/ready handshaking: write address (AW), write data (W), write response (B), read address (AR), read data (R) -- this channel split is what lets AXI pipeline multiple outstanding transactions and support burst transfers efficiently. Multiple masters (ARM cores, DMA engines) and slaves (peripherals) connect through an "AXI Interconnect" IP block that acts as a crossbar, routing each transaction to the right slave by address. Wishbone (this document's bus, described in the "Goal 6" section further down) is deliberately much simpler: no separate pipelined channels, one request/response at a time by default, easier to generate and reason about in Python via Migen -- which is exactly why LiteX picked it. The tradeoff is throughput: AXI's pipelining and multi-master crossbar are built for the ARM core's memory bandwidth needs; Wishbone is built for how easy it is to compose a SoC in a few lines of Python, at some cost to peak bus throughput. LiteX also has its own lightweight CSR bus (see below) bridged from Wishbone for slow peripheral registers -- roughly analogous to AXI-Lite's role next to full AXI4 in the Xilinx world.
* **Vitis**: IDE and SDK for writing software targeting the ARM processor and IP cores in the PL. Replaced the older Xilinx SDK. Resolved -- the original claim above was wrong, and the correction in the TODO was right: Vitis is closer to a GUI wrapper around cross-compilation toolchains (GCC for bare-metal/Linux userspace ARM code, plus Vitis HLS for compiling C/C++ into PL accelerator logic) -- roughly analogous to this document's `riscv64-unknown-elf-gcc`/bare-metal software layer, not to LiteX's SoC-composition layer at all. **PetaLinux** (below) is the actual Linux build-chain equivalent -- closer to this document's Buildroot + kernel-build combination.
* **IP Integrator / Block Design**: GUI in Vivado for connecting pre-built IP cores (AXI interconnect, DMA, Ethernet MAC). Each block in the diagram is a separate Verilog/VHDL module, all of which synthesize into a final bitstream. The hand-off file from Vivado to PetaLinux is an `.xsa` (Xilinx Support Archive) — a ZIP file containing the bitstream, hardware description XML, and device tree fragment — filling the same role as LiteX's `csr.json`. The `.hwh` (Hardware Handoff) file is a Vivado-generated XML file *inside* the `.xsa` that PYNQ specifically reads when you call `Overlay('design.bit')` in python. PYNQ parses the `.hwh` to discover what IP cores are present, their AXI base addresses, interrupt assignments, and register maps, then dynamically generates Python classes for each core — so `overlay.gpio_0.write(0x1234)` works without any Linux kernel driver. The `.hwh` is therefore the Xilinx-specific equivalent of LiteX's `csr.json` from PYNQ's perspective, while the `.xsa` is the whole package shipped between tools. (What a CSR register actually is: see the definition at the "LiteX `--doc`" bullet further down, in the Visualization section.)
* **PetaLinux**: Yocto-based Linux distribution builder pre-configured for Zynq hardware. Generates the FSBL, U-Boot, device tree, and filesystem automatically. Very convenient; also very opaque — it is difficult to trace exactly what commands it is running or where to intervene.

**The ECP5 + LiteX approach (the rest of this document):** There is **no hard processor**. VexRiscv is a *soft-core* — its entire implementation is LUTs and flip-flops in the FPGA fabric, exactly like any other custom logic you might write. Every part of the SoC (CPU, memory controller, Ethernet MAC, UART, boot ROM) is open-source HDL you can read, modify, and replace. Consequences:

* *Slower*: VexRiscv at 100 MHz is roughly comparable to an ARM9-class processor. Adequate for Python scripting and I/O control; not for GPU workloads or real-time audio/video encoding.
* *Less RAM*: The i9 board has 8 MB SDRAM vs. 512 MB on the PYNQ-Z2 (see the SDRAM-size debugging section below — an earlier draft of this document said 32 MB, which was wrong). Enough for a *minimal* Linux, not a comfortable Python environment.
* *More educational*: You can read the Verilog for the DDR memory controller and see exactly how SDRAM commands are sequenced and timed. There is no equivalent for the Zynq's hard DDR controller.
* *Fully open toolchain*: No registration, no closed-source tools, no license management, no 30 GB downloads.

The tradeoff: For maximum performance with minimal friction, use a Zynq with PetaLinux. For understanding the complete system from gate-level logic to Python, the ECP5 + LiteX stack delivers this in a way a Zynq cannot.

### Why VexRiscv over Other RISC-V Soft Cores?

* **VexRiscv**: 32-bit, in-order, configurable. The `vexriscv_smp` variant adds MMU (for virtual memory), SMP support, and optional FPU — exactly what Linux needs. It is the default LiteX CPU, the most tested, and has the most community documentation.
* **PicoRV32**: Smaller and simpler, but has no MMU, so it cannot run Linux (Linux requires virtual memory management).
* **NEORV32**: Clean, well-documented, but not Linux-capable by default (limited MMU support).
* **Rocket Chip**: The reference Berkeley 64-bit implementation; Linux-capable, but resource-heavy on ECP5 and the build system is complex.
* **CVA6**: More powerful, but the LiteX integration is less mature and ECP5 resource utilization is very high.

### Why LiteX over other aternatives?

LiteX is Python-level SoC composition, automatic address map generation, automatic device tree generation, a working simulation target out of the box, and pre-tested board support for the Colorlight i5/i9 -- and, confirmed by the board-selection and open-toolchain-board-survey sections above, also natively for OrangeCrab, `radiona_ulx3s`, and Icepi Zero (all have real, working `litex_boards`/`linux-on-litex-vexriscv` support). The one exception: `lattice_ecp5_evn` (the LFE5UM5G-85F-EVN) has a `litex_boards` platform file but no SDRAM wiring at all, so it isn't natively Linux-capable the way the others are -- see the board-selection section for why.

Where LiteX sits in the stack, concretely: it's the layer between "I have an FPGA and a place-and-route tool" and "I have a bootable SoC." Yosys/nextpnr/Trellis turn HDL into a bitstream but know nothing about CPUs, buses, or memory maps -- that's what LiteX's Python classes (`SoCCore`, `add_cpu()`, `add_sdram()`, `add_uart()`, etc.) generate: the VexRiscv instantiation, the Wishbone/CSR interconnect wiring every peripheral together, the BIOS, and (via `litex_json2dts_linux.py`) the device tree the Linux kernel needs at boot. `litex_boards` sits one layer above that again -- it's just a library of pre-written `SoCCore` subclasses (one per physical board) that already know each board's pin mapping, clock frequencies, and SDRAM chip, so you don't rewrite that from scratch per board. `linux-on-litex-vexriscv` is a further thin wrapper on top of `litex_boards` (see the "Alternative way to build the Gateware" section) that adds the Linux-specific defaults (OpenSBI, `cpu_variant="linux"`, `boot.json` layout, Buildroot rootfs plumbing). VexRiscv itself is just one of the CPU cores LiteX knows how to instantiate via `add_cpu()` -- LiteX isn't specific to VexRiscv, it's the SoC-composition layer that VexRiscv, the SDRAM controller, the UART, and everything else plug into.

Rejected alternatives to LiteX include:

* **Raw Verilog/SV SoC from scratch**: Fully educational, but a complete Linux-capable SoC is ~50,000+ lines of HDL. VexRiscv alone is tens of thousands of lines of SpinalHDL generating Verilog. Writing this from scratch is a multi-year project. Noteworthy open-source SoC projects that are *not* LiteX-based: **lowRISC Ibex** (small 32-bit RISC-V core, used in Google's OpenTitan secure microcontroller, no Linux); **CVA6 SoC** from OpenHW Group (complete 64-bit Linux-capable SoC in SystemVerilog, but requires a large FPGA or ASIC flow); **PicoSoC** (PicoRV32 + SPI flash + UART, minimal, no Linux); **ZipCPU + AutoFPGA** (open-source tools for building SoCs by Dan Gisselquist — more like a hand-crafted alternative to LiteX, interesting for learning). None of these are drop-in replacements for LiteX if the goal is Linux + Python on an ECP5 without weeks of integration work.
* **FuseSoC**: A package manager for HDL IP cores. You can assemble a SoC from pre-built cores, but the glue logic must still be written in HDL rather than Python, and the device tree / address map must be managed manually.
* **SERV + Zephyr**: SERV is a bit-serial RISC-V core that fits in a few hundred LUTs. It runs Zephyr RTOS (not Linux) and is appropriate for microcontroller-class applications.
* **CVA6 (Ariane)**: A high-performance 64-bit Linux-capable RISC-V core with out-of-order execution. More powerful than VexRiscv but much harder to place on an ECP5 — at ECP5-85F utilization is very tight (~90%+ LUTs) [citation needed] and may not close timing at a useful frequency. Most CVA6 evaluations target larger Xilinx boards (KC705, ZCU102) with Vivado. The minimum credible open-source board would be the ECPIX-5 85F; a more comfortable target would be a Xilinx UltraScale+ board accepted by the experimental `nextpnr-xilinx` backend, which remains immature for SoCs of this complexity.

**On LiteX's reach beyond its core community:** LiteX was created by Enjoy-Digital (a small French engineering firm) and is primarily used by a tight-knit open-source hardware community. It has found genuine niches: radio astronomy instruments (CASPER project boards [citation needed], some SDR hardware), particle physics detector readout electronics (CERN), retrocomputing (running old console/arcade hardware as soft-cores), and academic SoC research groups. It is not used in mainstream commercial embedded Linux products — that space belongs to vendor SDKs. But for a technical education context, LiteX sits in a unique position: it is expressive enough to build real, working systems, transparent enough to trace every design decision to source code, and small enough that a motivated student can read the entire relevant codebase in a few weeks.

### Visualization in the Open-Source Flow: The Block Diagram Gap

Vivado's IP Integrator (Block Design editor) is one area where the open-source flow has no equivalent. A Vivado block diagram shows every IP core as a labeled box, every AXI4 bus as a thick expandable line you can click to trace individual lanes, clock domains color-coded across the canvas, and parameter settings reachable by double-clicking any block. The `AUTO` connection mode propagates bus widths and clock rates automatically. This is simultaneously design entry and documentation — someone unfamiliar with the project can orient themselves in minutes.

**The honest answer: there is no LiteX equivalent of this.** No open-source tool takes a LiteX Python SoC description and renders an interactive, editable block diagram. It would be nice to have something like Vivado or even the GNU Radio Companion (GRC) to connect blocks. GRC works because GNU Radio blocks have uniform, typed ports (streams of float, complex, or byte samples) and the connection semantics are simple. A LiteX SoC has heterogeneous interconnects — Wishbone bus, CSR bus, individual control signals, clock domains, resets, interrupt lines — and representing all of that visually with enough fidelity to be *useful*, and keeping it synchronized with the Python source as a bidirectional editor, is a hard problem the small open-source FPGA community has not yet solved. This is a genuine and acknowledged gap, not a missing convenience feature.

In practice, exploring a LiteX SoC means reading a well-structured object-oriented codebase: `self.submodules +=` calls are the bus connections, and following `self.bus.add_slave()` with a code editor's jump-to-definition replaces clicking through a block hierarchy. This rewards software engineering skills rather than visual spatial reasoning, and that is a real cost for newcomers — especially for a signal processing pipeline where the *flow of data through stages* is the primary thing to understand. An advantage is that LLMs and version tracking work much better than with Vivado.

**What visual tools do exist** in the open-source flow, short of a block diagram editor:

* **`nextpnr --gui`**: The place-and-route tool has a built-in graphical viewer showing the ECP5 device fabric — LUT tiles, DSP blocks, BRAM blocks, routing channels — with your placed design overlaid on the actual silicon floorplan. Click any cell to see which net it drives, highlight critical timing paths, and verify that signals land on the correct I/O pins. This does not show architectural structure (which Python module is which), but it is the primary visual tool for understanding physical resource utilization, spotting routing congestion, and confirming pin assignments. See the LFSR synthesis section for usage.
* **`yosys show`**: After synthesis, appending `; show` to a Yosys command renders the synthesized gate-level netlist as a schematic via Graphviz. Useful for checking what the synthesizer inferred from a small module — flip-flops vs. latches, MUX trees, combinatorial paths. For a full SoC the graph becomes unreadably large. The `netlistsvg` tool takes the same Yosys JSON output and renders a cleaner SVG suitable for documentation.
* **GTKWave** (simulation and hardware capture): The primary waveform viewer for the entire open-source flow. GTKWave reads `.vcd` (Value Change Dump) files from Icarus Verilog testbenches, Verilator simulation, LiteX simulation traces, and LiteScope hardware captures. It is the visual tool you will use most often.
* **LiteScope → GTKWave**: LiteScope is an optional embedded logic analyzer peripheral added to a LiteX SoC with `self.submodules.analyzer = LiteScopeAnalyzer(...)`. It captures signal samples into BRAM on the running FPGA, then streams them to your laptop via `litescope_cli`, producing a `.vcd` file viewable in GTKWave. This is the hardware counterpart to simulation waveform viewing — no external logic analyzer required — and the closest equivalent to Vivado's Integrated Logic Analyzer (ILA).
* **LiteX `--doc`**: Any LiteX SoC build accepts a `--doc` flag (`python3 -m litex_boards.targets.colorlight_i5 --doc`) that generates a static HTML page listing every CSR register, its base address, bit field names, and description strings — the auto-generated register reference that replaces Vivado's "Address Editor" view.

**What a CSR register is**, resolved (this answers the TODO left in the intro, "define what CSRs are and how they affect actual hardware," and the duplicate TODO that was here): CSR stands for Control and Status Register -- a small, memory-mapped register that a peripheral (UART, LEDs, timer, SPI flash controller, etc.) exposes so the CPU can configure it or read its state, as opposed to a location in main RAM that just stores data. In LiteX, a peripheral written as a Migen `Module` declares its registers with `CSRStorage` (CPU-writable, e.g. "turn this LED on") and `CSRStatus` (CPU-readable, e.g. "is there a byte waiting in the UART RX FIFO") -- the `AutoCSR` mixin then auto-assigns each one a unique address and wires it onto the lightweight CSR bus (bridged from the main Wishbone bus, see the Goal 6 section further down), rather than the peripheral author picking addresses by hand. Reading/writing a CSR is an ordinary memory load/store from the CPU's perspective (`mem_write 0xf0003000 1` from the BIOS console earlier in this document is a literal CSR write, to the LED chaser's register) -- the "control and status" distinction is purely about what's on the other end: actual logic and physical pins, not a DRAM cell.

Together these cover most of what Vivado's block diagram, Address Editor, and ILA cover — as separate, focused tools rather than one integrated GUI. The one thing that remains genuinely absent is a high-level architectural diagram showing *which modules connect to which buses* at design time; for that, you either read the Python source or draw a diagram by hand (as in the file dependency graph in the "What This Document Still Needs" section below).

---

# Getting to "FPGA linux boot"

Complete set of instructions to go from a new Ubuntu install on a laptop to building a simple LiteX linux demo. **Default target as of 2026-08-27: the Icepi Zero** (see "Default target: Icepi Zero" right before "Build the Gateware" below for why, and "Confirmed working: Linux boots on real Icepi Zero hardware" for the full session). The toolchain-install sections immediately below are board-agnostic and apply either way. Most of the detailed walkthrough in this document was originally written against the Colorlight i9 module with carrier, and that material is kept for its teaching value (pin mapping, DAPLink/JTAG debugging, raw Verilog, LiteScope) even though the i9 itself never achieved a full Linux boot -- see the "Colorlight i9 equivalent" callouts throughout.

The following sections will answer:

* What development tools do I need to install?
* What's the fastest path from source to booting linux? Maybe some "download this pre-compiled image" will be tolerated on a first pass, but eventually these gaps should be filled in.
* Side quest: (or test of the tools) a simple SystemVerilog blinky, counter, or LFSR demo, maybe with button inputs and LED outputs. This exercises pin mapping, I/O properties, clocking, simulation, and "get the thing onto the FPGA hardware".
* What are the commands to flash the design to the board temporarily (RAM) and then permenantly (flash)?
* Side quest: a RISC-V soft-core FPGA processor running a bare-metal C program
* Side quest: RISC-V soft-core, but with something like Zephyr. Maybe ChibiOS or NuttX if those are appropriate.
* What is the procedure for running a verilator-based (or other) emulation of the linux boot process on the particular SoC, all the way to an interactive terminal?
* What would be good tutorials to make a new SoC peripheral and control it through C, linux, and python?

## Install the **OSS CAD Suite** Toolchain

**Resolved.** The individual tools this document needs (Yosys, nextpnr-ecp5, Project Trellis, openFPGALoader, Icarus Verilog, Verilator, GTKWave, `fujprog`, and more) are each separate upstream projects, normally built and versioned independently -- getting a working, mutually-compatible set of all of them by building from source yourself is real, fiddly work (matching library versions, Python bindings, etc.). [OSS CAD Suite](https://github.com/YosysHQ/oss-cad-suite-build) (maintained by YosysHQ, the company behind Yosys) solves this by publishing a single date-stamped tarball containing pre-built, known-good-together binaries for essentially the entire open-source FPGA toolchain across all the major vendors (Lattice/Trellis, Gowin/Apicula, CologneChip/Peppercorn, and more) plus the simulation tools around them -- one download, one `PATH` addition, and every tool this document uses is available and mutually compatible, no separate builds or version-matching required. The tradeoff is exactly what you'd expect from a bundled binary release: it's a big download (hundreds of MB), it's tied to whatever date-stamped snapshot you grabbed rather than each tool's own latest release, and (per the warning already in this section) it must be kept up to date manually since there's no package-manager-style auto-update.

```bash
# 1. Update system packages and install core dependencies
sudo apt update && sudo apt upgrade -y
sudo apt install -y git python3 python3-pip python3-venv build-essential \
                    libevent-dev libjson-c-dev verilator libftdi1-dev \
                    libusb-1.0-0-dev wget curl libhidapi-dev

# 2. Create a development directory and download the latest OSS CAD Suite
mkdir -p ~/openfpga && cd ~/openfpga
# WARNING: The URL below is version-specific (date-stamped). Before running, visit:
#   https://github.com/YosysHQ/oss-cad-suite-build/releases/latest
# and replace both the URL and the filename in the tar command with the current release.
wget https://github.com/YosysHQ/oss-cad-suite-build/releases/download/2026-08-16/oss-cad-suite-linux-x64-20260816.tgz

# 3. Extract the archive (update filename to match the version you downloaded)
tar -xvzf oss-cad-suite-linux-x64-20260816.tgz

# 4. Add the toolchain permanently to your shell PATH
echo 'export PATH="$HOME/openfpga/oss-cad-suite/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc


# Check for locations and versions
which yosys
# should give /home/USERNAME/openfpga/oss-cad-suite/bin/yosys
yosys --version
which nextpnr-ecp5
nextpnr-ecp5 -V
which openFPGALoader
openFPGALoader --version
```

## Install LiteX

**Resolved** (the "what is LiteX" question is answered more fully in the "Why LiteX over other alternatives?" section above, which now spells out where it sits in the stack -- this confirms that guess was correct): yes, LiteX is a Python framework for composing a complete SoC (CPU + buses + peripherals + memory map) as Python objects rather than hand-written HDL, and for exposing those peripherals' registers back to Python (both on the laptop via `litex_server`/`litex_cli`, and from Linux running on the SoC itself). What it needs to know about a specific board (like `colorlight_i5`) is exactly what `litex_boards/litex_boards/platforms/colorlight_i5.py` and `.../targets/colorlight_i5.py` supply: pin mapping/I/O standards (the platform file) and which peripherals + CPU to instantiate (the target file) -- see "How LiteX manages peripheral addresses → device tree → Python" below for the rest of that pipeline. VexRiscv is covered separately in "Goal 5" further down: it's just one of the CPU cores LiteX knows how to instantiate, selected via `cpu_type="vexriscv_smp"`.

**Resolved:** Migen (a hardware description library) and FHDL (Migen's underlying Fragmented Hardware Description Language) are Migen's own components, not part of LiteX -- LiteX is built *on top of* Migen (LiteX SoC classes generate Migen `Module`/`Signal` objects, which Migen's backend then converts to Verilog for Yosys). Confirmed directly: Migen is installed by `litex_setup.py --init --install` below as its own separate git clone (`~/openfpga/migen`), not bundled with the OSS CAD Suite -- the OSS CAD Suite only provides the downstream synthesis/place-and-route/simulation *tools* (Yosys, nextpnr, GTKWave, etc.), not the Python HDL-generation layer that produces the Verilog those tools consume.

From <https://github.com/enjoy-digital/litex>

```bash
cd ~/openfpga

# Download the automated LiteX bootstrap script
wget https://raw.githubusercontent.com/enjoy-digital/litex/master/litex_setup.py
# Resolved: --gitter is not a real litex_setup.py flag at all -- checked its actual argparse
# definition (`litex_setup.py --help`), and no such option exists, so there was nothing to skip.
# --gcc=riscv IS real (choices: riscv, mips, powerpc, openrisc, lm32) and would additionally
# install a RISC-V cross-compiler at this same step -- this document instead installs
# gcc-riscv64-unknown-elf separately via apt in the next section, which is the specific
# package linux-on-litex-vexriscv's own instructions call for, rather than whatever
# litex_setup.py --gcc=riscv would fetch.

# A dependency (skip this and come back if litex_setup.py fails next):
python3 -m pip install --user --upgrade "packaging>=24.2"

# Initialize, download all repository ecosystems, and install them locally
python3 litex_setup.py --init --install --user

# Sanity check from a directory OTHER than ~/openfpga -- see warning below.
cd $HOME
python3 -c "import litex; print('LiteX OK')"
which litex_sim
litex_sim --help                                          # should print litex_sim usage
python3 -m litex_boards.targets.colorlight_i5 --help     # board-specific options
```

Warning: **Never run `python3`/`litex_sim`/etc. while your shell's current directory is `~/openfpga` itself** (or any other directory that directly contains the bare git clones, e.g. `litex/`, `migen/`, `litedram/`). Each clone's repo root has no `__init__.py` (only the nested `litex/litex/__init__.py` does), so if `~/openfpga` ever ends up on `sys.path`, Python's default `PathFinder` mistakes `~/openfpga/litex` for a namespace package and silently shadows the correct package — producing confusing errors like `ImportError: cannot import name 'get_data_mod' from 'litex' (unknown location)`.


## Setup the Linux-on-LiteX Project

**Resolved** -- confirmed directly from `soc_linux.py` and `boards.py` in this repo, and already stated more fully in the "Alternative way to build the Gateware" section further down: `linux-on-litex-vexriscv` is a thin, Linux-specific wrapper *on top of* `litex_boards` (installed in "Install LiteX" above), not a separate SoC-building framework. It adds: `boards.py`'s registry of which boards are Linux-tested and their Linux-specific default kwargs (`l2_size`, capabilities like `serial`/`ethernet`/`sdcard`); `soc_linux.py`'s `SoCLinux()` wrapper, which forces `cpu_type="vexriscv_smp"`, `cpu_variant="linux"`, adds the OpenSBI memory region, and generates the device tree/`.dtb`; `make.py`, the CLI front-end used throughout this document; the `images/boot.json`-style templates and `images/` directory this document's `litex_term` commands load from; and Buildroot/kernel-build glue for producing the actual Linux `Image`/`rootfs.cpio.gz`. Without this repo, `litex_boards` alone can build a working bare-metal LiteX SoC (BIOS console, no Linux) for any supported board, but has no concept of OpenSBI, device trees, or a Linux rootfs.

From <https://github.com/litex-hub/linux-on-litex-vexriscv>

```bash
# Prerequisites
sudo apt install build-essential device-tree-compiler wget git python3-setuptools gcc-riscv64-unknown-elf

# Test that the compiler is installed and in path
riscv64-unknown-elf-gcc --version
# add this to bash startup for the future
export LITEX_ENV_CC_TRIPLE=riscv64-unknown-elf

# Go back to the directory where we were cloning and installing things
cd ~/openfpga
git clone https://github.com/litex-hub/linux-on-litex-vexriscv.git
cd linux-on-litex-vexriscv

# get list of supported boards
./make.py --help
# make sure that your board (like icepi_zero or colorlight_i5) is listed

# install the Meson build system. Required for ./sim.py
pip3 install meson

# Download the pre-compiled binaries (Linux kernel Image, rootfs, OpenSBI)
# WARNING: ./get_images.py no longer works: the script fetches from GitHub release URLs that
# were reorganized by the maintainers. Use the manual wget method in the Simulate section below.
#./get_images.py
```

## Simulate Linux-on-LiteX

```bash
# Get images manually.
# See: https://github.com/litex-hub/linux-on-litex-vexriscv/issues/164
#
# linux_2022_03_23.zip contains: Image (RISC-V Linux kernel), rootfs.cpio (BusyBox initramfs),
#   and opensbi.bin. These are required for both the sim target and hardware targets.
# orangecrab_2022_03_23.zip contains: board-specific BIOS binary for the OrangeCrab target only.
# Resolved: Image and rootfs.cpio(.gz) are generic RISC-V rv32/BusyBox binaries with no board-specific
# addresses baked in -- they should work unmodified on the Colorlight i9, ULX3S, and Icepi Zero alike.
# The board-specific piece is the .dtb, which this zip does NOT include -- it always comes from your
# own `--build` output (`build/<board>/<board>.dtb`, copied to images/rv32.dtb by combine_dtb()), per
# the "How LiteX manages peripheral addresses" section below. opensbi.bin from this zip is a stock
# build assuming ~16.5 MiB+ of RAM is present (the default OpenSBI offset -- see "Making Linux
# actually fit" further down): fine as-is for ULX3S/Icepi Zero (32 MiB), but NOT for a stock
# Colorlight i9 build (8 MiB) -- that needs the community-patched opensbi.bin from that same section.
# from ~/openfpga/linux-on-litex-vexriscv/
cd images
wget https://github.com/litex-hub/linux-on-litex-vexriscv/files/8331338/linux_2022_03_23.zip
unzip linux_2022_03_23.zip
gzip -k rootfs.cpio  # keep the unzipped. This is for the sim.py step below to work
# Only needed if targeting the OrangeCrab board:
# wget https://github.com/litex-hub/linux-on-litex-vexriscv/files/8331388/orangecrab_2022_03_23.zip
# unzip orangecrab_2022_03_23.zip

cd ..
./sim.py
# I had to go back to images directory and `gzip rootfs.cpio` for this to work
# This boots linux, but takes a long, long wall-clock time, even though Linux thinks it only took 5 seconds
# login: root   <no password>
# within the simulated linux terminal, print system information by typing:
uname -a
# I got the response:
# Linux buildroot 5.14.0 #1 SMP Tue Sep 21 12:57:31 CEST 2021 riscv32 GNU/Linux

# To quit the simulator, ctrl-c
```

## Run a Verilator-Based Emulation

When you run the `sim.py` command, the system is not simulating a Colorlight i9, an OrangeCrab, or any other physical PCB. Instead, you are building and running a completely independent, purely virtual hardware target called the LiteX Simulation Platform (sim).

This decoupling is one of LiteX's greatest architectural advantages. It separates the logical design of a computer (CPU, registers, memory maps) from the physical constraints of a piece of silicon (pin numbers, voltage levels, chip vendors). The differences are:

* No Physical Pins: A physical board requires a constraint file (like a `.lpf` file for the Lattice ECP5 or `.xdc` for Xilinx) to tell the compiler which Verilog wire connects to which physical copper leg on the chip. The sim target uses zero pin files. It compiles down to raw, abstract logic ports. Resolved, with names -- confirmed in `litex/litex/tools/litex_sim.py`'s `_io` list: just plain named signals like `sys_clk`, `sys_rst`, and `serial` (no package pin, no I/O standard, no drive strength -- those concepts don't exist for something that never touches silicon).
* C++ Software Peripherals: Instead of wiring the VexRiscv CPU to a physical memory chip or a real UART transceiver, LiteX wires the CPU to C++ software models (SDRAMPHYModel, LiteEthPHYModel).
* The virtual UART's wires are mapped directly to your computer's stdout and stdin inside your terminal window.
* Same linux kernel Image for both hardware and sim: The Device Tree (`.dtb`) tells Linux if it's `colorlight.dts` or `sim.dts` and these are generated from the JSON map of components' memory addresses and interrupt lines.

**Resolved: what `sim.py` can and can't debug.** It can debug essentially everything on the *digital logic* side that's expressed as real Verilog: the VexRiscv core itself, the Wishbone/CSR bus fabric, any custom peripheral's HDL, cache behavior, interrupt timing, and the full Linux boot sequence and syscalls -- all bit-accurate, all traceable with `--trace` into a `.vcd` (see the LiteScope/GTKWave section above). It *cannot* debug anything that only exists as physical silicon behavior, because those parts aren't simulated as HDL at all -- they're replaced by the C++ behavioral models mentioned in the bullet above: the SDRAM controller's real timing/training sequence (`SDRAMPHYModel` just behaves like ideal instant memory, it doesn't run the actual LiteDRAM PHY Verilog), Ethernet PHY-level signaling, PLL lock behavior, SERDES/transceiver electrical characteristics, or any I/O pin electrical property (drive strength, slew rate, voltage level). If a bug is specific to the DRAM controller's actual HDL implementation, PLL configuration, or anything downstream of "a wire leaves the FPGA package," `sim.py` cannot reproduce it -- you're back to the physical hardware (and LiteScope, for hardware-side waveform capture) for that class of bug.

## How LiteX manages peripheral addresses → device tree → Python

This pipeline is one of LiteX's most important features and directly addresses the goal of understanding how peripheral addresses propagate from HDL all the way to Linux and Python:

1. **Python SoC definition**: When you add a peripheral in the SoC target Python file (resolved -- a concrete example to look at is exactly `~/openfpga/litex-boards/litex_boards/targets/colorlight_i5.py`, already the file this document points at two paragraphs below for adding a new peripheral) (e.g., `self.add_uart()`, `self.add_spi_flash()`), LiteX's Migen/FHDL layer assigns it a unique non-overlapping base address in the SoC memory map automatically.
2. **CSR JSON**: After `--build`, LiteX writes `build/<board>/csr.json` — a complete map of every Control and Status Register, its base address, and its bit fields. This is the machine-readable ground truth.
3. **Device Tree Source (`.dts`)**: LiteX simultaneously generates `build/<board>/dts/<board>.dts`. This file describes all peripherals in the format the Linux kernel expects: `compatible` strings (which kernel driver to bind), `reg` properties (base address and size), and interrupt lines. `dtc` compiles this to the binary `.dtb` passed to the kernel at boot.
4. **Python access from Linux**: After booting, `litex_server` exposes the CSR map so `litex_cli` on your laptop can load `csr.json` and give you a Python REPL where `soc.uart.ev.pending.read()` reads the actual hardware UART interrupt register remotely. No kernel driver needed for rapid prototyping.

**Resolved -- correcting a factual error in point 4 above**: `litex_server` runs on the **laptop/host side**, not on the RISC-V/SoC itself, for every case (sim included) -- confirmed directly in `litex/litex/tools/litex_server.py`'s argparse: `--uart` (with `--uart-port`), `--udp` (Etherbone, with `--udp-ip`/`--udp-port`), `--pcie`, `--jtag`, and `--usb` are all *transport backends litex_server dials out over from the host*, not something it runs as. What has to exist on the target side is just a passive bridge for whichever transport you pick: the BIOS/Linux UART for `--uart`, an Etherbone core added to the SoC (`self.add_etherbone()`) for `--udp`, etc. -- there's no separate "litex_server" process running on the softcore. Etherbone (the `--udp` case) is exactly what the TODO described: it tunnels the Wishbone bus over Ethernet UDP packets, so `litex_server --udp` on your laptop can reach a board's CSRs/memory over a real network connection the same way `--uart` reaches it over a serial cable -- applicable to any board with `self.add_etherbone()` in its SoC (Colorlight i5/i9 and the Tang boards' Ethernet-capable configs are the ones already discussed in this document; `sim.py` uses `--uart` by default since it has no simulated Ethernet PHY in play by default).

To add a new peripheral: edit `~/openfpga/litex-boards/litex_boards/targets/colorlight_i5.py`, add a CSR module in the SoC class, re-run `--build`. The JSON, DTS, and Python bindings all regenerate automatically. This is the "intervention point" to add or modify the example.

```bash
# For Pin mappings and IOStandard definitions for the PCB:
less ~/openfpga/litex-boards/litex_boards/platforms/colorlight_i5.py

# For SoC peripherals like PLLs, serial, USB, Ethernet:
less ~/openfpga/litex-boards/litex_boards/targets/colorlight_i5.py
```

For a human-readable view of the resulting register map, run `python3 -m litex_boards.targets.colorlight_i5 --doc` to generate a static HTML page listing every peripheral, its base address, all CSR registers, and their bit fields. Resolved -- confirmed directly in `soc_linux.py`'s `generate_doc()`: it lands at `build/<board_name>/doc/`, then gets rendered to HTML via Sphinx into `build/<board_name>/doc/_build/` (so `build/colorlight_i5/doc/_build/html/index.html` for this document's usual build). This is the auto-generated equivalent of Vivado's Address Editor view — not interactive, but always in sync with the actual build.

⚠ **Dependency ordering issue:** `./make.py --board=sim --build` internally needs to regenerate the VexRiscv CPU Verilog from its SpinalHDL source using `sbt`. The **Install Scala Build Tool** section below must be completed first. Even after that, these commands invoke a complete from-source Verilator build that takes significant time and has additional prerequisites.

The `./sim.py` path in the **Simulate** section above uses a *pre-compiled* Verilator model shipped with the litex-sim package — that is the faster, recommended starting point.

Once sbt is installed (see below), the full from-source sim build is:

```bash
cd ~/openfpga/linux-on-litex-vexriscv

# 1. Compile the hardware simulation executable (requires sbt installed, takes ~10-20 min)
./make.py --board=sim --build

# 2. Run the simulation (then wait several real minutes for Linux to boot)
./make.py --board=sim --run
```

## Install Scala Build Tool (sbt) to build the VexRiscv processor

The VexRiscv processor core isn't originally written in standard Verilog or VHDL. It is written in SpinalHDL, a next-generation hardware description language nested inside the Scala programming language.

Because sbt runs on the Java Virtual Machine, you need to install Java first, then register the official Scala repository so your native package manager (apt) can pull the official tool down cleanly.

sbt 2.x requires JDK 17 or newer. Don't use `default-jdk` — on Ubuntu 22.04 it resolves to JDK 11, which is too old. Install `openjdk-17-jdk` explicitly instead (also available on 24.04/26.04). 17 is chosen because it's the oldest LTS release that satisfies sbt's minimum, and Ubuntu keeps LTS JDK packages (17, 21, 25) in its repos far longer than the interim, 6-month-support releases (18, 19, 20, 22, ...) — 21 or 25 would work equally well for sbt itself, but 17 is the safest baseline for compatibility with the rest of the Scala/SpinalHDL toolchain used to build VexRiscv:
```bash
sudo apt install -y openjdk-17-jdk
sudo update-alternatives --config java   # pick the JDK 17 entry if you have multiple JDKs installed
java -version   # should print openjdk version "17..." or newer
```

From <https://www.scala-sbt.org/download/>

```bash
cd ~/openfpga
wget https://github.com/sbt/sbt/releases/download/v2.0.6/sbt-2.0.6.tgz
tar xvfz sbt-2.0.6.tgz
cd sbt
./bin/sbt
# that errors out in a few seconds, but proves that the binary runs. TODO: better test here

# Add ~/openfpga/sbt/bin to the path (put this in your .bashrc):
# for the sbt, required to build linux-on-litex-vexriscv
export PATH="$HOME/openfpga/sbt/bin:$PATH"
```


Old:
```bash
curl -sL "https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x2EE0EA64E40A89B84B2DF73499E82A75642AC823" | sudo gpg --dearmor -o /etc/apt/keyrings/scalasbt.gpg
echo "deb [signed-by=/etc/apt/keyrings/scalasbt.gpg] https://repo.scala-sbt.org/scalasbt/debian all main" | sudo tee /etc/apt/sources.list.d/sbt.list
sudo apt-get update
sudo apt-get install sbt
```

The sbt install is the one step in this entire toolchain that doesn't feel like standard open-source tooling. Scala is a JVM language with a niche build system, and the sbt install requires adding a third-party apt repository and a GPG key manually. The reason it exists at all: VexRiscv's configurable architecture is expressed in SpinalHDL/Scala, and sbt is the only way to re-run that code generator.

An alternative that avoids sbt entirely: some distributions package a pre-compiled `VexRiscv_Linux_SMP.v` directly. If you only need to regenerate CPU variants (e.g., adding FPU support or changing cache sizes), consider using the Docker image maintained at `ghcr.io/spinalhdl/docker` which packages a working Scala/sbt environment without polluting your system:

Old:
```bash
docker run --rm -v $PWD:/workspace ghcr.io/spinalhdl/docker sbt "runMain vexriscv.GenCoreDefault"
```

## Default target: Icepi Zero (2026-08-27)

**This document's default target for building and installing Linux-on-LiteX is now the Icepi Zero, not the Colorlight i9.** Reason, stated plainly: on real hardware, the Icepi Zero reached a full Linux login prompt on the first real attempt with zero board-specific engineering beyond patience for a slow serial transfer; the Colorlight i9, after this document's entire "Making Linux actually fit in 8MB" ordeal (kernel stripping, a community-patched OpenSBI, a custom `boot.json`) plus a long DAPLink-reliability investigation, **never achieved a full Linux boot** (see "the kernel never starts running" in the section below, and the `<DAPLink:Overflow>` sections later in this document). The i9 walkthrough is kept below for its genuine teaching value (pin mapping, JTAG/DAPLink debugging, raw Verilog, LiteScope), not because it's still the recommended path to a working Linux system.

**Condensed, confirmed-working command sequence** (assumes the OSS CAD Suite / LiteX / linux-on-litex-vexriscv setup from the sections above is already done, and an Icepi Zero is plugged in over USB-C):

```bash
cd ~/openfpga/linux-on-litex-vexriscv

# 1. Build the gateware (~3.5 min; no board= sub-variant or --device override needed --
#    LFE5U-25F is already the only real chip size for this target):
./make.py --board=icepi_zero --build

# 2. udev rule for the FTDI FT231X programmer/serial chip (once per laptop, same rule Colorlight uses):
wget https://raw.githubusercontent.com/trabucayre/openFPGALoader/master/99-openfpgaloader.rules
sudo cp 99-openfpgaloader.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
# unplug/replug the board after this

# 3. Load the bitstream (SRAM-only, not written to flash):
openFPGALoader -b icepi-zero build/icepi_zero/gateware/icepi_zero.bit
# at this point, the white LEDs should "chase"

# 4. Get the stock Linux/OpenSBI/rootfs images (same zip this document already uses for sim.py;
#    no repatching needed -- see "why this just works" below):
cd images
wget https://github.com/litex-hub/linux-on-litex-vexriscv/files/8331338/linux_2022_03_23.zip
unzip -o linux_2022_03_23.zip
gzip -k rootfs.cpio  # keep the unzipped too
cd ..

# 5. Start litex_term LISTENING FIRST -- see the shared-USB-device gotcha below for why the
#    order matters here (opposite of what you'd do with the i9's DAPLink probe):
litex_term --images=images/boot.json /dev/ttyUSB0
# If you're fast, you can watch litex start up, otherwise hit <enter> a few times to get a prompt.
# Then, once you see the "litex>" prompt echoed in litex_term, type:
serialboot
# Upload takes roughly 15 minutes at 115200 baud (see timing note below) -- this is normal,
# not a hang. It ends with a "buildroot login:" prompt. Login as root, no password.
```

**Gotcha found live, worth flagging because it inverts the i9's procedure:** the Icepi Zero's FTDI FT231X chip is a *single* USB device doing double duty for JTAG programming and the UART console (unlike the Colorlight carrier's DAPLink, which exposes those as genuinely separate USB interfaces). Trying to have `litex_term` already listening *across* a bitstream (re)load -- the natural thing to try, since that's what catches the BIOS's serial-boot handshake right at reset -- kills the connection instead: `openFPGALoader` claiming the shared device drops `litex_term`'s open port out from under it (`[LITEX-TERM] Lost connection to the device, exiting.`), confirmed by reproducing it directly. **The order that actually works:** load the bitstream *first* (finishing and releasing the port), *then* start `litex_term`, *then* type `serialboot` at the idle `litex>` prompt it echoes back -- that retriggers the handshake from within the already-open `litex_term` session instead of relying on catching it at reset.

**Timing note:** the four files (`Image` 7.53 MiB, `rootfs.cpio.gz` 1.83 MiB, `opensbi.bin` 52.4 KiB, `rv32.dtb` ~2.9 KiB -- about 9.0 MiB total) upload at 115200 baud, which is close to its ~11.5 KiB/s raw line rate -- roughly 14-15 minutes wall clock, confirmed end-to-end with zero frame errors. That's slow but simply patience, not a bug; if faster iteration matters more than using the stock upstream images, the i9-oriented "Making Linux actually fit" section below already produced a smaller, generic (board-agnostic) stripped `Image` (~5.7 MiB) and `rootfs.cpio.gz` (~700 KiB) that drop straight into `images/` here too and roughly halve the transfer, since neither file has board-specific addresses baked in (only `rv32.dtb` does, and that one always comes fresh from this build's own `combine_dtb()` regardless).

**A faster baud rate for this same stock-image transfer, confirmed on real hardware (2026-08-27): use `--uart-baudrate=460800` on the `make.py --build` above and `litex_term --speed=460800 ...` to match.** The UART baud sweep further down this document ("Icepi Zero UART baud-rate stress test") found the raw serial link itself clean up to 2,000,000 baud, but `litex_term`'s actual bidirectional upload protocol is far more sensitive than a one-way stream: `--uart-baudrate` values of 921,600, 1,500,000, and 2,000,000 all failed immediately with repeated "serial frame error" during upload calibration and never completed. **460,800 was the fastest rate that negotiated cleanly (zero frame errors) and completed the full four-file transfer end-to-end: 278 seconds, about 4.6 minutes — roughly 3.2× faster than 115200's ~14-15 minutes**, confirmed by a real login and `uname -a` afterward. Note the speedup (3.2×) is well short of the raw baud-rate ratio (4×) — consistent with USB round-trip/ack overhead, not wire bit-rate, being the dominant cost once the link itself is fast enough (the FTDI driver's `latency_timer` was already at its 1ms floor, so that specific lever wasn't available to push further). Don't reuse `--uart-baudrate` above 460800 for this specific board/tutorial without retesting -- the failure mode above 460800 is a hard, immediate cliff, not a gradual slowdown.

**Why the stock images just work here with no repatching, unlike the i9:** `boot_ram0.json`'s default offsets (`opensbi.bin` at `main_ram`+15 MiB, `rootfs.cpio.gz` at +16 MiB) and the hardcoded `main_ram_base + 0x00f0_0000` OpenSBI region both assume ~16.5 MiB+ of real SDRAM. The Icepi Zero has 32 MiB (confirmed both by geometry math on its `W9825G6KH6` SDRAM module and directly by the running system's own `free` output below), comfortably past that -- so none of the i9's custom-offset `boot.json`, community-patched `opensbi.bin`, or kernel/rootfs size surgery is needed at all.

### Confirmed working: full Linux boot on real Icepi Zero hardware (2026-08-27)

Ran the sequence above end-to-end against a real Icepi Zero over USB-C. `openFPGALoader -b icepi-zero --detect` first confirmed the board and chip before touching anything:

```
Jtag probe limited to 3MHz
index 0:
	idcode 0x41111043
	manufacturer lattice
	family ECP5
	model  LFE5U-25
	irlength 8
```

`./make.py --board=icepi_zero --build` completed in 3m26s with **0 errors**. The only nextpnr warning was unrelated to this document's goal: `Max frequency for clock '$glbnet$hdmi5x_clk': 147.80 MHz (FAIL at 200.00 MHz)` -- a timing miss on the HDMI/GPDI video-output clock domain, which this document doesn't use for a serial-console Linux boot (the same `with_video_terminal` capability the ULX3S section above had to disable for a *build error*; here it only produces a timing warning, and was left alone since it doesn't block anything this document needs). Every other clock domain passed. Output: `build/icepi_zero/gateware/icepi_zero.bit` (395,630 bytes) and `build/icepi_zero/icepi_zero.dtb`.

After loading the bitstream and stock images per the sequence above, `litex_term`'s log shows the full pipeline working cleanly -- upload calibration, all four files transferring with **no frame errors** (unlike the i9's `Got unknown reply 'b'E'' from the device` failures from addresses past the end of physical RAM), then the OpenSBI jump, then the kernel itself:

```
Executing booted program at 0x40f00000
OpenSBI v0.8-1-gecf7701
...
[    0.000000] Linux version 5.14.0 ...
...
[   29.570354] Run /init as init process
Starting syslogd: OK
Starting klogd: OK
Running sysctl: OK
Starting network: OK

Welcome to Buildroot
buildroot login: root

  32-bit RISC-V Linux running on LiteX / VexRiscv-SMP.

root@buildroot:~# uname -a
Linux buildroot 5.14.0 #1 SMP Tue Sep 21 12:57:31 CEST 2021 riscv32 GNU/Linux
root@buildroot:~# free
              total        used        free      shared  buff/cache   available
Mem:          24548        3340       15844          16        5364       15144
Swap:             0           0           0
```

`free` confirms ~24 MiB of usable RAM out of the board's 32 MiB physical SDRAM (the remainder reserved for OpenSBI/BIOS/rounding) -- consistent with the "why stock images just work" note above, and a direct, concrete contrast with the i9's 8 MiB ceiling that drove this whole document's kernel-stripping exercise.

**Total session time, reset to login prompt:** roughly 15 minutes, essentially all of it the serial upload itself (kernel boot after the OpenSBI jump took well under a minute). No hardware-specific debugging was needed beyond the shared-USB-device ordering gotcha documented above -- a sharp contrast with the many real-hardware sessions the Colorlight i9/DAPLink material below required for a boot that, in the end, still didn't fully succeed.

## Build the Gateware (logical architecture) and FPGA bitstream

Because we have the i9 rather than the i5, we need to go through an additional confusing hoop:
`--board=colorlight_i5` selects which *target/board-class* make.py loads (there is no
separate `colorlight_i9` class in linux-on-litex-vexriscv's boards.py -- the i9 module is
handled *inside* the colorlight_i5 target as a physical sub-variant).
That sub-variant is picked by a `board=` kwarg on litex_boards.targets.colorlight_i5.BaseSoC
(default "i5"), which is DIFFERENT from make.py's own `--board=` flag above -- the two just
happen to share the name "board". Because `--board` is already claimed by make.py's target
selector, you can't write `--board=i9` a second time (it would just overwrite the target
selection and fail with a KeyError). Instead pass it as a bare, dash-less `board=i9` token,
which make.py's argument parser forwards straight through as a kwarg to BaseSoC/Platform.
It MUST be the last thing on the command line -- once argparse hits a non-flag token it
sweeps everything after it into that passthrough bucket too, so any real --flag placed
after it would be silently ignored.

```bash
cd ~/openfpga/linux-on-litex-vexriscv
./make.py --board=colorlight_i5 --revision=7.2 --build board=i9

ls ./build/colorlight_i5/
# Resolved -- the files worth knowing about, all referenced elsewhere in this document:
#   gateware/colorlight_i5.bit      the bitstream (see below)
#   csr.csv, csr.json               CSR register map -- "How LiteX manages peripheral addresses" above
#   colorlight_i5.dts, .dtb         device tree source/binary -- same section
#   software/bios/bios.bin          the BIOS binary baked into the bitstream -- "Interlude" section below
#   doc/                            only present after --doc -- "LiteX --doc" bullet above

# The compiled FPGA bitstream will be located at
ls -lh ./build/colorlight_i5/gateware/colorlight_i5.bit
# My .bit file was 470K
```

**ULX3S (CS-ULX3S-03, 85F) equivalent.** `boards.py`'s `board_name` is derived automatically from the class name (`camel_to_snake("ULX3S")` = `"ulx3s"`, confirmed by reading `make.py`'s `get_supported_boards()`), so `--board=ulx3s` is the target selector here -- no `colorlight_i5`-style two-tier "board inside a board" indirection needed. **Correction (found the hard way, and worth flagging since an earlier revision of this doc got it wrong): `--device` does *not* need the `board=i9`-style bare-token REMAINDER trick at all.** Checked `make.py`'s own top-level argparse directly: it defines genuine `--device`, `--revision`, `--variant`, `--toolchain`, and `--bus-standard` flags (`parser.add_argument("--device", default=None, ...)` etc.) specifically as generic passthroughs to whichever target's `BaseSoC` accepts them -- unlike `--board`, none of these collide with anything, so ordinary `--flag=value` syntax works:

```bash
cd ~/openfpga/linux-on-litex-vexriscv
./make.py --board=ulx3s --device=LFE5U-85F --build

ls ./build/ulx3s/
ls -lh ./build/ulx3s/gateware/ulx3s.bit
```

Note: `radiona_ulx3s.py` also accepts `--revision` (default `"2.0"`, other option `"1.7"`) for PCB pinout revisions -- this is a *different* numbering scheme from Crowd Supply's own "v3.1.7" batch/campaign numbering seen in their update titles, so don't assume they correspond. Leave `revision` at its default unless something doesn't line up (wrong pins, build errors referencing missing signals), in which case try `--revision=1.7`.

**Known build error and the fix.** The command above fails during nextpnr placement with:

```text
ERROR: Pseudo-differential IO 'gpdi_eth_p$tr_io' must be output
```

Cause: `linux-on-litex-vexriscv` turns on HDMI video output by default for every ULX3S build (nothing you did wrong). Doing so requests a pin group that, on revision 2.0 (the default hardware revision), includes two extra pins nothing in the design drives, and `nextpnr-ecp5` won't accept them left undriven.

**Fix — edit one file:** open `~/openfpga/linux-on-litex-vexriscv/boards.py`, find `class ULX3S(Board):`, and comment out the `"framebuffer"` line in its `soc_capabilities`:

```python
        Board.__init__(self, radiona_ulx3s.BaseSoC, soc_capabilities={
            "serial",
            "sdcard",
            # "framebuffer",   # <- comment this line out
        })
```

This turns off HDMI/GPDI video output, which this document doesn't need (the goal is booting Linux over serial). There's no CLI flag that fixes this instead -- `make.py` re-enables video from this same file after reading your command-line options, so any attempt to disable it with `with_video_framebuffer=False` on the command line gets silently overridden.

**Is there a way to keep GPDI working instead of disabling it?** Tried it, and no simple one exists: tying the two unused pins to a constant does get past this specific error, but trades it for a different one (`must be constrained to 'A' side of pair`) -- they're a genuine differential pair, and satisfying nextpnr properly needs real ECP5 differential-pair setup, not a one-line patch. Disabling the framebuffer is the practical fix for this document's goal.

**Confirmed working:** after this edit, a clean `rm -rf build/ulx3s && ./make.py --board=ulx3s --device=LFE5U-85F --build` completes with no errors and produces `build/ulx3s/gateware/ulx3s.bit`.

**Icepi Zero equivalent.** `camel_to_snake("Icepi_zero")` = `"icepi_zero"`. Its target script's only real chip size is `LFE5U-25F` (already the default), so no `device=` override is needed at all -- this is the simplest of the three:

```bash
cd ~/openfpga/linux-on-litex-vexriscv
./make.py --board=icepi_zero --build

ls ./build/icepi_zero/
ls -lh ./build/icepi_zero/gateware/icepi_zero.bit
```

### Equivalent of `make clean && make` here

There's no `--clean` flag and no Makefile-style timestamp caching for the gateware: every time `--build` is passed, `Builder._build()` (`litex/soc/integration/builder.py`) sets `run = self.compile_gateware` (`True` by default) and unconditionally re-runs the whole Migen -> Yosys -> nextpnr -> ecppack pipeline from scratch, regenerating everything under `build/colorlight_i5/gateware/`. The BIOS software directory is even self-invalidating: `_build()` diffs the freshly-generated `variables.mak` (which encodes the CSR/memory layout) against the previous one and automatically wipes+rebuilds `build/colorlight_i5/software/` if anything relevant changed. So in practice, just re-running the same command already forces a full rebuild in almost all cases. (This applies identically to `build/ulx3s/` and `build/icepi_zero/` -- the caching/self-invalidation logic in `Builder._build()` is board-agnostic.)

The one bulletproof way to guarantee zero stale state (bitstream, BIOS binary, generated headers, `csr.csv`/`csr.json`, `.dts`, yosys/nextpnr intermediate files) is to delete the whole per-board build directory first, then rebuild:

```bash
cd ~/openfpga/linux-on-litex-vexriscv
rm -rf build/colorlight_i5
./make.py --board=colorlight_i5 --revision=7.2 --build board=i9

# ULX3S:
rm -rf build/ulx3s
./make.py --board=ulx3s --build device=LFE5U-85F

# Icepi Zero:
rm -rf build/icepi_zero
./make.py --board=icepi_zero --build
```

**Note (relevant to the SDRAM-size debugging above): a clean rebuild will *not* change the reported `SDRAM: 8.0MiB`.** Checked `litex_boards/targets/colorlight_i5.py`'s SDR SDRAM section: `module = EM638325(sys_clk_freq, sdram_rate)` is unconditional -- there's no `if board == "i9"` branch there at all (only the SPI flash chip is board-specific: `GD25Q16` for i5 vs `W25Q64` for i9). `EM638325` is `nbanks=4, nrows=2048, ncols=256` at 16-bit width = exactly 8MiB, matching the boot log exactly. The fact that flash reported `8.0MiB` (`W25Q64`) confirms `board=i9` *did* apply correctly to this build -- it's specifically the SDRAM chip model that's hardcoded the same for both i5 and i9 in this litex-boards version, independent of the `board=` kwarg. This is a separate, still-open question from the passing-tokens/clean-build mechanics: either the real i9 SDRAM chip genuinely is only 8MB (contradicting this doc's earlier "32MB SDRAM" claim), or `litex_boards`' i9 support needs a board-specific SDRAM module override that this checkout doesn't have.

## Install tools to flash (load) the bitstream onto the board

To flash without requiring sudo privileges every time, set up the udev permissions first (do this once per laptop):

```bash
# Download the openFPGALoader udev rules (covers CMSIS-DAP / DAPLink on the carrier board)
wget https://raw.githubusercontent.com/trabucayre/openFPGALoader/master/99-openfpgaloader.rules
sudo cp 99-openfpgaloader.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
# Unplug and replug the USB cable after running the above
```

Note: The Colorlight carrier board uses an STM32 running DAPLink firmware, which presents as a CMSIS-DAP device. The correct rules file is `99-openfpgaloader.rules` — it covers CMSIS-DAP and all other programmers supported by openFPGALoader. The `60-openocd.rules` file is for OpenOCD-based JTAG adapters and is NOT needed here.

**This same udev-rules step covers ULX3S and Icepi Zero too** -- the same `99-openfpgaloader.rules` file's stated purpose ("CMSIS-DAP and all other programmers supported by openFPGALoader") includes their FTDI-based programming interface, confirmed by checking openFPGALoader's own built-in board database directly (`openFPGALoader --list-boards`): both `ulx3s` and `icepi-zero` use the `ft231X` driver (an FTDI FT231X chip), distinct from Colorlight's `cmsisdap`. No separate download needed -- do this step once and it covers all three boards.

**One thing the udev rule does *not* cover, for any of the three boards**: read/write access to the `/dev/ttyUSB*`/`/dev/ttyACM*` serial device itself (used by `picocom`/`litex_term`) is governed separately, by the standard Linux `dialout` group, not by `openFPGALoader`'s udev rules (those are about the libusb/hidraw programming interface). If `picocom`/`litex_term` fail with a permissions error even though `openFPGALoader --detect` works fine, add yourself to `dialout` and log out/in (or reboot) for it to take effect:

```bash
sudo usermod -a -G dialout $USER
# then log out and back in (or reboot) -- group membership doesn't apply to already-open sessions
```

Connect your laptop to the USB-C port on the Muse Lab extension breakout carrier board for the Colorlight i9. To confirm the board enumerates correctly over USB and that the udev rule is actually in effect:

```bash
# 1. Confirm the OS sees the CMSIS-DAP interface at all (look for "CMSIS-DAP" or similar in the description). Plug and unplug and watch:
sudo dmesg --follow
# The DAPLINK shows up as a composite device:
# (as usual, your device numbers may vary)
# 1. vitual drive called DAPLINK, a 64 MB FAT. 
#      Drag a .bin/.hex/.uf2 file onto the drive to flash.
# 2. /dev/ttyACM0 USB UART serial port bridge. Use with
#      picocom -b 115200 /dev/ttyACM0
# 3. /dev/hidraw1 and /dev/usb/hiddev0
#      The JTAG/SWD probe interface -- what openFPGALoader, OpenOCD, or pyOCD talk to over HID reports to program the FPGA/flash and (if you ever wire up OpenOCD+GDB for the VexRiscv bare-metal debugging section) do JTAG debugging 

# 2. Confirm openFPGALoader itself can find and identify the probe
openFPGALoader --scan-usb

# 3. The real permission + driver test: this must succeed WITHOUT sudo if the udev rule is working. By default, `--detect` assumes a generic FTDI ft2232 driver, so tell it explicitly which driver to use instead:
openFPGALoader -c cmsisdap --detect
# It will look for v2 first and then fall back to v1
```

**ULX3S and Icepi Zero equivalents.** Both use a single FTDI FT231X chip for programming *and* the serial console -- unlike Colorlight's DAPLink, which exposes the JTAG/SWD probe (`/dev/hidraw*`) and the UART (`/dev/ttyACM0`) as genuinely separate USB interfaces, these two boards' FT231X does both jobs over the *same* physical connection, switching mode internally. Practically: the board will enumerate as a single `/dev/ttyUSB0`-style device (confirm the exact number with `dmesg`, same caveat as above), and `openFPGALoader` and `picocom`/`litex_term` can't both hold it open at once -- the same "only one program on the serial port at a time" rule this document already established for `litex_term` vs. `picocom` on Colorlight applies here too, just for a different underlying reason (shared USB device, not just shared UART bytes). Instead of `-c cmsisdap`, pass the board's own profile with `-b`, which openFPGALoader resolves to the correct driver automatically:

```bash
# ULX3S:
openFPGALoader -b ulx3s --detect

# Icepi Zero:
openFPGALoader -b icepi-zero --detect
```

## Flash (load) the bitstream to run Linux onto the board

To view the terminal output as Linux-on-LiteX FPGA configuration loads and Linux boots on the hardware, open a serial terminal emulator in another terminal, targeting the serial bridge exposed by your carrier board:

```bash
# In a 2nd terminal, to monitor the serial boot process
picocom -b 115200 /dev/ttyACM0
```

**ULX3S / Icepi Zero:** same idea, different (and shared-with-programming, see above) device node -- confirm the exact number with `dmesg`, don't assume `ttyUSB0` if you have other FTDI devices plugged in:

```bash
picocom -b 115200 /dev/ttyUSB0
```

Official way of loading the Linux-on-LiteX firmware. From the laptop:

```bash
cd ~/openfpga/linux-on-litex-vexriscv
./make.py --board=colorlight_i5 --revision=7.2 --load board=i9
```

**ULX3S / Icepi Zero equivalents.** Neither goes through `ecpdap` the way Colorlight does (see below) -- `radiona_ulx3s.py`'s `create_programmer()` returns `fujprog()` (the ULX3S project's own dedicated loader, a different tool again, not `openFPGALoader`), while `icepi_zero.py`'s returns `OpenFPGALoader(board="icepi-zero")` (so `--load` *does* shell out to `openFPGALoader` for this board specifically, using the same `-b icepi-zero` profile as the manual command above):

```bash
# ULX3S (uses fujprog, not openFPGALoader -- confirmed already bundled in oss-cad-suite/bin/ alongside the tools installed earlier, no separate install needed):
./make.py --board=ulx3s --load device=LFE5U-85F

# Icepi Zero:
./make.py --board=icepi_zero --load
```

This gave me the following output on the picocom terminal:

```
        __   _ __      _  __
       / /  (_) /____ | |/_/
      / /__/ / __/ -_)>  <
     /____/_/\__/\__/_/|_|
   Build your hardware, easily!

 (c) Copyright 2012-2026 Enjoy-Digital
 (c) Copyright 2007-2015 M-Labs

 BIOS CRC passed (d7bca692)

 LiteX git sha1: 37b75bd46

--================ SoC =================--
CPU:		VexRiscv SMP-LINUX @ 60MHz
BUS:		wishbone 32-bit data/32-bit addr
CSR:		32-bit data big ordering
ROM:		64.0KiB
SRAM:		6.0KiB
L2:		2.0KiB
FLASH:		8.0MiB
SDRAM:		8.0MiB 32-bit @ 60MT/s (CL-2 CWL-2)
MAIN RAM:	8.0MiB

--=========== Initialization ===========--
Ethernet init...
Local IP: 192.168.1.50
Initializing SDRAM @0x40000000...
Switching SDRAM to software control.
Switching SDRAM to hardware control.
Memtest at 0x40000000 (2.0MiB)...
  Write: 0x40000000-0x40200000 2.0MiB     
   Read: 0x40000000-0x40200000 2.0MiB     
Memtest OK
Memspeed at 0x40000000 (Sequential, 2.0MiB)...
  Write speed: 22.3MiB/s
   Read speed: 27.3MiB/s

Initializing w25q64 SPI Flash @0x00800000...
SPI Flash clk configured to 30 MHz (div: 2)
Memspeed at 0x800000 (Sequential, 4.0KiB)...
   Read speed: 2.7MiB/s
Memspeed at 0x800000 (Random, 4.0KiB)...
   Read speed: 1.2MiB/s

--================ Boot ================--
Booting from serial...
Press Q or ESC to abort boot completely.
sL5DdSMmkekro
             Timeout
Booting from network...
Local IP: 192.168.1.50
Remote IP: 192.168.1.100
Booting from boot.json...
ARP failed
Booting from boot.bin...
Copying boot.bin to 0x40000000... ARP failed

Network boot failed.
No boot medium found

--============== Console ===============--

litex> 
```

Once programmed, a gren LED blinks on the module to the right of the bright red LED.

The `litex>` prompt is the LiteX BIOS console (a bare-metal bootloader/monitor), not a Linux shell -- Linux itself never booted here ("No boot medium found"). Type `help` to list the BIOS commands available in this build (things like `reboot`, `flush_l2_cache`, `mem_list`, `mem_read`, `mem_write`, `crc`, `boot`).

The `leds` command works to turn on and off the green LED on the i9 module, but it works oppositely (0 is on, 1 is off):

```
litex> leds 0

Setting LEDs to 0x0
litex> leds 1

Setting LEDs to 0x1
```

The LED blink pattern you can already see on the board is really a one-LED chase pattern, driven automatically by the `with_led_chaser=True` hardware in the SoC and runs independently of anything typed at the prompt -- it's already your external confirmation that the gateware loaded and the CPU is executing.

To toggle an LED by directly writing to an address from the BIOS, use `mem_write <leds_csr_address> <value>` with the address from `build/colorlight_i5/csr.csv`; to control it from a real OS you'd need Linux booted and `/sys/class/leds` or direct GPIO access.

```bash
# From the laptop,
$ cd  ~/openfpga/linux-on-litex-vexriscv
$ grep -i led build/colorlight_i5/csr.csv
csr_base,leds,0xf0003000,,
csr_register,leds_out,0xf0003000,1,rw

# Then from picocom, turn LED on and off by writing directly to the memory address of the LEDs:
litex> mem_write 0xf0003000 0
litex> mem_write 0xf0003000 1
```

The exact same `grep -i led build/<board>/csr.csv` pattern works for ULX3S and Icepi Zero (`build/ulx3s/csr.csv`, `build/icepi_zero/csr.csv`) -- but don't reuse `0xf0003000` from above, it's specific to this exact Colorlight build's CSR layout. Every board/build combination gets its own address map, generated fresh each `--build`; always re-`grep` after switching boards.

`make.py --load` loads `.bit` file onto the FPGA (that's why you got a working BIOS console above) -- but it does **not** invoke `openFPGALoader`. Its `--load` flag calls `board.load()`, which by default runs `self.platform.create_programmer().load_bitstream(...)`; `colorlight_i5.Platform.create_programmer()` returns an `EcpDapProgrammer`, which shells out to a *different* CMSIS-DAP tool called [`ecpdap`](https://github.com/adamgreig/ecpdap), not `openFPGALoader`. (ULX3S and Icepi Zero each go through yet another path here -- `fujprog` and `openFPGALoader` respectively, see the "Install tools to flash" section above.)



Alternate 1: Temporary Boot (SRAM / Volatile) straight into the FPGA's volatile memory. It is fast and safe for iterative testing, but the design will vanish the moment you unplug or reset the power rail. The following is similar to `make.py --load`, which used a *different* CMSIS-DAP tool called [`ecpdap`].  

```bash
openFPGALoader  -c cmsisdap build/colorlight_i5/gateware/colorlight_i5.bit
```

ULX3S and Icepi Zero equivalents -- using `openFPGALoader`'s own board profiles (`-b`) rather than `-c cmsisdap`, per the driver info confirmed above (`openFPGALoader --list-boards`):

```bash
# ULX3S:
openFPGALoader -b ulx3s build/ulx3s/gateware/ulx3s.bit

# Icepi Zero:
openFPGALoader -b icepi-zero build/icepi_zero/gateware/icepi_zero.bit
```

Alternate 2: Permanent Boot (SPI Flash / Non-Volatile) This method writes the configuration directly onto the onboard non-volatile SPI flash chip. The FPGA's gateware (VexRiscv + BIOS) reloads automatically every single time the board is powered up -- **correction to an earlier draft of this document, which overclaimed that this alone makes "your Linux system" reload automatically: it doesn't, by itself. See the "What actually auto-starts on power-up alone?" section right below** for exactly what this command does and doesn't get you standalone.

```bash
openFPGALoader  -c cmsisdap -f build/colorlight_i5/gateware/colorlight_i5.bit
```

```bash
# ULX3S:
openFPGALoader -b ulx3s -f build/ulx3s/gateware/ulx3s.bit

# Icepi Zero:
openFPGALoader -b icepi-zero -f build/icepi_zero/gateware/icepi_zero.bit
```

### What actually auto-starts on power-up alone? (USB into a wall charger / power bank, no computer)

A direct question worth a direct, sourced answer, since it's easy to conflate "flash the bitstream" with "the whole thing boots itself" -- they're not the same claim. Answered by reading `litex/soc/software/bios/main.c` and `boot.c` directly rather than guessing, and cross-checked against this exact Colorlight i9 build's own generated headers.

* **Can the FPGA bitstream itself auto-load from flash? Yes, unconditionally, and this part of the document already had it right.** This is a *hardware* mechanism, nothing to do with the BIOS or LiteX at all: the ECP5's own configuration logic reads `CFG_MD` at power-up, and by default streams the bitstream in from SPI flash address 0 (see "FPGA Configuration: How the ECP5 Loads Its Bitstream" further down). `openFPGALoader -f` writes the bitstream there. This is why the green LED chaser (pure gateware, `with_led_chaser=True`, no CPU involvement) starts blinking on every power-up with nothing else connected -- it's your visual confirmation that *this* part works standalone, and it works regardless of anything below.
* **Can a bare-metal C program auto-load and start, with no host at all? Yes -- but not from anything this document's build commands have set up so far.** The BIOS has a real, working `flashboot()` path (`boot.c`): it reads a flat image (4-byte length + 4-byte CRC32 + payload) from a fixed address `FLASH_BOOT_ADDRESS`, copies it to SDRAM (or executes it in place if no SDRAM), and jumps to it -- fully autonomous, no serial/network required. The catch: `FLASH_BOOT_ADDRESS` is a C macro that has to be `#define`d at build time, and **grepping the entire `litex` and `litex-boards` source trees turns up zero targets that define it** -- confirmed directly against this exact SoC's own `build/colorlight_i5/software/include/generated/*.h`, where it's simply absent. `flash_boot_method()` is compiled out entirely (`#if defined(FLASH_BOOT_ADDRESS)`) for every build this document has produced. This is a real, supported LiteX feature that's just never been wired up here -- doing so would mean adding a constant to the SoC's Python target file and writing a correctly-formatted length+CRC+payload image to that flash offset (via the BIOS's own `flash_write` console command, or a host-side flashing tool), neither of which this document currently covers.
* **Does LiteX always need serial or Ethernet to start running something? No -- but "no host at all" narrows the real options down to two, and this document hasn't exercised either yet.** Reading `boot_sequence()` in `main.c`, the BIOS tries every *compiled-in* boot method in priority order: serial (0) → flash (10, absent here) → rom (20, absent here) → sdcard (30, only present with `--with-sdcard`/`--with-spi-sdcard`) → sata (40, absent) → net (50, only present with `--with-ethernet`, and even then needs a DHCP+TFTP server on the other end -- not "no host," just "no *direct cable* to a host"). The one method that's both genuinely host-free *and* already fully documented elsewhere in this document is **SD card boot**: `sdcardboot()` reads a `boot.json` (or `boot.bin`) straight off the SD card's filesystem, the exact same multi-file format (`Image`, `rootfs.cpio.gz`, `rv32.dtb`, `opensbi.bin`) `litex_term --images=` streams over serial -- so a full Linux boot *can* run with zero host connection once wired up, just onto an SD card instead of over UART. That requires the SD-card PMOD from the "PMODS" section of the platform file (`sdcard_pmod_io()`, `--with-sdcard`), which this document mentions in passing but has never actually built or tested.
* **What actually happens if you power this exact board (as built everywhere else in this document) from a USB charger with no computer attached?** The bitstream configures, VexRiscv boots the BIOS, the BIOS tries serial boot (immediate timeout -- nothing is listening on the other end of a charger), tries network boot if Ethernet was enabled (fails without a DHCP/TFTP server actually present), and then falls through to sitting at the idle `litex>` console -- exactly the sequence captured in the real boot log earlier in this document ("Booting from serial... Timeout... Booting from network... ARP failed... No boot medium found"). No C program and no Linux runs on its own. The LED chaser blinks (gateware, gets that from power alone); nothing else does, unless one of the two paths above (flash-boot a raw image, or SD-card `boot.json`) is set up first.

## Interlude: What the `.bit` file contains

What the `.bit` file contains, and how the RISC-V core and BIOS come up from it:

* `make.py --build` first compiles the SoC hardware description (the VexRiscv SMP core, buses, peripherals, memory controllers, etc.) with Migen/LiteX, then compiles the small BIOS (a C program under LiteX's `soc/software/bios`) separately into `build/colorlight_i5/software/bios/bios.bin`.
* The BIOS binary is then read back in (`Builder._initialize_rom_software()` in `litex/soc/integration/builder.py`) and used to set the *initial contents* of the SoC's integrated ROM memory (`soc.init_rom(...)`), padded with zeros to fill the configured ROM size (64KiB here). This happens *before* synthesis/place-and-route, so the ROM's initial values are baked into the design as a Migen `Memory` with an `init=` parameter.
* ECP5 block-RAM (BRAM) primitives support bitstream-configurable initial contents, so when yosys/nextpnr/ecppack turn that design into the final `.bit` file, the BIOS binary ends up encoded directly in the bitstream as BRAM init values -- alongside the LUT/routing configuration for the CPU, buses, and peripherals. That's why a single `.bit` file (and a volatile, SRAM-only `--load`) is enough to get a fully working BIOS console with no separate flash-write or SDRAM-write step.
* Main RAM (SDRAM), by contrast, is not preloaded by the bitstream at all -- it's just a memory controller in the FPGA fabric; its contents (Linux, rootfs, etc.) will only exist once the running BIOS/software writes something there, which is what the "Loading Linux over Serial" section below does.
* On configuration, the ECP5 releases reset and the VexRiscv fetches its first instruction from a hardwired reset vector. In LiteX, `SoCCore.add_cpu()` sets that reset address to `self.mem_map["rom"]`, which defaults to `0x00000000` (confirmed in `litex/soc/integration/soc.py`'s `soc_core_mem_map`), and `VexRiscvSMP.reset_vector = 0` matches it.
* `0x00000000` is mapped to the "rom" bus region -- the very BRAM whose contents were set to the BIOS binary above (`SoCCore._finalize_cpu_reset_address()` explicitly checks that the reset address falls inside the `"rom"` region and sets `cpu.use_rom = True` when it does). So the CPU boots directly into the LiteX BIOS with no bootloader stage of its own.
* The BIOS then runs the initialization that was seen in the log: bring up the SDRAM controller, memtest it, and probe serial/network/flash for a bootable Linux payload -- which is where this document's next section ("Loading Linux over Serial") picks up.


## Loading Linux over Serial

**Resolved, and already spelled out just above in "Interlude: What the `.bit` file contains"**: the previous step's `--load`/`openFPGALoader` only put the *gateware* (CPU, buses, peripherals, and the tiny BIOS baked into BRAM) onto the FPGA -- that's enough for the `litex>` BIOS prompt seen at the end of that section, but SDRAM starts out empty every power-cycle (it's just a controller in the fabric, not preloaded by the bitstream). "Loading Linux" means getting the actual kernel `Image`, device tree, OpenSBI, and rootfs *into that empty SDRAM* so the BIOS has something to boot into -- which is exactly what `litex_term --images=...` does below: it waits for the BIOS's serial-boot handshake, then streams all four files to their addresses in RAM over the same UART, byte by byte.

From <https://github.com/litex-hub/linux-on-litex-vexriscv/tree/master>

Since loading over Serial works for all boards, this is the recommended way to do initial tests even if your board has more capabilities. **Resolved:** yes, Ethernet is the main other option -- any board with `self.add_etherbone()` (Colorlight i5/i9 among them) can netboot via the `boot.json`-equivalent flow over Etherbone/TFTP instead of the UART, seen partially in the boot log earlier in this document ("Booting from network... ARP failed" -- that attempt failing is why it fell through to the serial-boot prompt). Serial is "recommended for initial tests" specifically because it has no network configuration to get right first (no IP/ARP/DHCP to debug) -- it's the same reasoning this document already gives for U-Boot-less boards preferring the simplest working path first.

```bash
cd ~/openfpga/linux-on-litex-vexriscv
litex_term --images=images/boot.json /dev/ttyACM0
```
The files `images/boot.json` references (`Image`, `rv32.dtb`, `rootfs.cpio.gz`, `opensbi.bin`) do all exist in `~/openfpga/linux-on-litex-vexriscv/images/`, so that wasn't the problem.

**ULX3S / Icepi Zero: same command, different device node, and (important) unlike the Colorlight i9 above, no `boot.json`/OpenSBI patching is needed at all:**

```bash
cd ~/openfpga/linux-on-litex-vexriscv
litex_term --images=images/boot.json /dev/ttyUSB0
```

Why this just works here where it doesn't for the i9: `images/boot_ram0.json`'s stock offsets (`opensbi.bin` at `main_ram`+15 MiB, `rootfs.cpio.gz` at +16 MiB -- see the table below) and the hardcoded `main_ram_base + 0x00f0_0000` OpenSBI `SoCRegion` in `litex/soc/cores/cpu/vexriscv_smp/core.py` both assume there's real SDRAM out to roughly 16.5 MiB. ULX3S and Icepi Zero both have 32 MiB (confirmed above), comfortably past that -- so the exact same "Making Linux actually fit" ordeal documented below for the i9's 8 MiB is specific to the i9 (and would equally apply to anything else under ~16.5 MiB, like Colorlight 5A-75x). No OpenSBI repatch, no custom `boot.json`, no `--rootfs=sdcard`/`nfs` detour -- the default `--rootfs=ram0` should carry a full RAM-based initramfs on both boards. **Confirmed (2026-08-27) for the Icepi Zero** -- see "Confirmed working: full Linux boot on real Icepi Zero hardware" earlier in this document for the full session, including one board-specific wrinkle: unlike DAPLink, the Icepi Zero's FT231X shares one USB device between programming and serial, so `litex_term` needs to be started *after* the bitstream load finishes (not listening across it) and catch the handshake via a `serialboot` typed at the idle `litex>` prompt rather than at reset.

**One more per-board gotcha worth flagging**: `images/boot.json`, `images/rv32.dtb`, and `images/opensbi.bin` are *not* namespaced by board -- `make.py --build` overwrites them in place every time (`combine_dtb()` copies `build/<board>/<board>.dtb` over `images/rv32.dtb` unconditionally). Building for Colorlight, then ULX3S, then Colorlight again means the last `--build` run's files are the ones sitting in `images/` -- there's no per-board `images/` subdirectory to switch between. If you're flipping between boards, either re-run `--build` for whichever board you're about to load, or copy `images/` aside per board yourself before switching.

## LiteX and Linux Files that get transfered to RAM

`images/boot.json` (built by `make.py --build` as a copy of `images/boot_<rootfs>.json`) tells `litex_term` four files and four RAM addresses to send them to. All four default addresses are offsets from `main_ram`'s base, `0x40000000`:

| File | Default address | What it is |
|---|---|---|
| `Image` | `0x40000000` (base + 0) | Raw Linux kernel, RISC-V `Image` format -- position-independent, runs from wherever it's loaded |
| `rv32.dtb` | `0x40ef0000` (base + 15.6 MiB) | Devicetree blob for this exact build's CSR addresses, peripherals, and RAM size |
| `opensbi.bin` | `0x40f00000` (base + 15 MiB) | M-mode firmware (OpenSBI) -- sets up the SBI runtime, then jumps into the kernel |
| `rootfs.cpio.gz` | `0x41000000` (base + 16 MiB) | Root filesystem, gzipped cpio archive, mounted as an in-RAM initramfs (`root=/dev/ram0`) |

**Why the defaults don't work on the i9 (or i5).** Type `mem_list` at the `litex>` BIOS prompt (or just read the boot-time log printed on every power-up) to see the real memory map:

```text
Region    Origin     End        Size
OPENSBI   0x40f00000 0x40f7ffff 0x80000
MAIN_RAM  0x40000000 0x407fffff 0x800000
```

`MAIN_RAM` is 8 MiB (`0x40000000`-`0x407fffff`), confirmed three independent ways: the BIOS's own boot log (`SDRAM: 8.0MiB`), `litex_boards`' source (the `EM638325`/`M12L64322A` SDRAM modules used for the i5/i9 are both 8 MiB, and there's no i9-specific override), and the vendor's own board doc (`M12L64322A 8MB SDRAM`). (An earlier revision of this document incorrectly said 32 MiB for the i9 -- corrected everywhere now.) But `boot_ram0.json`'s default addresses put `rv32.dtb`, `opensbi.bin`, and `rootfs.cpio.gz` at +15-16 MiB -- past the end of physical RAM entirely. Sending a file there fails with a serial frame error (`Got unknown reply 'b'E'' from the device, aborting`) because nothing is mapped on the Wishbone bus at that address -- only `Image`, loaded at offset 0, lands somewhere real. This is an i9/i5-only problem: ULX3S and Icepi Zero both have 32 MiB and never hit it. The fix is the next section.

**Using `litex_term` correctly, independent of address layout.** Two things trip people up every time:

1. **Only one program may hold the serial port.** `picocom` and `litex_term` racing to read the same `/dev/ttyACM0` split the incoming byte stream between them unpredictably -- always close `picocom` before starting `litex_term`.
2. **`litex_term` is passive.** It only starts an upload in the few seconds after the BIOS actively sends its `sL5DdSMmkekro` handshake string -- i.e. right at reset/power-up, or after typing `serialboot` at the `litex>` prompt (a BIOS command that re-runs the same handshake without a full SoC reset). If `litex_term` is started while the BIOS is already idle at the prompt, it has already missed that window and will wait forever with no error message. There's no `litex_term` flag that sends `serialboot`/`reboot` for you -- type it into `litex_term`'s own pass-through once you see the prompt echoed there.

`--serial-boot` doesn't help with either of these: it only auto-answers a BIOS boot-menu string (`"F7:    boot from serial"`) that doesn't exist in this LiteX version's BIOS. Catching the `sL5DdSMmkekro` handshake happens unconditionally whenever `--images`/`--kernel` is passed, regardless of that flag.

### Making Linux actually fit in the i9's real 8 MB SDRAM

**This section is i9/i5-specific.** ULX3S and Icepi Zero both have 32 MiB of RAM and never hit any of this -- skip to "Alternative way to build the Gateware" below if you're on one of those boards.

There are two ways to make Linux fit in 8 MiB, and both require source edits in two upstream repos (`litex`, `opensbi`) since neither is exposed as a `make.py` flag today:

- **Move the rootfs off RAM entirely** (SD card or NFS) -- the approach [kazkojima/colorlight-i5-tips](https://github.com/kazkojima/colorlight-i5-tips) documents for the sibling i5 board, and the one to reach for if you just want a working system quickly.
- **Build a kernel and rootfs small enough that everything, rootfs included, fits in RAM** -- what this section walks through. It goes further than kazkojima's approach: they explicitly didn't attempt a RAM-only rootfs ("due to the 8MB memory limit, it's difficult to put the root filesystem on the RAM like other boards... NFS or micro SD will be a good candidate"). This got as far as a **fully verified, correct OpenSBI boot**, but not a booting kernel -- read the "Known issue" at the end before starting, so you know what you're signing up for.

Every step below was run for real, on the physical i9, over `/dev/ttyACM0`. The addresses and file sizes are the exact ones this produced.

**Step 1 -- build a minimal kernel.** The stock kernel `Image` this repo ships is already too big once OpenSBI and a DTB also need to fit in the remaining space. Clone a fresh kernel and cross-compile with the *glibc* RISC-V toolchain (`riscv64-linux-gnu-`), not the bare-metal one used elsewhere in this document (`riscv64-unknown-elf-`) -- the kernel's vDSO build needs `-shared`, which the bare-metal linker refuses outright:

```bash
cd ~/openfpga
git clone https://github.com/litex-hub/linux --branch litex-rebase
cd linux
sudo apt install -y gcc-riscv64-linux-gnu   # skip if already installed

make ARCH=riscv CROSS_COMPILE=riscv64-linux-gnu- defconfig 32-bit.config
scripts/config --enable SERIAL_LITEUART --enable SERIAL_LITEUART_CONSOLE \
    --enable LITEX_SOC_CONTROLLER --enable BLK_DEV_INITRD --enable RD_GZIP \
    --enable CC_OPTIMIZE_FOR_SIZE
# Strip everything a headless, serial-only, single-purpose board doesn't need --
# this is the single biggest lever, and what gets Image from ~7.5 MB to ~5.7 MB:
scripts/config --disable DEBUG_INFO --disable DEBUG_KERNEL --disable KALLSYMS \
    --disable NET --disable SOUND --disable USB_SUPPORT --disable DRM --disable FB \
    --disable MMC --disable SCSI --disable ATA --disable EXT4_FS --disable BTRFS_FS \
    --disable NFS_FS --disable SECURITY --disable MODULES \
    --disable STRICT_KERNEL_RWX --disable STRICT_MODULE_RWX \
    --disable FTRACE --disable TRACING --disable CGROUPS --disable AUDIT \
    --disable PERF_EVENTS --disable KEXEC --disable SWAP --disable MISC_FILESYSTEMS
make ARCH=riscv CROSS_COMPILE=riscv64-linux-gnu- olddefconfig
make ARCH=riscv CROSS_COMPILE=riscv64-linux-gnu- -j$(nproc)

ls -l arch/riscv/boot/Image   # 5,977,600 bytes in this build
```

`STRICT_KERNEL_RWX` matters more than it looks: leaving it on forces huge-page-aligned gaps between kernel segments, which `objcopy -O binary` zero-pads across -- it alone was the difference between a 9 MB and a 26 MB `Image` while building this. If your `Image` comes out unexpectedly large, run `readelf -l vmlinux`: widely-spaced segment `PhysAddr` values mean this is happening.

**Step 2 -- cross-build musl libc for rv32.** There's no prebuilt musl package for this target, and a static glibc rootfs is too large to fit the remaining budget -- musl + static BusyBox is what actually gets under 8 MiB:

```bash
cd ~/openfpga
git clone git://git.musl-libc.org/musl musl-src
cd musl-src
CC=riscv64-linux-gnu-gcc CFLAGS="-march=rv32imac -mabi=ilp32" \
    ./configure --target=riscv32 --prefix=$HOME/openfpga/musl-install --disable-shared
make AR=riscv64-linux-gnu-ar RANLIB=riscv64-linux-gnu-ranlib -j$(nproc)
make AR=riscv64-linux-gnu-ar RANLIB=riscv64-linux-gnu-ranlib install
```

(`AR`/`RANLIB` need to be explicit -- the archiver name musl's `configure` auto-derives from `--target=riscv32`, `riscv32-ar`, doesn't exist on this system.) If the build fails on `SYS_nanosleep` undeclared in `src/time/clock_nanosleep.c`: RISC-V's syscall table never defined the legacy `SYS_nanosleep` (only `SYS_clock_nanosleep_time64`), and musl's fallback path references it unconditionally in otherwise-dead code. Wrap that fallback block in `#ifdef SYS_nanosleep` / `#endif` and rebuild.

**Step 3 -- cross-build a static BusyBox against musl.**

```bash
cd ~/openfpga
git clone https://git.busybox.net/busybox
cd busybox
make defconfig
sed -i 's/# CONFIG_STATIC is not set/CONFIG_STATIC=y/' .config
```

Disable two groups of applets that don't apply to this build and would otherwise chase down missing headers for no benefit: all networking applets (the kernel from Step 1 has `CONFIG_NET=n`, so `IFCONFIG`/`WGET`/`TELNETD`/etc. can't work anyway) and the console-tools applets plus `HWCLOCK` (`CHVT`, `LOADFONT`, `SETKEYCODES`, ... need `linux/vt.h`/`linux/kd.h`; `HWCLOCK` needs an RTC this board doesn't have) -- edit those to `is not set` in `.config`, or use `make menuconfig`.

musl's bundled headers are missing the UAPI headers those console-tools applets would have needed, and the Ubuntu `riscv64-linux-gnu` package only ships a 64-bit `libgcc.a` (BusyBox's final link needs a real rv32 one) -- two prep steps first:

```bash
# Real UAPI headers, generated straight from the kernel source cloned in Step 1:
cd ~/openfpga/linux
make ARCH=riscv INSTALL_HDR_PATH=$HOME/openfpga/linux-uapi-headers headers_install

# Bridge the bare-metal toolchain's rv32 libgcc/startup objects into the names
# riscv64-linux-gnu-gcc's hosted-Linux specs expect (crtbeginT.o/crtbeginS.o/
# crtendS.o/crtendT.o instead of the bare-metal crtbegin.o/crtend.o):
mkdir -p ~/openfpga/rv32-libgcc-bridge
BAREMETAL_LIBDIR=$(dirname "$(riscv64-unknown-elf-gcc -march=rv32imac -mabi=ilp32 -print-libgcc-file-name)")
ln -sf "$BAREMETAL_LIBDIR/crtbegin.o" ~/openfpga/rv32-libgcc-bridge/crtbeginT.o
ln -sf "$BAREMETAL_LIBDIR/crtbegin.o" ~/openfpga/rv32-libgcc-bridge/crtbeginS.o
ln -sf "$BAREMETAL_LIBDIR/crtend.o"   ~/openfpga/rv32-libgcc-bridge/crtendS.o
ln -sf "$BAREMETAL_LIBDIR/crtend.o"   ~/openfpga/rv32-libgcc-bridge/crtendT.o
ln -sf "$(riscv64-unknown-elf-gcc -march=rv32imac -mabi=ilp32 -print-libgcc-file-name)" \
    ~/openfpga/rv32-libgcc-bridge/libgcc.a
```

Now the BusyBox build itself:

```bash
cd ~/openfpga/busybox
make \
    CC="$HOME/openfpga/musl-install/bin/musl-gcc" \
    CFLAGS="-march=rv32imac -mabi=ilp32 -I$HOME/openfpga/linux-uapi-headers/include -B$HOME/openfpga/rv32-libgcc-bridge -Wl,-melf32lriscv" \
    LD="riscv64-linux-gnu-ld -m elf32lriscv" \
    -j$(nproc)
riscv64-linux-gnu-strip busybox_unstripped -o busybox
file busybox   # ELF 32-bit LSB executable, UCB RISC-V, statically linked, stripped
```

Both `-Wl,-melf32lriscv` (final `gcc`-driven link) and `-m elf32lriscv` on the raw `LD` (intermediate partial links) are needed -- drop either one and you get "target emulation elf64-littleriscv does not match elf32-littleriscv" at whichever stage is missing it.

**Step 4 -- build the rootfs image.** A minimal root directory, BusyBox's applet symlinks installed into it, one `/init` script, packed as a gzipped `cpio` archive (the format the kernel's initramfs code expects):

```bash
mkdir -p ~/openfpga/rootfs-root/{bin,sbin,etc,proc,sys,dev}
cp ~/openfpga/busybox/busybox ~/openfpga/rootfs-root/bin/
cd ~/openfpga/rootfs-root/bin
./busybox --install -s .
cd ..

cat > init <<'EOF'
#!/bin/sh
mount -t proc proc /proc
mount -t sysfs sysfs /sys
exec /bin/sh
EOF
chmod +x init

find . | cpio -o -H newc | gzip > ~/openfpga/i9-8mb-images/rootfs.cpio.gz
ls -l ~/openfpga/i9-8mb-images/rootfs.cpio.gz   # 721,148 bytes in this build
```

**Step 5 -- patch and build OpenSBI for the 8 MiB layout.** [kazkojima/colorlight-i5-tips](https://github.com/kazkojima/colorlight-i5-tips) already worked out where OpenSBI and the DTB need to live to fit under 8 MiB, for the sibling i5 board (identical 8 MiB SDRAM) -- reuse their addresses and patch directly:

```bash
cd ~/openfpga
git clone https://github.com/litex-hub/opensbi --branch 0.8-linux-on-litex-vexriscv
git clone https://github.com/kazkojima/colorlight-i5-tips
cd opensbi
patch -p1 < ../colorlight-i5-tips/linux/opensbi-config-fixmap.patch
```

The patch moves `FW_TEXT_START` from `0x40F00000` to `0x407C0000`, and `FW_JUMP_FDT_ADDR`/`FW_PAYLOAD_FDT_ADDR` from `0x40EF0000` to `0x40780000`, inside `platform/litex/vexriscv/config.mk` -- packing OpenSBI and the DTB into the last 512 KiB below the real 8 MiB ceiling instead of 15+ MiB out where nothing exists. Also worth checking `platform/litex/vexriscv/platform.c`'s `VEX_HART_COUNT` matches this build's actual `cpu_count` (`1`, for the default single-core `vexriscv_smp` build this document uses -- upstream's default of `8` is likely harmless here but not obviously correct):

```bash
sed -i 's/#define VEX_HART_COUNT 8/#define VEX_HART_COUNT 1/' platform/litex/vexriscv/platform.c
make CROSS_COMPILE=riscv64-unknown-elf- PLATFORM=litex/vexriscv -j$(nproc)

cp build/platform/litex/vexriscv/firmware/fw_jump.bin ~/openfpga/i9-8mb-images/opensbi.bin
ls -l ~/openfpga/i9-8mb-images/opensbi.bin   # 53,640 bytes
```

**Step 6 -- move LiteX's own OpenSBI region to match, and rebuild the gateware.** The OpenSBI address isn't just a `boot.json` number -- it's baked into the gateware itself, in `litex/soc/cores/cpu/vexriscv_smp/core.py`'s `add_soc_components()`:

```python
soc.bus.add_region("opensbi", SoCRegion(origin=self.mem_map["main_ram"] + 0x00f0_0000, size=0x8_0000, cached=True, linker=True))
```

Change `0x00f0_0000, size=0x8_0000` to `0x007c_0000, size=0x4_0000` to match Step 5, then rebuild the gateware exactly as in "Build the Gateware" above:

```bash
cd ~/openfpga/linux-on-litex-vexriscv
rm -rf build/colorlight_i5
./make.py --board=colorlight_i5 --revision=7.2 --build board=i9
```

**This file is shared by every board target in this document (ULX3S, Icepi Zero included) -- revert it to stock as soon as the build finishes**, so the next gateware build for any other board isn't silently using the wrong OpenSBI offset:

```bash
cd ~/openfpga/litex
git diff --stat litex/soc/cores/cpu/vexriscv_smp/core.py   # confirm it's the only file changed
git checkout -- litex/soc/cores/cpu/vexriscv_smp/core.py
```

**Step 7 -- generate a matching device tree with a real initrd address.** `make.py`'s own DTB generation (`soc_linux.py`'s `combine_dtb()`/`generate_dts()`) never overrides the default initrd start address (`+16 MiB` -- past our 8 MiB RAM entirely), and there's no CLI flag for it. Call the underlying tool directly instead, pointing the initrd at the real rootfs address and size from Step 4:

```bash
cd ~/openfpga/linux-on-litex-vexriscv
litex_json2dts_linux build/colorlight_i5/csr.json \
    --initrd-start=6291456 --initrd-size=721148 \
    > build/colorlight_i5/colorlight_i5.dts
dtc -O dtb -o ~/openfpga/i9-8mb-images/rv32.dtb build/colorlight_i5/colorlight_i5.dts
```

`--initrd-start=6291456` is `0x600000`, i.e. `main_ram` base + 6 MiB: below the `0x40780000` DTB/OpenSBI region from Step 5/6, above the ~5.7 MiB kernel `Image` from Step 1, with headroom on both sides. `--initrd-size` is Step 4's actual `rootfs.cpio.gz` byte count.

**Step 8 -- assemble `boot.json`.** Same four files as the table above, new addresses, packed against the real 8 MiB ceiling instead of spread across 16+ MiB:

```json
{
    "Image"          : "0x40000000",
    "rootfs.cpio.gz" : "0x40600000",
    "rv32.dtb"       : "0x40780000",
    "opensbi.bin"    : "0x407c0000"
}
```

**Key order matters, and it's undocumented:** `litex_term` jumps to whichever file's address is listed *last* in this JSON once every file is uploaded -- `opensbi.bin` must be the last key, or `litex_term` jumps straight into the rootfs or DTB instead of into OpenSBI. (Confirmed against the stock `images/boot_ram0.json` template, which also lists `opensbi.bin` last -- not a coincidence.)

**Step 9 -- flash the rebuilt gateware and boot.** Same `openFPGALoader` command as "Flash the bitstream" above, `-c cmsisdap` with no `-f` -- SRAM-only, nothing written to flash:

```bash
openFPGALoader -c cmsisdap ~/openfpga/linux-on-litex-vexriscv/build/colorlight_i5/gateware/colorlight_i5.bit

cd ~/openfpga/linux-on-litex-vexriscv
cp ~/openfpga/i9-8mb-images/{Image,rootfs.cpio.gz,rv32.dtb,opensbi.bin} images/
cp ~/openfpga/i9-8mb-images/boot.json images/boot.json   # the JSON from Step 8

# litex_term needs a real controlling TTY (fails with "Inappropriate ioctl for
# device" otherwise) and its writer thread dies the moment stdin hits EOF in a
# non-interactive shell -- a never-closing stdin pipe through `script` fixes both:
tail -f /dev/null | script -qc "litex_term /dev/ttyACM0 --images=images/boot.json" litex_term.log
```

With that running and nothing else holding the port, type `serialboot` at the `litex>` BIOS prompt (or power-cycle the board) to trigger the handshake and start the upload.

**Confirmed working, on real hardware:** all four files upload with no frame errors, `litex_term` reports `Executing booted program at 0x407c0000` (OpenSBI's address -- correct, per the key-order rule in Step 8), and OpenSBI prints its full banner over the same serial link: platform name, HART count, PMP count, firmware base/size -- immediately before executing `mret` into the kernel.

**Known issue: the kernel never starts running.** After OpenSBI's `mret`, there is no further console output, and the CPU does not appear to execute even its first instruction at `0x40000000` -- confirmed directly by temporarily replacing the kernel's real entry point with an LED-toggle loop as the literal first instructions of `_start` in `arch/riscv/kernel/head.S` (ahead of any of the normal `CONFIG_EFI`/header code) and reflashing: the LED never changed from its default idle blink pattern. Ruled out so far, with direct evidence, none of it the actual fix:

- **HART count mismatch** between OpenSBI's `VEX_HART_COUNT` and the SoC's real `cpu_count=1` -- fixed in Step 5, no change.
- **Instruction-cache coherency** after OpenSBI writes/jumps -- added an explicit `fence.i` immediately before the `mret` in OpenSBI's `sbi_hart_switch_mode()` -- no change.
- **Kernel entry-path specifics** (the `CONFIG_EFI` conditional at the top of `_start`, compressed-instruction decoding, etc.) -- bypassed entirely by the literal-first-instruction LED test above, which sits before any of that code -- no change.
- **OpenSBI's generic PMP setup denying S-mode access to RAM** -- read through OpenSBI's PMP dump output and setup code; it appears to correctly grant full access. This weakens the hypothesis but doesn't fully eliminate it.

Root cause is unresolved at the source level. The next real diagnostic step would be JTAG/GDB visibility into the CPU's actual program counter and register state at the moment of the jump -- but VexRiscv's debug port is never wired to a pin the onboard DAPLink can reach for this board (`add_jtag()` is never called anywhere in `colorlight_i5.py` or its platform file); getting there would mean new gateware engineering (routing the debug signals out through the ECP5's `JTAGG` primitive), which is out of scope for this document. **No full Linux boot was achieved on real i9 hardware.** The furthest confirmed point is a fully correct OpenSBI run, ending in a verified-correct jump to the kernel's entry address, after which the kernel does not visibly execute.

**Reconsidered hypothesis, added later (2026-08-22), not present in the original root-cause list above: a dead serial link, not a dead CPU.** Much later in this document (see the PRBS31 section's "`<DAPLink:Overflow>` (2026-08-22)" note), this exact DAPLink probe was found to reproducibly corrupt or kill its own USB-serial bridge under a burst of console output -- confirmed independently with two unrelated terminal programs, and confirmed to be a property of the probe/connection itself, not of any particular gateware. That note was written without initially remembering this section, but the symptom described here -- verbose, successful OpenSBI output (platform name, HART count, PMP dump, firmware base/size) immediately followed by **total silence**, taken at the time as evidence "the kernel never executes even its first instruction" -- is *exactly* the signature a DAPLink overflow produces: a burst of legitimate text right up to the point of failure, then nothing, with no error surfaced to the user because the link died rather than the program. None of the four things ruled out above (HART count, i-cache coherency, entry-path specifics, PMP setup) actually tested for this, because the possibility wasn't known yet. **This is a real, unproven-but-plausible alternative explanation for the whole "kernel never starts running" mystery, worth revisiting before any further RTL-level debugging if this section is picked back up again:** the LED-toggle-at-`_start` test still stands as evidence *something* was wrong (a dead link wouldn't explain an LED that never lights), but it doesn't rule out a link failure happening independently, close in time, and being mistaken for confirmation of the wrong theory. Cheap thing to check first: re-run this exact boot with the console captured via two independent terminal tools simultaneously (or with a fresh USB replug immediately beforehand, per the mitigation that worked for the DAPLink overflow elsewhere), and see whether the kernel's own early console output (`printk`, before framebuffer/consoles are up) appears when the link survives.

All artifacts from this attempt (`Image`, `opensbi.bin`, `rootfs.cpio.gz`, `rv32.dtb`, `boot.json`) are kept in `~/openfpga/i9-8mb-images/` for anyone picking this back up.

## Alternative way to build the Gateware for the Colorlight i9 (ignorable)

"Gateware" is the FPGA-world term for what "firmware" is to a microcontroller: the compiled digital logic design that configures the FPGA's LUTs/routing/BRAM (the `.bit` file), as opposed to software that runs on a fixed CPU. Everything under "Build the Gateware" above (`make.py --build`) is already building gateware -- this section isn't a different concept, it's a different *path* to build it.

This command invokes `litex_boards.targets.colorlight_i5` directly, instead of going through `linux-on-litex-vexriscv/make.py`. `make.py`'s `SoCLinux` (in `linux-on-litex-vexriscv/soc_linux.py`) is a thin Linux-oriented wrapper *on top of* this exact same `litex_boards.targets.colorlight_i5.BaseSoC` class -- it adds the Linux-tailored bits (board-specific `soc_kwargs` defaults, `images/boot.json`-compatible layout, buildroot/rootfs plumbing) but the underlying gateware-building call (`Builder(soc, ...).build()`) is identical either way. So this isn't an older or alternate way of building -- it's the lower-level primitive that `make.py` itself is built on, useful if you want a plain LiteX SoC without any of the Linux-specific extras.

One real difference worth calling out: unlike `make.py`, `--board` here is a genuine, ordinary argparse flag (`parser.add_target_argument("--board", default="i5", ...)` in `litex_boards/targets/colorlight_i5.py`) -- there's no naming collision with a `--board=colorlight_i5` target-selector flag like make.py has, so no `board=i9`-style REMAINDER workaround is needed; `--board=i9 --revision=7.2` below works exactly as written.

Does `make.py` above properly handle the DM/byte-mask issue? Yes, silently: `linux-on-litex-vexriscv/boards.py`'s `Colorlight_i5.soc_kwargs = {"l2_size": 2048}` (comment: "Use Wishbone and L2 for memory accesses"), and `make.py`'s own logic auto-forces `args.with_wishbone_memory = True` whenever `l2_size != 0` -- so the earlier `make.py --build board=i9` command in this doc got the same Wishbone-memory fix automatically, even without ever passing `--with-wishbone-memory` on the command line. This raw `litex_boards.targets.colorlight_i5` path has no such auto-default (`BaseSoC` just does `l2_cache_size = kwargs.get("l2_size", 8192)` with no forcing logic), so here you must pass `--with-wishbone-memory` explicitly yourself, which the command below already does. (`--with-wishbone-memory` itself isn't a colorlight_i5-specific flag -- it's added generically by the `vexriscv_smp` CPU class whenever `--cpu-type=vexriscv_smp` is selected, in `litex/soc/cores/cpu/vexriscv_smp/core.py`.)

Compile the gateware. This process calls Yosys for synthesis and nextpnr to map the design onto the i9's ECP5-45F chip architecture.

Because the i9 shares its physical board design with the i5 module, use the `colorlight_i5` target script but pass `--board=i9 --revision=7.2` to select the larger logic capacity and correct flash settings:

```bash
# The Colorlight i9's 32-bit SDRAM PHY does not expose byte-mask (DM) pads, which vexriscv_smp
# requires for its native LiteDRAM path. The fix is --with-wishbone-memory, which routes main
# RAM through the Wishbone/L2 bus writing full 32-bit words, bypassing the byte-mask issue.
python3 -m litex_boards.targets.colorlight_i5 --board=i9 --revision=7.2 --cpu-type=vexriscv_smp --with-wishbone-memory --build
```

**ULX3S and Icepi Zero equivalents.** Both boards route DQM/byte-mask pins properly (confirmed above: `dm` pins present in both platform files' `"sdram"` connector, 2 pins each), so `--with-wishbone-memory` is *optional* here, not required for correctness the way it is for the i9 -- VexRiscv's native LiteDRAM path can issue sub-word writes safely on either board. Omitting it gets full native write throughput; including it is harmless (same read-modify-write tradeoff described above) and matches what `make.py --build` does automatically behind the scenes via its `l2_size != 0` auto-forcing logic. Neither target script has a `--board` flag at all (unlike `colorlight_i5.py` -- there's no i5/i9-style physical sub-variant to select), so board size selection is just the ordinary `--device` flag, no REMAINDER-token trick needed:

```bash
# ULX3S (85F). --with-wishbone-memory omitted -- DQM is routed, native LiteDRAM path is safe:
python3 -m litex_boards.targets.radiona_ulx3s --device=LFE5U-85F --cpu-type=vexriscv_smp --build

# Icepi Zero. Device already defaults to LFE5U-25F, the only real chip size for this board:
python3 -m litex_boards.targets.icepi_zero --cpu-type=vexriscv_smp --build
```


# Simple LFSR in Verilog (no linux)

This tutorial guides you through implementing a PRBS7 (Pseudo-Random Binary Sequence) generator using a Linear Feedback Shift Register (LFSR) on the Colorlight i9 (V7.2) development board.

**This section is Colorlight i9-specific; the Icepi Zero port is confirmed working below ("Icepi Zero port — confirmed working on real hardware").** ULX3S remains unadapted. Unlike the LiteX/`make.py` workflow above, this is raw Verilog with a hand-written `.lpf` constraints file (below) tied directly to the i9's exact pin-to-signal mapping (`P3`, `K18`, `L2`) -- porting it to ULX3S or Icepi Zero means writing a new `.lpf` with *their* clock/LED/PMOD pin names, which requires each board's own pinout reference (`litex_boards/litex_boards/platforms/radiona_ulx3s.py` and `.../platforms/icepi_zero.py` are the canonical source for those, same role `colorlight_i5.py` plays below for the i9) -- not something to guess at without checking the actual platform file first, the same standard the rest of this document holds itself to.

* Board: Colorlight i9 v7.2 (Lattice ECP5 LFE5U-45F-6BG381C) mounted on the standard Ext-Board breakout.
* Onboard Clock: 25 MHz crystal oscillator routed to FPGA pin P3.
* High-Speed Output Pin: PMOD 1, Pin 1 routed to FPGA pin K18.
* Onboard Diagnostic LED: Green LED D2 routed to FPGA pin L2.
* Toolchain Required: yosys, nextpnr-ecp5, ecppack (from Project Trellis), and openFPGALoader.

Verilog: `prbs7.v`

```verilog
module prbs7 (
    input  wire clk,
    output wire prbs_out,
    output wire led
);

    // 7-bit internal shift register initialized to all 1s (non-zero seed)
    // FPGAs honor inline initial values during configuration power-up.
    reg [6:0] shift_reg = 7'h7F; 

    always @(posedge clk) begin
        // Polynomial: x^7 + x^6 + 1 
        // 0-indexed representation maps x^7 to index 6 and x^6 to index 5
        shift_reg <= {shift_reg[5:0], shift_reg[6] ^ shift_reg[5]};
    end

    // Output a fresh bit at the full rate of the clock every cycle
    assign prbs_out = shift_reg[6];
    
    // Mirror to the onboard LED (it will look constantly dim due to high speed)
    assign led = shift_reg[6];

endmodule
```

Constraints: `colorlight_i9.lpf`

```
# Onboard 25MHz Oscillator
LOCATE COMP "clk" SITE "P3";
IOBUF PORT "clk" IO_TYPE=LVCMOS33;
FREQUENCY PORT "clk" 25.0 MHz;

# Onboard Green LED D2
LOCATE COMP "led" SITE "L2";
IOBUF PORT "led" IO_TYPE=LVCMOS33;

# High-Speed Output Pin (PMOD 1, Pin 1)
LOCATE COMP "prbs_out" SITE "K18";
IOBUF PORT "prbs_out" IO_TYPE=LVCMOS33;
```

## What the .lpf file is doing — pins on PCB → HDL → Linux

The `.lpf` (Lattice Physical constraints File) is the complete answer to "how does what is connected to each FPGA pin get stored and used?" It bridges three worlds:

1. **HDL port names** (`clk`, `led`, `prbs_out`): purely logical signals with no physical meaning by themselves. They appear in the Verilog `module` port list.
2. **Package ball/pin site names** (`"P3"`, `"L2"`, `"K18"`): physical copper BGA pads on the ECP5 package, cross-referenced between Lattice's package datasheet and the Colorlight i9 schematic. Finding which site corresponds to which ball is the "what is connected to each FPGA pin" question for this board.
3. **Electrical properties** — `IO_TYPE=LVCMOS33` selects the 3.3 V LVCMOS I/O standard. `nextpnr` uses this to pick the correct I/O buffer primitive (`IFS1P3BX`, `OFS1P3BX`, etc.) from the ECP5 I/O tile library. Other legal values include `LVCMOS18`, `LVCMOS25`, `LVDS33`, `SSTL135D_I`, and others depending on the bank's power supply.

The `FREQUENCY PORT "clk" 25.0 MHz;` line is a **timing constraint**, not electrical. It tells nextpnr's static timing analysis what clock rate to optimize for. If logic on the critical path can't resolve within 40 ns, nextpnr reports negative slack and refuses to emit a bitstream.

**Drive strength and slew rate** are controlled by additional .lpf keywords not used here: `DRIVE=8` (mA, typically 4/8/12/16) and `SLEWRATE=FAST` or `SLEWRATE=SLOW`. The defaults (8 mA / SLOW) are fine for LEDs and low-speed signals. For LVDS pairs, DDR data buses, or any signal you will probe with an oscilloscope at high speed, you tune these explicitly in the .lpf.

**Clocking inside the FPGA:** The 25 MHz oscillator enters via a global clock input pin and travels on a dedicated low-skew global clock network that reaches every flip-flop on the chip. For higher frequencies (e.g., 125 MHz for Ethernet), you instantiate an `EHXPLLL` PLL primitive — either directly in HDL or, in LiteX, by calling `self.crg = _CRG(platform, sys_clk_freq)` in the SoC Python class. The PLL multiplies/divides the reference to produce multiple domain clocks (sys, fast, idelay, etc.) that feed separate clock trees.

**In the LiteX world you never write an .lpf by hand.** The `litex_boards/platforms/colorlight_i5.py` file programmatically defines every pin, its site, I/O type, and available connectors as Python objects. When LiteX builds the SoC, it synthesizes your design, calls nextpnr, and generates the .lpf automatically from those Python pin definitions. To understand or modify any pin assignment for the Colorlight i9, `colorlight_i5.py` is the canonical place to look and edit.

```bash
# 1. Synthesize with Yosys  --  concrete architecture netlist format (.json) mapped for the ECP5 architecture.
yosys -p "synth_ecp5 -top prbs7 -json prbs7.json" prbs7.v
# 2. Place & Route with nextpnr-ecp5 -- assigns the netlist components onto the physical components inside the ECP5-45F chip while satisfying the 25 MHz timing constraints.
nextpnr-ecp5 --45k --package CABGA381 --json prbs7.json --lpf colorlight_i9.lpf --textcfg prbs7.config
# 3. Compress and Pack with ecppack -- into the binary configuration bitstream format needed by the hardware
ecppack --compress prbs7.config prbs7.bit
```

**Visual inspection — synthesis:** To see a schematic of what Yosys inferred from the HDL, replace the command above with `yosys -p "synth_ecp5 -top prbs7 -json prbs7.json; show" prbs7.v`. This opens a Graphviz-rendered gate-level netlist view — flip-flops, LUT equations, MUX trees — in an xdot window. Useful for small modules; for a full SoC the graph is too large to be legible.

### Icepi Zero port: PRBS7 LFSR — confirmed working on real hardware (2026-08-27)

The line above ("hasn't been adapted for ULX3S/Icepi Zero") is now resolved for the Icepi Zero. Two changes from the i9 version, both read straight from `litex_boards/litex_boards/platforms/icepi_zero.py` per this document's own standard of checking the actual platform file rather than guessing: the onboard oscillator is **50 MHz** here (`clk50`, site `M1`), not 25 MHz, and there's no PMOD high-speed output pin to wire up at all (Icepi Zero has none — the `prbs_out` port from the i9 version is simply dropped; the LFSR still runs, it's just not brought out to an external pin). The onboard LED used is `user_led` index 0, site `E13` — one of **5** real, populated white LEDs (`E13`, `D14`, `E12`, `C13`, `D13`), confirmed on real hardware by writing directly to the LiteX BIOS's `leds` CSR register (`leds 31` with an already-built Linux gateware lit all 5). That same test also settled the polarity question: **these LEDs are active-HIGH** (`leds 31` = all on), the opposite of the Colorlight i9's active-low LEDs, so — unlike the i9's raw-Verilog and PMOD demos elsewhere in this document — no `assign led = ~value` inversion is needed anywhere in the Icepi Zero versions of these tutorials.

Verilog: `prbs7.v` (identical LFSR logic to the i9 version above, just a narrower port list — no `prbs_out`):

```verilog
module prbs7 (
    input  wire clk,
    output wire led
);
    reg [6:0] shift_reg = 7'h7F;
    always @(posedge clk) begin
        shift_reg <= {shift_reg[5:0], shift_reg[6] ^ shift_reg[5]};
    end
    assign led = shift_reg[6];  // active-high, no invert needed (see above)
endmodule
```

Constraints: `icepi_zero.lpf`

```
# Onboard 50MHz Oscillator
LOCATE COMP "clk" SITE "M1";
IOBUF PORT "clk" IO_TYPE=LVCMOS33;
FREQUENCY PORT "clk" 50.0 MHz;

# Onboard white LED 0 (of 5), user_led index 0 in litex_boards' icepi_zero.py
LOCATE COMP "led" SITE "E13";
IOBUF PORT "led" IO_TYPE=LVCMOS33;
```

Build and flash — same three-stage Yosys/nextpnr/ecppack/openFPGALoader pipeline as the i9 version, just the chip parameters and `-b` board profile swapped (`LFE5U-25F-6BG256C` → `--25k --package CABGA256 --speed 6`, confirmed against the same string the SoC build banner reports elsewhere in this document):

```bash
yosys -p "synth_ecp5 -top prbs7 -json prbs7.json" prbs7.v
nextpnr-ecp5 --25k --package CABGA256 --speed 6 --json prbs7.json --lpf icepi_zero.lpf --textcfg prbs7.config
ecppack --compress prbs7.config prbs7.bit
openFPGALoader -b icepi-zero prbs7.bit
```

**Confirmed working:** `nextpnr-ecp5` reported `Max frequency for clock '$glbnet$clk$TRELLIS_IO_IN': 610.50 MHz (PASS at 50.00 MHz)` — trivially met, as expected for a 7-bit shift register. After flashing, one white LED (the one farthest from the board edge, at site `E13`) lit up dim and steady — exactly the expected look for a single bit toggling at 50 MHz (persistence of vision averages it to a constant dim glow, not a visible blink), the same behavior the i9 version's own comment predicted. The other 4 LEDs stayed off, as expected since nothing else in this minimal design drives them.

**Visual inspection — place and route:** Add `--gui` to the nextpnr command to open nextpnr's graphical device viewer after place-and-route completes:

```bash
nextpnr-ecp5 --45k --package CABGA381 --json prbs7.json --lpf colorlight_i9.lpf --textcfg prbs7.config --gui
```

The viewer shows the ECP5 device fabric with your placed LUTs and routing overlaid. Click any cell or wire to highlight it. For the PRBS7 design, placement finishes instantly — use `--gui` to explore how seven flip-flops and one XOR gate look on a 45K-LUT device before flashing. For larger designs, the routing density view makes congestion hotspots obvious.

Flash to the board. The Colorlight extension board features an onboard STM32 microcontroller running DAPLink firmware. openFPGALoader natively supports this via its CMSIS-DAP driver.

Into volatile SRAM memory for testing:

```bash
openFPGALoader -b colorlight-i9 prbs7.bit
```

Into non-volatile SPI flash memory with `-f`:

```bash
openFPGALoader -b colorlight-i9 -f prbs7.bit
```

Checks:

1. Visual: green LED (D2) will instantly glow with roughly 50% luminosity because it is flipping at 25 MHz
2. Oscilloscope: to pin K18 (PMOD 1, Pin 1). Bits update exactly every 40 ns. The total sequence pattern length is 2^7-1=127 bits long, meaning you will see the entire bit configuration pattern repeat identically every 5.08 μs.

Optional Simulation Testbench: `prbs7_tb.v`

```verilog
`timescale 1ns / 1ps

module prbs7_tb;

    // 1. Declare local signals to connect to the Device Under Test (DUT)
    reg clk;
    wire prbs_out;
    wire led;

    // 2. Instantiate the PRBS7 module
    prbs7 dut (
        .clk(clk),
        .prbs_out(prbs_out),
        .led(led)
    );

    // 3. Generate a 25 MHz Clock
    // A 25 MHz clock has a period of 40ns. Toggling every 20ns creates this frequency.
    always begin
        #20 clk = ~clk;
    end

    // 4. Control the Simulation Flow
    initial begin
        // Initialize the clock
        clk = 0;

        // Instruct the simulator to record signal transitions to a VCD file
        $dumpfile("prbs7_tb.vcd");
        $dumpvars(0, prbs7_tb);

        // Run the simulation long enough to see the PRBS7 sequence repeat.
        // The sequence length is 127 cycles. 127 * 40ns = 5080ns.
        // We will run for 6000ns to see the loop start over.
        #6000;

        // Stop the simulator
        $display("Simulation finished successfully!");
        $finish;
    end

endmodule
```

Icarus Verilog (`iverilog`) acts like an interpreter: it models all four logic states (0, 1, X=unknown, Z=high-impedance) with time delays, making it accurate for undefined-state propagation and bus conflicts. Verilator acts like a compiler: it converts synthesizable Verilog into C++ and compiles that to a native binary. Verilator is 10–100× faster for large designs but cannot model X/Z states or delays — it is primarily for cycle-accurate functional simulation of RTL, not for timing verification.

```bash
# 1. Compile the testbench and implementation file into a simulation object
iverilog -o prbs7_sim prbs7_tb.v prbs7.v
# 2. Run the simulation using the vvp runtime engine
vvp prbs7_sim
# 3. View the Waveform in GTKWave
gtkwave prbs7_tb.vcd   # display stuff on the left and zoom way out
```

GTKWave is the universal waveform viewer for this entire toolchain. It reads `.vcd` files from Icarus Verilog (as here), from Verilator-based simulation, from LiteX full-system simulation (`./sim.py --trace`), and from LiteScope hardware captures on the live FPGA. In all cases the workflow is identical: run the simulation or capture, open the `.vcd` in GTKWave, drag signals from the signal list on the left into the wave window, and zoom to the region of interest.

Note: Two main differences between System Verilog and classic Verilog:

* The `logic` Data Type replaces reg and wire: In classic Verilog, deciding between `reg` and `wire` is a major point of confusion for beginners. You had to use `reg` if a signal was driven inside an `always` block, and `wire` if it was driven by an `assign` statement. SystemVerilog resolves this by introducing `logic`. It can be used for both sequential blocks and continuous assignments. The toolchain automatically infers whether it should compile down to a physical flip-flop or a copper wire mesh.
* `always_ff` replaces `always`: Traditional Verilog uses a generic `always @(posedge clk)` block. If you accidentally write combinatorial logic inside it, or forget a clock edge, classic Verilog will compile it anyway and create messy simulation mismatches. SystemVerilog provides `always_ff`. This explicitly tells your compiler (Yosys) and simulator (Icarus): "This block must compile into sequential flip-flops." If you make a typo that accidentally creates a hardware latch or combinational loop, the compiler will instantly halt and throw a compile-time error.

SystemVerilog: `prbs7.sv`

```verilog
module prbs7 (
    input  logic clk,
    output logic prbs_out,
    output logic led
);

    // 7-bit internal shift register initialized to all 1s
    logic [6:0] shift_reg = 7'h7F; 

    // 'always_ff' explicitly enforces synchronous sequential flip-flop logic
    always_ff @(posedge clk) begin
        // Polynomial: x^7 + x^6 + 1
        shift_reg <= {shift_reg[5:0], shift_reg[6] ^ shift_reg[5]};
    end

    // Continuous assignment using modern 'logic' data type
    assign prbs_out = shift_reg[6];
    assign led      = shift_reg[6];

endmodule
```

TestBench: `prbs7_tb.sv`

```verilog
`timescale 1ns / 1ps

module prbs7_tb;

    // 1. Declare local testbench signals using the modern 'logic' type
    logic clk;
    logic prbs_out;
    logic led;

    // 2. Instantiate the Device Under Test (DUT) using the Implicit Port Connection
    prbs7 dut (.*);

    // 3. Generate a 25 MHz Clock (Period = 40ns)
    always begin
        #20 clk = ~clk;
    end

    // 4. Verification Test Control Flow
    initial begin
        // Initialize clock
        clk = 0;

        // Waveform capture setup
        $dumpfile("prbs7_tb.vcd");
        $dumpvars(0, prbs7_tb);

        // Run the simulation for 6000ns to see the 127-cycle loop repeat
        #6000;

        $display("SystemVerilog simulation completed smoothly!");
        $finish;
    end

endmodule
```

Simulate it. Pass the -g2012 flag to iverilog to turn on the IEEE 1800-2012 SystemVerilog engine:

```bash
iverilog -g2012 -o prbs7_sv_sim prbs7_tb.sv prbs7.sv
vvp prbs7_sv_sim
gtkwave prbs7_tb.vcd
```

Yosys: Use the -sv flag to ensure it reads the always_ff blocks and logic assignments correctly:

```bash
yosys -p "read_verilog -sv prbs7.sv; synth_ecp5 -top prbs7 -json prbs7.json"
```

# Verilog-only GPIO demo: 8 LEDs + 4 buttons + 4 switches (no LiteX, no Linux)

This extends the PRBS7 tutorial above with actual switch/button *inputs*, not just an oscillator-driven output, and fills in the constraint file this document was previously missing for a two-PMOD hardware setup: an 8-LED PMOD and a 4-button + 4-switch PMOD plugged into the Colorlight i9 extension board.

For a picture of the physical pinout, scroll down on <https://github.com/wuxx/Colorlight-FPGA-Projects>. We will use P6. If the USB port is at the bottom, P6 is to the right, pointing down. P6 is designed to acomodate two 3.3V PMOD connectors, one all the way to the left and one all the way to the right, with two columns (4 pins) in between, remaining unconnected.

**Which physical header, and why:** checked directly against `litex_boards/litex_boards/platforms/colorlight_i5.py`'s `_connectors_v7_2` list (the same file the LiteX flow uses to auto-generate pin constraints, see "What the .lpf file is doing" above) rather than guessing pin numbers. Extension-board header **P6** breaks out two independent 8-signal PMOD-compatible connectors, called `pmodk` and `pmodl` in that file:

* `pmodk` = `R3 M4 L5 J16 N4 L4 P16 J18` — P6 next to the USB — all 8 sites are real, populated pins, and none of them are reused elsewhere on the board (checked by grepping the platform file). Use this one for the **8-LED PMOD**.
* `pmodl` = `R1 U1 W1 M1 T1 Y2 V1 N2` — P6, farthest away from the USB — also all 8 real, also unused elsewhere. Use this one for the **4-button + 4-switch PMOD**. Which of these 8 pins are buttons and which are switches (and in what order) is *not* a simple "first 4, last 4" split — this raw connector-pin order turned out to interleave the two groups when tested on real hardware, same as the LED PMOD; see the empirically-verified `.lpf` below and the explanation that follows it, not this raw pin list.

Other candidate connectors on this board have problems that make them worse choices for this demo: `pmodc` reuses site `L2` (the onboard LED) and `K18` (the `cpu_reset_n` button net) — collisions you'd rather not discover after wiring a PMOD in; `pmodh` only has 6 real sites (two are `-`, i.e. not connected) so it can't carry 8 signals; `pmodi`/`pmodj` overlap the default UART pins (`F4`, `J17`, `H18`). `pmodk`/`pmodl` are the clean pair.

Verilog: `led_button_demo.v`

```verilog
module led_button_demo (
    input  wire       clk,    // 25 MHz onboard oscillator, FPGA pin P3
    input  wire [3:0] btn,    // 4-button PMOD, bit-position order (verified on hardware,
                              // fully commented in the .lpf below): btn[3] = leftmost
                              // physical button (MSB) .. btn[0] = rightmost (LSB) -- NOT
                              // English reading order. Idle-high/actuated-low.
    input  wire [3:0] sw,     // 4-switch PMOD, same bit-position convention as btn[] above:
                              // sw[3] = leftmost physical switch (MSB) .. sw[0] = rightmost
                              // (LSB). Idle-high/actuated-low.
    output wire [7:0] led     // 8-LED PMOD, active-low (a LOW output lights the LED).
                              // led[7] = leftmost physical LED (MSB) .. led[0] = rightmost
                              // (LSB) -- i.e. any 8-bit value assigned to `led` (before the
                              // active-low invert below) reads left-to-right exactly like
                              // ordinary binary notation. This is NOT pmodk's raw
                              // connector-pin order; see the .lpf below and the empirical
                              // note that follows it for why and how this was determined
                              // on real hardware, and why the bit order was then mirrored.
);

    // Buttons and switches are external, asynchronous to `clk` -- a 2-stage
    // synchronizer avoids metastability, the same job Migen's MultiReg()
    // does automatically for LiteX's GPIOIn peripheral (see below).
    reg [3:0] btn_s0 = 4'h0, btn_s1 = 4'h0;
    reg [3:0] sw_s0  = 4'h0, sw_s1  = 4'h0;
    always @(posedge clk) begin
        btn_s0 <= btn; btn_s1 <= btn_s0;
        sw_s0  <= sw;  sw_s1  <= sw_s0;
    end

    // Buttons are idle-high/actuated-low (see the port comments above), so
    // invert to get the natural "1 = held down" sense used below.
    wire       reverse = ~btn_s1[0]; // held: reverse chase direction
    wire       pause   = ~btn_s1[1]; // held: freeze the chase
    // Switches are used as a raw 4-bit magnitude, not individual on/off flags,
    // so no inversion is needed here: "up" already reads as 1, and since "up"
    // is the more-1s state, more switches up naturally means a higher (faster)
    // value under this board's own idle-high wiring.
    wire [3:0] speed   = sw_s1;     // 0 = slowest (all down), 15 = fastest (all up)

    // Free-running prescaler. Selecting a higher bit with `speed` produces
    // a slower visible rate; the +12 offset just keeps the whole range
    // human-visible instead of either instant or glacial.
    reg [26:0] prescaler = 27'h0;
    always @(posedge clk)
        prescaler <= prescaler + 1'b1;

    wire tick = prescaler[speed + 5'd12];

    // Edge-detect: turn the tick level into a single-cycle step pulse.
    reg tick_d = 1'b0;
    always @(posedge clk) tick_d <= tick;
    wire step = tick & ~tick_d;

    reg [7:0] pos = 8'h01;
    always @(posedge clk) begin
        if (!pause && step)
            pos <= reverse ? {pos[0], pos[7:1]} : {pos[6:0], pos[7]};
    end

    assign led = ~pos;  // active-low PMOD: invert so the set bit lights the LED

endmodule
```

Constraints: `colorlight_i9_gpio_demo.lpf`

```
# Onboard 25 MHz oscillator
LOCATE COMP "clk" SITE "P3";
IOBUF PORT "clk" IO_TYPE=LVCMOS33;
FREQUENCY PORT "clk" 25.0 MHz;

# 8-LED PMOD -- extension-board header P6, next to the USB connector ("pmodk").
# Sites below are NOT pmodk's raw connector-pin order (R3 M4 L5 J16 N4 L4 P16 J18) --
# they're the order empirically verified on real hardware to light physical
# positions left-to-right, matching the silkscreen text below the LEDs, and then
# deliberately mirrored into bit-position order so a raw 8-bit value assigned to
# `led` reads left-to-right like ordinary binary notation. See the note after
# this .lpf for how/why this had to be reverse-engineered.
#   led[7] = LEFTMOST  physical LED (bit 7 / MSB), site J18.
#   led[0] = RIGHTMOST physical LED (bit 0 / LSB), site R3.
#   ACTIVE-LOW: this module sinks current to light an LED, so a pin driven LOW
#   (0) turns its LED ON, and HIGH (1) turns it OFF -- backwards from the
#   naive "1 = on" assumption. `assign led = ~value;` in the Verilog above
#   undoes this, so `value`'s own bits read normally (1 = on) everywhere else.
LOCATE COMP "led[7]" SITE "J18";
LOCATE COMP "led[6]" SITE "J16";
LOCATE COMP "led[5]" SITE "P16";
LOCATE COMP "led[4]" SITE "L5";
LOCATE COMP "led[3]" SITE "L4";
LOCATE COMP "led[2]" SITE "M4";
LOCATE COMP "led[1]" SITE "N4";
LOCATE COMP "led[0]" SITE "R3";
IOBUF PORT "led[7]" IO_TYPE=LVCMOS33;
IOBUF PORT "led[6]" IO_TYPE=LVCMOS33;
IOBUF PORT "led[5]" IO_TYPE=LVCMOS33;
IOBUF PORT "led[4]" IO_TYPE=LVCMOS33;
IOBUF PORT "led[3]" IO_TYPE=LVCMOS33;
IOBUF PORT "led[2]" IO_TYPE=LVCMOS33;
IOBUF PORT "led[1]" IO_TYPE=LVCMOS33;
IOBUF PORT "led[0]" IO_TYPE=LVCMOS33;

# 4-button + 4-switch PMOD -- extension-board header P6, farthest from the USB
# connector ("pmodl"). Sites below are NOT pmodl's raw connector-pin order --
# they're empirically verified, and (like the LEDs above) deliberately ordered
# bit-position-style rather than English reading order: index 3 is the
# LEFTMOST physical control (MSB), matching led[]'s convention, so a button
# or switch's raw connector.pin order (R1 U1 W1 M1 / T1 Y2 V1 N2) shouldn't be
# assumed to say anything about left-to-right physical layout either.
#   btn[3] = LEFTMOST  physical button (bit 3 / MSB), site N2.
#   btn[0] = RIGHTMOST physical button (bit 0 / LSB), site R1.
#   sw[3]  = LEFTMOST  physical switch (bit 3 / MSB), site M1.
#   sw[0]  = RIGHTMOST physical switch (bit 0 / LSB), site T1.
#   IDLE-HIGH / ACTUATED-LOW (opposite of the typical Digilent PmodBTN/PmodSWT
#   assumption -- confirmed on this specific module): an unpressed button or
#   a switch left "up" reads 1 on its pin; pressing the button or pulling the
#   switch "down" drives it to 0. PULLMODE=UP below matches this idle state.
LOCATE COMP "btn[3]" SITE "N2";
LOCATE COMP "btn[2]" SITE "V1";
LOCATE COMP "btn[1]" SITE "U1";
LOCATE COMP "btn[0]" SITE "R1";
LOCATE COMP "sw[3]"  SITE "M1";
LOCATE COMP "sw[2]"  SITE "W1";
LOCATE COMP "sw[1]"  SITE "Y2";
LOCATE COMP "sw[0]"  SITE "T1";
IOBUF PORT "btn[3]" IO_TYPE=LVCMOS33 PULLMODE=UP;
IOBUF PORT "btn[2]" IO_TYPE=LVCMOS33 PULLMODE=UP;
IOBUF PORT "btn[1]" IO_TYPE=LVCMOS33 PULLMODE=UP;
IOBUF PORT "btn[0]" IO_TYPE=LVCMOS33 PULLMODE=UP;
IOBUF PORT "sw[3]"  IO_TYPE=LVCMOS33 PULLMODE=UP;
IOBUF PORT "sw[2]"  IO_TYPE=LVCMOS33 PULLMODE=UP;
IOBUF PORT "sw[1]"  IO_TYPE=LVCMOS33 PULLMODE=UP;
IOBUF PORT "sw[0]"  IO_TYPE=LVCMOS33 PULLMODE=UP;
```

**Why the LED sites above don't match `pmodk`'s raw connector order, and how that was found out.** The PMOD standard only fixes the mechanical/electrical interface (pin spacing, 3.3V logic) — it says nothing about which internal pin drives which physical LED, and different vendors wire that up differently. The specific modules used here are AliExpress-sourced "Sipeed Tang FPGA PMOD module" LED and button/switch boards — built for Sipeed's Tang series, not the Colorlight i9, and merely PMOD-compatible with it — so there was no reason to expect their LED order would match `pmodk`'s connector-pin order (`R3 M4 L5 J16 N4 L4 P16 J18`), and it doesn't. Two things had to be determined empirically, on real hardware, before this `.lpf` could be written correctly:

1. **Polarity.** A first attempt drove all 8 LEDs with a simple counter, expecting a single lit LED to march across. Instead, *all but one* LED was lit at any time, wandering in a seemingly scrambled order — the giveaway that these are **active-low** (a LOW output lights the LED, common for a resistor-per-LED bar wired back to 3.3V, where the FPGA pin sinks current to turn one on).
2. **Per-bit site mapping.** Inverting the output (so a single LED lit, rather than a single LED dark) turned "seemingly scrambled" into "an actual fixed permutation, just not the connector's order." The permutation was solved in two rounds: first, a one-hot marching-LED test (one bit set at a time, cycling `led[0]` through `led[7]`) revealed most of the mapping but left an ambiguous swap between two positions that were hard to distinguish by eye during a fast march. Second, a *cumulative bit-fill* test (drive `led[7:0]` with the sequence `00000000, 00000001, 00000011, 00000111, ..., 11111111`, one more bit added each step) resolved it cleanly: because each added bit stays lit for the rest of the sequence, the exact step at which each physical LED position first turns on directly gives that position's `led[]` index, with no ambiguity — a good general technique any time a marching single bit is too fast or fiddly to track reliably by eye.

**This mapping is specific to this exact PMOD module on this exact `pmodk` connector — don't assume it transfers to a different LED PMOD, a different connector, or even the same module wired to `pmodl` instead.** The 4-button + 4-switch PMOD on `pmodl` above is still using the untested raw connector order and should get the same empirical treatment before being trusted.

**Why `led[7]` ends up on the left, not `led[0]`.** The empirical process above only pins down *a* correct permutation — it says nothing about which end should be the MSB. Once every physical position's `led[]` index was known, the indices were deliberately mirrored one more time (`led[7]`→leftmost, ..., `led[0]`→rightmost) so that any raw register value assigned to `led` displays left-to-right exactly the way you'd write it in ordinary binary notation, MSB first — the natural choice for a design where a Verilog variable's numeric value is what's usually being manipulated, so it's what should be intuitive to read off the board. Worked example: assigning `led = ~8'h53` (as `assign led = ~pos;` does above) drives the pins so that, reading the physical LEDs left to right, you see `0x53`'s own binary digits (`0101 0011`) directly as off/on/off/on/off/off/on/on — `led[7]` (MSB, value `0`) leftmost and off, `led[0]` (LSB, value `1`) rightmost and on. The active-low inversion and the bit-order mirroring are two independent fixes stacked on top of each other: the inversion corrects *polarity* (so `1` in the pre-inverted value means "on"), the mirroring corrects *position* (so bit 7 lands on the left).

**Why the button/switch sites above don't match `pmodl`'s raw connector order either, and what else was found while determining that.** With the LED permutation already solved and verified, a diagnostic firmware wired each of the 8 raw `pmodl` pins (guessed, at the time, as 4 "buttons" followed by 4 "switches" in connector order) straight to one dedicated LED each, active-low-inverted the same way as the LEDs. Idle state (all switches up, no buttons pressed) lit every LED — the first surprise: these controls are **idle-high, actuated-low** (opposite of the typical Digilent PmodBTN/PmodSWT assumption that a first draft of this section made, which turned out to be wrong for this specific Sipeed-style module). Pressing or flipping one control at a time turned exactly one LED off, and reading off which LED responded to which physical control — the same "toggle one thing, watch what changes" method used for the LEDs, just done directly rather than needing the two-round march/fill technique, since each of the 8 controls could be tested independently in a single pass — solved the permutation in one round. The result was more scrambled than expected: the raw connector order isn't simply "4 buttons, then 4 switches" reordered internally, it interleaves across that boundary too (e.g. the physical switch nearest the button row's guessed `btn[3]` site actually landed on `pmodl`'s `M1` pin, which this document's own earlier connector-order guess had labeled a button). `PULLMODE=UP` reflects the now-confirmed idle-high behavior; the original `PULLMODE=DOWN` guess in an earlier draft was empirically harmless (the module's own idle-high behavior overrides whatever the FPGA-side pull requests) but was pulling in the wrong direction and worth correcting now that the real polarity is known. If you instead wired bare mechanical switches directly to the header with no PMOD board in between, getting the pull direction right becomes load-bearing — without it, an open switch leaves the input floating, and (per the "I/O pin protection" note earlier in this document) the i9's I/O pins have no external protection network of their own to fall back on.

**Why `btn[3]`/`sw[3]` end up on the left, not `btn[0]`/`sw[0]`.** The same MSB-on-the-left goal that drove the LED mirroring above applies here too, but it's easy to get backwards on a first pass: it's natural to describe buttons and switches "left to right" the way English reads, which is exactly what an earlier draft of this `.lpf` did (`btn[0]` = leftmost physical button). That reads fine as a sentence, but it's the opposite of `led[]`'s own convention (`led[0]` = rightmost = bit 0 = LSB) — so wiring a switch/button panel to display a value on the LEDs the obvious way (`led[3:0] = btn`, `led[7:4] = sw`) came out mirrored: pressing the *rightmost* button lit `led[3]`, not `led[0]`, i.e. binary `00001000` instead of the intended `00000001`. The sites above are the corrected version: `btn[0]`/`sw[0]` are each panel's *rightmost* physical control, matching `led[]`'s bit-position convention rather than reading order, so `led[3:0] = btn` and `led[7:4] = sw` now display buttons and switches as an ordinary binary number with no mental reversal needed.

Build and flash exactly as with `prbs7.v` above:

```bash
yosys -p "synth_ecp5 -top led_button_demo -json led_button_demo.json" led_button_demo.v
nextpnr-ecp5 --45k --package CABGA381 --json led_button_demo.json --lpf colorlight_i9_gpio_demo.lpf --textcfg led_button_demo.config
ecppack --compress led_button_demo.config led_button_demo.bit
openFPGALoader -b colorlight-i9 led_button_demo.bit
```

Check: one LED lit at a time, chasing across the 8-LED PMOD. Hold button 0 to reverse direction, button 1 to pause, and move the switches to change speed — all without a CPU, an SDRAM controller, or a single line of Python; every bit of behavior comes from the synchronous logic above and the constraint file's pin mapping.

## Icepi Zero port — confirmed working on real hardware (2026-08-27), scaled down for no PMODs

The Icepi Zero has no PMOD headers at all, so the i9 version above (8 PMOD LEDs, 4 PMOD buttons, 4 PMOD switches) has no direct equivalent. What it does have, onboard: the same **5 white LEDs** used in the PRBS7 port above, and **2 buttons** — but one of them (site `C4`) is wired to the same pin as the board's `rst` net, so treating it as an ordinary input is riskier than it's worth for a tutorial. This port is deliberately scaled down to what's actually safe and available: a **5-LED chase, one working button for direction reverse, no speed control** (there are no onboard switches to drive it from, and adding an external one would mean wiring something to the 40-pin GPIO header, which this document doesn't assume you have to hand).

**Button polarity, confirmed empirically first, the same "toggle one thing, watch what changes" method this document already used for the i9's PMOD controls above.** Rather than guess from the platform file's own uncertain comment (`PULLMODE=UP) # Pull down?` — the board designer's comment, not this document's), a throwaway one-line test (`assign led = btn1;`, no invert, wired straight to site `C5`) was flashed and checked by hand: idle (nothing pressed) lit the LED, and holding down the button nearest the USB connectors turned it off. **Confirmed: idle-high, actuated-low** — `PULLMODE=UP` was the right call, matching the same idle-high/actuated-low convention the i9's PMOD buttons turned out to have. The other onboard button (nearest the 40-pin Raspberry Pi-header end, site `C4`, shared with `rst`) was deliberately left unwired in this test and, as expected, did nothing.

Verilog: `led_chase.v`

```verilog
module led_chase (
    input  wire       clk,   // 50 MHz onboard oscillator, site M1
    input  wire       btn1,  // bottom button (toward the USB connectors), site C5.
                              // Idle-high, actuated-low -- confirmed on real hardware.
                              // Held down: reverse the chase direction.
    output wire [4:0] led    // 5 onboard white LEDs, active-high -- confirmed on
                              // real hardware, no invert needed (unlike the i9's
                              // active-low PMOD LEDs above).
);
    reg btn_s0 = 1'b1, btn_s1 = 1'b1;
    always @(posedge clk) begin
        btn_s0 <= btn1;
        btn_s1 <= btn_s0;
    end
    wire reverse = ~btn_s1;

    // Free-running prescaler. Bit 24 gives roughly 3 steps/sec at 50 MHz --
    // no speed control (no onboard switches to drive it from).
    reg [24:0] prescaler = 25'h0;
    always @(posedge clk)
        prescaler <= prescaler + 1'b1;
    wire tick = prescaler[24];

    reg tick_d = 1'b0;
    always @(posedge clk) tick_d <= tick;
    wire step = tick & ~tick_d;

    reg [4:0] pos = 5'h01;
    always @(posedge clk) begin
        if (step)
            pos <= reverse ? {pos[0], pos[4:1]} : {pos[3:0], pos[4]};
    end

    assign led = pos;  // active-high: no invert
endmodule
```

Constraints: `icepi_zero_led_chase.lpf`

```
LOCATE COMP "clk" SITE "M1";
IOBUF PORT "clk" IO_TYPE=LVCMOS33;
FREQUENCY PORT "clk" 50.0 MHz;

# Bottom button (toward the USB connectors) -- user_btn index 1. The other
# onboard button (site C4) is deliberately not used -- it shares its pin
# with the board's reset net.
LOCATE COMP "btn1" SITE "C5";
IOBUF PORT "btn1" IO_TYPE=LVCMOS33 PULLMODE=UP;

# 5 onboard white LEDs -- user_led indices 0-4. led[0] is physically
# leftmost (USB-connector-down orientation), led[4] rightmost -- confirmed
# on real hardware, see the note below on why this is index-ascending
# left-to-right rather than the MSB-on-the-left convention used above.
LOCATE COMP "led[0]" SITE "E13";
LOCATE COMP "led[1]" SITE "D14";
LOCATE COMP "led[2]" SITE "E12";
LOCATE COMP "led[3]" SITE "C13";
LOCATE COMP "led[4]" SITE "D13";
IOBUF PORT "led[0]" IO_TYPE=LVCMOS33;
IOBUF PORT "led[1]" IO_TYPE=LVCMOS33;
IOBUF PORT "led[2]" IO_TYPE=LVCMOS33;
IOBUF PORT "led[3]" IO_TYPE=LVCMOS33;
IOBUF PORT "led[4]" IO_TYPE=LVCMOS33;
```

Build and flash — same pipeline, Icepi Zero chip parameters as the PRBS7 port above:

```bash
yosys -p "synth_ecp5 -top led_chase -json led_chase.json" led_chase.v
nextpnr-ecp5 --25k --package CABGA256 --speed 6 --json led_chase.json --lpf icepi_zero_led_chase.lpf --textcfg led_chase.config
ecppack --compress led_chase.config led_chase.bit
openFPGALoader -b icepi-zero led_chase.bit
```

**Confirmed working on real hardware.** One LED marches at a time across all 5, left to right by default (`led[0]`→`led[4]`, i.e. index-ascending), reversing to right-to-left while the USB-side button is held, released reverts back — exactly as designed, no CPU or Python involved.

**Why this is index-ascending left-to-right rather than MSB-on-the-left, unlike the i9 PMOD LEDs above.** The i9's PMOD LED mapping needed deliberate mirroring because the *raw connector order* it started from was an arbitrary, empirically-scrambled permutation with no inherent left-to-right meaning at all — mirroring it to put the MSB on the left was free, since there was no "natural" order to preserve either way. Here, `litex_boards`' own `user_led` 0..4 numbering already happens to read left-to-right in ascending index order on real hardware (confirmed above) — a real, physically-meaningful order, just LSB-first rather than MSB-first. Swapping `led[0]`↔`led[4]` and `led[1]`↔`led[3]` in the `.lpf` above would flip it to the MSB-on-the-left convention this document otherwise favors (matching `assign led = pos` reading left-to-right like ordinary binary notation), at the cost of no longer matching `litex_boards`' own index numbering. Left as index-ascending here since it's what was actually tested; swap the two pairs above if MSB-left consistency with the rest of this document matters more for a given use.

## Speed control note

The i9 version above used the switch PMOD's 4 bits as a speed selector (0 = slowest, 15 = fastest). The Icepi Zero has no onboard switches and no PMODs to attach a substitute panel to, so this port fixes the speed instead (prescaler bit 24, ~3 steps/sec) and gives the one safe onboard button entirely to direction reverse. A speed control is still possible with real hardware in hand — e.g. wiring a couple of switches to spare pins on the 40-pin Raspberry Pi-compatible GPIO header (the `("gpio", 0, Pins("G3 K3 T2 R2 R1 E1 F3 G1 H2 J1 L2 G2 J3 E3 P1 N1 H3 R3 N4 E4 F1 F2 P2 M2 L1 J2 D4 P3"), ...)` entry in `icepi_zero.py`) — but that requires soldering or a breadboard this document doesn't assume you have, so it's left as an extension rather than part of the confirmed base tutorial.

# Bare-metal C on a LiteX SoC: stock GPIO peripherals for the LED/button/switch PMODs

Same two PMODs, same physical wiring, but now driven from software on the VexRiscv soft core instead of hand-written HDL. This is the intervention point for "how are SoC peripherals configured and how do they talk to the processor," using LiteX's own built-in `GPIOOut`/`GPIOIn` peripherals (`litex/soc/cores/gpio.py`) — no Linux needed, and no custom HDL needed yet either (that's the next section).

## Add the PMOD pins to the platform, and the peripherals to the SoC

Following the exact pattern `colorlight_i5.py`'s own `sdcard_pmod_io()` function already uses for the SD-card PMOD (`Pins(f"{pmod}:N")` referencing a named connector from `_connectors_v7_2`), declare three new IO entries and add them with `platform.add_extension()`.

**Where the empirical re-ordering from the raw-Verilog section above has to go here:** `colorlight_i5.py` already has `pmodk`/`pmodl` as named connectors, but those are *raw connector-pin order* (`pmodk:0`..`pmodk:7` = sites `R3 M4 L5 J16 N4 L4 P16 J18`, in the order the schematic happens to list them) — exactly the naive order this document's empirical testing showed doesn't match physical position, let alone the bit-position convention settled on above. LiteX has no separate `.lpf`-equivalent step to patch afterward the way the raw-Verilog flow does; **the `Pins()` string's token order *is* the constraint** — whichever `pmodk:N`/`pmodl:N` token appears *first* becomes **bit 0** of the `Signal` that `platform.request()` hands back, always, with no way to reverse that direction. This is the one place in this document where bit 0 has to be written first rather than bit 7: everywhere else (Verilog `[7:0]`, `.lpf` comments) bit order is just prose/declaration style and this document writes the MSB first by convention, but `Pins()`'s token-position-*is*-bit-index behavior is a hard API constraint, not a style choice — reversing the token order here would reverse which physical pin is bit 0 vs. bit 7, not just how it reads. So the re-ordering has to happen directly in this token list (LSB-first, unavoidably), translating the verified `led[]`/`btn[]`/`sw[]` site assignments from the `.lpf` above into the equivalent `pmodk:N`/`pmodl:N` connector-index form (e.g. `led[1]`'s site `N4` is `pmodk:4`, since `_connectors_v7_2`'s `pmodk` list is `R3 M4 L5 J16 N4 L4 P16 J18` and `N4` is the 5th entry, index 4):

```python
# gpio_pmods.py -- new IO entries for the two PMODs from the section above,
# now addressed from the CPU instead of from hand-written HDL.
from litex.build.generic_platform import Pins, IOStandard, Misc

_gpio_pmod_io = [
    # Bit order matches the verified .lpf above (index 0 = rightmost physical
    # LED/button/switch, the LSB) -- NOT pmodk/pmodl's raw connector-pin order.
    # Pins() tokens are necessarily written LSB (index 0) first here -- see the
    # explanation above -- so this comment follows the same order as the
    # string below it, token for token, rather than this document's usual
    # MSB-first style:
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
```

**Where the active-low/idle-high polarity from the raw-Verilog section has to go here:** LiteX's stock `GPIOOut`/`GPIOIn` (`litex/soc/cores/gpio.py`) are polarity-agnostic — `GPIOOut` does a plain `self.comb += pads.eq(self.out.storage)` and `GPIOIn` does a plain `MultiReg(pads, self._in.status)`, neither one knows or cares that these particular pads are active-low. There's no `invert=` parameter to reach for. The fix is the same one line of logic as the raw-Verilog `assign led = ~pos;`, just moved into Migen and inserted between `platform.request()` and the peripheral instead of living inside a custom module:

```python
from migen import Signal
from litex.soc.cores.gpio import GPIOOut, GPIOIn
from gpio_pmods import _gpio_pmod_io

# inside BaseSoC.__init__, after SoCCore.__init__(...):
platform.add_extension(_gpio_pmod_io)

# LEDs are active-low -- invert between the raw pin and GPIOOut so a CSR write
# of 1 means "on", matching the raw-Verilog `assign led = ~pos;` convention.
led_pads  = platform.request("user_leds8")
led_logic = Signal(8)
self.comb += led_pads.eq(~led_logic)
self.leds8 = GPIOOut(led_logic)

# Switches are idle-high too, but "up" is already the natural 1 -- no invert
# needed here, unlike buttons below (same asymmetry as the raw-Verilog version).
self.switches = GPIOIn(platform.request("user_switches4"))

# Buttons are idle-high/actuated-low -- invert so a CSR read of 1 means "pressed".
btn_logic = Signal(4)
self.comb += btn_logic.eq(~platform.request("user_buttons4"))
self.buttons = GPIOIn(btn_logic)
```

`GPIOOut` registers one `CSRStorage` (attribute name `out`); `GPIOIn` registers one `CSRStatus` (attribute name, after LiteX strips its leading underscore, `in`). Combined with the parent attribute names above, `AutoCSR`'s name-gathering (see the CSR-register definition earlier in this document) produces three new memory-mapped registers: `leds8_out`, `switches_in`, `buttons_in` — no device tree work, no manual address assignment, exactly the "how do peripheral addresses propagate" pipeline described earlier, just pointed at these two PMODs instead of a UART or a timer. Because the polarity fix above lives in the gateware, not in software, `leds8_out`/`switches_in`/`buttons_in` already read and write with the natural "1 = on"/"1 = pressed" sense from C, Python, or Linux — none of the active-low bookkeeping leaks into software.

## Build a bare-metal (non-Linux) SoC

Nothing about this requires the Linux-capable CPU variant — leave `cpu_type` at its default (`vexriscv`, standard, no MMU/SMP, much smaller than `vexriscv_smp`):

```bash
python3 -m litex_boards.targets.colorlight_i5 --board=i9 --revision=7.2 --build --load
```

After the build, confirm the new registers landed where expected, the same way this document has checked CSR addresses before:

```bash
grep -iE "leds8|switches|buttons" build/i9/csr.csv
```

## Write and load a bare-metal C program against them

LiteX ships a minimal bare-metal demo app skeleton (`litex/litex/soc/software/demo/`) with its own `Makefile`, linker script, and a `litex_bare_metal_demo` helper script (`demo.py`) that copies the skeleton, patches the linker script for your target's memory map, and builds it against exactly the `build/<target>/software/include/generated/csr.h` this SoC just generated:

```bash
litex_bare_metal_demo --build-path=build/i9
```

Edit the copied `demo/main.c` (or add a new command to it) to read the switches/buttons and drive the LEDs — these are the plain C accessor macros LiteX auto-generates in `csr.h` from the CSR names above:

```c
#ifdef CSR_LEDS8_BASE
static void gpio_demo_cmd(void)
{
    printf("Reading switches/buttons, driving the 8-LED PMOD. Ctrl-C the terminal to stop.\n");
    while (1) {
        uint32_t switches = switches_in_read();  // bits [3:0], 1 = up
        uint32_t buttons  = buttons_in_read();   // bits [3:0], 1 = held
        // Switches sit physically above the buttons on the panel, so give
        // them the high nibble to match, buttons the low nibble -- both CSRs
        // already read with the natural "1 = on/pressed" sense, since the
        // active-low/idle-high inversion was fixed in the gateware above.
        uint32_t pattern = (switches << 4) | buttons;
        leds8_out_write(pattern);   // 1 = on, same reason
        busy_wait(20);
    }
}
#endif
```

Wire `gpio_demo_cmd` into `console_service()`'s command dispatch the same way the existing `led`/`donut`/`helloc` commands already are, following `main.c`'s own pattern. Rebuild with `make` inside `demo/` (or re-run `litex_bare_metal_demo`), then load it over the same serial link `litex_term` already uses for Linux images:

```bash
litex_term /dev/ttyACM0 --kernel=demo/demo.bin
```

Type `gpio` (or whatever name you gave the command) at the `litex-demo-app>` prompt. Flip switches and watch the high 4 LEDs track them live, with no OS, no device tree, and no kernel driver in the loop — just a C program polling two memory-mapped registers on a soft CPU.

**This will feel noticeably less crisp than the raw-Verilog `led_button_demo.v` version, and that's expected, not a bug.** The raw-HDL design is a synchronous circuit: a button/switch change is visible in the LED output within a couple of `clk` edges (tens of nanoseconds at 25 MHz), full stop. This C loop instead has to execute `switches_in_read()` (an actual load instruction over the CSR bus, not a wire), `buttons_in_read()`, some arithmetic, `leds8_out_write()`, then `busy_wait(20)` — each pass through the loop costs however long the CPU takes to fetch/decode/execute that handful of instructions on top of the deliberate ~20-something delay, easily tens of microseconds to low milliseconds depending on `busy_wait`'s units and VexRiscv's clock. For a couple of buttons and switches that's imperceptible either way, but it's the general and important tradeoff between the two approaches this document keeps returning to: hardwired combinational logic reacts at clock speed with zero software in the loop, a CPU polling loop reacts at "however fast this particular loop body executes" — fine for a UI-speed control panel, not fine for anything that needs cycle-accurate timing (that's what the custom HDL peripheral in the next section, or an interrupt-driven design, is for instead of a polling loop).

**Honest accounting: this section was substantially more work than the raw-Verilog one, even though it uses "stock" peripherals and not a single line of hand-written HDL.** Worth naming explicitly, since it's easy to assume "pre-built peripheral" means "less effort" than "write your own Verilog" — that wasn't the case here. The raw-Verilog flow is four commands (`yosys`, `nextpnr-ecp5`, `ecppack`, `openFPGALoader`) against one small file, done in seconds, with the result visible the instant the bitstream loads — no CPU, no boot process, nothing else in the way. This section instead needed: a whole SoC target file (a `BaseSoC` subclass pulling in VexRiscv, the SDRAM controller, the BIOS, and everything else a real SoC needs, not just the GPIO logic); re-deriving the same pin permutation a second time in a different notation (`.lpf` site names → `pmodk:N`/`pmodl:N` connector indices) because LiteX has no way to reuse the `.lpf` directly; the Migen inversion glue for the active-low/idle-high polarity, since the stock peripherals don't know about that; a full SoC synthesis + place-and-route (minutes, not seconds, because the whole SoC gets rebuilt, not just eight LUTs' worth of GPIO logic); a *separate* build step and toolchain for the C program against the generated `csr.h`; and finally a real boot process to get that program running at all — flash, catch the BIOS's serial-boot handshake within its open window, upload, jump. Getting this specific demo onto real hardware for this document involved exactly that last step going sideways (missing the handshake window, then a reflash-while-`litex_term`-was-attached leaving the DAPLink's JTAG/HID interface in a stuck state that needed a physical USB replug to clear) — a human sitting at a real interactive terminal doesn't hit the same *automation* friction (no need to choreograph a background process into catching a live handshake window), but the *structural* overhead — two separate build systems, a whole-SoC rebuild for a small peripheral change, an actual boot sequence standing between "built" and "running" — is real and inherent to the SoC-plus-CPU approach, not an artifact of how this particular session happened to drive the tools. That overhead is the price of programmability: the exact same gateware, unmodified, can now run a different C program (or, with the Linux-capable build, Python) without ever touching the FPGA fabric again — something the raw-Verilog version can't do at all, since changing its behavior means resynthesizing.

## Icepi Zero port: bare-metal C GPIO — confirmed working on real hardware (2026-08-27)

**A genuine wrinkle, worth naming, that the i9 version above doesn't hit: `litex_boards`' own `icepi_zero.py` target has a bug that blocks the obvious port.** Its `BaseSoC.__init__` has `if with_led_chaser or True:` — the `or True` makes the condition always true, so `self.leds = LedChaser(pads=platform.request_all("user_led"), ...)` runs unconditionally, claiming all 5 onboard LED pads, regardless of what `with_led_chaser=` is actually passed. That means a straight port of the i9 section above — add a fresh `GPIOOut` over `platform.request_all("user_led")` — would be a hard pin conflict (Migen refuses to let two peripherals claim the same physical pad) with a peripheral the stock target *already* wires up for you. Two ways to deal with it: patch out that line in a local copy of the target file, or just reuse what's already there. This port does the latter — `LedChaser` registers its own `CSRStorage` (`leds_out`), which is functionally the same "software writes a value, LEDs display it" register a from-scratch `GPIOOut` would give here (and it's the exact register already exercised live over the BIOS `leds` console command in this document's "Confirmed working" Linux section above) — so this SoC only adds what's genuinely missing: a `GPIOIn` for the one safe onboard button.

`icepi_zero_gpio_demo.py` — subclasses the stock `icepi_zero.BaseSoC` (imported directly, not copied) and adds the button after `SoCCore.__init__` has already run, the same "after `SoCCore.__init__(...)`" insertion point the i9 version above uses:

```python
from migen import Signal
from litex.soc.cores.gpio import GPIOIn
from litex.soc.integration.builder import Builder
from litex_boards.targets.icepi_zero import BaseSoC as IcepiZeroBaseSoC

class BaseSoC(IcepiZeroBaseSoC):
    def __init__(self, **kwargs):
        IcepiZeroBaseSoC.__init__(self, **kwargs)
        # user_btn index 1 (site C5, toward the USB connectors). Idle-high,
        # actuated-low -- confirmed on real hardware in the raw-Verilog
        # section above. Invert so a CSR read of 1 means "pressed". The
        # other onboard button (site C4) is skipped -- it shares its pin
        # with the board's reset net.
        btn_logic = Signal()
        self.comb += btn_logic.eq(~self.platform.request("user_btn", 1))
        self.button = GPIOIn(btn_logic)
```

(Full file, including the standard LiteX `main()`/argument-parser boilerplate every target script needs, mirrors `litex_boards/litex_boards/targets/icepi_zero.py`'s own `main()` — omitted here since it's unchanged from that file.)

Build (no Linux-capable CPU needed here either, same reasoning as the i9 version — plain `vexriscv` is the default, nothing overrides it):

```bash
python3 icepi_zero_gpio_demo.py --build --load
grep -iE "leds|button" build/icepi_zero/csr.csv
```

```text
csr_base,button,0xf0000000,,
csr_base,leds,0xf0001800,,
csr_register,button_in,0xf0000000,1,ro
csr_register,leds_out,0xf0001800,1,rw
```

`button_in`/`leds_out` landed exactly as expected — one read-only bit, one read-write 5-bit register.

`demo/main.c` — added a `gpio` command following the exact `#ifdef CSR_..._BASE` / `help()` / `console_service()` dispatch pattern the skeleton's own `led_cmd()` already uses:

```c
#ifdef CSR_BUTTON_BASE
static void gpio_demo_cmd(void)
{
    printf("Reading the button, driving the 5 onboard LEDs. Ctrl-C the terminal to stop.\n");
    while (1) {
        uint32_t pressed = button_in_read();  // bit 0, 1 = held (already inverted in gateware)
        leds_out_write(pressed ? 0x1f : 0x00); // all 5 LEDs on while held
        busy_wait(20);
    }
}
#endif
```

```bash
litex_bare_metal_demo --build-path=build/icepi_zero
# edit demo/main.c: add gpio_demo_cmd() above, wire into help() and console_service()
cd demo && make BUILD_DIR=../build/icepi_zero
litex_term --kernel=demo/demo.bin /dev/ttyUSB0
# at the litex> BIOS prompt this catches: type serialboot
# once you see litex-demo-app>: type gpio
```

**Confirmed working on real hardware.** The bare-metal app booted (`--== Liftoff! ==--`), listed `gpio` in `help`, and running it produced exactly the expected behavior: all 5 LEDs off with the button released, all 5 on while held down — the same button already validated in the raw-Verilog section above, this time read through a CSR from a C polling loop instead of directly in HDL, the core lesson of this whole section (see "This will feel noticeably less crisp..." above, which applies here unchanged).

# Writing a custom HDL LiteX peripheral, then using it as a LiteX peripheral

The PRBS31 goal from this document's original outline ("Linux can seed the LFSR, and each read advances it one step") is a good vehicle for the last piece: writing your *own* HDL peripheral (not `GPIOOut`/`GPIOIn` from LiteX's own library) and exposing it through the same CSR/device-tree/Python pipeline. Reusing the same two PMODs from above: the 8 LEDs display the running LFSR state, and the button/switch PMOD stays available for a hardware-side reseed as a suggested extension (see below).

**Two implementation paths, as this document originally sketched, both worked out in full below:** Path A (write the peripheral entirely in Migen/FHDL, no raw HDL at all) is the better fit for a peripheral you're designing from scratch — LiteX's `CSRStorage`/`CSRStatus` classes directly describe the registers and Migen generates correct Verilog and device tree entries with no `Instance()` boundary to get wrong. Path B (wrap existing Verilog with `Instance`) is the direct answer to "I already have a Verilog module (like `prbs7.v`/`led_button_demo.v` above) — how do I connect it into Linux?" without rewriting it in Migen. Both implement the identical polynomial (x³¹+x²⁸+1) and the identical CSR interface (`prbs31_seed`/`prbs31_state`, same addresses) — a deliberate choice, so the two are a direct apples-to-apples comparison of the two approaches rather than two different peripherals.

## Path B: wrap hand-written Verilog with `Instance`

Verilog: `prbs31.v`

```verilog
module prbs31 (
    input  wire        clk,
    input  wire        load,      // synchronous strobe: load `seed_in`
    input  wire [30:0] seed_in,
    input  wire        advance,   // synchronous strobe: take one LFSR step
    output wire [30:0] state      // combinationally reflects the *post-advance*
                                   // value whenever `advance` is asserted, so a
                                   // CSR read that pulses `advance` sees the new
                                   // state in the same cycle it requested it
);
    reg [30:0] shift_reg = 31'h1;                            // must never be seeded to all-zero
    wire        feedback   = shift_reg[30] ^ shift_reg[27];  // x^31 + x^28 + 1
    wire [30:0] next_state = {shift_reg[29:0], feedback};

    always @(posedge clk) begin
        if (load)
            shift_reg <= seed_in;
        else if (advance)
            shift_reg <= next_state;
    end

    assign state = advance ? next_state : shift_reg;

endmodule
```

Migen wrapper: `prbs31.py` — this is the actual LiteX peripheral. It owns the CSR registers, translates the CSR bus's read/write strobes into the raw Verilog module's `advance`/`load` pulses, and (optionally) drives the LED PMOD directly from hardware so the chase is visible even before Linux or Python ever touches the CSR:

```python
from migen import *
from litex.soc.interconnect.csr import CSRStorage, CSRStatus, AutoCSR

class PRBS31(Module, AutoCSR):
    def __init__(self, platform, led_pads=None):
        self.seed  = CSRStorage(31, description="Write to (re)seed the LFSR.")
        self.state = CSRStatus(31,  description="Current LFSR state; each CPU read advances it one step.")

        # # #

        self.specials += Instance("prbs31",
            i_clk     = ClockSignal("sys"),
            i_load    = self.seed.re,     # CSRStorage write strobe -> HDL "load"
            i_seed_in = self.seed.storage,
            i_advance = self.state.we,    # CSRStatus read strobe   -> HDL "advance"
            o_state   = self.state.status,
        )
        platform.add_source("prbs31.v")

        if led_pads is not None:
            # Mirror the top byte of the LFSR state onto the LED PMOD directly
            # in hardware -- visible even with no software polling it at all.
            # Inverted: these LEDs are active-low (see the GPIO section above),
            # and there's no CSR-level fix to lean on here since this drives
            # the pins directly rather than going through GPIOOut.
            self.comb += led_pads.eq(~self.state.status[-len(led_pads):])
```

`self.seed.re` and `self.state.we` are exactly the write/read strobes described in the CSR-register section earlier in this document (`re` = "CPU wrote this register this cycle"; `we` on a `CSRStatus` = "CPU read this register this cycle") — no new bus logic, no hand-rolled address decode, just two wires handed straight to the raw Verilog module's ports.

Wire it into the SoC target class alongside the GPIO peripherals from the previous section:

```python
from prbs31 import PRBS31

# inside BaseSoC.__init__:
platform.add_extension(_gpio_pmod_io)             # from the previous section
leds8_pads    = platform.request("user_leds8")
self.prbs31   = PRBS31(platform, led_pads=leds8_pads)
self.switches = GPIOIn(platform.request("user_switches4"))    # idle-high already means "up" = 1
btn_logic     = Signal(4)
self.comb    += btn_logic.eq(~platform.request("user_buttons4"))  # invert so 1 = pressed
self.buttons  = GPIOIn(btn_logic)
```

Rebuild (`python3 -m litex_boards.targets.colorlight_i5 --board=i9 --revision=7.2 --build --load`) and `grep -iE "prbs31|buttons" build/i9/csr.csv` to confirm `prbs31_seed` and `prbs31_state` landed at their own addresses — this is step 3 of the "Goal (incomplete)" checklist further down in this document, now actually done rather than left as a TODO.

**Suggested hardware extension** (left as an exercise rather than full code): OR a debounced pulse from `buttons` directly into the Migen wrapper's `load` signal (`self.comb += load.eq(self.seed.re | button_pulse)`), so a physical button reseeds the LFSR even with no CPU or software running at all — the same "hardware and CSR both drive the same control signal" pattern the LiteX BIOS itself uses for reset (`~rst_n | self.rst` in `colorlight_i5.py`'s `_CRG`, see the CRG code excerpted earlier in this document).

## Path A: pure Migen/FHDL, no raw HDL at all

The same 31-bit LFSR, same polynomial, same CSR semantics as Path B above — but written directly as Migen `Signal`/`If`/`Cat` logic instead of wrapping a separate Verilog file. No `Instance()`, no second HDL file to keep in sync, no `platform.add_source()`.

```python
from migen import *
from litex.soc.interconnect.csr import CSRStorage, CSRStatus, AutoCSR

class PRBS31Native(Module, AutoCSR):
    def __init__(self, platform, led_pads=None):
        self.seed  = CSRStorage(31, description="Write to (re)seed the LFSR.")
        self.state = CSRStatus(31,  description="Current LFSR state; each CPU read advances it one step.")

        # # #

        shift_reg  = Signal(31, reset=1)               # must never be seeded to all-zero
        feedback   = Signal()
        next_state = Signal(31)

        self.comb += [
            feedback.eq(shift_reg[30] ^ shift_reg[27]),         # x^31 + x^28 + 1
            next_state.eq(Cat(feedback, shift_reg[0:30])),      # Migen Cat() is LSB-first:
                                                                  # next_state[0]=feedback,
                                                                  # next_state[30:1]=shift_reg[29:0]
                                                                  # -- same shift as prbs31.v's
                                                                  # {shift_reg[29:0], feedback}
        ]

        self.sync += [
            If(self.seed.re,                # CSRStorage write strobe -> load
                shift_reg.eq(self.seed.storage)
            ).Elif(self.state.we,           # CSRStatus read strobe -> advance
                shift_reg.eq(next_state)
            )
        ]

        # Combinationally reflects the post-advance value whenever state.we is
        # asserted, so a CSR read sees the new state in the same cycle it
        # requested it -- same trick as prbs31.v's `assign state = advance ? ...`
        self.comb += self.state.status.eq(Mux(self.state.we, next_state, shift_reg))

        if led_pads is not None:
            # Active-low LEDs -- see the GPIO section of this document.
            self.comb += led_pads.eq(~self.state.status[-len(led_pads):])
```

The one thing worth double-checking whenever you translate a Verilog concatenation into Migen: **`Cat()`'s bit order is the opposite of Verilog's `{a, b}` syntax.** Verilog's `{shift_reg[29:0], feedback}` puts `shift_reg[29:0]` in the *high* bits and `feedback` in the *low* bit (leftmost operand = MSB, the same convention this document settled on for `led[]` and friends). Migen's `Cat(a, b)` is the reverse: the *first* argument is the *low* bits. `Cat(feedback, shift_reg[0:30])` is therefore the correct translation — get the argument order backwards and you'd build a right-shift register instead of a left-shift one, silently produce a different (but still plausible-looking) PRBS sequence, and have no compiler error to catch it.

Wiring it in is a one-line swap from Path B — same `_gpio_pmod_io`, same button/switch wiring, just a different class and import:

```python
from prbs31_native import PRBS31Native

# inside BaseSoC.__init__ -- everything else identical to the Path B wiring above:
platform.add_extension(_gpio_pmod_io)
leds8_pads    = platform.request("user_leds8")
self.prbs31   = PRBS31Native(platform, led_pads=leds8_pads)   # only this line changes
self.switches = GPIOIn(platform.request("user_switches4"))
btn_logic     = Signal(4)
self.comb    += btn_logic.eq(~platform.request("user_buttons4"))
self.buttons  = GPIOIn(btn_logic)
```

`grep -iE "prbs31" build/i9/csr.csv` after rebuilding shows the *identical* `prbs31_seed`/`prbs31_state` register names and addresses as Path B — confirmed on a real build. Inspecting the generated `colorlight_i5.v` confirms there's no `Instance("prbs31", ...)` and no separate `module prbs31` anywhere in it for this path — it's genuinely inlined Migen-generated logic, not a disguised wrapper.

## Icepi Zero port — both paths confirmed working on real hardware (2026-08-27)

**This is the first time this specific tutorial has been confirmed working on real hardware at all, on either board.** The i9 attempt below never got past `<DAPLink:Overflow>` — see the long investigation that follows. The Icepi Zero, using the same FT231X-based serial link already proven reliable for the Linux boot and every other tutorial in this document, hit no equivalent problem.

**One adaptation forced by a real `litex_boards` bug, not a choice.** Neither `PRBS31Native` (Path A) nor `PRBS31` (Path B) takes the i9 version's `led_pads` argument here — the stock `icepi_zero.py` target's `if with_led_chaser or True:` bug (already documented in the bare-metal-C GPIO section above) unconditionally claims all 5 onboard LED pads for its own `LedChaser`, so a peripheral driving those same pads directly in hardware would be a pin conflict. Both paths below instead expose the identical CSR interface as the i9 version (`prbs31_seed`/`prbs31_state`), and the running LFSR state is mirrored onto the LEDs by a small bare-metal C loop reading `prbs31_state` and writing `leds_out` — one extra step versus the i9's direct hardware mirroring, but a small price for a working confirmation.

**Path A (`prbs31_native.py`)** is a straight port of the Migen/FHDL code above, `led_pads` argument dropped, otherwise byte-for-byte identical logic (same polynomial, same `Cat()` ordering). **Path B (`prbs31_wrapper.py` + `prbs31.v`)** reuses the i9's `prbs31.v` completely unmodified — it was already board-agnostic (just `clk`/`load`/`seed_in`/`advance`/`state`, no physical pins) — with a Python `Instance()` wrapper that, likewise, drops `led_pads`.

Both wire into a small `BaseSoC` subclass, same shape as the bare-metal-C GPIO section's:

```python
# icepi_zero_prbs31_demo.py (Path A) -- icepi_zero_prbs31_pathb_demo.py (Path B)
# differs only in this one import + instantiation line:
from prbs31_native import PRBS31Native   # Path A
# from prbs31_wrapper import PRBS31      # Path B: from prbs31_wrapper import PRBS31

class BaseSoC(IcepiZeroBaseSoC):
    def __init__(self, **kwargs):
        IcepiZeroBaseSoC.__init__(self, **kwargs)
        btn_logic = Signal()
        self.comb += btn_logic.eq(~self.platform.request("user_btn", 1))
        self.button = GPIOIn(btn_logic)
        self.prbs31 = PRBS31Native()          # Path A
        # self.prbs31 = PRBS31(self.platform) # Path B
```

Build each (`python3 icepi_zero_prbs31_demo.py --build` / `python3 icepi_zero_prbs31_pathb_demo.py --build`) — both clean, both pass timing at 50 MHz, both land the identical addresses:

```text
csr_base,prbs31,0xf0002000,,
csr_register,prbs31_seed,0xf0002000,1,rw
csr_register,prbs31_state,0xf0002004,1,ro
```

Inspecting Path B's generated `icepi_zero.v` confirms the `Instance()` boundary is real, the same standard this document holds itself to elsewhere: `prbs31 prbs31(.advance(state_rd_stb), .clk(sys_clk), ...)` — an instantiation of a module defined in the separately-added `prbs31.v`, not inlined (`grep -c "module prbs31" build/icepi_zero/gateware/icepi_zero.v` returns `0` for Path B, confirming the module body lives only in the separate source file, the opposite of Path A).

**The single most useful confirmation, and worth calling out as its own reusable technique: exercising a custom CSR peripheral directly from the LiteX BIOS console, no C program required at all.** `mem_write`/`mem_read` are stock BIOS commands (see "Flash the bitstream" above) — since `prbs31_state`'s read strobe is wired straight to `advance`, simply reading its address *is* "take one step," so a plain `mem_read` loop at the `litex>` prompt directly demonstrates the peripheral's core behavior with nothing built or flashed beyond the gateware itself:

```
litex> mem_write 0xf0002000 1

litex> mem_read 0xf0002004 4

Memory dump:
0xf0002004  02 00 00 00                                      ....
litex> mem_read 0xf0002004 4

Memory dump:
0xf0002004  20 00 00 00                                       ...
litex> mem_read 0xf0002004 4

Memory dump:
0xf0002004  00 04 00 00                                      ....
litex> mem_read 0xf0002004 4

Memory dump:
0xf0002004  00 40 00 00                                      .@..
```

**Confirmed working on real hardware, both paths, byte-for-byte identical results.** `mem_write 0xf0002000 1` seeds the LFSR to `0x1` (matching each design's hardware reset value, so this specific test doesn't distinguish "did the write actually take effect" from "it just came up at its reset value" — a stronger test would seed to something other than `1` and confirm *that* value appears in the next read — but it does confirm the write completes without error and the peripheral is live). Four consecutive `mem_read`s each returned a *different* value (`0x2` → `0x20` → `0x400` → `0x4000`), directly confirming "each CPU read advances the LFSR one step," the whole point of this tutorial's CSR design — with **Path A and Path B producing the identical sequence**, byte for byte, confirming the two implementations really are behaviorally identical, not just address-identical. This exact sequence was reproduced on both `icepi_zero_prbs31_demo.py` (Path A) and `icepi_zero_prbs31_pathb_demo.py` (Path B) independently.

**Full confirmation with the bare-metal C demo app**, same `litex_bare_metal_demo`/`demo/main.c` pattern as the bare-metal-C GPIO section above — a `prbs` command added following the same `#ifdef CSR_..._BASE` style as the existing `led`/`gpio` commands:

```c
#ifdef CSR_PRBS31_BASE
static void prbs31_demo_cmd(void)
{
    printf("Advancing the PRBS31 custom peripheral, mirroring its top 5 bits\n");
    printf("onto the LEDs via leds_out. Ctrl-C the terminal to stop.\n");
    prbs31_seed_write(1);  // exercise the write/load path too, not just read/advance
    while (1) {
        uint32_t state = prbs31_state_read();  // each read pulses `advance`
        leds_out_write((state >> 26) & 0x1f);  // top 5 of 31 bits
        busy_wait(50);
    }
}
#endif
```

```bash
litex_bare_metal_demo --build-path=build/icepi_zero
# edit demo/main.c: add prbs31_demo_cmd() above, wire into help() and console_service()
cd demo && make BUILD_DIR=../build/icepi_zero
litex_term --kernel=demo/demo.bin /dev/ttyUSB0
# at litex>: serialboot -- once at litex-demo-app>: prbs
```

**Confirmed working on real hardware.** The demo app booted (`--== Liftoff! ==--`), listed `prbs` in `help`, and running it produced a visibly shifting, jittery pattern across all 5 LEDs — the expected look for a pseudo-random bit sequence read out roughly every 50ms, clearly distinct from the earlier LED-chase demo's smooth, predictable single-LED march.

**Verification status, and a note to future selves: `<DAPLink:Overflow>` (2026-08-22).** Both paths above were built for real on the Colorlight i9 (`--board=i9 --revision=7.2`), and both are confirmed correct at the *build* level: `csr.csv` shows the expected `prbs31_seed`/`prbs31_state` registers at matching addresses for both, and the generated Verilog netlist was inspected directly to confirm Path B's `Instance()` ports wire straight to the real CSR read/write strobes and Path A contains no `Instance()`/no second module at all. **Live, on-hardware confirmation of the actual read/advance/write behavior was not obtained**, and it's worth recording exactly why and how the diagnosis evolved, since it wasn't a PRBS31 bug and the first theory tried turned out wrong: both PRBS31 SoC builds reproducibly locked up the DAPLink's serial bridge with a `<DAPLink:Overflow>` error at the exact same point in the BIOS boot banner (right at the `ROM:` line), on every attempt, across a full USB replug and a fresh reflash each time. This was confirmed to be a hardware/firmware issue and not a `litex_term`-specific artifact by reproducing the identical failure, at the identical byte position, with two independent, unrelated terminal programs (`litex_term` and plain `picocom`). The first theory -- that this SoC's extra CSR peripheral (versus the shorter-banner GPIO-only SoC from the previous section, which had booted over this exact DAPLink reliably earlier the same session) pushed a marginal onboard buffer just past its limit -- **turned out to be wrong**: re-flashing that same previously-reliable GPIO-only `.bit` file, completely unchanged, hit the identical `<DAPLink:Overflow>` at the identical spot. At the same time, `/dev/hidraw1`'s permissions had silently reverted from the correct `plugdev`-group ownership back to `root`-only -- the exact same symptom that required a physical USB replug to clear earlier in this session. The real cause looks like **cumulative instability of this specific DAPLink probe under a long session of sustained, heavy JTAG/serial use** (many reflash cycles, many `openFPGALoader`/`litex_term` connect-disconnect cycles back to back), not anything about boot-banner length or CSR count -- that correlation was a coincidence of ordering, not a cause. **Update, same session, same day: a USB replug is not a reliable fix after all.** An earlier version of this note said a physical replug had "reliably cleared this every time" -- that held for the first two occurrences (both involving `openFPGALoader`/JTAG access actually failing outright), but does not hold for this specific overflow symptom: after two more full USB replugs, re-testing *both* the GPIO-only SoC (previously working earlier the same session) and this PRBS31 SoC, every single attempt reproduced the identical `<DAPLink:Overflow>` at the identical spot in the boot banner -- including one attempt with a deliberate 2-second delay between reflash and reattaching, in case timing/reset settling was a factor. It wasn't. One data point that doesn't fit "the probe is just generally flaky": `openFPGALoader --detect` and the underlying `/dev/hidraw1`/`/dev/ttyACM0` device permissions were healthy (correct `plugdev` ownership) on every one of these later attempts -- unlike the earlier lockups, which showed degraded/root-only permissions. That suggests this later, more persistent failure mode is a different (or additionally-triggered) problem from the permissions-loss one described just above, not the same thing recurring. **Net effect: within this session, this specific DAPLink probe appears to have entered a state where it cannot reliably stream this board's boot banner at all, and nothing tried from software -- reflashing, replugging, waiting, switching terminal programs -- fixed it.** If you pick this back up: things not yet tried are a different USB cable, a different USB port/host controller (ideally on different hardware entirely, to rule out this specific machine's USB stack), and checking the DAPLink firmware version against known-good releases (a firmware update was considered but deliberately not attempted in this session, since it carries real bricking risk and the specific firmware version/known-issue status was never actually looked up -- that's a real next step, not a dead end). Don't waste time looking at the peripheral Verilog/Migen code first -- the static evidence above already rules that out. **This same symptom was very likely seen once before, much earlier in this document, and misdiagnosed at the time:** see the "Reconsidered hypothesis" note added to the "Known issue: the kernel never starts running" paragraph in the Linux-boot section above -- the silent-after-a-burst-of-output signature there matches this bug closely enough to be worth another look before assuming that was a real RTL/software bug.

**Root cause found, and re-tested from a truly fresh state (2026-08-23).** Picking this back up after the laptop was hard-rebooted and the board sat unplugged overnight -- as fresh a state as this machine can produce, with a genuinely new USB enumeration for the DAPLink (confirmed via `lsusb`/lack of prior `dmesg` history) and healthy `plugdev`-group permissions on both `/dev/hidraw1` and `/dev/ttyACM0` from the moment it was plugged in. `~/openfpga`'s entire LiteX ecosystem (`litex`, `litex-boards`, `migen`, every `lite*`/`pythondata-*` clone, and `linux-on-litex-vexriscv`) was deleted and recloned/reinstalled from scratch via `litex_setup.py --init --install --user` to rule out any stale-toolchain contribution -- confirmed clean (`litex-boards`' git log is stock upstream HEAD, no local commits, so none of the `prbs31.v`/`prbs31.py` custom-peripheral work from the note above survived; those were evidently scratch files from the earlier session, never saved back into the tree, and would need to be recreated from the code blocks above if this section is revisited). **Result: the identical `<DAPLink:Overflow>`, at the identical spot (right after the `ROM:` line), on the very first reflash attempt** -- of the plainest possible build (stock, unmodified `colorlight_i5` target built with `--board=i9 --revision=7.2`, zero custom CSR peripherals, the shortest boot banner this document produces). This retires both standing theories at once: it isn't "cumulative instability from a long session of heavy JTAG/serial use" (this was attempt #1 after a full reboot), and it was never about banner length or CSR count (this build has neither).

**The actual mechanism: DAPLink's own firmware-level overflow *detection*, not corruption or a `litex`/toolchain bug.** Mounting the DAPLink's `MSD` volume and reading `/media/jason/DAPLINK/DETAILS.TXT` (a step the previous note flagged as "never actually looked up") shows `Overflow detection: 1` as an explicitly named, active firmware feature -- confirming `<DAPLink:Overflow>` is DAPLink deliberately reporting a real condition, not silent stream corruption. This specific probe is also a **MuseLab-customized DAPLink fork** (`Local Mods: 1`, Interface/Bootloader version `0254`, built `Oct 3 2020`) -- six years old, and not stock ARM mbed DAPLink, so its CDC-ACM receive-buffer sizing is whatever MuseLab shipped, not necessarily what upstream DAPLink issue trackers describe. The mechanism this points to: the BIOS blasts its boot banner over UART in one unthrottled burst with no flow control (no CTS/RTS between the ECP5's UART and the STM32 running DAPLink), and DAPLink's internal RX ring buffer for the virtual COM port can't drain over USB fast enough to keep up -- so it cuts the stream and reports the overflow, deterministically, at whatever byte offset the buffer actually fills. **A same-day follow-up test of that theory (rebuilding with `--uart-baudrate=9600` instead of the default `115200`) turned out to be inconclusive, for an interesting reason of its own.** The `--uart-baudrate=9600` CLI flag was confirmed, by directly monkeypatching `BaseSoC.__init__` and inspecting the received kwargs, to correctly reach `SoCCore`'s constructor as `uart_baudrate=9600` -- the Python-level argument plumbing is not at fault. And yet, empirically, the resulting bitstream's boot banner only came through cleanly when the *host* opened `/dev/ttyACM0` at **115200** -- reading it at 9600 (matching the build flag) produced a long run of null bytes before the same `<DAPLink:Overflow>` message, i.e. framing garbage consistent with a baud mismatch, not a working slow link. Likely explanation, not fully confirmed: opening a USB-CDC-ACM port like `/dev/ttyACM0` issues a `SET_LINE_CODING` request that (on some CDC-UART bridge firmware, quite possibly this MuseLab DAPLink fork) reconfigures *DAPLink's own* physical UART peripheral baud rate to match whatever the host asked for -- independent of whatever rate the FPGA's gateware was actually built to transmit at. If that's right, getting a genuinely slower physical link requires both sides to agree (rebuild *and* read at the same non-default rate), and this session never isolated which side was actually still running at 115200. **Not chased further, since it's a side question from the actual root cause above, not a prerequisite for it** -- worth returning to only if the overflow itself needs an actual mitigation beyond "expect it and work around it." A DAPLink firmware update remains untried (still carries real bricking risk), but now has a concrete version number to check against release notes -- MuseLab Interface `0254`, built 2020-10-03 -- rather than an unknown.

**Follow-up test, same day: does the underlying BIOS survive the overflow and keep booting -- can you just wait, send Enter, and get a working `litex>` prompt back?** A reasonable hypothesis, since `<DAPLink:Overflow>` is DAPLink dropping *its own* buffered bytes, not necessarily killing the target -- maybe the SoC finishes booting (memtest, `litex>` prompt) invisibly, deaf but not dumb, and the link just needs a nudge. Tested directly: open the serial port, wait for the JTAG reflash/reset to happen, let the overflow hit, then keep the *same* port open (deliberately never closing/reopening it, since that itself turned out to matter -- see below) and send a bare `\r\n` several seconds later. **Across three attempts, no `litex>` response ever came back** -- silence for the full remainder of each ~15-20 second observation window after the overflow, Enter included. One of these three additionally showed the DAPLink-firmware-generated overflow message clearly *not* followed by any further target-driven text at all (not even garbled bytes), which argues for the link (or possibly the target itself) actually being stuck, not merely a display/framing problem on the observation side. **Practical takeaway: no, waiting it out and sending Enter does not recover a session once `<DAPLink:Overflow>` has fired on this probe.** A full USB replug remains the only thing that's cleared it so far.

**A useful negative result surfaced along the way: it is not a DTR-triggered reset.** Before settling on the test above, the leading theory was that *opening* `/dev/ttyACM0` itself might be pulsing a reset via DTR (the well-known "opening the port resets my Arduino" behavior many USB-serial bridges have) -- which would mean every observation attempt was contaminating itself by triggering a fresh reset right as it started watching. Tested directly by constructing the `pyserial` object with DTR pinned low *before* the underlying file descriptor ever opens (the standard technique to suppress DTR-triggered auto-reset) and comparing against normal opens. **Identical behavior either way** -- so DTR is not the mechanism. What does appear to matter: opening the port fresh *after* the target has already been sitting idle for a few seconds consistently produced immediate nulls with no visible banner text at all (as if only the tail end of a fast, already-finished event was ever observable), while opening the port *before* triggering the reset (already stable and attached when the reset happens) is the only pattern that ever captured clean, readable banner text before the overflow. That said, this same "open before reset" pattern was tried four times total across this investigation and only succeeded cleanly once -- the other three (including all three of the wait-and-send-Enter attempts just above) still showed nulls-then-overflow despite the identical setup, suggesting this probe's reliability also degrades somewhat with repeated use within a session, on top of the overflow being fundamentally real and firmware-level. Both things can be true at once.

**New hazard, reproduced live in this same session: holding the serial (CDC) port open while a JTAG operation runs on the same probe corrupts the probe's HID interface.** While chasing the baud-rate test above, a small `pyserial` script was used to capture the boot banner programmatically (`picocom` can't be driven this way in a non-interactive/automated context -- see the toolchain note below). That script opened `/dev/ttyACM0` with `dtr`/`rts` asserted and was still holding it open when `openFPGALoader -b colorlight-i9 --detect` ran concurrently. Result: `JTAG is not supported by the probe` / `cmsisDAP: init Failed`, and `/dev/hidraw1` **disappeared from `/dev` entirely** (not just permission loss -- the device node was gone, while `lsusb` still showed the same DAPLink at the same bus/device number, i.e. no full re-enumeration happened, just the HID interface dropping out). This is almost certainly the same failure class as the "reflash-while-`litex_term`-was-attached leaving the DAPLink's JTAG/HID interface in a stuck state" symptom noted earlier in this document (see "Honest accounting" above) -- now confirmed with a second, completely unrelated serial client (`pyserial` instead of `litex_term`), which rules out that earlier note being specific to `litex_term`'s own connection handling. **Takeaway for future sessions, human or automated: never hold the serial port open while issuing a JTAG command (`--detect`, `--load`, `-f`) to this probe, and vice versa -- fully close one before opening the other.** A physical USB replug was the only thing that cleared it in every case tried so far; a software-only recovery (e.g. an unprivileged sysfs unbind/rebind of the USB device) was not attempted this session.

**Toolchain pitfall found and fixed along the way: don't `source ~/openfpga/oss-cad-suite/environment` for this workflow.** This document's own install instructions (see "Install the FPGA Toolchain" above) only ever add `~/openfpga/oss-cad-suite/bin` to `PATH` via `~/.bashrc` -- a plain, permanent, one-time addition, same as any other standalone CLI toolchain (`~/go/bin`, `~/.cargo/bin`), and deliberately *not* tied to any Python virtualenv (including this repo's own `DroneSDR/.venv`), since `yosys`/`nextpnr-ecp5`/`openFPGALoader`/etc. are compiled binaries with no relationship to a project's Python environment. OSS CAD Suite separately ships its own `environment` script (`~/openfpga/oss-cad-suite/environment`), which behaves like a Python venv `activate` script -- it additionally prepends `oss-cad-suite/py3bin` (a bundled Python **3.11**, with its own isolated site-packages) ahead of system Python on `PATH`, and sets `PYTHONHOME`/`VIRTUAL_ENV`. Sourcing it (as this session initially did, assuming it was the standard activation step) silently breaks the LiteX build: `litex`/`litex-boards` are `pip install --user` editable installs discovered via `.pth`-triggered import hooks in system Python 3.10's own site-packages machinery, which Python 3.11 never runs -- so `python3 -c "import litex"` fails from inside that shadowed environment, and the LiteX build's BIOS step (which shells out to plain `python3 -m litex.soc.software.crcfbigen`) fails with a confusing `ModuleNotFoundError: No module named 'litex'` that has nothing to do with `litex` actually being missing. **Fix used this session:** either don't source `oss-cad-suite/environment` at all (the plain `.bashrc` PATH line from the install instructions is sufficient for everything this document does), or if it's already been sourced for some other reason (e.g. Verilator/cocotb Python bindings elsewhere in this document), run `export PATH="/usr/bin:$PATH"` afterward to put system Python back in front before any `litex_boards`/`make.py` build command. Sanity check before trusting a build: `which python3` should print `/usr/bin/python3`, not a path under `oss-cad-suite`.

**Advice on `picocom` vs. scripted serial capture, for future sessions (automated or human).** `picocom` is built for an interactive human at a real TTY -- when driven from a non-interactive context (a backgrounded shell, a tool call with no real stdin) it reads zero bytes from stdin and exits almost immediately, regardless of `--exit-after`, so it silently produces no captured output rather than failing loudly. For automated capture (e.g. checking a boot banner for a specific string) a short Python script using `pyserial` is more reliable: open the port directly, explicitly set `.dtr = True` / `.rts = True` (some USB-CDC bridges, this DAPLink included, appear to gate output on DTR the way Arduino-style boards do -- a plain `cat /dev/ttyACM0` without asserting DTR captured nothing at all in this session, even redirected during a live reflash), and read in a timed loop. The one hazard this doesn't remove, and in fact makes easier to trip over by accident in a scripted sequence: the concurrent-serial-plus-JTAG hazard documented just above. Whatever tool is doing the serial capture, make sure its process/port has fully exited *before* the next `openFPGALoader` call, not just logically "done reading" -- a script that opens the port, reads for N seconds, and closes it, racing against a reflash issued from a separate shell invocation, is exactly the failure mode reproduced above.

**Major update, same day, after a hardware change: the DAPLink link itself is not the bottleneck -- a raw-Verilog isolation test says the overflow is much more likely LiteX/BIOS-specific.** Before this test, the laptop was fully unplugged from USB, the LED/button-switch PMODs were removed, **the ECP5 SODIMM module was reseated in its carrier-board socket, and everything was replugged** -- a plausible fix if the root cause were a marginal physical connection. Retesting the plain LiteX BIOS boot three times post-reseat showed no improvement (still nulls-then-overflow in most attempts, one run showing outright binary garbage instead of a clean overflow tag -- see raw capture in session history), so the reseat alone didn't resolve it, though it may still have been worth doing (a marginal connection wouldn't necessarily manifest as 100% failure either way).

**The decisive test: a small hand-written Verilog UART transmitter (`~/openfpga/uart_stress_test/uart_stress_test.v`), no LiteX, no CPU, no BIOS, driving the exact same physical pin** (`J17`, the same site `colorlight_i5.py`'s `"serial"` resource uses for `tx`) **through the same DAPLink probe.** A simple 8N1 bit-banger, parameterized by baud rate and by a burst-length limit (0 = send forever, N = send exactly N bytes then go idle), built and reflashed via the plain `yosys`/`nextpnr-ecp5`/`ecppack`/`openFPGALoader` raw flow (seconds per build, not LiteX's ~100s) -- see `build.sh`/`build_ascii.sh` in that directory for the parameterized build wrapper. Tested: a 600-byte burst at 115200 (matching the real BIOS overflow's byte count and rate) three times, a 30-second/256KB continuous stream at 115200 once, a 600-byte burst at a claimed 9600 baud once (inconclusive on the actual rate, for the same reason noted above -- a monotone `0x55` pattern is also a poor choice for cross-baud verification specifically, since continuous alternating-bit framing is periodic and can alias across mismatched baud rates; this doesn't affect the results below, which only depend on matched build/read rates), and a 600-byte burst of varied printable ASCII (`0x20`-`0x7E` cycling, closer to real banner text than a monotone byte) at 115200 twice more. **Result, across all seven runs: the actual design content arrived completely intact every single time** -- exact byte counts, correct bytes, zero corruption -- with at most a single stray null byte at the very start of a run (self-clearing within the same power-up, never repeating, never followed by an actual `<DAPLink:Overflow>` in six of the seven runs). Content variety didn't matter either -- the printable-ASCII variant was exactly as clean as the monotone one.

**What this rules out, and the refined leading hypothesis.** It rules out "DAPLink's CDC-ACM buffer can't sustain ~600 bytes at 115200" as the mechanism -- a design with zero software, zero CPU, zero DDR, zero PLL (driven straight off the raw 25 MHz oscillator, same as the earlier `prbs7.v` example) pushed the *same* burst size, at the *same* baud, through the *same* physical pin and the *same* DAPLink probe, repeatedly, cleanly. It also weakens "cumulative probe instability from heavy session use" as the primary explanation, since this simple design was reflashed seven times in the same already-long session with no degradation trend visible. What's left standing: something specific to the **LiteX/VexRiscv SoC's own reset/startup sequence** -- PLL lock, SDRAM/DDR calibration, or some other reset-adjacent activity happening on the same board at the same time the BIOS is trying to print its banner -- is the more likely source of whatever DAPLink is reacting to, not a generic throughput or buffer limit of the link itself. This also reframes the "reset-transient" observation two notes up: the transient glitch this raw-Verilog test occasionally shows (nulls, once, at power-up) looks like the *same* underlying event the BIOS boot reliably shows, but the BIOS's is apparently longer, worse, or otherwise more provoking -- consistent with it happening alongside real electrical activity (PLL/DDR) this bare-bones design never generates. **Natural next step, not yet done:** reflash the actual LiteX-built `colorlight_i5.bit` (with its PLL/SDRAM controller) but capture with a scope or logic analyzer on the `J17` pin directly, comparing its reset-adjacent electrical behavior against this clean raw-Verilog design's -- that would confirm or rule out the PLL/DDR-timing hypothesis directly, rather than inferring it from serial-side symptoms alone.

**Follow-up, same day, no oscilloscope available: checked the BIOS source directly to see what's actually happening right after `ROM:`, and it isn't SDRAM calibration yet.** `litex/litex/soc/software/bios/main.c` prints `SRAM:`, then (if present) `L2`/`FLASH`, then an `SDRAM:` line that only *reads* already-populated config (no pin toggling) -- the real `sdram_init()` call, which actually drives DRAM training/calibration, happens several `printf`s later, well past every failure point observed so far. So "DDR calibration crosstalk" as literally stated is wrong -- whatever's happening, it's earlier than that.

**Directly tested anyway, since the SDRAM *controller's mere presence in the fabric* (even completely unused by software at this point) was still a live suspect: rebuilt with `--integrated-main-ram-size=0x10000`, which drops the external SDR SDRAM PHY/controller from synthesis entirely and uses internal block RAM for `main_ram` instead** (`colorlight_i5.py`'s `if not self.integrated_main_ram_size: self.sdrphy = ...` skips it outright when this is set). Reflashed and captured three times. **Result: the identical `<DAPLink:Overflow>` still fired at the identical spot (right after `ROM:`) in every attempt that produced any output at all -- but in 2 of those 3, the link then recovered on its own and the boot continued cleanly all the way to a working `litex>` prompt** (Memtest OK on the 64KiB BRAM `main_ram`, memspeed, SPI flash detection, serial-boot timeout, `litex>`). This never happened once across every attempt with external SDRAM present in the build. **This is the clearest signal yet: the overflow itself isn't caused by the SDRAM controller (it still happens with SDRAM removed), but something about the SDRAM PHY/controller's continued presence in the fabric appears to be what prevents DAPLink from recovering afterward.** **Correction, checked directly against `colorlight_i5.py`'s `_CRG` class right after writing the note above: it is *not* the SDRAM clock domain/PLL output.** `_CRG.__init__` unconditionally creates the phase-shifted `sys_ps` clock domain and unconditionally drives the physical `sdram_clock` pin via `DDROutput` (lines ~90-92) -- this runs identically whether or not `--integrated-main-ram-size` is set, since `self.crg = _CRG(...)` happens before any SDRAM-presence check in `BaseSoC.__init__`. So that clock/pin activity is identical between the "recovers" and "doesn't recover" builds and can't be the differentiator. The one thing that *does* differ is `self.sdrphy` (a `GENSDRPHY` instance) and the LiteDRAM controller wired to it -- which, once instantiated, drives roughly four dozen additional physical pins (the SDRAM `a[11]`/`dq[32]`/`we_n`/`ras_n`/`cas_n`/`ba[2]` bus from the platform file) at whatever idle/reset state that PHY holds them at, and runs its own init/refresh state machine independent of the BIOS's software-driven `sdram_init()` (confirmed above to run much later, well past the failure point) -- current best guess is that *this*, not the clock domain, is the more likely noise source, but this is still inference from indirect symptoms, not a direct observation.

**Follow-up test, ruling out "just less overall switching activity/EMI at a lower clock" as an alternative explanation.** If the real cause were generic (more logic, higher clock, more simultaneous switching anywhere on the board -- not SDRAM-specific), then lowering `--sys-clk-freq` while *keeping* the SDRAM controller should also help, same as removing SDRAM did. Tested directly: rebuilt the normal SDRAM-enabled SoC at `--sys-clk-freq=48e6` instead of the default 60MHz, reflashed and captured three times. **Result: 0 of 3 recovered** -- same clean-banner-then-overflow-then-permanent-silence pattern as every other SDRAM-enabled build at every clock tried so far (one of the three didn't even get that far, showing plain binary garbage instead, consistent with the general session flakiness noted throughout). This is a real contrast with the SDRAM-*removed* build's 2-of-3 recovery rate at the *higher* 60MHz clock -- if a lower clock alone were the fix, this should have recovered at least some of the time, and it didn't, at all. **This strengthens the conclusion that the SDRAM controller's presence specifically (not overall design size or clock speed) is what prevents recovery**, though the exact mechanism -- most likely the SDRAM PHY's ~48 address/data/control pins and their reset-time/init-time behavior, per the correction above -- remains inferred rather than directly observed. Probe stayed JTAG-healthy through all three attempts this time, no replug needed. Practical implication: for anything that doesn't strictly need external SDRAM, dropping down to `--integrated-main-ram-size` may be a usable workaround on this specific probe/board pairing; it is **not** enough RAM for actual Linux (this document's own numbers put a minimal Linux fit at ~4MB flash/RAM, versus the ECP5-45F's roughly ~243KB of total block RAM, all of it also competing with ROM/SRAM/cache), but it's a strong pointer toward where to look next -- e.g. whether the SDRAM PHY's PLL output can be gated/delayed independently of whether SDRAM is actually in use. One remaining flaky attempt (near-total silence, no overflow tag, no banner) matches the general session-flakiness pattern already documented above and doesn't appear specific to this change. **Collateral damage: three back-to-back concurrent serial+JTAG cycles in this test broke the probe's HID interface again** (the hazard documented above) -- another physical replug was needed afterward.

## `<DAPLink:Overflow>` and the SDRAM finding: best-guess apportionment of blame (2026-08-23)

After the investigation above (fresh-reboot reproduction, raw-Verilog isolation, the SDRAM-removal test, the clock-speed control, and the LiteScope round-trip corruption test), here is a considered, evidence-based guess at how much of this is hardware, how much is DAPLink firmware, how much is LiteX gateware, and how much is unexplained -- written for whoever picks this up next, including future-Claude. **Treat this as an interacting failure with several contributing factors, not one single root cause** -- the evidence doesn't support pinning it on any one layer alone.

**LiteX gateware as the *trigger* (~35% -- high confidence in this specific role, not a claim that LiteX has a bug).** The single strongest piece of evidence in the whole investigation is the contrast between the raw-Verilog UART test and the real LiteX SoC: same pin, same probe, same baud, same or larger byte counts -- the raw-Verilog design triggered a real overflow in roughly 1 of 7 runs (a single self-clearing stray byte), while the LiteX SoC triggered it in the large majority of boots. The only meaningful difference is what LiteX's gateware is *doing electrically* around reset -- PLL lock, multiple clock domains, and (per the SDRAM finding) a lot more pins toggling. LiteX isn't doing anything wrong here; it's just legitimately doing more than a trivial bit-banger, and that activity level is what excites whatever's vulnerable on the probe side.

**DAPLink firmware as why it *sticks* rather than blipping (~40% -- the largest single bucket).** A transient glitch is one thing; going permanently silent afterward, and separately corrupting an *unrelated* CSR round-trip with literal fragments of its own `<DAPLink:Overflow>` string (`0x3c` = ASCII `<`, confirmed via a plain `ctrl_scratch` write/read-back test -- see the LiteScope section above), is a firmware robustness problem, not something LiteX or the FPGA gateware has any control over. `DETAILS.TXT` (readable by mounting the DAPLink's `MSD` volume) shows this is a **six-year-old MuseLab-customized fork** (`Local Mods: 1`, Interface/Bootloader version `0254`, built `2020-10-03`), not stock ARM mbed DAPLink. A more modern or better-engineered CDC-UART bridge would likely absorb the same glitch without losing state or corrupting an unrelated channel.

**Hardware as an enabling/coupling factor, not a sufficient cause on its own (~20%).** A physical SODIMM reseat (module out, PMODs off, full USB unplug, reseat, replug) didn't fix anything, and the raw-Verilog test barely ever triggers the issue *on this same physical hardware* -- so the board isn't spontaneously flaky by itself; it takes real gateware activity to excite it. But general session-to-session non-determinism (identical builds producing wildly different outcomes run to run), and the JTAG/HID interface separately breaking under concurrent serial+JTAG access (documented above), both have the flavor of marginal signal integrity or a stressed shared USB controller on the probe -- something that doesn't cause failure alone but lowers the bar for the gateware-generated glitch to actually corrupt the link.

**Other / unverified (~5%).** The host USB port, cable, and machine were never varied this session -- a genuinely open question, not ruled in or out. (The user reports already alternating between this laptop's two USB ports across the session, for what that's worth -- weak evidence against "just this one port" as a major factor, though not a controlled test.)

**The SDRAM-specific finding is best read as a sharper instance of the same "gateware trigger" bucket, not a separate cause.** Removing the SDRAM controller (BRAM instead) didn't stop the initial overflow -- it changed whether the link *recovered* afterward (2 of 3 vs. 0 of many with SDRAM present, even at a slower clock, which separately ruled out "just less overall switching activity" as the explanation). The exact mechanism remains unconfirmed without a scope, but the same three-way split applies: the SDRAM PHY's ~48 idle/init-time pins are LiteX-gateware-generated activity (not a bug -- SDRAM controllers legitimately need to drive those pins), whatever couples that activity into the serial line is a hardware/layout question, and whether the resulting glitch is recoverable or fatal is DAPLink firmware's call.

**If this is picked back up:** the most likely single "fix" is on the DAPLink firmware/probe side, since it's the layer actually deciding "drop and recover" vs. "drop and die," and it's the oldest, least-maintained link in the chain -- see "Is a DAPLink firmware update available?" below for what was found there. The already-validated practical mitigation (avoid instantiating the SDRAM controller when you don't strictly need it) works because it's the one layer actually under a hobbyist's control without new hardware.

## Raw-Verilog reliability, continued: a batch of repeats, and a new clue

Picking the "how much of this is reliable" question back up with more repeats of the raw-Verilog UART burst test (`~/openfpga/uart_stress_test/burst_600_115200.bit`, `cont_115200.bit` -- see above): **14 of 15 total raw-Verilog runs across this whole investigation came through completely clean** (exact byte counts, correct content, no `<DAPLink:Overflow>`), including a fresh batch of 8 back-to-back reps just now (all 8 clean) and a 60-second/~600KB continuous stream (clean except a single stray null byte at the very start). Six rapid-fire reflashes with **zero settle time and no serial listener at all** (pure JTAG hammering, isolating cycling-stress from the serial link entirely) left the probe's JTAG side completely healthy afterward.

**The one exception is the new clue.** Immediately after that 6x rapid-JTAG-hammer sequence, the very next serial capture (still the same simple 600-byte burst design) showed `<DAPLink:Overflow>` **and roughly double the expected byte count of clean `U` characters** (1156 U's captured against an expected 600) -- as if the design's fixed, one-shot 600-byte burst had actually run to completion *twice* in the same capture window. This is the same "apparent double boot" signature seen earlier with the LiteX BIOS in the LiteScope section above (a full banner printed twice in one capture). A design with a hard `BURST_LIMIT` and no way to re-trigger itself cannot legitimately produce this on its own -- the only way to see it twice is if the **target FPGA was actually reset a second time**, independent of any `openFPGALoader` command issued from the laptop.

**Checked immediately after, and confirmed: the DAPLink's own USB identity had changed.** `lsusb -d 0d28:0204` showed a new `device` number and a different internal `path` value compared to every single check earlier in this session -- without any physical replug. The most likely explanation: **the DAPLink probe's own STM32 microcontroller is, at least sometimes, actually crashing and rebooting** (not merely dropping or corrupting serial bytes), and that reboot is itself pulsing whatever line connects the probe to the target FPGA's reset net -- which would explain both the "double boot" symptom and, more importantly, gives a concrete physical mechanism for why the link sometimes needs a full USB replug to recover (a hung/crashed MCU, not just a full software buffer). This reframes the earlier "hardware coupling/EMI" guess in the apportionment above slightly: it may be less about analog crosstalk into the UART line and more about **the DAPLink MCU itself faulting**, which the next section's firmware research turned out to support directly.

## Is a DAPLink firmware update available? (researched, not attempted)

**Firmware lineage identified.** This probe's exact firmware (`Interface Version: 0254`, built `2020-10-03`, `Local Mods: 1`, per `DETAILS.TXT`) is almost certainly built from [wuxx/DAPLink](https://github.com/wuxx/DAPLink) -- a fork maintained by the same person (GitHub user `wuxx`, aka MuseLab/Johnny Wu) behind both the [Colorlight-FPGA-Projects](https://github.com/wuxx/Colorlight-FPGA-Projects) documentation this whole investigation has used and the iCESugar board family. Its own description: "an STM32 port for CMSIS-DAP with additional serial (CDC) support" -- i.e. the customization is specifically about *adding* CDC/serial support to a board port, not a deep rewrite of DAPLink's core buffering/overflow logic. **No board target folder matching "colorlight" was found** in a listing of the fork's `source/board` directory, so the exact board-specific patch used for this carrier board's chip wasn't directly located.

**The fork is stale, frozen at upstream's state from around April 2020.** Its commit history includes real upstream [ARMmbed/DAPLink](https://github.com/ARMmbed/DAPLink) maintainer commits (`flit`, `MarianSavchuk`, `0xc0170`) through early April 2020, with nothing found after that -- meaning **whatever this fork's own MuseLab-branded version number claims, it has not tracked ~6 years of upstream fixes since**. This probe's firmware, built October 2020, is consistent with being cut from very close to that April-2020 freeze point.

**Upstream ARMmbed/DAPLink is still actively maintained** (releases visible through at least 2024, including a `v0258` pre-release) -- it has not been abandoned, unlike the Colorlight-specific fork.

**Directly relevant upstream issues found, all in the same failure class as this session's symptoms:**
* **[#179](https://github.com/ARMmbed/DAPLink/issues/179)**, filed 2016: ring-buffer overflow in `uart.c` "not properly handled" -- on overflow, DAPLink should overwrite oldest data and keep the link alive, but doesn't. Old enough that if ever fixed, the fix should already be in this session's 2020 firmware -- but it illustrates this class of bug has a long, arguably never-fully-resolved history in DAPLink's core.
* **[#224](https://github.com/ARMmbed/DAPLink/issues/224)**: if the target sends serial data very early (before DAPLink's own CDC-ACM buffer is initialized), it can trigger a **bus fault** in the DAPLink firmware itself. Strikingly close to this investigation's own symptom -- the overflow consistently happens right at the very start of the BIOS's serial output, the earliest and fastest-arriving burst of real data in the whole boot sequence.
* **[#775](https://github.com/ARMmbed/DAPLink/issues/775)**, filed **February 2021** -- after this probe's firmware was built -- on a different DAPLink-based board (MAX32625PICO): once its UART ring buffer overflows, the link gets stuck in a corrupted state emitting only `*` characters forever, **with the overflow flag never cleared, requiring a full USB power cycle to recover**. This is about as close a precedent as could be hoped for: same underlying DAPLink CDC-ACM architecture, same "stuck permanently, needs a physical power cycle" recovery signature as this whole investigation's `<DAPLink:Overflow>` -- and it postdates this probe's firmware, so even if it was ever fixed upstream, that fix cannot be present here.

None of these three issues showed a confirmed linked fix/PR in what was checked -- worth re-verifying directly on GitHub (issue comments/linked PRs, not just search snippets) before concluding either way, if this is picked back up.

**Has anyone built a modern DAPLink firmware for this specific platform? Not found.** MuseLab's newer probe product, [nanoDAP-HS](https://github.com/wuxx/nanoDAP-HS) ("DAPLink High Speed"), is a **different physical product** on a different MCU family entirely (Atmel ATSAM3U2C, not whatever STM32 part is on this carrier board) -- not a firmware image that could be reflashed onto the existing hardware. No evidence was found of anyone maintaining an updated, Colorlight-carrier-specific DAPLink build against a current upstream checkout.

**Practical takeaway.** A simple "download the latest firmware and reflash" option does not appear to exist for this exact probe -- the vendor fork is stale, and no community successor was found. The real fix, if pursued, would mean porting whatever board-specific pin/CDC configuration this carrier board needs onto a *current* ARMmbed/DAPLink checkout and building it fresh -- a real, non-trivial undertaking (finding or reverse-engineering the exact board config, verifying flash/bootloader compatibility, and it still carries genuine bricking risk during the reflash itself), not attempted this session. Given that, and given the practical mitigations already in hand (avoid SDRAM in the fabric; expect and work around the flakiness; a physical replug reliably clears a stuck link), the more efficient path for anyone picking this up is likely what's already in motion: **try a different board with different debug hardware** (the ICEPi Zero, already on order as of this session, uses a fully open `trellis`-toolchain flow like this document's Colorlight examples and reportedly has enough RAM to sidestep this whole "Making Linux actually fit in 8MB" ordeal from earlier in this document -- see the ULX3S/Icepi Zero board-comparison section far above) rather than sinking more time into fixing six-year-old vendor firmware on this one.

**Why the ICEPi Zero/ULX3S probe is a structurally different bet, not just different hardware.** Per the ULX3S/Icepi Zero equivalents note earlier in this document (see "Install tools to flash" above), both boards use an **FTDI FT231X** chip instead of DAPLink -- a fixed-function USB-to-serial/JTAG bridge chip, not a general-purpose microcontroller running custom firmware at all. That's the direct structural contrast with everything diagnosed in this section: this whole investigation's leading suspect was DAPLink's *firmware* (a small vendor's customized, six-years-stale fork, seemingly crashing/rebooting under an early data burst -- see the upstream issues above). FT231X has no equivalent firmware layer to crash, being mature, high-volume, well-characterized silicon used across thousands of unrelated products -- reasoned grounds for expecting better reliability here, though untested at the time this was written. **Confirmed (2026-08-27):** see "Icepi Zero UART baud-rate stress test" near the end of this section -- 56 clean reflash-and-capture attempts with zero corrupted bytes from 9,600 up through 2,000,000 baud, no `<DAPLink:Overflow>`-style lockups at any point. The real trade-off: FT231X is single-channel, so JTAG and serial genuinely cannot be open at once (an architectural limit), versus DAPLink's separate HID/CDC interfaces which *can* theoretically be used concurrently but turned out to be unreliable in practice when actually tried (see the concurrent-serial-plus-JTAG hazard above).

## Cable swap test (2026-08-23): rules out this specific cable as a major factor

Same laptop, same two USB ports already alternated between earlier in this session, but a **different USB-C cable** -- one already known-good from other, unrelated projects. Fresh USB enumeration confirmed (`lsusb` showed a new `device` number and `path` back to the value seen in the very first fresh-boot test of this whole investigation).

**Raw-Verilog side: still fully reliable**, same as on the old cable -- 4 clean 600-byte bursts, a clean 30-second/~256KB continuous stream, JTAG staying healthy throughout. Not a surprising result (this side was already near-perfect), but a useful confirmation that the new cable didn't somehow make things *worse*.

**The real test -- the SDRAM-enabled LiteX SoC build that reliably overflows and never recovers -- came back identical to the old cable: 0 of 3 clean recoveries.** One attempt was total silence (0 bytes captured), two were the by-now-familiar clean-banner-then-`<DAPLink:Overflow>`-then-permanent-silence pattern, at the exact same `ROM:` line as every other attempt all session. **This cable swap does not fix the core issue.** Combined with the fact that this session had already been alternating between this laptop's two USB ports throughout (per the user, informally, not a controlled test), this weakens "it's just this one cable/port" as an explanation, though a different *laptop* entirely remains untested and is still the more informative remaining variable (already planned).

One messy, not-cleanly-reproduced side note from this batch: one early attempt (interrupted by a 2-minute shell timeout mid-run) showed a captured stream that looked like it was still coming from the *previous* bitstream (the raw-Verilog continuous generator) well after `openFPGALoader` had reported a successful reflash to the LiteX SoC -- i.e. a possible case of the reported-successful reflash not actually taking hold immediately. Not investigated further; worth watching for if it recurs, but not treated as a confirmed finding here.

## Bisecting the gap between raw Verilog and LiteX: is this hardware still appropriate for a Verilog-only tutorial?

By this point, the pattern was clear: **the bottom-up raw-Verilog UART tests are reliable; the full LiteX SoC boot is not.** That raises a real question for this document's own purpose (getting students up to speed) -- is this specific board/probe pairing still a reasonable platform to teach the raw-Verilog material on, or has the underlying hardware/probe instability made even that unsafe to rely on? Rather than guess, the gap was bisected from both directions: adding LiteX-like complexity to the raw-Verilog side, and stripping LiteX down toward the bare minimum ("a CPU running a program baked directly into on-chip block RAM," per the original framing of this test) -- to find out *where*, specifically, reliability breaks down, all files under `~/openfpga/uart_stress_test/pll_test/` and `~/openfpga/litescope_prbs_demo/minimal_soc.py`.

**Bottom-up: raw Verilog, with LiteX's own clock-generation machinery bolted on.** Using `ecppll` (bundled with the OSS CAD Suite / Project Trellis) to generate a real ECP5 PLL wrapper -- 25MHz in, 60MHz `sys` out plus a 180°-phase-shifted `sys_ps` out, exactly matching `colorlight_i5.py`'s `_CRG` -- and additionally driving the physical `sdram_clock` pin via the same `ODDRX1F` DDR-output primitive LiteX's own `DDROutput` lowers to (site `B9`), all with zero CPU and zero SDRAM controller behind it:

* **PLL + phase-shifted clock + `sdram_clock` pin, no CPU, no SDRAM controller: 7 of 8 clean.** Close to the plain-oscillator baseline (14 of 15 clean established earlier) -- the PLL/clock-generation machinery alone is not the differentiator.
* **The same, plus all ~48 real SDRAM bus pins (`a[11]`, `dq[32]`, `we_n`/`ras_n`/`cas_n`, `ba[2]` -- the exact pins `colorlight_i5.py`'s `"sdram"` platform resource uses) driven with a raw, dense toggle pattern at full `sys_clk` rate, still with no real SDRAM protocol/controller: 8 of 8 clean.** This is a real result, not a null one -- it directly tests and rules out "simultaneous switching noise from many SDRAM pins toggling" as a sufficient explanation on its own, since the pins here toggle just as much (arguably more randomly/densely) as they would under a real memory controller, with zero effect on reliability.

**Top-down: stripping LiteX to the bare minimum.** Built directly from `SoCCore` (not `BaseSoC`, which unconditionally adds SPI flash) -- VexRiscv CPU, BIOS ROM, 8KiB integrated SRAM, UART. No SPI flash, no LED chaser, no `main_ram`/SDRAM region at all -- about as close to "just a CPU running from on-chip block RAM" as the standard BIOS toolchain allows without writing custom startup code:

* **4 attempts: 1 overflow (at essentially the same relative point, just later in the now-shorter banner -- right at the "Initialization" section header, since there's no `FLASH:`/`SDRAM:` line to print first), 3 completely clean straight through to `litex>`.** Better than the earlier "no-SDRAM but still has SPI flash + LED chaser" `BaseSoC` test's roughly 2-of-3 clean-recovery rate, and meaningfully better than the full SDRAM-enabled `BaseSoC`'s effectively-zero rate across many attempts all session -- but still not as reliable as raw Verilog, even in this most-stripped-down form.

**What this rules out, and what's left standing.** Neither "PLL/multi-clock-domain activity" nor "SDRAM pins physically switching" is, by itself, sufficient to reproduce LiteX's much higher failure rate -- both were tested in isolation, on the same hardware, same session, and both came back close to the raw-Verilog baseline. Peripheral count matters somewhat (SPI flash + LED chaser removed measurably improved the SDRAM-free case's odds), but even the single most stripped-down real LiteX SoC -- just a CPU actually fetching instructions and executing BIOS software -- still overflowed once in four tries, something the pin-toggling-only tests never did across 16 combined attempts. **The remaining, most specific suspect is the VexRiscv CPU itself actually running -- its own reset-time cache-fill/wishbone-bus activity, or the specific bursty timing of software-driven UART writes (one CSR write per character, at whatever pace the CPU's fetch/decode loop allows) -- as opposed to a hardware state machine driving the same pins with perfectly uniform timing.** Not confirmed further this session (would need either LiteScope on the wishbone bus during boot, given the retrieval caveats documented below, or a scope on the CPU's own reset/cache-related signals).

**Answering the original question: yes, still appropriate for the raw-Verilog material specifically.** Every raw-Verilog test all session, across three variants and roughly 24 combined attempts (baseline UART burst, PLL+clock pin, PLL+48 SDRAM pins), stayed in the 87-100% clean range, with JTAG staying healthy through everything including deliberate rapid-fire reflash stress. **The LiteX/BIOS material is the part that's genuinely unreliable on this hardware** -- worth keeping that distinction explicit for students working through this document: the raw Verilog sections (PRBS7, the LED/button GPIO demo, this UART test) are a reasonable, reliable teaching platform on this exact board and probe; the LiteX-SoC-and-beyond sections (BIOS console, `litex_server`/LiteScope retrieval, and definitely full Linux) are where this specific hardware pairing's flakiness actually bites, and where the ICEPi Zero (or any FT231X-based alternative) is worth trying first before sinking more time in.

## Debugging without an oscilloscope: LiteScope

No scope was available to directly observe the `J17` pin during the DAPLink:Overflow investigation above, so this section covers the scope-free alternative that was actually used: **LiteScope**, LiteX's own in-FPGA logic analyzer. It captures internal digital signals (any Migen `Signal`, any width, at the design's own clock rate) into on-chip block RAM, then pulls the capture back to the laptop over the same USB link already used for everything else -- no external hardware beyond what this document already has. This section is written to be reusable for debugging *any* signal, not just the SDRAM question above -- the worked example below is a fast PRBS31 generator, chosen deliberately because it needs no external RAM at all (see "Keep in mind: no reliable SDRAM" below).

**How LiteScope works, in one paragraph.** `LiteScopeAnalyzer` is just another CSR-mapped peripheral, added to a SoC target file exactly like any other (`self.analyzer = LiteScopeAnalyzer(signals, depth=..., ...)`). It watches a list of signals every cycle, and on a configurable trigger condition (a rising/falling edge, a specific value match, or "fire immediately") it freezes a window of samples (`depth` deep, with a configurable pre-trigger `offset`) into a small dedicated block-RAM FIFO. Retrieval is a completely separate step, done from the laptop: `litex_server` opens a connection to the board (UART, JTAG, Ethernet, or USB -- whatever transport the SoC exposes) and acts as a Wishbone/CSR bus bridge; `litescope_cli` (or a hand-written Python script using the same `litex.RemoteClient`/`litescope.LiteScopeAnalyzerDriver` API) then configures the trigger, arms the capture, waits for it to complete, and downloads the samples as a VCD (viewable in GTKWave) or other formats.

### Worked example: capturing a fast PRBS31 generator

Full working files: `~/openfpga/litescope_prbs_demo/` (`litescope_prbs_demo.py` is the SoC target; `manual_capture2.py` is a hand-written low-level capture script -- see "Gotchas" below for why the high-level `litescope_cli` path didn't work reliably on this probe).

```python
from migen import *
from litex_boards.targets.colorlight_i5 import BaseSoC
from litex.soc.integration.builder import Builder
from litex.soc.cores.prbs import PRBS31Generator   # LiteX's own canonical PRBS31 core --
                                                     # no need to write custom Verilog for this.
from litescope import LiteScopeAnalyzer

class LiteScopePRBSSoC(BaseSoC):
    def __init__(self):
        BaseSoC.__init__(self,
            board                    = "i9",
            revision                 = "7.2",
            sys_clk_freq             = 60e6,
            integrated_rom_size      = 0x20000,  # see Gotcha #1 below
            integrated_main_ram_size = 0x10000,  # BRAM, not external SDRAM -- see note below
        )

        self.prbs = prbs = PRBS31Generator(n_out=8)   # fast: a new 8-bit value every sys_clk cycle

        counter = Signal(32)             # free-running reference count alongside the PRBS bits
        self.sync += counter.eq(counter + 1)

        self.analyzer = LiteScopeAnalyzer([prbs.o, counter],
            depth        = 2048,
            clock_domain = "sys",
            samplerate   = self.sys_clk_freq,
            csr_csv      = "analyzer.csv")   # per-signal name/width metadata for the retrieval side

def main():
    soc     = LiteScopePRBSSoC()
    builder = Builder(soc, csr_csv="csr.csv")
    builder.build(run=True)
    prog = soc.platform.create_programmer()
    prog.load_bitstream(...)  # same openFPGALoader-based load as every other example in this document

if __name__ == "__main__":
    main()
```

Build and flash exactly like any other raw target script (`python3 litescope_prbs_demo.py --build --load`, or `--build` then `openFPGALoader -b colorlight-i9 build/colorlight_i5/gateware/colorlight_i5.bit` separately). Once the board is up and sitting at the `litex>` prompt (or really, at any point after boot -- the CPU doesn't need to be doing anything in particular), retrieve a capture from the laptop:

```bash
litex_server --uart --uart-port=/dev/ttyACM0 --uart-baudrate=115200 &
litescope_cli --list                    # confirms the bridge works: prints "o" and "counter"
litescope_cli -r counter --dump prbs_capture.vcd   # trigger on counter's rising edge, save VCD
```

`--list` alone is a good quick health check for the whole pipeline (JTAG/probe, gateware, CSR bus, bridge) before trying an actual capture -- it round-trips real CSR reads without touching the more failure-prone trigger/storage state machine.

### Gotchas found getting this working on this board (all reusable beyond this specific PRBS example)

1. **Constructing a SoC directly in Python (not through `LiteXArgumentParser`) silently disables the BIOS.** `BaseSoC(...)` called directly, as in the target script above, only gets the kwargs explicitly passed to it -- every other `SoCCore.__init__` parameter falls back to *its own* raw Python default, not the CLI's default. `integrated_rom_size` defaults to `0` in `SoCCore.__init__` (BIOS/ROM disabled entirely, `cpu.use_rom` becomes `False`, and the builder silently skips compiling any BIOS software with no warning at all) versus `0x20000` when the same SoC is built through `python3 -m litex_boards.targets.colorlight_i5 ...`, whose `LiteXArgumentParser` always supplies that default. Symptom: a bitstream builds and flashes successfully, boots, but the "boot banner" you see over serial afterward is stale buffered bytes from a *previous* bitstream still sitting in the kernel's tty ring buffer, not real output from the new one (the kernel's `cdc_acm` driver keeps accumulating incoming bytes in the background even before an application opens the port -- see the picocom/pyserial note above). **Fix: always pass `integrated_rom_size=0x20000` (or whatever CLI default you'd otherwise get) explicitly when constructing a SoC directly in Python.**

2. **The trigger-memory "done" flag can appear permanently stuck on a first-ever capture, and it's easy to misdiagnose as a link/gateware bug when it's neither.** `analyzer.run()` (and `litescope_cli` under the hood) calls a `_load_trigger_terms()` step that disarms the trigger and polls `trigger_done` before loading new terms; reading LiteScope's own gateware (`litescope/core.py`'s `_Trigger` class) shows this `done` flag is driven by a `flushing` signal that only starts on a real high-to-low *edge* of `enable` -- which never happens on a SoC's very first capture, since the trigger was never previously armed. In practice this polling loop timing out looked exactly like a dead link (which this session had plenty of independent, real instances of) but forcing a manual `enable=1` then `enable=0` transition first didn't fix it either -- **the actual fix that worked was bypassing `_load_trigger_terms`/`.run()` entirely**: write the trigger term once (`trigger_mem_mask`/`trigger_mem_value`/`trigger_mem_write`, mask=0 for an unconditional "fire immediately" trigger), then arm directly (`storage_length`, `storage_offset`, `storage_enable.write(1)`, `trigger_enable.write(1)`), and poll `storage_done` instead of `trigger_done` -- this is exactly the pattern LiteScope's own simulation regression test (`litescope/test/test_analyzer.py`) uses, which turned out to be the more reliable reference than the higher-level driver/CLI path for a first-time capture on real, imperfect hardware.

3. **`storage_mem_level` (the "how many words are ready to read" register) is not trustworthy on a noisy link, and neither is any other individual CSR read -- verify this before trusting a capture.** A direct test on this specific probe -- writing 30 known values to a plain, unrelated scratch register (`ctrl_scratch`) and reading each straight back -- showed genuine mismatches, including corrupted reads starting with `0x3c` (ASCII `<`, the first byte of `<DAPLink:Overflow>` -- the same overflow string leaking into what should have been a clean binary CSR response). `mem_level` reading back as `134757436` (many times larger than the `depth=2048` capacity, clearly impossible) on this board was this same corruption, not a real hardware value. **Fix used here: never trust `mem_level` -- always read back a fixed, known word count** (`length_you_armed_with × ceil(storage_width/32)` raw 32-bit words -- see #4), and treat any multi-word capture as suspect (implausible jumps in a signal you know should be monotonic, like the free-running `counter` here, are the tell) until you've independently confirmed the link is behaving, e.g. with the same scratch-register round-trip test. **Run that round-trip sanity check first, every time, before trusting any capture** -- it's cheap and it's the single best predictor of whether a capture attempt is worth making right now.

4. **A capture "sample" and a raw 32-bit CSR word are not the same thing once your combined signal width exceeds 32 bits.** `depth`/`length`/`offset` in the LiteScope API all count *samples* (one PRBS+counter pair here, 40 bits wide combined). Each sample takes `ceil(storage_width / 32)` raw 32-bit CSR reads to retrieve (`swpw` in `litescope`'s own driver code) -- 2 in this example (8+32=40 bits). Reconstruct each logical sample from its raw words as `value = word[0] | (word[1] << 32) | ...` (low word first), then slice out each named signal by its declared bit position (signals are packed LSB-first in the order they're listed in the `LiteScopeAnalyzer([...])` call -- `prbs.o` first here means it occupies bits `[7:0]`, `counter` occupies bits `[39:8]`). Getting this wrong (e.g. treating raw words as samples 1:1) silently produces data that looks superficially plausible but is actually every other word of a real capture interleaved with garbage.

**Status, honestly: the mechanism above is confirmed correct end-to-end** -- `litescope_cli --list` reliably shows the right signal names, and the low-level arm/trigger/`storage_done` sequence reliably completes (verified: `storage_done` genuinely asserts, not just a stuck poll). **Getting a fully clean, uncorrupted multi-word data capture through *this specific* probe in its current degraded state was not achieved this session** -- reconstructed `counter` values jumped by amounts a real free-running 60MHz counter sampled every cycle cannot produce, consistent with exactly the same link-level byte corruption independently demonstrated by the `ctrl_scratch` round-trip test, not a flaw in the capture method itself. If picked back up on a healthier link (a different USB port/cable, or after whatever's degrading this probe over a session is addressed -- see the DAPLink:Overflow investigation above), the exact same code and sequence here should produce a clean capture with no changes needed.

**Keep in mind: no reliable SDRAM.** This example deliberately uses `integrated_main_ram_size` (internal block RAM) instead of external SDRAM, both because the PRBS generator itself has no need for external memory at all, and because the DAPLink:Overflow investigation above found external SDRAM's mere presence in the fabric is what prevents the serial console from recovering after the overflow -- a LiteScope-instrumented SoC still needs *some* way to reach `litex>`/stay up long enough for `litex_server` to connect, so avoiding SDRAM here isn't just tidiness, it measurably improves the odds of getting a usable session at all on this board/probe pairing.

## Controlling it from bare-metal C, from the laptop, and from Linux

* **Bare-metal C** (extending the `demo/main.c` from the previous section): `prbs31_seed_write(0x1);` to reseed, then repeated calls to `prbs31_state_read()` each advance the LFSR by one step and return the new 31-bit value — no polling loop needed around the read itself, since advancing is a side effect of reading.
* **From the laptop, no kernel driver at all**: `litex_server --uart --uart-port=/dev/ttyACM0` in one terminal, then `litex_cli --write prbs31_seed 1` / `litex_cli --read prbs31_state` in another — the same mechanism described in the "Debugging Techniques" section above, just pointed at a peripheral you wrote yourself instead of a stock one.
* **From Linux and Python** (once this SoC is rebuilt with `cpu_type=vexriscv_smp`, `cpu_variant=linux`, and booted the way the rest of this document describes): the `prbs31_seed`/`prbs31_state` CSR addresses appear in the auto-generated device tree the same way `switches_in`/`buttons_in` did above. Without a real kernel driver, the simplest access from userspace is `/dev/mem` + `mmap()` at the CSR region base (`0xF0000000`-relative, per the memory-map section above) offset by the register's address from `csr.csv`; the "Goal (incomplete)" list below still names writing an actual char-device kernel driver as the more production-appropriate next step.

This closes the loop the intro asked for: a pin on a PMOD header, through a hand-written Verilog module (or, via Path A, no separate HDL file at all), through a thin Migen/CSR wrapper, into the LiteX-generated device tree, and out the other end as a plain register read/write from C or Python — build-verified at every layer above, rather than the bare TODO this section used to be. The one remaining gap is the live, physically-observed confirmation (the LED PMOD actually chasing once you write to `prbs31_seed`) — blocked for now by the DAPLink issue noted above, not by anything wrong with the design.

## `<DAPLink:Overflow>` on a second (desktop) machine: same probe, opposite pattern (2026-08-23)

Same physical DAPLink probe and Colorlight i9 board, moved to a different computer's USB port directly (hostname `bell`, no hub) to isolate whether the failure travels with the probe/board or is host-specific -- the single most informative untested variable named at the end of the laptop investigation above. New test code lives in `~/openfpga/uart_stress_test/` (`uart_stress_test.v`, `build.sh`, `capture_serial.py`, `capture_raw.py`) since the laptop's own copy of this directory was scratch and never survived to be committed.

**First build attempt produced a false lead: yosys `chparam` does not reliably re-elaborate a baud-derived `localparam` after overriding a module `parameter`.** The initial `uart_stress_test.v` computed `BAUD_DIV` as a `localparam` from `parameter BAUD_RATE`, set post-`read_verilog` via `chparam -set BAUD_RATE ... -set ... uart_stress_test`. The resulting bitstream transmitted at roughly 8x the intended baud, which decoded on the host as a real, internally-consistent but heavily aliased byte sequence (each observed byte 8 apart from the next, not 1) -- worth remembering for any future parameterized raw-Verilog build on this toolchain: bake literal values into the source (`sed`-templated per build, what `build.sh` does now) rather than trusting `chparam` to propagate into a dependent `localparam`.

**Once that was fixed, the raw-Verilog continuous UART stream -- the case that was the single most reliable thing tested on the laptop (14/15 clean, no CPU, no LiteX, same J17 pin, same DAPLink probe) -- overflowed 5 out of 5 times on this desktop, always within about 490-556 bytes (~43-48ms) of the stream starting.** Re-testing the identical design at 9600 baud instead of 115200 produced zero overflows across three 15-second/~14,400-byte captures (with only 1-2 stray bytes per run, consistent with the laptop's own noted SET_LINE_CODING/baud-mismatch artifact, not a new failure mode). Byte position scaling with elapsed time rather than staying fixed as baud drops points at a **real-time USB-draining problem on this host**, not a fixed-size firmware ring buffer filling after a constant number of bytes -- the same DAPLink firmware/probe that drains 115200 baud fine on the laptop for 30-60 seconds straight cannot keep up with the identical byte rate here for even 50ms.

**The LiteX BaseSoC boot (stock `colorlight_i5 --board=i9 --revision=7.2 --build`, external SDRAM present) showed the opposite divergence from the laptop.** This exact configuration was the laptop's *worst* case -- 100% overflow, 0 recoveries across many attempts, even after a full reboot and a from-scratch LiteX reinstall. Here: of 2 completed attempts, one booted **completely cleanly to `litex>` with no overflow at all**, and the other hit `<DAPLink:Overflow>` at the identical spot (`ROM:` line) but **recovered on its own** and continued through SDRAM init, memtest, and on to a working `litex>` prompt -- a recovery rate this exact SDRAM-present configuration never once showed on the laptop.

**Net finding: the failure is not a fixed property of the probe or the board -- the host side changes both which cases fail and how badly.** On the laptop: raw Verilog near-bulletproof, LiteX-with-SDRAM reliably fatal. On this desktop: raw Verilog (the "easy" case) fails every time at 115200, while LiteX-with-SDRAM (the laptop's worst case) mostly works. That inversion argues against "DAPLink firmware crashing under load" or "SDRAM PHY pin noise" as the dominant mechanism (both are properties of the probe/board, which didn't change) and argues for **host-side USB scheduling/latency** -- how promptly this machine's USB stack services the CDC-ACM endpoint -- as a major, previously untested contributor. Concretely actionable: if this hardware needs to teach the raw-Verilog UART material reliably, this desktop's port is presently the *worse* choice for that specific material, despite being unambiguously better for the LiteX/BIOS material that mattered most on the laptop.

**A third data point worth having before trusting either machine's numbers: try a different USB port/controller on this same desktop**, not just laptop-vs-desktop, since a single port was tested here (no hub, but only one physical port tried) and USB controllers frequently differ port-to-port on desktop motherboards (chipset vs. discrete controller, different root hub). Not yet done.

**Session ended here by hitting the exact HID-corruption hazard the laptop investigation already documented**, not a new failure mode: after a shell timeout interrupted a JTAG/capture sequence mid-flight, `openFPGALoader --detect` started reporting `JTAG init failed: DAP connection in JTAG mode failed`, and `/dev/hidraw3` (this machine's DAPLink HID node) disappeared from `/dev` entirely while `lsusb` still showed the same device at the same bus/device/path -- i.e. the HID interface dropped out without a full re-enumeration, identical to the laptop's "concurrent serial+JTAG" and "reflash-while-something-else-attached" incidents. The serial (CDC) side was unaffected (`/dev/ttyACM4` stayed present and correctly permissioned throughout). Per the laptop's own findings, a software-only fix was never found for this; **a physical USB replug is the next step** before any further testing on this machine.

## Refined understanding of the HID-corruption hazard, and a second desktop USB port (2026-08-23, same day)

Re-tested after a physical replug into a **different port on the same desktop** (still no hub). Test code now lives permanently in `DroneSDR/fpga/openfpga_testing/` (`uart_stress_test/`, `bare_metal_gpio_demo/`) rather than `~/openfpga/`, specifically so it survives being wiped/recloned and moved between machines.

**Raw-Verilog continuous UART, this second port: 4/5 overflowed at 115200 (~490-514 bytes in), 0/3 overflowed at 9600 across ~43,000 bytes.** Same pattern as the first port (5/5 and 0/3 respectively) -- confirms this isn't one bad port, and reinforces the rate/USB-draining read from before.

**LiteX BaseSoC boot (SDRAM present), this second port: 1 clean boot + 1 overflow-then-recovered out of 2 completed attempts** -- again matching the first port's pattern, not the laptop's (0 recoveries ever, on this exact SDRAM-present config).

**The HID-corruption hazard happened a third time this session, and this time the actual trigger was caught directly: a Bash-tool command's own timeout (2 minutes, not raised for a multi-iteration hardware loop) fired while an `openFPGALoader` flash was in flight, and the resulting SIGTERM is what corrupted the probe -- not "concurrent serial+JTAG access" as the leading theory before now.** The laptop's original two incidents (reflash-while-`litex_term`-attached, and the deliberate concurrent-serial-plus-JTAG reproduction) both really were concurrency, but this session's repeat -- with the serial port already closed, nothing else touching the probe -- shows the hazard is broader than that: **any abrupt interruption of an in-progress JTAG operation on this probe, for any reason, appears able to leave it in this stuck state.** Practical fix used for the rest of this session: give every hardware-touching command a generous explicit timeout and keep multi-attempt loops short enough to finish well inside it, rather than relying on the tool's default. No further corruption occurred for the remainder of the session after adopting this.

## Bare-metal C on a LiteX SoC (GPIO tutorial), confirmed working with no PMODs attached (2026-08-23)

Implemented the "Bare-metal C on a LiteX SoC: stock GPIO peripherals" section above as an actual standalone target (`openfpga_testing/bare_metal_gpio_demo/colorlight_i9_gpio.py` + `gpio_pmods.py`), building on top of the stock `litex_boards.targets.colorlight_i5.BaseSoC` exactly the way that file's own `main()` already bolts on `_sdcard_pmod_io` post-`__init__` -- no subclassing or monkeypatching needed. Gateware build succeeded first try (~44s, timing closes at 63.7MHz on a 60MHz target); `csr.csv` confirmed `buttons_in`/`leds8_out`/`switches_in` at their own addresses as the tutorial predicts.

**`litex_bare_metal_demo --build-path=...` and the subsequent `make` both needed one adjustment not mentioned in the tutorial text: `make` must be given `BUILD_DIR=<absolute path to build/colorlight_i5>` explicitly** -- the generated `demo/Makefile`'s own default (`BUILD_DIR?=../build/`) only resolves correctly under a specific cwd/layout assumption that a fresh `mkdir`-and-copy workflow doesn't automatically satisfy. Added a `gpio` console command per the tutorial's `gpio_demo_cmd()`, with one deliberate deviation: **bounded to 20 iterations with a printed reading each time**, rather than the tutorial's `while(1)` with silent LED output -- since no PMODs are attached this session (kept unplugged specifically to keep their electrical effects out of the DAPLink reliability tests above), there'd otherwise be nothing observable and no way to end the command from a non-interactive script.

**A second, separate tooling gap: `litex_term` itself requires a real TTY on stdin** (`termios.tcgetattr`) and fails immediately (`termios.error: (25, 'Inappropriate ioctl for device')`) when driven from a non-interactive context -- confirmed even under a `script`-allocated pty, which fixed the termios error but then never caught the boot handshake in the available window, most likely because the handshake window had already elapsed between flashing and the wrapped process actually starting. This is the same class of problem this document already hit with `picocom`. Rather than fight `script`'s timing, wrote `serial_boot.py`: a from-scratch, dependency-free reimplementation of just the SFL upload protocol `litex_term` uses internally (`sfl_*` constants, frame format, `crc16` table lifted from `litex/litex/tools/litex_term.py` and verified byte-for-byte identical against the source's own hardcoded table before trusting it). No TTY needed, fully scriptable.

**Result, on real hardware, first full attempt after the tooling was sorted out: 2 of 5 flash attempts hit `<DAPLink:Overflow>` at the usual `ROM:` spot with no recovery inside a 20-25s window (consistent with the SDRAM-present failure rate established above), but the other 3 booted completely cleanly, uploaded the ~6.6KB `demo.bin` over the SFL protocol without a single CRC retry, jumped to it, and ran it.** The `gpio` command's output, all 20 iterations, every attempt: `switches=0xf buttons=0x0 -> leds8_out=0xf0 (readback=0xf0)` -- exactly the expected idle state with no PMODs attached (switches pulled up, read uninverted, so "up" reads as `1`; buttons pulled up then inverted in gateware, so "not held" also reads as `1` pre-inversion -> `0` post-inversion), and the `leds8_out` readback exactly matching what was just written. **This confirms the entire CSR pipeline end-to-end on real hardware -- C code on the actual VexRiscv core, through the auto-generated `csr.h` accessors, through the CSR bus, through the Migen polarity-inversion glue, out to real physical pins and back -- with nothing left unverified except the final "does a physically attached LED/switch/button actually match," which needs PMODs plugged back in to check.** Given this is otherwise working, that's a reasonable next step whenever the PMODs go back on.

## PMODs plugged back in: a real wiring bug, and its cause (2026-08-23, same day)

Board unplugged, PMODs physically plugged into the LED (`pmodk`) and button+switch (`pmodl`) headers, USB replugged. Same flash + `serial_boot.py` upload flow as above worked immediately (3 clean boots in a row this time). Running `gpio`, though, read `switches=0xf buttons=0x0` on every single iteration -- **unchanged from the no-PMODs-attached baseline, even with switches physically toggled between reads.** That's a materially different symptom from "wrong bit order" (which would still change *something* when a switch moves) -- it means the reading never responded to the physical hardware at all.

**Added a second diagnostic command, `ledtest`** (see `openfpga_testing/bare_metal_gpio_demo/`), to get an unambiguous read on the output side too rather than guessing from one static LED pattern under uncertain lighting: holds all-off, all-on, low-nibble, high-nibble, single-bit-0, and single-bit-7 for 4 seconds each, looping forever specifically so there's no race against how long it takes a human to go look at the board. (Blocking bug found and noted for next time: because it loops forever inside its own command handler, `console_service()` never regains control -- a command typed while it's running is silently dropped rather than queued, and only a fresh JTAG reflash gets back to a working prompt, not `reboot`.)

**Root cause, found by inspection once actually looking at the right header: the PMODs were plugged into the wrong physical connector.** The board's orientation this session (upside down, in a tighter space) didn't match the orientation used during the original raw-Verilog empirical pin verification earlier in this document, and it wasn't visually obvious which header was actually P6 from the new angle. Once moved to the correct header, `ledtest`'s all-off/all-on phases showed a clear toggle and the single-bit phases showed one LED moving to a distinctly different physical position -- confirming real, per-bit electrical control, not just "something is stuck on." Re-running `gpio` then read `switches=0x9` (binary `1001`) with two (middle) switches held down, confirmed by direct comparison against the actual physical switch positions to be exactly correct under the LSB-first convention established in the raw-Verilog section (`switches[3]`=leftmost .. `switches[0]`=rightmost).

**Net result: the "Bare-metal C on a LiteX SoC" GPIO tutorial is now confirmed fully correct end-to-end on real hardware, PMODs included** -- gateware pin mapping, polarity inversion, CSR plumbing, and the C accessor macros all check out. The only bug found this session was a physical one (wrong header for the board's current orientation), not anything in the LiteX/Migen/C code. **Lesson for next time this board changes orientation or moves to a tighter space: verify which header is actually P6 before assuming a software bug** -- a "reading never changes at all" symptom (as opposed to "reading changes but looks wrong") is the tell that points at disconnection/wrong-header rather than a bit-order or polarity bug in the code.

**Follow-up live-interaction test, same day: added a `gpiolive` command** (continuous version of `gpio_demo_cmd`, prints only on change to avoid flooding the link) so the user could physically press each button and flip switches over an extended period rather than a fixed 20-iteration/~4s window. Result: all four buttons independently toggled their own bit (`0x1`, `0x2`, `0x4`, `0x8`), and switches tracked cleanly through several manual changes -- confirmed correct by direct comparison against the actual physical actions taken. Interesting incidental data point: after enough sustained print traffic from repeated button presses, the link eventually hit `<DAPLink:Overflow>` anyway -- consistent with everything already established about this link's behavior under sustained output, not a new finding, but a reminder that "prints only on change" reduces but doesn't eliminate the exposure if the change rate stays high enough for long enough.

## Retrospective: how much of the DAPLink:Overflow/replug trouble was the Bash-tool-timeout bug, and can the raw-Verilog examples be made reliable? (2026-08-23)

Asked directly, after the GPIO work above was done, to separate two failure classes that had been getting conflated: `<DAPLink:Overflow>` itself, versus the "JTAG stuck, needs a physical replug" hazard.

**`<DAPLink:Overflow>` itself: unrelated to the timeout bug, 0% attributable to it.** Every overflow observed happened during an actively-running, uninterrupted capture -- nothing was killed, no tool timed out, the link just organically died mid-stream. This is a real, reproducible, rate-dependent link limitation, independent of any tooling mistake.

**The "need to physically replug" hazard, in this session specifically: both incidents traced directly to the Bash tool's own default 2-minute timeout firing while `openFPGALoader` was mid-flash**, not to concurrent serial+JTAG access (the leading theory from the laptop investigation) -- the serial port was already closed both times this happened here. Once hardware-touching commands were given explicit longer timeouts and multi-attempt loops were kept short enough to finish within them, this stopped happening entirely for the rest of the session (roughly a dozen more flash/upload cycles with zero further corruption). Best unifying read across both this session and the laptop's original incidents: this probe's JTAG state machine doesn't handle *any* abnormal termination of a transaction gracefully -- concurrent access and an external kill signal are just two different ways to produce an incomplete transaction, and either one trips the same stuck state.

**Can the raw-Verilog UART example be made reliable? Substantially, not perfectly.** Tested by dropping the design's baud rate from 115200 to 9600 and re-running a large batch: at 115200, 9 of 10 attempts across two ports overflowed; at 9600, across 16 total attempts (6 from earlier in this session plus a fresh batch of 10), **15 were clean and 1 still overflowed** -- at byte offset 494, landing in almost the identical byte-count range as the 115200 failures despite taking roughly 12x longer in wall-clock time to get there. That's a genuine, large improvement (roughly a 15x reduction in failure rate, not a 100x-or-better elimination), and it's worth being precise about that rather than overclaiming a full fix: **9600 baud is a strong mitigation, not a guarantee.** The one residual failure landing at nearly the same byte offset as the 115200 case, despite the very different elapsed time to reach it, is a loose thread worth flagging for whoever picks this up next -- it sits awkwardly with the "pure real-time USB-draining" theory (which would predict the failure point scaling with wall-clock time, not byte count, as baud drops) without fully overturning it on a single data point. Practical takeaway for teaching the raw-Verilog material on this specific board/probe/host combination: build and read at 9600 baud rather than the default 115200, and don't promise students it will never fail -- just that it will very rarely fail instead of usually failing.

## A sharp follow-up question, and a hypothesis that got disproved within the hour (2026-08-23, same day)

Asked directly: if LiteX's BIOS also runs its UART at the default 115200 baud, why would this desktop's raw-Verilog test fail *more* often (~90%) than LiteX's SDRAM-present boot (which mostly succeeds here), when the laptop showed the exact opposite bias? Baud rate alone can't explain a same-line-rate divergence that runs in opposite directions on two hosts.

**First hypothesis, proposed and then tested within minutes: maybe it's about total exposure/duration, not baud** -- my raw-Verilog "continuous" test runs indefinitely (tens of thousands of bytes over 8-15s), while LiteX's actual failure point is very early (right at the `ROM:` line, comparable in byte count to where raw-Verilog itself tends to fail, ~490-556 bytes) and its whole banner is only a few hundred bytes to a couple KB. Reasoning: if there's a brief early "vulnerable window" both designs have to get through, maybe surviving it once (LiteX's short banner) is easier than surviving it and then continuing for tens of thousands more bytes (the continuous test).

**Tested directly, and the hypothesis did not survive contact with data.** Built a *bounded* one-shot 600-byte burst (same design, `BURST_LIMIT=600` instead of continuous) at 115200 and ran it 5 times: 4 of 4 successfully-captured attempts overflowed at **exactly byte offset 524**, every single time (the 5th attempt captured 0 bytes, most likely the known capture-timing race for a fast one-shot burst rather than a different outcome) -- statistically indistinguishable from the continuous stream's own ~90% failure rate and near-identical failure offset. Shortening the burst to stop right after the danger zone did not improve reliability at all. **Duration/total-byte-count is not the explanatory variable; something deterministically related to being ~500-plus bytes into a 115200 transmission is, regardless of whether more bytes are coming after that point.**

**Best remaining (unconfirmed) partial explanation: duty cycle, not bit rate.** My raw-Verilog design starts each byte's start bit on the very next baud tick after the previous byte's stop bit -- zero inter-byte gap, 100% duty cycle, the maximum possible sustained throughput at that baud. LiteX's BIOS prints via software (`putchar()`-style: check TX-ready, write, repeat), which almost certainly has non-zero per-character CPU overhead -- its *average* sustained throughput at the same nominal 115200 bit rate is plausibly somewhat lower than a zero-gap hardware bit-banger's. If the underlying hazard is sensitive to sustained aggregate throughput rather than pure per-bit rate, a lower-duty-cycle source would be more forgiving on a given host than a 100%-duty-cycle one. **This is a plausible contributor, not a confirmed mechanism, and it does not by itself explain the laptop's opposite bias** -- under a pure-throughput theory, the higher-duty-cycle raw-Verilog design should be the *worse* case on any host, not the better one on the laptop and the worse one here. Confirming or refuting this for real would need a scope/logic analyzer comparing the actual inter-byte gap structure of LiteX's real console output against this raw-Verilog design's, on both hosts -- not something determinable from serial-capture behavior alone. **Left as a genuinely open question for whoever picks this up next.**

## Icepi Zero UART baud-rate stress test: how fast can this FPGA-to-FT231X link actually go? (2026-08-27)

The "structurally different bet" note earlier in this document (see "Why the ICEPi Zero/ULX3S probe is a structurally different bet, not just different hardware") reasoned that the Icepi Zero's FTDI FT231X should be more reliable than the Colorlight i9's DAPLink probe, since FT231X is fixed-function silicon with no firmware layer to crash or overflow the way DAPLink's does — but flagged that as untested reasoning, not a measurement. Everything else in this document's Icepi Zero work all session (a 15-minute, zero-frame-error Linux serial-boot upload; every raw-Verilog and LiteX tutorial above) is consistent with that reasoning, but none of it was a dedicated stress test. This section runs the same methodology as the i9's `uart_stress_test.v` investigation above — a raw-Verilog UART bit-banger, no LiteX/CPU/BIOS, transmitting continuously, checked across repeated reflash-and-capture attempts — directly against the Icepi Zero, and pushes past the two baud rates this document has actually used (9600, tested in the i9 investigation, and 115200, the default for everything Linux-related) to find where the link actually breaks.

**Reused, unmodified: `uart_stress_test.v`** from the i9 investigation — it was already generic (`clk`/`tx`/`led` ports only, `CLK_FREQ`/`BAUD`/`BURST_LIMIT` parameters, no board-specific pins hardwired in). Only the `.lpf` and build parameters changed for the Icepi Zero: `clk` → site `M1` (50 MHz, not 25 MHz), `tx` → site `K15` (the same physical pin LiteX's own BIOS console uses on this board), `led` → site `E13`, and the nextpnr device/package swapped to `--25k --package CABGA256 --speed 6` (same as every other Icepi Zero raw-Verilog build above).

**Methodology, adapted for one Icepi Zero-specific wrinkle.** `BURST_LIMIT=0` (continuous transmission) was used throughout, not the i9 test's fixed-size bursts — deliberately, to sidestep a real race this same session already hit and documented (see "Default target: Icepi Zero"'s shared-USB-device gotcha): the FT231X is a *single* USB device for both JTAG programming and the UART, so the serial port cannot be held open across a reflash the way it sometimes could with DAPLink's genuinely separate interfaces. That forces "reflash first, fully releasing the port, then open the serial port" ordering — and a one-shot fixed-size burst could finish transmitting before the host even attaches. Continuous transmission sidesteps this: whatever window gets read after opening the port is still a valid sample of an ongoing, steady stream. Each attempt: reflash, a brief 150ms settle, then open `/dev/ttyUSB0` via `pyserial` and read for 350ms (capped at 8192 bytes), checking every received byte equals the expected `0x55` pattern. A brief startup transient — a handful of leading non-`0x55` bytes right at connection time — was treated as an established, benign artifact and excluded before judging correctness, the same precedent this document's i9 UART test already set ("at most a single stray null byte at the very start of a run, self-clearing"); anything wrong *after* that leading transient counts as a failure. 8 reflash-and-capture attempts per baud rate.

**Bit-rate matching, done properly, learning from the i9 investigation's own baud-mismatch pitfall.** The i9 section above ran into a real ambiguity about whether a `--uart-baudrate` build flag and a host-side read rate were actually talking about the same physical rate at all, given DAPLink's CDC-ACM `SET_LINE_CODING` quirk. FT231X has no such ambiguity — it's a real hardware UART bridge, and setting a baud rate via the host's `ftdi_sio` driver programs the chip's actual divisor registers directly, the same mechanism already relied on for every other Icepi Zero test in this document. The one thing that *does* need care: `uart_stress_test.v`'s `BIT_DIV = CLK_FREQ / BAUD` is plain Verilog integer division, so at a 50 MHz clock a requested baud rate that doesn't divide evenly gets silently rounded to whatever the nearest achievable rate is (e.g. a nominal "2,100,000" request yields `BIT_DIV=23`, an *actual* transmitted rate of 2,173,913 — a 3.5% difference from the nominal ask). The host side was set to match this *actual* achieved rate exactly for every test, not the nominal one, so any failures below are not simply host/device baud mismatches.

**Results:**

| Nominal baud | Actual (FPGA-side, quantized) | Result (8 attempts) |
|---|---|---|
| 9,600 | 9,600 (exact) | 8/8 clean |
| 115,200 | 115,207 | 8/8 clean |
| 230,400 | 230,414 | 8/8 clean |
| 460,800 | 462,962 | 8/8 clean |
| 921,600 | 925,925 | 8/8 clean |
| 1,500,000 | 1,515,151 | 8/8 clean |
| 2,000,000 | 2,000,000 (exact) | 8/8 clean |
| 2,100,000 | 2,173,913 | 0/8 (garbled — bytes arrive, none decode as `0x55`) |
| 2,250,000 | 2,272,727 | 0/8 (garbled) |
| 2,500,000 | 2,500,000 (exact) | 0/8 (garbled) |
| 2,750,000 | 2,777,777 | 0/8 (garbled) |
| 3,000,000 | 3,125,000 | 0/8 (silent — no bytes received at all, most attempts) |
| 4,000,000 | 4,166,666 | 0/8 (silent) |

**Confirmed on real hardware: this link is clean and fully reliable — zero corrupted bytes across 56 total reflash-and-capture attempts — at every rate from 9,600 up through 2,000,000 baud**, spanning more than two orders of magnitude, including both of the two rates this document actually uses elsewhere (9,600 in the i9 investigation, 115,200 for every Icepi Zero Linux/tutorial serial link in this document). This is a direct, positive confirmation of the "structurally different bet" reasoning: across 48 clean attempts at the six rates from 9,600 to 1,500,000 alone, this session never saw anything resembling the i9's DAPLink `<DAPLink:Overflow>` behavior — no dropped links, no corrupted bytes, no reflash-triggered lockups requiring a physical replug.

**The breakdown is a real cliff, not a gradual degradation, and it has two distinct failure modes.** Between 2,000,000 (clean) and 2,100,000 (broken), reliability falls off a cliff rather than degrading gradually — no baud rate in this sweep showed a partial pass rate (e.g. 3/8 or 5/8); every rate was either 8/8 clean or 0/8 failed. From roughly 2.1M through 2.75M, the failure mode is **garbled**: the host receives a full window of bytes, but none of them decode as the expected `0x55` — consistent with a genuine bit-rate mismatch or framing breakdown somewhere in the chain, though this test doesn't isolate whether the bottleneck is the FPGA's own coarse-grained `BIT_DIV` bit-timing (as low as 22-23 clock cycles per bit at these rates, versus 5208 at 9600 baud) or the FT231X's own internal baud-rate generator running out of precision at these rates (plausible, since even FTDI's own datasheet-rated maximum for the FT-X series is quoted around 3 Mbaud with less headroom than lower, more commonly-used rates) — untangling those would need an oscilloscope or logic analyzer on the `K15` pin directly, the same kind of direct electrical measurement this document's i9 investigation flagged as its own next step and never had available. At 3,000,000 baud and above, the failure mode changes again, to **silent** — most attempts received zero bytes at all, as if the host-side open/configure step itself couldn't establish a working link at that rate, rather than establishing one that then decoded incorrectly. That mode change is itself a useful data point: it suggests 3 Mbaud is closer to (or past) a hard ceiling in the FTDI driver or chip itself, not just "the same graceful degradation, more of it."

**Practical takeaway for this document: 2,000,000 baud is a solid, empirically-confirmed ceiling for the raw physical link** — nearly 17× the 115,200 baud everything else in this document runs at, with zero corrupted bytes across every rate tested up to that point.

**Correction, tested directly on the actual Linux tutorial (2026-08-27): this raw-link ceiling does *not* carry over to `litex_term`'s real serial-boot protocol.** The paragraph above originally speculated that a future tutorial could just point `--uart-baudrate` at something near 2,000,000 for a faster Linux upload — tested, and wrong. `litex_term`'s bidirectional, windowed upload protocol (used for the actual four-file Linux transfer, not this section's one-way bit-banger) failed immediately with repeated "serial frame error" during upload calibration at 921,600, 1,500,000, and 2,000,000 alike, never completing even given several minutes. Only 460,800 negotiated cleanly and completed end-to-end (278 seconds vs. 115200's ~14-15 minutes, about 3.2× faster — short of the 4× the baud ratio alone would suggest, consistent with USB round-trip/ack overhead being the real bottleneck for this chattier protocol, not wire bit-rate). See "A faster baud rate for this same stock-image transfer" in the Linux-boot section above for the full result. **The lesson: a clean one-way raw-link stress test like this one bounds the hardware, but doesn't predict a real bidirectional protocol's actual ceiling — that has to be tested directly, on the actual traffic pattern that matters.**

# Linux vs. Zephyr: Choosing the Right Software Stack

Both Linux (this document) and Zephyr are legitimate targets for a soft-core RISC-V FPGA SoC. The choice is about which matches the requirements of the application.

## What Zephyr Is

Zephyr is a real-time operating system (RTOS) maintained by the Linux Foundation. It is not a stripped-down Linux — it shares essentially no code with Linux. It is a from-scratch RTOS designed for resource-constrained embedded systems: microcontrollers with 64 KB to a few MB of RAM, no MMU, and hard real-time requirements.

Key characteristics:

* **Statically linked**: Zephyr applications, the RTOS kernel, and all drivers compile into a single ELF binary. There are no shared libraries, no dynamic loading, no processes.
* **No MMU required**: Zephyr runs in physical address space. Any RISC-V core works — PicoRV32, NEORV32, VexRiscv without the Linux SMP variant. You don't need to implement or configure virtual memory.
* **Deterministic scheduling**: Zephyr uses a preemptive, priority-based scheduler. The worst-case interrupt latency is bounded and measurable. Linux's scheduler optimizes for throughput, not latency; even with the `PREEMPT_RT` patch, worst-case latency is hundreds of microseconds. Zephyr's is typically single-digit microseconds.
* **Device Tree**: Zephyr uses the same `.dts` format as Linux for hardware description. The `Kconfig` system (also shared with Linux) configures which subsystems are included. This is the strongest common thread between the two stacks.
* **Much smaller resource requirement**: A minimal Zephyr application fits in 64 KB flash and 8 KB RAM. A minimal Linux fit is ~4 MB flash and ~8 MB RAM; a comfortable working environment is 32+ MB RAM.
* **LiteX support exists**: Zephyr has a `litex-vexriscv` board target. Drivers for LiteX UART, timer, SPI, and I2C are in the upstream Zephyr tree. You can boot Zephyr on the same LiteX SoC used for Linux without changing the gateware, just by flashing a different binary.

## When to Choose Zephyr

Choose Zephyr when:

* **Hard real-time is the primary requirement**: Sampling an ADC at exactly 1 MHz with <1 µs jitter; generating a PWM waveform with cycle-accurate timing; responding to a GPIO interrupt within 10 µs guaranteed. Linux cannot provide this without significant OS-level modifications.
* **The FPGA is acting as a smart controller, not a general-purpose computer**: Motor drives, sensor fusion, protocol converters, PID loops, radio MAC layers. The CPU's job is responding to hardware events, not running user applications.
* **RAM is scarce**: If you have to fit your entire system into 4 MB of SDRAM or even on-chip BRAM, Zephyr is the only viable choice. A minimal LiteX SoC for Zephyr can run entirely from 64 KB of block RAM — no external memory chip needed.
* **OpenAMP / co-processor model**: A common architecture pairs a Linux host (Zynq ARM, or a separate computer) with a Zephyr co-processor on the FPGA soft-core. Linux handles networking, filesystems, and user interaction; Zephyr handles the real-time control loop. They communicate over shared memory or a serial link using the OpenAMP / RPMsg protocol.
* **Power budget is very tight**: Zephyr can put the CPU into a sleep state between events. Linux has kernel threads and timers running continuously, making sub-milliwatt power modes difficult.
* **Simpler, faster iteration**: A Zephyr application compiles in seconds (no kernel build step, no rootfs build step). Flash it, it boots in milliseconds. The full LiteX Linux build cycle from scratch is hours.

## When to Choose Linux (this document)

Choose Linux when:

* **You need TCP/IP networking with the full BSD socket API**: Zephyr has a networking stack, but it is limited compared to the Linux kernel's. Python's `socket`, `requests`, `asyncio`, and every networked library work on Linux without porting.
* **Python scripting and dynamic libraries**: Zephyr has no dynamic linker, no Python runtime, no pip. If the goal is a system where you SSH in and run a Python script against hardware registers, Linux is the target. Zephyr requires you to write everything in C.
* **USB host mode** (connecting USB devices): The Linux USB subsystem supports thousands of device classes via generic drivers. Zephyr has USB device support but limited USB host support.
* **A filesystem, persistent storage, and package installation**: Reading and writing files, databases, configuration storage. Zephyr has LittleFS for embedded flash, but no concept of a hierarchical filesystem with permissions, mounts, etc.
* **Multiple concurrent independent user processes with isolation**: Running a web server, a data logger, and a signal processing pipeline simultaneously as separate processes with memory protection. Zephyr has cooperative and preemptive threads but no process isolation.
* **Rich debugging**: `gdb`, `strace`, `perf`, `valgrind`, `ftrace`. These are Linux tools. Zephyr debugging is via JTAG/OpenOCD + GDB only, without the runtime instrumentation available on Linux.
* **The goal is understanding the full system**: This document's stated goal. Linux forces every component to be named and connected: kernel config, device drivers, device tree, system calls, userspace libraries. Zephyr's monolithic binary blurs these boundaries by design.

## Toolchain Differences

| | Linux (this document) | Zephyr |
|---|---|---|
| Cross-compiler | `riscv64-unknown-elf-gcc` or `riscv64-linux-gnu-gcc` | `riscv64-zephyr-elf-gcc` (from Zephyr SDK) |
| Build system | `make` (kernel), `make` (Buildroot) | CMake + `west` meta-tool |
| Hardware description | Device tree (auto-generated by LiteX) | Device tree (manual or auto-generated) |
| Configuration | `make menuconfig` (Kconfig) | `west build -b litex_vexriscv` |
| Boot time | ~30–60 seconds (real wall clock, even though Linux thinks it's 5s) | <1 second |
| Debug | SSH, gdb, strace, perf | OpenOCD + GDB via JTAG |
| Python access to hardware | `litex_cli` (no kernel driver needed) or write a char device driver | Not applicable (no Python) |

## Summary Recommendation

For drones and RF, the goals split naturally:

* **Flight control, motor commands, sensor sampling loops**: Zephyr on a small RISC-V core or ARM microcontroller. Hard real-time, no OS overhead, direct register access.
* **Signal processing pipeline orchestration, SDR control, data logging, remote access, Python analysis**: Linux on LiteX or (for more performance) a Zynq. File systems, networking, Python.
* **Learning how a computer works from gates to Python**: Linux on LiteX (this document). There is no substitute for having read every piece of code in the stack.

Zephyr and Linux are not competitors in the same design space — they answer different questions. The interesting systems use both.



---

# Beyond Linux: MicroPython, Zephyr, and Future Directions

* **Python on Linux** (near-term, high priority): Buildroot can include CPython. Add it in `make menuconfig` under *Target packages → Interpreter languages → python3*. Note that `pip` and pre-built binary wheels for `riscv32` are essentially nonexistent — packages must be built from source inside Buildroot or cross-compiled. `numpy`, `scipy`, and any C-extension package requires explicit Buildroot recipe support. Pure-Python packages (`requests`, `pyserial`, etc.) work without modification.
* **MicroPython on LiteX**: MicroPython has been ported to LiteX and runs *without* Linux, directly on the LiteX BIOS hardware. This is a useful intermediate: more interactive than bare C firmware, much lighter than full Linux. See <https://enjoy-digital.github.io/posts/micropython-on-litex/> and <https://github.com/litex-hub/micropython/tree/litex-rebase/ports/litex>.
* **Zephyr on LiteX**: The `litex-vexriscv` board target is in the upstream Zephyr tree. `west build -b litex_vexriscv samples/hello_world` should produce a binary that boots on the same LiteX gateware used for Linux. Good starting point for real-time control co-processor experiments.

# What This Document Still Needs (Opinionated Gaps)

The following are significant missing pieces, ordered by how much they would contribute to the stated goals. An ideal version of this document — suitable as the basis for a graduate or advanced undergraduate course where the philosophy is "understand every layer, use only open tools, run everything from a terminal" — would cover all of these.

## 1. Cross-Compilation: Two Different Toolchains for Two Different Purposes

The document uses `riscv64-unknown-elf-` in one place without explaining what it is or why it's different from `riscv64-linux-gnu-`. This matters:

* **`riscv64-unknown-elf-gcc`** (also called the "bare-metal" or "newlib" toolchain): Targets a RISC-V processor with no OS. Links against `newlib` (a minimal C library for embedded targets). Output: a standalone ELF binary suitable for the LiteX BIOS, OpenSBI, or a Zephyr application. Use this to compile anything that runs before or without Linux.
* **`riscv64-linux-gnu-gcc`** (also called the "Linux" toolchain): Targets Linux userspace. Links against `glibc` or `musl`. Output: a dynamically linked ELF that expects to be loaded by the Linux kernel via `execve()`. Use this (or the Buildroot-internal cross-compiler) to compile programs that run on top of your LiteX Linux.

Buildroot generates its own internal cross-compiler tuned to the exact C library and architecture variant it's building for. The path is `output/host/bin/riscv32-buildroot-linux-gnu-gcc`. Use this to compile any C code you want to include in the rootfs.

## 2. FPGA Configuration: How the ECP5 Loads Its Bitstream

The document tells you how to write to flash, but not what happens next. The ECP5 configuration process:

1. On power-up, the ECP5's internal configuration logic reads the `CFG_MD` pins to determine the boot mode (active serial SPI is the default on most boards).
2. It drives the SPI flash CS and CLK lines, reads the bitstream from address 0x0 of the flash at 1–25 MHz.
3. It streams the bitstream into the SRAM configuration cells, setting every LUT equation, every routing mux, every I/O buffer type and direction.
4. Once the entire bitstream has been loaded and verified (CRC check), the `DONE` pin goes high and all I/O pins are released from their power-up tristate to their configured functions.
5. VexRiscv's program counter is set to the BRAM address where the LiteX BIOS is mapped, and execution begins.

The total time from power-up to BIOS prompt for a 5 Mbit ECP5-45F bitstream at 25 MHz SPI is about 10–20 ms. This is why the ECP5 appears to "just work" after a power cycle.

## 3. BRAM vs. SDRAM: The Memory Map

VexRiscv at reset sees a flat physical address space. Where things live:

* `0x00000000`: BRAM (on-chip block RAM, 64 KB by default) containing the LiteX BIOS. Executes immediately on reset, no DDR training needed.
* `0x40000000` (or similar): SDRAM, available after the BIOS completes LiteDRAM initialization and training.
* `0xF0000000` (or similar): CSR region — all peripheral control registers.

The exact addresses are in `build/colorlight_i5/csr.json` and `build/colorlight_i5/dts/colorlight_i5.dts` after a build. The linker script for the BIOS is at `litex/soc/cores/bios/linker.ld` and constrains the BIOS to fit in BRAM. The Linux kernel loads into SDRAM and is told its base address via the Device Tree.

**Resolved: both paths exist, and this document already covers both.** Over serial/USB: the "Loading Linux over Serial" section above -- `litex_term --images=boot.json` streams `Image`/`.dtb`/`opensbi.bin`/`rootfs.cpio.gz` into SDRAM at their target addresses over the UART, one frame at a time, triggered by the BIOS's serial-boot handshake. From SPI flash: the "Flash (load) the bitstream" section's Alternate 2 (`openFPGALoader -f`) writes the images to the non-volatile SPI flash instead of just the bitstream, and the BIOS's own boot sequence (seen in the captured boot log, "Booting from flash...") reads them from flash into SDRAM automatically on every power-up -- no laptop connection needed after that point. There's no third path -- USB in this context *is* the serial/UART connection (the DAPLink/FTDI chip bridges USB to UART), not a separate debug-only channel.

**Partially resolved -- most of what this TODO asks for already exists elsewhere in this document, just not consolidated into one section**: the LiteX BIOS's role is covered in "Interlude: What the `.bit` file contains" and "Goal 8: Boot Process" below (bring up SDRAM, probe serial/network/flash, load OpenSBI+kernel); Buildroot is covered in "Goals 9 & 10: Kernel and Filesystem from Source" below (what it is, why it's preferred over Yocto, the `litex_vexriscv_defconfig` starting point); the full boot sequence (BIOS → OpenSBI → kernel → initramfs, no U-Boot) is "Goal 8" below in detail, including why there's no U-Boot/FSBL in this stack. What's still genuinely missing, and would need its own real research pass rather than a short fix here: exactly how the initramfs unpacking mechanics work internally (kernel-side `cpio` extraction, `/sbin/init` handoff) and precisely what lives at which SPI flash offset for the permanent-boot case -- flagging that gap rather than guessing at it.

## 4. How to Actually Use Linux Once It Boots

The document shows how to boot Linux but not how to use it as a development environment:

* **Login**: `root`, no password (default BusyBox initramfs).
* **Compile a C program on the host and run it on the target**: Cross-compile with Buildroot's cross-compiler (`output/host/bin/riscv32-buildroot-linux-gnu-gcc hello.c -o hello`), then transfer via `litex_term`'s file upload feature or over Ethernet (`scp` if SSH is enabled in the rootfs).
* **Install Python packages**: Pure-Python packages can be installed with `pip install` if Python and pip are included in the Buildroot config. C-extension packages (NumPy, etc.) must be cross-compiled inside Buildroot's package system — most do not have pre-built `riscv32` wheels on PyPI.
* **Enabling SSH**: Add `openssh` in Buildroot's menuconfig under *Target packages → Networking applications*. Then `ssh root@<ip>` from your laptop (Ethernet must be configured).

## 5. Debugging Techniques

Nothing in this document explains what to do when something doesn't work. The main tools:

* **UART console**: The most valuable debugging tool. Every `printk()` in the kernel, every Python `print()`, every BIOS message comes out the UART. `picocom -b 115200 /dev/ttyUSB0` is always the first thing to open.
* **`litex_server` + `litex_cli`**: Even if Linux is not booting, you can run `litex_server` and inspect peripheral registers from your laptop to verify the gateware is working. This is the equivalent of a logic analyzer for the SoC bus fabric. Resolved -- full mechanism (host-side process, `--uart`/`--udp`/`--pcie`/`--jtag`/`--usb` transport backends, and why it never runs on the RISC-V itself) is covered in "How LiteX manages peripheral addresses → device tree → Python" above.
* **OpenOCD + GDB**: For debugging the BIOS or a bare-metal program running on VexRiscv before Linux boots. VexRiscv implements the RISC-V Debug Specification; OpenOCD connects to it via JTAG. The JTAG interface is the STM32 DAPLink on the carrier board. `riscv64-unknown-elf-gdb` connects to OpenOCD's GDB server. You can set breakpoints, single-step, and inspect registers.
* **Simulation debugging**: Add `--trace` to `./sim.py` to dump a VCD waveform of the simulation. Open in GTKWave and inspect every bus transaction, including the Wishbone and CSR buses. Resolved -- covered in "Goal 6: SoC Peripherals" below (Wishbone is the primary interconnect all peripherals attach to, VexRiscv is the Wishbone master; CSR is a lightweight secondary bus for slow control/status registers, reached via a Wishbone-to-CSR bridge) and the CSR-register definition above. Short version of the address-space mapping: it's one flat linear address space from the CPU's perspective (`0x00000000` ROM, `0x40000000` SDRAM, `0xF0000000` CSR region, per the memory map earlier in this section) -- the Wishbone-to-CSR bridge is just what routes CSR-region addresses onto the separate, simpler CSR bus instead of the main Wishbone fabric once a transaction lands in that address range, invisibly to software.
* **LiteScope** (hardware logic analyzer): For debugging on actual hardware, add a `LiteScopeAnalyzer` peripheral to the LiteX SoC to capture signals from the running FPGA into BRAM. After triggering, `litescope_cli` reads out the capture and saves it as a `.vcd` file, viewable in the same GTKWave used for simulation. This is the hardware-side counterpart to simulation waveform viewing — the equivalent of Vivado's ILA — and requires no external logic analyzer. See the "Block Diagram Gap" section for details.

## 6. Display Output (Intro Goal 12)

The Colorlight i9 carrier board does not have an HDMI connector. HDMI from an ECP5 is possible using the built-in SERDES lanes (which can be configured as TMDS transmitters for HDMI at 720p/1080p). The ULX3S has an HDMI output doing exactly this, with a LiteX HDMI framebuffer peripheral (`litex_boards` includes HDMI support for the ULX3S). Adding HDMI to the Colorlight i9 would require either a PMOD-attached HDMI adapter (works at low resolutions) or designing a custom carrier board that routes SERDES lanes to an HDMI connector. This is a significant hardware addition, and the ULX3S is the most practical path if HDMI output is a real requirement.

For a small embedded display (SPI-attached LCD, e.g., ILI9341): this is within reach on the Colorlight i9. LiteX has an SPI master peripheral; a small SPI TFT display can be connected to the PMOD header, driven from Linux via the `litex_spi` kernel driver and a framebuffer driver.

## 7. Radio Communication from the FPGA (Intro Goal 13)

The path from "boots Linux" to "transmits and receives QPSK" involves:

1. **High-speed I/O from the FPGA pins**: Direct digital output at 25 MHz (the oscillator frequency) is trivial. Faster output requires a PLL to clock the output logic at higher rates. LVDS output via the ECP5's differential I/O banks enables multi-Gbps signaling to a suitable plugin board.
2. **Hardware PLLs, Hardware Costas Loop**: For absolute minimal latency, hardare PLLs, multipliers, and comparators would be put on a custom PCB. PSK is easier than QPSK here.
3. **A DAC/ADC and/or RF front end**: Bare digital FPGA pins cannot drive an antenna. Options:
   * **PMOD DAC** (e.g., PMOD DA2 or Digilent PMOD ADA, which uses AD7303 or AD9648): Low-speed, easy to drive from SPI.
   * **LimeSDR-style frontend**: A plugin board with an LMS7002M transceiver. LiteX has peripheral IP for LMS7002M.
   * **Custom PCB**: FPGA + memory + DAC + LNA all on one board. The ultimate solution, and the natural endpoint of this learning path.
4. **GNU Radio with LiteX**: LiteX ethernet + GNU Radio's gr-zeromq or custom gr-litex source block would allow streaming IQ samples from the FPGA into a GNU Radio flowgraph on the host computer. This is how many software-defined radio systems are structured.


## 8. The Cross-Tool View: How All the Files Relate

A reader coming from Vivado/PetaLinux is used to a clear handoff graph: Vivado produces `.xsa`, PetaLinux consumes `.xsa`, produces `BOOT.BIN` + `image.ub`. The equivalent graph for the LiteX stack:

```
[LiteX Python target file]
         |
         | python3 make.py --build
         v
[Yosys synthesis] --> [nextpnr P&R] --> [ecppack] --> [.bit bitstream]
         |                                                    |
         | (simultaneously)                          openFPGALoader
         v                                                    v
  [csr.json] [.dts] [BIOS ELF]                         [FPGA SRAM or SPI flash]
      |          |        |
      |         dtc       | objcopy
      |          |        v
      |          v   [bios.bin] --------+
      |       [.dtb]                   |
      |          |                     | (packed by litex_term or raw flash)
      v          v                     v
 [litex_cli]  [kernel boot args]   [opensbi.bin] + [Image] + [rootfs.cpio] + [.dtb]
 [litex_server]                                                |
                                                     [boots Linux on VexRiscv]
```

Understanding this graph — what produces each file, what consumes it, and what happens if any step is skipped or out of date — is the central skill that this document is building toward.

# Unmet Goals and Paths Forward

The following goals from the introduction are not yet worked through in this document.

## Goal 5: RISC-V Processor (VexRiscv) — How It Works, Is Configured, and Built

VexRiscv is written in SpinalHDL (Scala). The standard LiteX build downloads a **pre-compiled Verilog file** (`VexRiscv_Linux_SMP.v`) from the `pythondata-cpu-vexriscv-smp` pip package — you do not need sbt just to build and run the SoC. The sbt section in this document is only needed if you want to regenerate the CPU Verilog from its SpinalHDL source.

⚠ **sbt requires Java.** If you see an error like `sbt: command not found` or `No JDK found`, install Java first:

```bash
sudo apt install -y default-jdk
java -version   # should print OpenJDK version
```

Then re-run the sbt install commands. The `sudo apt-get install sbt` step does not automatically pull Java as a dependency in all Ubuntu configurations.

To understand the CPU configuration:

* `~/.local/lib/python3.x/site-packages/pythondata_cpu_vexriscv_smp/verilog/` — the pre-compiled Verilog files for different CPU configurations (single-core vs. SMP, with/without FPU, MMU sizes, etc.)
* <https://github.com/SpinalHDL/VexRiscv> — SpinalHDL source, with `src/main/scala/vexriscv/GenCoreDefault.scala` being the entry point for the Linux-capable SMP configuration
* In `litex_boards/targets/colorlight_i5.py`, the `cpu_type="vexriscv_smp"` argument selects the configuration, and `cpu_variant` selects sub-variants (standard, linux, linuxd, linuxq)

To regenerate the Verilog from SpinalHDL source (requires sbt):

```bash
git clone https://github.com/SpinalHDL/VexRiscv
cd VexRiscv
sbt "runMain vexriscv.GenCoreDefault"
```

## Goal 6: SoC Peripherals — How They Are Configured and Talk to the Processor

In LiteX, peripherals are Python classes inheriting from `Module` and (optionally) `AutoCSR`. The `AutoCSR` mixin automatically registers any `CSRStorage` or `CSRStatus` fields as memory-mapped registers accessible to the CPU.

Key concepts:

* **Wishbone bus**: the primary interconnect inside the LiteX SoC. All peripherals attach to the Wishbone crossbar via `self.bus.add_slave()`. The CPU (VexRiscv) is the Wishbone master.
* **CSR bus**: a lightweight secondary bus for slow control/status registers. Peripheral CSRs are accessible to the CPU via a Wishbone-to-CSR bridge.
* **Interrupts**: peripherals raise CPU interrupts via `self.irq.add("peripheral_name")` in the SoC class.

The `litex/soc/cores/` directory contains the implementations of the standard peripherals (uart, timer, spi, i2c, etherbone, etc.). Reading one of the simpler ones (e.g., `litex/soc/cores/gpio.py`) is the best way to understand the full pattern.

## Goal 8: Boot Process — LiteX BIOS → OpenSBI → Kernel

The full boot sequence for linux-on-litex-vexriscv (no U-Boot in the default setup):

1. **LiteX BIOS**: On power-up, VexRiscv begins executing the LiteX BIOS stored in on-chip block RAM (compiled from C, source at `litex/soc/cores/bios/`). It initializes SDRAM, probes for a UART terminal, and loads the next stage (OpenSBI + kernel) from SPI flash or via serial (`litex_term`).
2. **OpenSBI** (`opensbi.bin`): Runs in RISC-V Machine mode (M-mode). Provides the Supervisor Binary Interface — a standardized firmware layer exposing hardware services (console, timer, IPI) to the kernel running in Supervisor mode (S-mode). Source: <https://github.com/litex-hub/opensbi>.
3. **Linux kernel** (`Image`): OpenSBI passes control to the kernel in S-mode, handing it the Device Tree Blob (`.dtb`) as a boot argument. The `.dtb` — generated by LiteX from the SoC's JSON memory map — tells the kernel what peripherals exist and where they are in the address space.
4. **Initramfs** (`rootfs.cpio`): The kernel unpacks this BusyBox ramdisk and runs `/sbin/init`.

There is **no U-Boot** in this flow. The LiteX BIOS is the first-stage bootloader, OpenSBI is the second stage, and it jumps directly to the kernel.

**Why no U-Boot, and why no FSBL?**

In the Zynq world, the boot chain is: on-chip ROM → FSBL → U-Boot → Linux. Each stage exists for a specific reason. The FSBL runs because the Zynq's hard ARM needs to initialize the PS (DDR controller, clock fabric, MIO pin muxing) before external memory is accessible — this initialization must happen in code, not in the FPGA bitstream, because the DDR controller is part of the hard silicon. U-Boot then handles image loading (finding the kernel on an SD card FAT filesystem or over TFTP), setting up the boot arguments, and loading the device tree blob before jumping to the kernel.

In the LiteX soft-core flow:

* **No FSBL needed**: There is no separate PS to initialize. The FPGA configuration bitstream *is* the hardware — it programs the DDR PHY as part of the LiteDRAM logic, and the LiteX BIOS (which starts running immediately in BRAM when the FPGA comes out of configuration) completes DDR training. The bitstream does what the FSBL does on Zynq.
* **U-Boot replaced by LiteX BIOS**: The BIOS handles loading the next stage from either SPI flash (at fixed address offsets) or over a serial link via `litex_term`. It does not support filesystems — images are stored at raw flash offsets specified in `images/boot.json`. This covers the main things U-Boot does for a minimal embedded Linux, without U-Boot's large codebase (~500,000 lines). The tradeoff is lost flexibility: no SD card FAT boot, no boot menu, no environment variables, no TFTP fallback out of the box.
* **Could U-Boot be added?** Yes, and there are litex-hub experiments doing exactly this for more capable boot scenarios (SD card boot, network boot). It requires porting U-Boot to the specific LiteX SoC, which changes with every build (because the peripheral addresses are reassigned). The LiteX BIOS is the pragmatic minimum for getting Linux running; U-Boot is an optional complexity upgrade.

## Goals 9 & 10: Kernel and Filesystem from Source

**Kernel from source:**

```bash
git clone https://github.com/litex-hub/linux.git -b litex-rebase
cd linux
make ARCH=riscv CROSS_COMPILE=riscv64-unknown-elf- litex_defconfig
make ARCH=riscv CROSS_COMPILE=riscv64-unknown-elf- -j$(nproc)
# Output: arch/riscv/boot/Image
```

`arch/riscv/configs/litex_defconfig` is the starting point for understanding which drivers are enabled (LiteX UART, LiteX timer, LiteX Ethernet). Use `make menuconfig` to explore the full configuration tree.

**Mainline vs. litex-hub kernel:** As of Linux 6.x, most LiteX platform drivers are **in the mainline kernel**: `liteuart` (UART), `litex_mmc` (SD/MMC), `litex_eth` (Ethernet MAC wrapper), `litex_spi`, `litex_i2c`, `litex_timer`. The `litex-hub/linux` fork exists to carry patches that have not yet been accepted upstream, and to host the `litex_defconfig` configuration file before it lands upstream. In practice, a current mainline kernel can boot on LiteX hardware using only upstream drivers and the LiteX-generated device tree. The litex-hub fork is the safe, pre-tested path for this workflow.

Comparison to the Zynq world: The Zynq Linux kernel uses entirely mainline drivers for the hard peripherals (Cadence Ethernet GEM, Xilinx UART PS, Xilinx XADC, etc.) that have been upstream for years. PetaLinux uses a Xilinx-maintained Yocto layer (`meta-xilinx`) that pulls the mainline kernel and adds board-specific device tree fragments. The concept is the same — a fork or downstream layer that carries board-specific patches — but Yocto's layer architecture makes the separation between mainline and Xilinx-specific patches more explicit.

**Filesystem from source (Buildroot):**

```bash
git clone https://github.com/litex-hub/buildroot -b litex-rebase
cd buildroot
make litex_vexriscv_defconfig
make -j$(nproc)
# Output: output/images/rootfs.cpio
```

`make menuconfig` inside Buildroot lets you add packages (Python, Python pip, networking tools) to the rootfs. The Buildroot `configs/litex_vexriscv_defconfig` is the baseline.

**Why Buildroot and not Yocto?**

Both Buildroot and Yocto build a complete embedded Linux distribution from source — they fill the same role that PetaLinux fills in the Xilinx world. (PetaLinux is Yocto-based under the hood, using `meta-xilinx` as its primary BSP layer.)

* **Yocto**: A complete, highly configurable build framework. Supports multiple machines from one configuration tree, produces installable packages (RPM/DEB/IPK), has enormous community and commercial support, and is the standard for most commercial embedded Linux products. Downside: steep learning curve (layers, recipes, bbappend files, BitBake metadata language), very slow first build (~6+ hours on a fast machine), and a complex mental model. PetaLinux makes Yocto less painful for Zynq users by hiding most of this complexity behind `petalinux-build`.
* **Buildroot**: Much simpler. One `.config` file, one `make` command, you have a compressed filesystem image. Faster to build from scratch (~30–60 min). The downside is less runtime flexibility: no package manager on the target, packages must be selected at build time, harder to maintain multiple configurations.

For LiteX, Buildroot is preferred because: (1) the image must be small — the initramfs loads into SDRAM alongside the kernel, and SDRAM is a tight budget on these boards (32 MB on OrangeCrab/ULX3S-class boards; only 8 MB on the Colorlight i9 — see the SDRAM-size debugging section above); (2) rebuilding from scratch is fast enough to be practical; (3) `litex_vexriscv_defconfig` gives a working starting point immediately.

**Using Yocto instead:** You would need `meta-riscv` for the RISC-V architecture support, plus a custom `meta-litex` BSP layer defining the machine configuration (device tree, preferred kernel version, U-Boot config). No pre-existing `meta-litex` layer exists as of 2026. This is a non-trivial undertaking; Buildroot is the practical choice unless you have a specific reason to need Yocto's package management or multi-machine support.

## Goal (mostly done): Adding a Custom SoC Peripheral End-to-End

**Steps 1-4 are now worked through in full** in "Writing a custom HDL LiteX peripheral, then using it as a LiteX peripheral" above (the `prbs31.v` + `prbs31.py` example, wired to the same LED/button/switch PMODs used throughout the GPIO sections before it):

1. ~~Writing the Migen/FHDL module (or wrapping existing Verilog using `Instance`)~~ — done: `prbs31.py`'s `Instance("prbs31", ...)` wrapper.
2. ~~Adding it to the SoC target class with `AutoCSR` registers~~ — done: `self.prbs31 = PRBS31(platform, led_pads=leds8_pads)`.
3. ~~Re-running `--build` and inspecting `csr.json`/`csr.csv` for the new register addresses~~ — done: the `grep -iE "prbs31|buttons" build/i9/csr.csv` step.
4. ~~Using `litex_server` + `litex_cli` to read/write registers from Python without any kernel driver~~ — done: the `litex_cli --write prbs31_seed 1` / `--read prbs31_state` example.

**Still genuinely missing:**

* Writing a minimal Linux platform driver (char device with `read`/`write`) for production use — the section above covers the `/dev/mem`+`mmap()` fallback, not a real kernel driver. This is the one item this document still just names rather than works through.

Reference: <https://github.com/litex-hub/fpga_101> covers steps 1–3 with worked examples.

# See also

<https://github.com/litex-hub/fpga_101>

Zynq-7000 completely without Xilinx tools: Antmicro maintains a repository specifically demonstrating how to patch LiteX, compile a BIOS, hook up a serial terminal, and boot.

# TODO

* <https://tomverbeure.github.io/2021/01/22/The-Colorlight-i5-as-FPGA-development-board.html> links to STM32 firmware at <https://github.com/wuxx/Colorlight-FPGA-Projects/tree/master/firmware> which may be newer.

## Researched (2026-08-27), not attempted: reviving the i9's DAPLink via newer STM32 firmware

Following up on the TODO line above. **The board's current firmware is genuinely old** — MuseLab's DAPLink fork, Interface/Bootloader `0254`, built 2020-10-03 (`DETAILS.TXT` on the mounted `DAPLINK` volume) — and `wuxx/Colorlight-FPGA-Projects/firmware/` does have something newer: `flash_image_20220122.bin` (2022-01-22, ~15 months newer), alongside two older ones (`flash_image_20201029.bin`, `flash_image_20210824.bin`).

**Why this wasn't attempted: no confirmed way to actually write it.** These are named `flash_image_*`, not the `bl.bin`/`if.bin` pair a normal DAPLink MSD drag-and-drop update uses (an earlier commit in that repo shows `bl.bin`/`if.bin` being replaced by these files) — size and naming are consistent with a raw full-flash image (the STM32 is an `STM32F103C8T6`, confirmed from the reference schematic) meant for direct SWD programming by a *separate* probe, not a self-update over the same USB cable already in use. The repo's own SWD/JTAG tooling (`dapprog`, `cmsisdap-flash.cfg`) turned out to be for programming the **ECP5 FPGA**, not the STM32 — no documented STM32 flashing procedure was found in the repo itself.

**Physical SWD access: resolved, conclusively, and it's not there — this document's own research process got this wrong twice before the user's own hardware knowledge settled it.** The `TCK TMS TDI TDO` pads on the carrier board (`doc/ext-board-2.jpg`, next to the STM32) are **spring-loaded pogo pins**, not a solder header — and they don't connect to the STM32 at all. The Colorlight i5/i9 SODIMM *module itself* has 4 matching plated through-holes right next to its ECP5 FPGA, labeled `J30 J32 J31 J27` (confirmed directly in `doc/i5-top.jpg` — visible immediately left of the `LFE5U-25F` chip). When the module is seated in its SODIMM slot and pressed down, those 4 pogo pins poke up through the module's through-holes and make contact from below (visible in `doc/ext-board-1.jpg`, module installed). **This is the ECP5 FPGA's own JTAG interface** — a second, dedicated mechanical/electrical path into the module's FPGA, entirely separate from the SODIMM edge-finger pins, and exactly what this repo's own `dapprog`/`cmsisdap-flash.cfg` tools (noted earlier as "for the FPGA, not the STM32") actually use. It has nothing to do with the STM32 DAPLink chip. **The user's original assessment — "these are probably not what you need" — was correct from the start.** This document's own subsequent research took a schematic net-name match (`TCK_SWCLK` etc. resembling the STM32's alternate-function pin names) as stronger evidence than it actually was, without verifying the physical pin-level connection; a follow-up question correctly flagged that gap; and the module's own through-hole labels (`J30`/`J32`/`J31`/`J27`) are what actually settled it.

**Net result: no confirmed SWD/JTAG access point to the STM32 has been found on this board.** The only exposed 4-pin JTAG-labeled interface goes to the FPGA, not the debugger chip. Reflashing the STM32 would need either an actual STM32-specific debug header this document hasn't located (none found in the schematic or on the board), or direct probing of the STM32's own package pins (34/37/38/39 = PA13/PA14/PA15/PB3 on the `STM32F103C8T6`, LQFP48) — genuinely delicate work on a ~0.5mm-pitch package, not something to attempt without fine probes or a hot-air/microscope setup, and not attempted or recommended here.

**Status: this specific path is a dead end, not merely parked.** The newer firmware from `wuxx/Colorlight-FPGA-Projects` (`flash_image_20220122.bin`) is real and does exist, but there's currently no known way to write it to this board's STM32 without either finding an undiscovered debug point or fine-pitch package-level probing. If this is revisited, the productive next step isn't wiring up the second programmer to these pads (confirmed to be the wrong target) — it's determining whether the STM32's SWD pins are reachable anywhere else on the board at all.

# Interesting stuff to do

Raspbery Pi "New High-speed AD9708 AD9280 AD / DA Module FPGA Development Board" AD is an AD9280 (8-bit 32 MSPS) and the DA is an AD9708 (8-bit 125 MSPS).

AD9226 (ADC) + AD9767 (DAC) — parallel, "Hermes-Lite 2" pair

AD9226 breakout (real 12-bit, 65 MSPS ADC — enough to do FFTs, IQ demodulation, a genuine lock-in on the FPGA) with a class-built R-2R DAC