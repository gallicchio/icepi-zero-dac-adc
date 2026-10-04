"""Opening ("motivating") figures for the pages: one picture at the top of each, plus a map of
the address space for 2.01.  No hardware and no measured data: diagrams, two terminal
"screenshots" copied from the pages' console blocks, and two computed illustrations.

    python3 fig_openers.py              # all of them, into ../../tutorial/img/
    python3 fig_openers.py soc linux    # only those whose names contain "soc" or "linux"

Sections are named as the pages are, chapter.section (1.00, 2.03, ...); a figure says "§2.03".
Every fact in a figure comes from the page named beside it, or from the file named:

  toolchain.png     1.00  the open-source FPGA flow, counter.sv -> Yosys -> nextpnr-ecp5 ->
                        ecppack -> openFPGALoader -> the FPGA; Icarus Verilog to the side.
                        Tool jobs from 1.00's table; the file names (counter.json,
                        counter.config, counter.bit, icepi_adda.lpf) from 1.01's build.
  soc.png           2.00-2.05  the system on chip of Chapter 2: VexRiscv at 50 MHz,
                        Wishbone, ROM with the BIOS (128 kB of block RAM), 8 kB SRAM, the
                        SDRAM controller and 32 MB SDRAM, UART -> FT231X -> USB -> laptop,
                        timer, LED chaser, the CSRs, and 2.03-2.05's function generator,
                        capture (16 kB buffer on the bus) and lock-in (the function
                        generator's phase as its reference), with the AD9280/AD9708 module (0.00).
  bios_banner.png   2.01  the BIOS banner: lines copied from 2.01's console block, with "..."
                        where lines are left out (the page's own "..." included).
  memory_map.png    2.01  the stock SoC's whole address space: mem_list's four regions as 2.01
                        prints them (ROM, SRAM, MAIN_RAM, CSR), the rest empty (an access there
                        times out as a bus error, which ctrl_bus_errors counts: LiteX's
                        SoCController and its bus timeout).  The CSR region zoomed in, from
                        src/riscv/build/stock/csr.csv, the file 2.01 quotes: ctrl, leds and
                        timer0's registers, and where identifier_mem, sdram and uart begin.
                        ctrl_scratch starts as 0x12345678, and 0x15 on leds_out, from 2.01;
                        the timer as 2.02's stopwatch.
  c_flow.png        2.02  main.c (src/riscv/primes/) -> riscv64-unknown-elf-gcc (make) ->
                        primes.bin (4.5 kB) ->
                        litex_term --kernel, serialboot -> SDRAM at 0x40000000 -> the BIOS
                        jumps there -> 9592 primes in 1182 ms; 5.8 ms on the desktop, 98 ms
                        in Python there.
  linux_files.png   3.00  Tux, the Linux SoC's whole address space (not to scale), and the
                        five files with 3.00's sizes in the 32 MB SDRAM.  The address space is
                        LINUX_MAP, from that SoC's csr.json ("memories" and "csr_bases": rom,
                        sram, main_ram, capture_buf, csr, clint, plic; funcgen at 0xf0002000).
                        In the SDRAM each file is drawn to scale where src/linux/prebuilt/
                        images/boot.json puts it, with its size and first and last address
                        from the files there, except that the two smallest get a visible
                        minimum height and the device tree is nudged below OpenSBI.  Tux:
                        dev/data/tux.png, from Wikimedia Commons (TUX_URL below; the 256 px
                        size is refused, 500 px works), attributed in the figure.
  linux_boot.png    3.01  the login and first commands, copied from 3.01's console blocks
                        ("root" typed at the login prompt, as 3.01 says to).
  driver_stack.png  3.02  echo 123456 > .../f0002000.adda/funcgen/frequency -> write() ->
                        frequency_store() in adda.ko -> writel() -> a store on the VexRiscv,
                        a Wishbone write to 0xf0002000 -> funcgen_core's tuning word -> the
                        phase accumulator -> the DAC -> 123455.992 Hz at DAC OUT.
  linux_build.png   3.03  sbt/SpinalHDL -> VexRiscv Verilog; make.py + make_linux.py ->
                        icepi_zero_adda.bit and csr.json; LiteX's json2dts (in make.py) writes
                        icepi_zero_adda.dts from csr.json, make_linux.py adds the adda and LED
                        nodes, dtc -> rv32.dtb; boot.json copied from images/boot_*.json;
                        Buildroot 2026.02.3 with icepi_adda_defconfig (musl) -> cross-compiler,
                        Image (Linux 6.12), opensbi.bin (fw_jump.bin), rootfs.cpio.gz and
                        rootfs.ext2 (BR2_TARGET_ROOTFS_EXT2, which make_sd_image.py puts on the
                        card); kbuild -> adda.ko -> /root.  Each product coloured by where it
                        ends up on a board that boots by itself (3.04's table).  Times from
                        3.00's table and 3.03.
  sd_card.png       3.04  a microSD card (11 x 15 mm, its step and notch; the partitions not to
                        scale): MBR, partition 1 (64 MiB FAT32: Image, opensbi.bin, rv32.dtb,
                        boot.json), partition 2 (ext2: 4 GiB from install-sd.sh, 512 MiB in
                        prebuilt/sdcard.img.xz, read from its partition table), the SPI flash
                        with the bitstream; and the boot timeline: 3.04's table (0, 2.8, 3.1,
                        17.5, 17.9, 27.2, 86.5 s), plus about 1.5 s for the FPGA's own start-up
                        (3.04: the bitstream at 2.4 MHz takes about 1.5 s, and quad SPI at
                        62 MHz brings Memtest OK 1.44 s sooner).  What /sbin/init does: the
                        root file system's /etc/inittab and /etc/init.d/S* (Buildroot's, run by
                        BusyBox's init); the 17 s from the remount to S01seedrng, from 3.04's
                        Try this.
  chirp_sonar.png   4.10  computed: a 2-20 kHz chirp (4.10), a wall 1.5 m away, sound at
                        343 m/s, noise; the cross-correlation's two peaks, 8.75 ms apart.
                        16384 samples at 50 MHz / 64, the 21 ms loop 4.10 suggests.  The 3 ms
                        chirp, the echo (0.3 of the direct sound) and the noise (0.6 rms)
                        are choices for the illustration.
  xcorr_noise.png   5.08  computed: two ADCs share a small common noise (the resistor's
                        Johnson noise) under larger independent noise; the cross-spectrum,
                        averaged over N = 1, 10, 100, 1000 records, settles on the common
                        part.  The 25 MS/s sample rate is the ADC's (2.03); 1024-sample
                        records and a common part of 0.1 of each ADC's own noise power are
                        choices for the illustration.
"""
import json
import os
import sys

import numpy as np
from matplotlib.patches import FancyBboxPatch, Rectangle, Circle, Polygon, Arc
from plotstyle import plt, C1, C2, C3, INK, INK2, MUTED, AXIS, SURFACE

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, "..", "..", "tutorial", "img")
TUX = os.path.join(HERE, "..", "data", "tux.png")
TUX_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/3/35/Tux.svg/500px-Tux.svg.png"
DPI = 130

NEUTRAL, NEUTRAL_EDGE = "#f3f1ea", INK2      # an ordinary box
BLUE_BG, ORANGE_BG, GREEN_BG = "#e4eefb", "#fde9df", "#ddf3ea"   # ADC, DAC, and "yours"
CHIP = "#1d1d1f"                              # a chip outside the FPGA
MONO = "DejaVu Sans Mono"


# ---- drawing helpers: a canvas in units of 0.1 inch ---------------------------------------
def canvas(w, h):
    """A blank figure w x h inches; the axes count in tenths of an inch, origin bottom left."""
    fig = plt.figure(figsize=(w, h))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 10 * w)
    ax.set_ylim(0, 10 * h)
    ax.axis("off")
    return fig, ax


def finish(fig, name):
    fig.savefig(os.path.join(IMG, name), dpi=DPI, facecolor=fig.get_facecolor())
    plt.close(fig)
    print("wrote", name)


def box(ax, x, y, w, h, fc=NEUTRAL, ec=NEUTRAL_EDGE, lw=1.2, r=1.0, ls="-", z=2):
    """A rounded box with its lower-left corner at (x, y)."""
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                fc=fc, ec=ec, lw=lw, ls=ls, zorder=z))


def label(ax, x, y, lines, size=9.5, color=INK, z=5, ha="center", va="center", gap=1.55):
    """Lines of text centred on (x, y).  Each line is a string, or (string, dict of text
    options), e.g. ("Yosys", {"weight": "bold"}) or ("counter.json", {"family": MONO}).
    gap is the line spacing in units (0.1 in) at size 10, scaled with each line's size."""
    items = [(s, {}) if isinstance(s, str) else s for s in lines]
    heights = [gap * kw.get("size", size) / 10 for s, kw in items]
    top = y + sum(heights) / 2
    for (s, kw), hgt in zip(items, heights):
        top -= hgt
        opts = dict(size=size, color=color, ha=ha, va="baseline", zorder=z)
        opts.update(kw)
        ax.text(x, top + 0.28 * hgt, s, **opts)


def node(ax, cx, cy, w, h, lines, fc=NEUTRAL, ec=NEUTRAL_EDGE, size=9.5, ls="-", lw=1.2):
    """A box centred on (cx, cy) with lines of text in it."""
    box(ax, cx - w / 2, cy - h / 2, w, h, fc=fc, ec=ec, ls=ls, lw=lw)
    label(ax, cx, cy, lines, size=size)


def arrow(ax, p0, p1, color=INK2, lw=1.3, style="-|>", ms=11, ls="-", z=3, both=False, rad=0):
    ax.annotate("", p1, p0, zorder=z, arrowprops=dict(
        arrowstyle="<|-|>" if both else style, color=color, lw=lw, mutation_scale=ms,
        linestyle=ls, shrinkA=0, shrinkB=0, connectionstyle=f"arc3,rad={rad}"))


def chip(ax, cx, cy, w, h, lines, pins=5, size=9, color=CHIP, text="#e8e8e8"):
    """An integrated circuit seen from above: a dark body with pins on all four sides
    (`pins` along the top and bottom; the sides get as many as fit at the same pitch)."""
    pl = 0.9                                      # pin length
    side = max(1, int(round(pins * h / w)))
    for n, horizontal in [(pins, True), (side, False)]:
        for k in range(n):
            f = (k + 0.5) / n
            if horizontal:
                spots = [(cx - w / 2 + f * w - 0.3, cy + h / 2, 0.6, pl),
                         (cx - w / 2 + f * w - 0.3, cy - h / 2 - pl, 0.6, pl)]
            else:
                spots = [(cx - w / 2 - pl, cy - h / 2 + f * h - 0.3, pl, 0.6),
                         (cx + w / 2, cy - h / 2 + f * h - 0.3, pl, 0.6)]
            for (px, py, pw, ph) in spots:
                ax.add_patch(Rectangle((px, py), pw, ph, fc="#9a9a9a", ec="none", zorder=2))
    box(ax, cx - w / 2, cy - h / 2, w, h, fc=color, ec=color, r=0.4, z=3)
    label(ax, cx, cy, lines, size=size, color=text)


def want(name):
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    return not args or any(a in name for a in args)


# ==== 1.00: the toolchain ======================================================================
def fig_toolchain():
    fig, ax = canvas(9, 3.25)
    y = 17.0                                         # the row of boxes
    w, h, step = 13.6, 9.6, 15.6
    xs = [7.9 + k * step for k in range(5)]
    steps = [
        [("your design", {"weight": "bold"}), "SystemVerilog", ("counter.sv", {"family": MONO, "size": 8.8})],
        [("Yosys", {"weight": "bold"}), "synthesis:", "a netlist of the", "FPGA's blocks"],
        [("nextpnr-ecp5", {"weight": "bold"}), "place and route:", "which block does", "what, and wiring"],
        [("ecppack", {"weight": "bold"}), "packs it into", "a bitstream"],
        [("openFPGALoader", {"weight": "bold"}), "sends it to the", "board over USB"],
    ]
    outs = [None, "counter.json", "counter.config", "counter.bit", None]
    for k, (x, lines) in enumerate(zip(xs, steps)):
        node(ax, x, y, w, h, lines, size=9, fc=GREEN_BG if k == 0 else NEUTRAL,
             ec=C3 if k == 0 else NEUTRAL_EDGE)
        if outs[k]:                                  # the file each step writes
            ax.text(x, y + h / 2 + 0.9, "→ " + outs[k], ha="center", va="bottom", size=8.6,
                    family=MONO, color=INK2)
    xc = xs[4] + w / 2 + 6.9                         # the FPGA itself
    for k in range(5):
        x0 = xs[k] + w / 2
        x1 = xs[k + 1] - w / 2 if k < 4 else xc - 5.3
        arrow(ax, (x0 + 0.2, y), (x1 - 0.2, y))
    chip(ax, xc, y, 7.6, 7.6, [("ECP5", {"weight": "bold"}), "FPGA"], pins=6, size=9.5)
    ax.text(xc, y - 5.6, "a running", ha="center", va="top", size=9, color=INK)
    ax.text(xc, y - 7.1, "circuit", ha="center", va="top", size=9, color=INK)
    # the constraints file, into nextpnr
    cx = xs[2]
    node(ax, cx, 3.4, 13.6, 4.0, [("icepi_adda.lpf", {"family": MONO, "size": 8.8}),
                                  "which pin is which"], size=8.6)
    arrow(ax, (cx, 5.4), (cx, y - h / 2))
    # simulation, off to the side
    cx = xs[0]
    node(ax, cx + 1.4, 3.4, 15.8, 4.0, [("Icarus Verilog", {"weight": "bold"}),
                                        "simulation, no hardware"], size=8.6, ls="--")
    arrow(ax, (cx, y - h / 2), (cx, 5.4), ls="--")
    # where things happen
    for x0, x1, t in [(xs[0] - w / 2, xs[4] + w / 2, "on your laptop"),
                      (xc - 5.5, xc + 5.5, "on the board")]:
        ax.plot([x0, x0, x1, x1], [27.4, 28.2, 28.2, 27.4], color=MUTED, lw=1)
        ax.text((x0 + x1) / 2, 29.0, t, ha="center", va="bottom", size=9, color=INK2)
    finish(fig, "toolchain.png")


# ==== 2.00-2.05: the system on chip ==============================================================
def laptop(ax, cx, cy, w=8.0, lines=("laptop",), size=9):
    """A laptop icon centred on (cx, cy): screen and keyboard, label underneath."""
    sh = 0.62 * w
    box(ax, cx - w / 2 + 0.6, cy, w - 1.2, sh, fc="#d9d7cf", ec=INK2, r=0.5)
    box(ax, cx - w / 2 + 1.2, cy + 0.6, w - 2.4, sh - 1.2, fc="#fbfbf8", ec="none", r=0.2, z=3)
    ax.add_patch(Polygon([(cx - w / 2 + 0.6, cy), (cx + w / 2 - 0.6, cy), (cx + w / 2, cy - 1.2),
                          (cx - w / 2, cy - 1.2)], closed=True, fc="#d9d7cf", ec=INK2, lw=1.2, zorder=2))
    label(ax, cx, cy - 1.9 - 0.75 * len(lines), lines, size=size)


def fig_soc():
    fig, ax = canvas(9, 5.6)
    # the FPGA
    box(ax, 12, 8.5, 61.5, 38.5, fc="none", ec=INK2, lw=1.3, ls=(0, (5, 3)), r=1.5, z=1)
    ax.text(13.3, 45.6, "inside the FPGA", ha="left", va="center", size=9.5, color=INK2, style="italic")
    # top row: CPU and memories, on the Wishbone bus
    bus_y = 33.2
    top = [(20.5, 13, [("VexRiscv CPU", {"weight": "bold"}), "RISC-V, 50 MHz"]),
           (35.5, 13, [("ROM: the BIOS", {"weight": "bold"}), "128 kB, block RAM"]),
           (48.0, 8, [("SRAM", {"weight": "bold"}), "8 kB"]),
           (61.5, 15, [("SDRAM", {"weight": "bold"}), "controller"])]
    for cx, w, lines in top:
        node(ax, cx, 40.3, w, 6.4, lines, size=9)
        ax.plot([cx, cx], [37.1, bus_y], color=INK2, lw=2.2, zorder=1)
    ax.plot([14, 71.5], [bus_y, bus_y], color=INK2, lw=4, solid_capstyle="round", zorder=1)
    ax.text(43, bus_y - 1.0, "Wishbone bus", ha="center", va="top", size=9, color=INK2)
    # the CSRs and what hangs off them
    node(ax, 22.0, 26.9, 16, 6.2, [("CSRs", {"weight": "bold"}), "control and status", "registers"],
         size=8.6)
    ax.plot([22.0, 22.0], [30.0, bus_y], color=INK2, lw=2.2, zorder=1)
    csr = dict(color=MUTED, lw=1.3, zorder=1)
    csr_y, csr_x = 21.0, 56.0
    ax.plot([17.5, 17.5], [23.8, csr_y], **csr)
    ax.plot([17.5, csr_x], [csr_y, csr_y], **csr)
    stock = [(17.5, 8, ["UART"]), (27.5, 8, ["timer"]), (38.5, 10, ["LED chaser"])]
    for cx, w, lines in stock:
        node(ax, cx, 15.5, w, 4.6, lines, size=9)
        ax.plot([cx, cx], [17.8, csr_y], **csr)
    # Chapter 2's peripherals
    ch2 = [(28.0, [("capture", {"weight": "bold"}), "§2.04"], BLUE_BG, C1),
           (20.3, [("lock-in", {"weight": "bold"}), "§2.05"], BLUE_BG, C1),
           (12.6, [("function", {"weight": "bold"}), ("generator", {"weight": "bold"}), "§2.03"], ORANGE_BG, C2)]
    px, pw = 64.8, 13
    for cy, lines, fc, ec in ch2:
        node(ax, px, cy, pw, 5.4 if len(lines) < 3 else 6.4, lines, size=9, fc=fc, ec=ec)
        ax.plot([csr_x, px - pw / 2], [cy, cy], **csr)
    ax.plot([csr_x, csr_x], [12.6, 28.0], **csr)
    ax.text(csr_x - 0.6, 24.2, "CSRs", ha="right", va="center", size=8, color=MUTED)
    ax.plot([69.5, 69.5], [30.7, bus_y], color=C1, lw=2.2, zorder=1)
    ax.text(68.8, 31.9, "16 kB buffer", ha="right", va="center", size=8, color=C1)
    arrow(ax, (61.0, 15.8), (61.0, 17.6), color=C2, lw=1.3, ms=9)
    ax.text(60.4, 16.7, "phase", ha="right", va="center", size=8, color=C2)
    # outside the FPGA: SDRAM, FT231X and laptop, LEDs, the ADC/DAC module
    chip(ax, 61.5, 51.5, 13, 4.0, [("SDRAM, 32 MB", {"weight": "bold"})], pins=7, size=9)
    arrow(ax, (61.5, 43.5), (61.5, 48.6), both=True, ms=9)
    chip(ax, 17.5, 4.0, 9, 4.0, [("FT231X", {"weight": "bold"})], pins=5, size=9)
    arrow(ax, (17.5, 13.2), (17.5, 6.9), both=True, ms=9)
    ax.plot([7.7, 12.1], [4.0, 4.0], color=INK2, lw=1.3)
    ax.text(9.9, 4.6, "USB", ha="center", va="bottom", size=8, color=INK2)
    laptop(ax, 4.0, 3.6, w=7.0, lines=[], size=8.5)
    ax.text(4.0, 1.0, "laptop", ha="center", va="center", size=8.5, color=INK)
    for k in range(5):
        x = 33.5 + 2.5 * k
        ax.add_patch(Circle((x, 4.0), 0.85, fc="#fffbe6", ec=INK2, lw=1.0, zorder=3))
    ax.text(46.5, 4.0, "5 LEDs", ha="left", va="center", size=9, color=INK)
    arrow(ax, (38.5, 13.2), (38.5, 5.4), ms=9)
    # the module
    mx = 81.6
    box(ax, 75.2, 6.0, 12.8, 26.5, fc="#f7f6f2", ec=AXIS, lw=1.0, r=1.2, z=1)
    ax.text(mx, 30.4, "ADC/DAC", ha="center", va="center", size=8.6, color=INK2)
    ax.text(mx, 28.9, "module", ha="center", va="center", size=8.6, color=INK2)
    chip(ax, mx, 23.0, 6.4, 5.0, [("ADC", {"weight": "bold", "color": "#9cc3f2"}), ("AD9280", {"size": 7.5})],
         pins=4, size=9)
    chip(ax, mx, 13.0, 6.4, 5.0, [("DAC", {"weight": "bold", "color": "#f6ad8c"}), ("AD9708", {"size": 7.5})],
         pins=4, size=9)
    arrow(ax, (mx - 4.3, 24.0), (px + pw / 2, 27.4), color=C1)
    arrow(ax, (mx - 4.3, 22.0), (px + pw / 2, 20.8), color=C1)
    arrow(ax, (px + pw / 2, 12.6), (mx - 4.3, 12.6), color=C2)
    ax.text(mx, 18.6, "ADC IN", ha="center", va="center", size=8.6, color=C1, weight="bold")
    ax.text(mx, 8.6, "DAC OUT", ha="center", va="center", size=8.6, color=C2, weight="bold")
    finish(fig, "soc.png")


# ==== 2.01 and 3.01: terminal "screenshots" ======================================================
TERM_BG, TERM_BAR, TERM_TEXT, TERM_CMD = "#1e1f22", "#2e3035", "#c9c9c2", "#ffffff"
PAGES = os.path.join(HERE, "..", "..", "tutorial")

BIOS_LINES = [                     # 2.01's console block; "..." marks lines left out
    r"        __   _ __      _  __",
    r"       / /  (_) /____ | |/_/",
    r"      / /__/ / __/ -_)>  <",
    r"     /____/_/\__/\__/_/|_|",
    r"   Build your hardware, easily!",
    "...",
    "--================ SoC =================--",
    "CPU:\t\tVexRiscv @ 50MHz",
    "BUS:\t\twishbone 32-bit data/32-bit addr",
    "CSR:\t\t32-bit data big ordering",
    "ROM:\t\t128.0KiB",
    "SRAM:\t\t8.0KiB",
    "L2:\t\t8.0KiB",
    "SDRAM:\t\t32.0MiB 16-bit @ 50MT/s (CL-2 CWL-2)",
    "MAIN RAM:\t32.0MiB",
    "",
    "--=========== Initialization ===========--",
    "Initializing SDRAM @0x40000000...",
    "...",
    "Memtest OK",
    "...",
    "No boot medium found",
    "",
    "--============== Console ===============--",
    "",
    "litex> ",
]

LINUX_LINES = [                    # 3.01's console blocks ("root" typed at the login, as 3.01 says)
    "Welcome to Buildroot",
    "buildroot login: root",
    "# uname -a",
    "Linux buildroot 6.12.0 #1 SMP Sat Oct  3 15:43:09 PDT 2026 riscv32 GNU/Linux",
    "# cat /proc/cpuinfo | head -4",
    "processor\t: 0",
    "hart\t\t: 0",
    "isa\t\t: rv32ima",
    "mmu\t\t: sv32",
    "# free",
    "              total        used        free      shared  buff/cache   available",
    "Mem:          22944        3128       16024          12        3792       15312",
    "# ls /sys/class/leds",
    "led0  led1  led2  led3  led4",
    "# echo 1 > /sys/class/leds/led0/brightness",
    "# ls /proc/device-tree/soc/",
    "adda@f0002000                  gpio@f0003000                  mmc@f0004000",
    "clint@f0010000                 interrupt-controller@f0c00000  serial@f0001000",
    "...",
    "# devmem 0xf0002000 32 0x051eb852",
    "# ",
]


def check_against_page(lines, page, extra=()):
    """Warn about any line that is no longer, word for word, a line of the page."""
    try:
        text = open(os.path.join(PAGES, page)).read().splitlines()
    except OSError:
        return
    for ln in lines:
        if ln.strip() in ("", "...", "#", "litex>") or ln in extra:
            continue
        if ln not in text:
            print(f"  warning: not found in {page}: {ln!r}")


def terminal(lines, name, title, cols=80, size=9.5, is_cmd=lambda ln: False):
    """A dark terminal window holding `lines`, with a title bar; the last line gets a cursor."""
    cw = size * 0.602 / 72                   # DejaVu Sans Mono advance, inches per column
    lh = size * 1.32 / 72                    # line height, inches
    pad, bar, margin = 0.22, 0.30, 0.14
    W = cols * cw + 2 * pad + 2 * margin
    H = len(lines) * lh + 2 * pad + bar + 2 * margin
    fig = plt.figure(figsize=(W, H))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")
    ax.add_patch(FancyBboxPatch((margin, margin), W - 2 * margin, H - 2 * margin,
                                boxstyle="round,pad=0,rounding_size=0.08", fc=TERM_BG, ec="#0f0f10", lw=1))
    ax.add_patch(FancyBboxPatch((margin, H - margin - bar), W - 2 * margin, bar,
                                boxstyle="round,pad=0,rounding_size=0.08", fc=TERM_BAR, ec="none"))
    ax.add_patch(Rectangle((margin, H - margin - bar), W - 2 * margin, bar / 2, fc=TERM_BAR, ec="none"))
    for k, c in enumerate(["#e0605a", "#e0b04a", "#5fb85a"]):
        ax.add_patch(Circle((margin + 0.17 + 0.17 * k, H - margin - bar / 2), 0.048, fc=c, ec="none"))
    ax.text(W / 2, H - margin - bar / 2, title, ha="center", va="center", size=8.5,
            color="#a9a9a3", family=MONO)
    x0 = margin + pad
    y = H - margin - bar - pad
    for ln in lines:
        y -= lh
        t = ln.expandtabs(8)
        cmd = is_cmd(ln)
        ax.text(x0, y + 0.25 * lh, t, ha="left", va="baseline", size=size, family=MONO,
                color=TERM_CMD if cmd else TERM_TEXT, weight="bold" if cmd else "normal")
    t = lines[-1].expandtabs(8)                # the cursor, after the last line
    ax.add_patch(Rectangle((x0 + len(t) * cw, y + 0.08 * lh), cw, 0.85 * lh, fc="#d0d0c8", ec="none"))
    fig.savefig(os.path.join(IMG, name), dpi=DPI, facecolor=SURFACE)
    plt.close(fig)
    print("wrote", name)


def fig_bios_banner():
    check_against_page(BIOS_LINES, "2_01_a_cpu_and_its_bios.md")
    terminal(BIOS_LINES, "bios_banner.png", "litex_term /dev/ttyUSB0", cols=60,
             is_cmd=lambda ln: ln.startswith("litex>"))


def fig_linux_boot():
    check_against_page(LINUX_LINES, "3_01_booting_linux.md", extra=("buildroot login: root",))
    terminal(LINUX_LINES, "linux_boot.png", "litex_term /dev/ttyUSB0", cols=80,
             is_cmd=lambda ln: ln.startswith("# "))


# ==== 2.01: the address space the BIOS's mem_read and mem_write reach ======================
# mem_list's four regions, as 2.01 prints them: (name, first, last, what)
STOCK_MAP = [("ROM", 0x00000000, 0x0001ffff, "the BIOS, 128 kB"), ("SRAM", 0x10000000, 0x10001fff, "8 kB"),
             ("MAIN_RAM", 0x40000000, 0x41ffffff, "the SDRAM, 32 MB"), ("CSR", 0xf0000000, 0xf000ffff, "64 kB")]
# The CSR region, from src/riscv/build/stock/csr.csv (2.01 shows its first five lines): a register
# and a note, or ("...", the first address left out, what is there)
STOCK_CSRS = [("ctrl_reset", 0xf0000000, ""),
              ("ctrl_scratch", 0xf0000004, "starts as 0x12345678"),
              ("ctrl_bus_errors", 0xf0000008, "counts bus errors"),
              ("...", 0xf0000800, "identifier_mem's registers"),
              ("leds_out", 0xf0001000, "the five LEDs: try 0x15"),
              ("...", 0xf0001800, "sdram's registers"),
              ("timer0_load", 0xf0002000, ""),
              ("timer0_reload", 0xf0002004, ""),
              ("timer0_en", 0xf0002008, ""),
              ("timer0_update_value", 0xf000200c, ""),
              ("timer0_value", 0xf0002010, ""),
              ("...", 0xf0002014, "three more of timer0's"),
              ("...", 0xf0002800, "uart's registers"),
              ("...", 0xf0003000, "no registers, up to 0xf000ffff")]
CSR_FC, CSR_EC = "#fbf1cf", "#c99a1e"              # the CSRs, in both columns


def fig_memory_map():
    fig, ax = canvas(9, 5.3)
    # ---- the whole address space, not to scale ----
    ax0, aw, ab, at = 16.5, 15.0, 3.0, 44.5
    bands = {"ROM": (3.0, 9.0), "SRAM": (11.5, 15.5), "MAIN_RAM": (18.0, 25.0), "CSR": (35.0, 40.5)}
    empty_band(ax, ax0, ab, aw, at - ab)
    for name, first, last, what in STOCK_MAP:
        lo, hi = bands[name]
        fc, ec = (CSR_FC, CSR_EC) if name == "CSR" else (NEUTRAL, INK2)
        ax.add_patch(Rectangle((ax0, lo), aw, hi - lo, fc=fc, ec=INK2, lw=1.0, zorder=3))
        label(ax, ax0 + aw / 2, (lo + hi) / 2, [(name, {"weight": "bold", "family": MONO, "size": 9}), what],
              size=8.4)
        xr = ax0 - 0.8
        ax.text(xr, lo + 0.55, "0x%08x" % first, ha="right", va="center", size=7.8, family=MONO, color=INK2)
        ax.text(xr, hi - 0.55, "0x%08x" % last, ha="right", va="center", size=7.8, family=MONO, color=INK2)
    ax.add_patch(Rectangle((ax0, ab), aw, at - ab, fc="none", ec=INK2, lw=1.2, zorder=4))
    ax.text(ax0 - 0.8, at - 0.55, "0xffffffff", ha="right", va="center", size=7.8, family=MONO, color=INK2)
    label(ax, ax0 + aw / 2, 30.0, [("empty", {"weight": "bold", "color": INK2}),
                                   "a load or store here", "is a bus error"], size=8.2, color=INK2, z=6)
    ax.add_patch(Rectangle((ax0 + 1.6, 27.0), aw - 3.2, 6.0, fc=SURFACE, ec="none", zorder=5))
    ax.text(ax0 + aw / 2, at + 3.6, "all 4 GB of addresses", ha="center", va="center", size=10,
            weight="bold", color=INK)
    ax.text(ax0 + aw / 2, at + 1.8, "mem_list's four regions; not to scale", ha="center", va="center",
            size=8, color=MUTED)

    # ---- the CSR region, zoomed in: one row per 32-bit register ----
    px0, px1, pb, pt = 40.0, 89.5, 1.5, 48.0          # the panel
    box(ax, px0, pb, px1 - px0, pt - pb, fc="#fdfaf0", ec=CSR_EC, lw=1.0, r=0.8, z=1)
    zoom(ax, ax0 + aw, *bands["CSR"], px0, pb, pt, fc="#f6ecc8")
    ax.text(px0 + 1.5, pt - 2.0, "CSR, zoomed in: one row per 32-bit register", ha="left", va="center",
            size=10, weight="bold", color=INK)
    ax.text(px0 + 1.5, pt - 3.9, "from build/stock/csr.csv", ha="left", va="center", size=8, color=MUTED)
    cx, cw, rh, gh = 52.5, 17.0, 2.9, 2.6              # cells: left, width, register row, "..." row
    xa = cx - 0.8                                       # the addresses
    xn = cx + cw + 1.0                                  # the notes
    y = pb + 1.6
    cells = {}
    for name, addr, note in STOCK_CSRS:
        if name.startswith("..."):                     # registers left out
            ax.text(xa, y + gh / 2, "0x%08x" % addr, ha="right", va="center", size=7.8, family=MONO,
                    color=MUTED)
            ax.text(cx + 0.8, y + gh / 2, "⋮  " + note, ha="left", va="center", size=7.8, color=MUTED,
                    style="italic")
            y += gh
            continue
        ax.add_patch(Rectangle((cx, y), cw, rh, fc=CSR_FC, ec=CSR_EC, lw=0.9, zorder=3))
        ax.text(cx + 0.8, y + rh / 2, name, ha="left", va="center", size=8.4, family=MONO, color=INK, zorder=4)
        ax.text(xa, y + rh / 2, "0x%08x" % addr, ha="right", va="center", size=7.8, family=MONO, color=INK2)
        if note:
            ax.text(xn, y + rh / 2, note, ha="left", va="center", size=8.2, color=INK2)
        cells[name] = (y, y + rh)
        y += rh
    # the timer, as one group
    y_lo, y_hi = cells["timer0_load"][0], cells["timer0_value"][1]
    bx = cx + cw + 0.8
    ax.plot([bx, bx + 0.7, bx + 0.7, bx], [y_lo + 0.2, y_lo + 0.2, y_hi - 0.2, y_hi - 0.2], color=INK2, lw=0.9)
    label(ax, bx + 1.7, (y_lo + y_hi) / 2, ["the timer, which", "§2.02 uses as", "a stopwatch"],
          size=8.2, color=INK2, ha="left")
    finish(fig, "memory_map.png")


# ==== 2.02: C onto the CPU ====================================================================
def fig_c_flow():
    fig, ax = canvas(9, 4.7)
    yr, h = 39.5, 7.2                                 # the laptop's row
    row = [(7.5, 12.5, [("main.c", {"family": MONO, "weight": "bold"}), "your C"], GREEN_BG, C3),
           (27.5, 22, [("riscv64-unknown-elf-gcc", {"family": MONO, "size": 8.4}), "cross-compiler (make)"], NEUTRAL, INK2),
           (49.5, 17, [("primes.bin", {"family": MONO, "weight": "bold"}), "RISC-V machine", "code, 4.5 kB"], NEUTRAL, INK2),
           (77.0, 23, [("litex_term", {"family": MONO, "weight": "bold"}), ("--kernel=primes.bin", {"family": MONO, "size": 8.4}), "sends it"], NEUTRAL, INK2)]
    for cx, w, lines, fc, ec in row:
        node(ax, cx, yr, w, h, lines, size=9, fc=fc, ec=ec)
    for (a, wa, *_), (b, wb, *_) in zip(row[:-1], row[1:]):
        arrow(ax, (a + wa / 2 + 0.2, yr), (b - wb / 2 - 0.2, yr))
    ax.text(1.0, yr + h / 2 + 1.4, "on your laptop", ha="left", va="center", size=9.5, color=INK2, style="italic")
    # the board's column
    cx, w = 77.0, 23
    col = [(26.5, [("the BIOS (serialboot)", {"weight": "bold"}), "puts it in the SDRAM", ("at 0x40000000", {"family": MONO})]),
           (14.0, [("then jumps there:", {"weight": "bold"}), "the CPU runs main()"])]
    for cy, lines in col:
        node(ax, cx, cy, w, 7.4, lines, size=9)
    arrow(ax, (cx, yr - h / 2 - 0.2), (cx, 26.5 + 3.7 + 0.2))
    ax.text(cx + 1.0, (yr - h / 2 + 30.2) / 2, "USB serial port", ha="left", va="center", size=8.5, color=INK2)
    arrow(ax, (cx, 26.5 - 3.7 - 0.2), (cx, 14.0 + 3.7 + 0.2))
    ax.plot([62.5, 89.5], [32.3, 32.3], color=AXIS, lw=1, ls=(0, (4, 3)))
    ax.text(89.5, 31.4, "on the board", ha="right", va="top", size=9.5, color=INK2, style="italic")
    # what it prints
    tx, ty, tw, th = 53.5, 1.6, 36.0, 4.2
    box(ax, tx, ty, tw, th, fc=TERM_BG, ec=TERM_BG, r=0.6)
    ax.text(tx + 1.2, ty + th / 2, "9592 primes below 100000, found in 1182 ms.", ha="left", va="center",
            size=8.8, family=MONO, color=TERM_TEXT, zorder=5)
    arrow(ax, (cx, 14.0 - 3.7 - 0.2), (cx, ty + th + 0.2))
    # how fast: 2.02's numbers
    ax.text(1.0, 28.6, "The same primes, timed", ha="left", va="center", size=9.5, weight="bold", color=INK)
    bars = [("FPGA's CPU, C", 1182, "1182 ms", C3),
            ("desktop, Python", 98, "98 ms", MUTED),
            ("desktop, C", 5.8, "5.8 ms", MUTED)]
    x0, full = 17.5, 38.0
    for k, (name, t, txt, c) in enumerate(bars):
        y = 23.6 - 4.2 * k
        ax.text(x0 - 1.0, y, name, ha="right", va="center", size=9, color=INK)
        L = max(full * t / 1182, 0.25)
        box(ax, x0, y - 1.2, L, 2.4, fc=c, ec="none", r=0.3)
        ax.text(x0 + L + 0.8, y, txt, ha="left", va="center", size=9, color=INK2)
    ax.text(1.0, 9.6, "desktop: an AMD Ryzen 9 3900X, where the C is 200 times faster ...", ha="left",
            va="center", size=8.3, color=INK2)
    label(ax, 1.0, 6.5, ["... but the open-source processor in the FPGA is yours",
                         "to read, change and understand."], size=9, color=INK, ha="left")
    finish(fig, "c_flow.png")


# ==== 2.06: the registers from the laptop ======================================================
def fig_uartbone():
    """2.06: remote.py and litex_term on the laptop, litex_server between them and the serial
    port, LiteX's UART bridge on the bus inside the FPGA.  Names and numbers from 2.06 and
    src/riscv/build/bone/csr.csv."""
    fig, ax = canvas(10, 4.3)
    # the laptop
    ax.text(1.0, 40.6, "on your laptop", ha="left", va="center", size=9.5, color=INK2, style="italic")
    node(ax, 13.5, 32.0, 24, 9.0, [("remote.py", {"family": MONO, "weight": "bold"}), "your Python:",
                                   ("wb.regs.leds_out.write(0x15)", {"family": MONO, "size": 8.0})],
         fc=GREEN_BG, ec=C3, size=9)
    node(ax, 13.5, 18.5, 24, 7.2, [("litex_term crossover", {"family": MONO, "weight": "bold", "size": 8.8}),
                                   "the BIOS's console, as before"], size=9)
    node(ax, 41.5, 25.5, 18, 9.0, [("litex_server", {"family": MONO, "weight": "bold"}), "owns the serial port;",
                                   "clients connect to it"], size=9)
    arrow(ax, (25.7, 31.0), (32.3, 27.5), both=True)
    arrow(ax, (25.7, 19.5), (32.3, 23.5), both=True)
    ax.text(29.0, 33.5, "by name, via\ncsr.csv", ha="center", va="bottom", size=8, color=INK2)
    # the board
    box(ax, 59.0, 3.0, 39.5, 35.5, fc="none", ec=INK2, ls=(0, (5, 3)), r=1.5)
    ax.text(60.5, 36.6, "inside the FPGA", ha="left", va="center", size=9.5, color=INK2, style="italic")
    node(ax, 78.5, 29.5, 21, 7.0, [("UART bridge", {"weight": "bold"}), "reads and writes the bus"],
         fc=ORANGE_BG, ec=C2, size=9)
    arrow(ax, (50.7, 26.5), (67.8, 29.0), both=True)
    ax.text(57.5, 24.6, "USB serial,\n115200 baud", ha="right", va="top", size=8.3, color=INK2)
    ax.plot([61.5, 96.0], [21.5, 21.5], color=INK2, lw=3.2, solid_capstyle="round", zorder=2)
    ax.text(96.0, 23.0, "Wishbone bus", ha="right", va="bottom", size=8.3, color=INK2)
    ax.plot([78.5, 78.5], [26.0, 21.5], color=INK2, lw=1.6)
    bus = [(66.0, [("CPU + BIOS", {"weight": "bold"}), "still there"]),
           (78.5, [("crossover", {"weight": "bold"}), "UART"]),
           (91.0, [("CSRs", {"weight": "bold"}), ("funcgen_tw", {"family": MONO, "size": 7.6}),
                   ("lockin_x ...", {"family": MONO, "size": 7.6})])]
    for cx, lines in bus:
        node(ax, cx, 12.0, 11.0, 9.0, lines, size=8.6)
        ax.plot([cx, cx], [16.5, 21.5], color=INK2, lw=1.6)
    ax.text(78.5, 4.6, "and the 16 kB capture buffer, at 0x80000000", ha="center", va="center", size=8.3,
            color=INK2)
    finish(fig, "uartbone.png")


# ==== 3.00: what Linux needs ==================================================================
TUX_CREDIT = "Tux: Larry Ewing (lewing@isc.tamu.edu) and The GIMP"


def text_width(ax, t):
    """The width of a text artist, in canvas units (tenths of an inch)."""
    r = ax.figure.canvas.get_renderer()
    return t.get_window_extent(renderer=r).width / ax.figure.dpi * 10


def name_size(ax, x, y, name, size_txt, fs=8.6, ha="right", color=INK):
    """'name  size' on one line: the name bold, the size plain, aligned at x (left or right)."""
    if ha == "right":
        t = ax.text(x, y, size_txt, ha="right", va="center", size=fs - 0.3, color=INK2, zorder=5)
        ax.text(x - text_width(ax, t) - 0.7, y, name, ha="right", va="center", size=fs, weight="bold",
                color=color, zorder=5)
    else:
        t = ax.text(x, y, name, ha="left", va="center", size=fs, weight="bold", color=color, zorder=5,
                    family=MONO)
        ax.text(x + text_width(ax, t) + 0.9, y, size_txt, ha="left", va="center", size=fs - 0.4,
                color=INK2, zorder=5)


def empty_band(ax, x, y, w, h):
    """A stretch of address space with nothing in it: light hatching."""
    ax.add_patch(Rectangle((x, y), w, h, fc=SURFACE, ec=AXIS, lw=0, hatch="////", zorder=2))


def zoom(ax, x0, y0a, y0b, x1, y1a, y1b, fc="#eceae2"):
    """Zoom lines from the band [y0a, y0b] at x0 out to [y1a, y1b] at x1, the wedge lightly filled."""
    ax.add_patch(Polygon([(x0, y0a), (x1, y1a), (x1, y1b), (x0, y0b)], closed=True, fc=fc, ec="none",
                         alpha=0.6, zorder=0))
    for ya, yb in [(y0a, y1a), (y0b, y1b)]:
        ax.plot([x0, x1], [ya, yb], color=MUTED, lw=0.9, zorder=1)


IMAGES = os.path.join(HERE, "..", "..", "src", "linux", "prebuilt", "images")
# The Linux SoC's whole address space, from its csr.json ("memories" and "csr_bases"), as built
# by make_linux.py (lolv-repo/build/icepi_zero_adda/csr.json): (name, base, size).
LINUX_MAP = [("rom", 0x00000000, "64 kB"), ("sram", 0x10000000, "6 kB"), ("main_ram", 0x40000000, "32 MB"),
             ("capture_buf", 0x80000000, "16 kB"), ("csr", 0xf0000000, "64 kB"),
             ("clint", 0xf0010000, "64 kB"), ("plic", 0xf0c00000, "4 MB")]


def fig_linux_files():
    fig, ax = canvas(9, 5.3)
    # Tux, if the download worked: top right
    if os.path.exists(TUX):
        im = plt.imread(TUX)
        tw = 13.0
        th = tw * im.shape[0] / im.shape[1]
        tx, ty = 75.5, 35.0
        ax.imshow(im, extent=(tx, tx + tw, ty, ty + th), zorder=4, interpolation="lanczos")
        ax.set_xlim(0, 90)
        ax.set_ylim(0, 53)
        ax.set_aspect("auto")
        label(ax, tx + tw / 2, ty - 2.6, ["Tux: Larry Ewing", "(lewing@isc.tamu.edu)", "and The GIMP"],
              size=7, color=MUTED)
    else:
        print("  (no", TUX, "- Tux left out)")

    # ---- the whole 32-bit address space, not to scale ----
    ax0, aw, ab, at = 18.0, 7.5, 4.0, 45.0             # column left, width, bottom, top
    bands = {"rom": (4.0, 7.0), "sram": (9.0, 12.0), "main_ram": (14.0, 21.0), "capture_buf": (23.0, 26.0),
             "csr": (28.2, 33.6), "clint": (33.6, 37.4), "plic": (39.6, 42.6)}
    empty_band(ax, ax0, ab, aw, at - ab)
    for name, base, sz in LINUX_MAP:
        lo, hi = bands[name]
        fc = "#f7f6f2" if name == "main_ram" else NEUTRAL
        ax.add_patch(Rectangle((ax0, lo), aw, hi - lo, fc=fc, ec=INK2, lw=1.0, zorder=3))
        xr = ax0 - 0.9
        top = hi - 0.75 if name != "main_ram" else (lo + hi) / 2 + 0.75
        name_size(ax, xr, top, name, sz, fs=8.4)
        ax.text(xr, top - 1.5, "0x%08x" % base, ha="right", va="center", size=7.8, family=MONO,
                color=INK2, zorder=5)
        if name == "csr":
            for k, t in enumerate(["the peripherals' registers:", "funcgen at 0xf0002000, ..."]):
                ax.text(xr, top - 3.0 - 1.35 * k, t, ha="right", va="center", size=7.6, color=INK2, zorder=5)
    ax.add_patch(Rectangle((ax0, ab), aw, at - ab, fc="none", ec=INK2, lw=1.2, zorder=4))
    ax.text(ax0 - 0.9, at - 0.6, "0xffffffff", ha="right", va="center", size=7.8, family=MONO, color=INK2)
    ax.text(ax0 + aw / 2, at + 4.0, "all 4 GB of addresses", ha="center", va="center", size=10,
            weight="bold", color=INK)
    ax.text(ax0 + aw / 2, at + 2.2, "not to scale; hatched: empty", ha="center", va="center", size=8,
            color=MUTED)

    # ---- the SDRAM, to scale: 32 MiB tall ----
    MiB = 2 ** 20
    cx0, cw, y0, Y = 40.0, 9.0, 4.0, 41.0          # column left, width, bottom, height
    per = Y / 32
    zoom(ax, ax0 + aw, *bands["main_ram"], cx0, y0, y0 + Y)
    box(ax, cx0, y0, cw, Y, fc="#f7f6f2", ec=INK2, lw=1.2, r=0.4, z=2)
    ax.text(cx0 + cw / 2, y0 + Y + 4.0, "32 MB of SDRAM", ha="center", va="center", size=10,
            weight="bold", color=INK)
    ax.text(cx0 + cw / 2, y0 + Y + 2.2, "to scale", ha="center", va="center", size=8, color=MUTED)
    ax.text(cx0 - 0.6, y0 - 0.3, "0x40000000", ha="right", va="top", size=7.8, family=MONO, color=INK2)
    ax.text(cx0 - 0.6, y0 + Y + 0.3, "0x41ffffff", ha="right", va="bottom", size=7.8, family=MONO, color=INK2)
    # Each file where src/linux/prebuilt/images/boot.json puts it, its size from the file itself;
    # the sizes printed are 3.00's.  The device tree (3 kB) and OpenSBI (264 kB) are too thin to see
    # at this scale: they get a minimum height, and the device tree (really 64 kB below OpenSBI)
    # is nudged down to show below it.
    boot = json.load(open(os.path.join(IMAGES, "boot.json")))
    files = [("Image", C1, "the Linux kernel (6.12)", "9.2 MB", 9.5, 0),
             ("rv32.dtb", INK2, "the device tree", "3 kB", 17.5, -0.75),
             ("opensbi.bin", C3, "OpenSBI, the RISC-V firmware", "264 kB", 25.5, 0),
             ("rootfs.cpio.gz", C2, "the root file system", "1.5 MB", 33.5, 0)]
    lx = cx0 + cw + 5.0
    for name, c, what, sz, ly, nudge in files:
        start = int(boot[name], 16)
        nbytes = os.path.getsize(os.path.join(IMAGES, name))
        yb = y0 + (start - 0x40000000) / MiB * per + nudge
        hgt = max(nbytes / MiB * per, 0.4)
        ax.add_patch(Rectangle((cx0 + 0.15, yb), cw - 0.3, hgt, fc=c, ec="none", zorder=3))
        ym = yb + hgt / 2
        ax.plot([cx0 + cw + 0.3, lx - 1.0], [ym, ly], color=MUTED, lw=0.8, zorder=1)
        name_size(ax, lx, ly + 1.65, name, sz, fs=9.3, ha="left")
        ax.text(lx, ly, "0x%08x – 0x%08x" % (start, start + nbytes - 1), ha="left", va="center",
                size=7.8, family=MONO, color=INK2)
        ax.text(lx, ly - 1.6, what, ha="left", va="center", size=8.6, color=INK2)
    # boot.json: the map
    bx, by = 61.5, 42.0
    node(ax, bx, by, 14.0, 5.6, [("boot.json", {"family": MONO, "weight": "bold"}), "130 bytes: where",
                                 "each file goes"], size=8.4, ls="--")
    arrow(ax, (bx - 7.0, by), (cx0 + cw + 0.4, by), ls="--", color=INK2)
    finish(fig, "linux_files.png")


# ==== 3.02: one shell command, all the way down ==============================================
def fig_driver_stack():
    fig, ax = canvas(9, 4.85)
    cx, w, h, pitch, top = 33.0, 60.0, 4.6, 6.6, 44.1
    ys = [top - k * pitch for k in range(7)]
    m = lambda t: (t, {"family": MONO, "size": 8.6})
    layers = [
        None,                                          # the shell: drawn as a terminal line
        ([("sysfs: the file funcgen/frequency", {"weight": "bold"}), "the shell's write() system call lands in the kernel"], NEUTRAL, INK2),
        ([("the driver, adda.ko: frequency_store()", {"weight": "bold"}), m("writel(div_u64(hz << 32, a->clk), a->funcgen + FUNCGEN_TW);")], NEUTRAL, INK2),
        ([("a store instruction on the VexRiscv", {"weight": "bold"}), "a Wishbone write to 0xf0002000"], NEUTRAL, INK2),
        ([("funcgen_core: a new tuning word, tw", {"weight": "bold"}), "f = tw × 50 MHz / 2³²"], ORANGE_BG, C2),
        ([("the DDS: the phase accumulator turns faster", {"weight": "bold"}), m("phase <= phase + tw;")], ORANGE_BG, C2),
        ([("the DAC (AD9708)", {"weight": "bold"}), "DAC OUT: a sine at 123455.992 Hz"], ORANGE_BG, C2),
    ]
    # the bands, and their names on the right
    bands = [(ys[0] + 3.4, ys[0] - 3.3, "user space"), (ys[1] + 3.3, ys[2] - 3.3, "Linux kernel"),
             (ys[3] + 3.3, ys[5] - 3.3, "inside the FPGA"), (ys[6] + 3.3, ys[6] - 3.4, "on the module")]
    for k, (y1, y2, name) in enumerate(bands):
        ax.add_patch(Rectangle((0.8, y2), 88.4, y1 - y2, fc="#f4f3ee" if k % 2 == 0 else SURFACE,
                               ec="none", zorder=0))
        ax.text(88.4, (y1 + y2) / 2, name, ha="right", va="center", size=9.5, color=INK2, style="italic")
    # the shell command
    box(ax, cx - w / 2, ys[0] - h / 2, w, h, fc=TERM_BG, ec=TERM_BG, r=0.6)
    ax.text(cx - w / 2 + 1.4, ys[0], "# echo 123456 > /sys/bus/platform/devices/f0002000.adda/funcgen/frequency",
            ha="left", va="center", size=8.6, family=MONO, color="#ffffff", weight="bold", zorder=5)
    for k in range(1, 7):
        lines, fc, ec = layers[k]
        node(ax, cx, ys[k], w, h, lines, size=9, fc=fc, ec=ec)
    for k in range(6):
        arrow(ax, (cx, ys[k] - h / 2 - 0.1), (cx, ys[k + 1] + h / 2 + 0.1), ms=9)
    # a sine coming out of DAC OUT
    t = np.linspace(0, 1, 200)
    sx = cx + w / 2 + 3.0 + 8.0 * t
    ax.plot(sx, ys[6] + 1.5 * np.sin(2 * np.pi * 2 * t), color=C2, lw=1.8, zorder=4)
    arrow(ax, (cx + w / 2 + 0.2, ys[6]), (cx + w / 2 + 2.4, ys[6]), color=C2, ms=8)
    finish(fig, "driver_stack.png")


# ==== 3.03: building Linux ====================================================================
# Where each built file ends up on a board that boots by itself (3.04): (fill, edge, legend)
DEST = {"flash": (ORANGE_BG, C2, "the FPGA's SPI flash"),
        "fat": (GREEN_BG, C3, "SD card, partition 1 (FAT32)"),
        "ext": (BLUE_BG, C1, "SD card, partition 2 (ext2)")}


def fig_linux_build():
    fig, ax = canvas(9, 5.86)
    B = {"weight": "bold"}
    m = lambda t, **kw: (t, dict({"family": MONO, "size": 8.2}, **kw))
    small = dict(ha="center", va="center", size=7.8, color=INK2)
    # the products, coloured by where they end up
    px, pw, ph = 81.5, 16.0, 3.8
    pl = px - pw / 2 - 0.2                            # where arrows into them end
    prods = {"bit": (48.5, [m("icepi_zero_adda.bit", weight="bold", size=8.4)], "flash"),
             "json": (42.6, [m("boot.json", weight="bold", size=8.4)], "fat"),
             "dtb": (36.4, [m("rv32.dtb", weight="bold", size=8.4)], "fat"),
             "img": (29.6, [m("Image", weight="bold", size=8.4)], "fat"),
             "sbi": (24.6, [m("opensbi.bin", weight="bold", size=8.4)], "fat"),
             "rfs": (18.4, [m("rootfs.cpio.gz", weight="bold", size=8.4), m("rootfs.ext2", size=8.0)], "ext")}
    for key, (y, lines, dest) in prods.items():
        fc, ec, _ = DEST[dest]
        node(ax, px, y, pw, ph if len(lines) == 1 else 5.4, lines, fc=fc, ec=ec, size=8.4)
    ax.text(px, 52.6, "what the board boots", ha="center", va="center", size=9, color=INK2, style="italic")
    ax.text(px + pw / 2, 45.7, "the BIOS is inside", ha="right", va="center", size=7.6, color=INK2)

    # lane 1: the CPU and the SoC
    y1 = 48.5
    node(ax, 7.6, y1, 14, 6.4, [("sbt + SpinalHDL", B), "Scala; once,", "then cached"], size=8.4)
    node(ax, 24.6, y1, 13.5, 6.4, [("VexRiscv CPU", B), "as Verilog,", "with an MMU"], size=8.4)
    node(ax, 45.5, y1, 21, 6.4, [m("make.py", weight="bold", size=8.4), m("+ make_linux.py", size=8.4),
                                 "LiteX, with add_adda()"], size=8.4)
    arrow(ax, (14.8, y1), (17.6, y1))
    arrow(ax, (31.6, y1), (34.8, y1))
    arrow(ax, (56.2, y1), (pl, y1))
    ax.text(64.5, y1 + 0.8, "5 min", ha="center", va="bottom", size=8.2, color=INK2)
    arrow(ax, (56.2, y1 - 2.2), (pl, prods["json"][0]))
    ax.text(64.0, 44.0, "copied", ha="center", va="center", size=7.8, color=INK2,
            bbox=dict(fc=SURFACE, ec="none", pad=0.6))

    # the device tree: csr.json -> a .dts -> dtc -> rv32.dtb
    yd = 36.4
    node(ax, 33.0, yd, 14.0, 4.0, [m("csr.json", weight="bold", size=8.4)], size=8.4)
    ax.text(33.0, yd - 3.2, "every peripheral's address,", **small)
    ax.text(33.0, yd - 4.5, "written by LiteX from", **small)
    ax.text(33.0, yd - 5.8, "the SoC description", **small)
    arrow(ax, (45.5, y1 - 3.3), (35.0, yd + 2.1))
    node(ax, 57.0, yd, 19.0, 4.0, [m("icepi_zero_adda.dts", weight="bold", size=8.2)], size=8.4)
    ax.text(57.0, yd - 3.2, "LiteX writes most of it; make_linux.py", **small)
    ax.text(57.0, yd - 4.5, "adds nodes for the ADC/DAC", **small)
    ax.text(57.0, yd - 5.8, "peripherals and the LEDs", **small)
    arrow(ax, (40.2, yd), (47.3, yd))
    arrow(ax, (66.7, yd), (pl, yd))
    ax.text(69.9, yd + 0.6, "dtc", ha="center", va="bottom", size=8.2, color=INK2, family=MONO)

    # lane 2: Buildroot
    y2 = 20.6
    node(ax, 9.0, y2, 16.5, 7.0, [("Buildroot", B), m("icepi_adda_defconfig", size=7.8), "musl; src/linux"], size=8.4)
    ax.text(9.0, y2 - 4.6, "15–30 min,", ha="center", va="top", size=8.2, color=INK2)
    ax.text(9.0, y2 - 6.1, "the first time", ha="center", va="top", size=8.2, color=INK2)
    node(ax, 29.5, y2, 17, 6.4, [("cross-compiler", B), m("riscv32-buildroot-"), m("linux-musl-gcc")], size=8.4)
    node(ax, 50.5, y2, 17, 6.4, [("compiles", B), "Linux 6.12, OpenSBI,", "BusyBox"], size=8.4)
    arrow(ax, (17.4, y2), (20.8, y2))
    arrow(ax, (38.2, y2), (41.8, y2))
    for key in ["img", "sbi", "rfs"]:
        arrow(ax, (59.2, y2), (pl, prods[key][0]))

    # lane 3: the driver, which ends up in the root file system's /root
    y3 = 7.6
    node(ax, 29.5, y3, 17, 5.2, [("kbuild", B), m("adda.c")], size=8.4)
    fc, ec, _ = DEST["ext"]
    node(ax, 50.5, y3, 12, 4.0, [m("adda.ko", weight="bold", size=8.4)], fc=fc, ec=ec, size=8.4)
    arrow(ax, (29.5, y2 - 3.3), (29.5, y3 + 2.7))
    arrow(ax, (46.5, y2 - 3.3), (33.5, y3 + 2.7))
    ax.text(41.3, 14.0, "its kernel", ha="left", va="center", size=8.0, color=INK2)
    arrow(ax, (38.2, y3), (44.3, y3))
    ax.text(41.25, y3 + 0.7, "seconds", ha="center", va="bottom", size=7.8, color=INK2)
    arrow(ax, (56.7, y3), (pl, prods["rfs"][0] - 2.9))
    ax.text(67.2, 10.2, "into /root", ha="left", va="center", size=8.0, color=INK2)

    # the legend: where each file ends up, and the serial boot (below the drawing)
    ax.set_ylim(-2.6, 56.0)
    t = ax.text(0.8, 1.9, "where each file ends up:", ha="left", va="center", size=8.2, color=INK, weight="bold")
    x = 0.8 + text_width(ax, t) + 1.8
    for key in ["flash", "fat", "ext"]:
        fc, ec, txt = DEST[key]
        box(ax, x, 1.9 - 0.7, 2.4, 1.4, fc=fc, ec=ec, lw=1.0, r=0.3)
        t = ax.text(x + 3.2, 1.9, txt, ha="left", va="center", size=8.0, color=INK2)
        x += 3.2 + text_width(ax, t) + 2.6
    ax.text(0.8, -1.0, "For the serial boot of §3.01, litex_term sends the same files over the serial port "
            "instead, with rootfs.cpio.gz as the root file system.", ha="left", va="center", size=7.8,
            color=INK2)
    finish(fig, "linux_build.png")


# ==== 3.04: booting from the card =============================================================
def microsd(ax, x0, y0, s, fc="#2b2d31"):
    """A microSD card's outline, 11 x 15 mm at s units per mm, lower-left corner at (x0, y0), the
    contact end at the top: 9.7 mm wide there, with the notch and the step out to the full 11 mm
    on the right.  Returns the narrow width, in units."""
    mm = [(0, 0), (11, 0), (11, 8.0), (9.7, 8.9), (9.7, 9.5), (9.25, 9.5), (9.25, 10.3), (9.7, 10.3),
          (9.7, 15), (0, 15)]
    ax.add_patch(Polygon([(x0 + s * u, y0 + s * v) for u, v in mm], closed=True, fc=fc, ec=fc, lw=1.5,
                         joinstyle="round", zorder=1))
    return 9.7 * s


def fig_sd_card():
    fig, ax = canvas(9, 6.5)
    B = {"weight": "bold"}
    m = lambda t, **kw: (t, dict({"family": MONO, "size": 8.3}, **kw))
    fl_fc, fl_ec, _ = DEST["flash"]
    p1_fc, p1_ec, _ = DEST["fat"]
    p2_fc, p2_ec, _ = DEST["ext"]
    # the flash chip
    box(ax, 1.2, 55.0, 29.0, 8.4, fc=fl_fc, ec=fl_ec, lw=1.0, r=0.8, z=0)
    chip(ax, 6.6, 59.2, 5.6, 3.8, [("flash", {"size": 8.2})], pins=4, size=8.2)
    ax.text(11.8, 61.0, "SPI flash", ha="left", va="center", size=9, weight="bold", color=INK)
    ax.text(11.8, 59.2, "icepi_zero_adda.bit", ha="left", va="center", size=8.3, family=MONO, color=INK)
    ax.text(11.8, 57.4, "the gateware, BIOS inside", ha="left", va="center", size=8.3, color=INK2)
    # the card, 11 x 15 mm; its partitions not to scale
    s, x0, y0 = 2.8, 1.5, 7.0
    narrow = microsd(ax, x0, y0, s)
    bx0, bx1 = x0 + 0.65 * s, x0 + narrow - 0.65 * s
    bands = [(45.6, 47.6, "#8d8c86", [("MBR: the partition table", {"size": 8, "color": "#ffffff"})]),
             (35.4, 45.0, p1_fc, [("partition 1: 64 MiB, FAT32", B), m("Image  opensbi.bin"),
                                  m("rv32.dtb  boot.json")]),
             (9.0, 34.8, p2_fc, [("partition 2: ext2", B), ("4 GiB from install-sd.sh,", {"size": 8.2}),
                                 ("512 MiB in sdcard.img.xz", {"size": 8.2}), ("", {"size": 5}),
                                 "the root file system:", m("/bin  /etc  /sbin  /usr"),
                                 m("/root/adda.ko  ...")])]
    for y_lo, y_hi, fc, lines in bands:
        box(ax, bx0, y_lo, bx1 - bx0, y_hi - y_lo, fc=fc, ec="none", r=0.4, z=2)
        label(ax, (bx0 + bx1) / 2, (y_lo + y_hi) / 2, lines, size=8.6)
    # partition 2 also fills the card's wider end, below the step
    y_lo, fc = bands[-1][0], bands[-1][2]
    xw, ys = x0 + 10.35 * s, y0 + 7.75 * s            # the wide part's right edge, and the step
    box(ax, bx1 - 2.0, y_lo, xw - bx1 + 2.0, ys - y_lo, fc=fc, ec="none", r=0.4, z=2)
    ax.add_patch(Polygon([(bx1 - 1.0, ys - 0.5), (xw, ys - 0.5), (xw, ys), (bx1, y0 + 8.65 * s),
                          (bx1 - 1.0, y0 + 8.65 * s)], closed=True, fc=fc, ec="none", zorder=2))
    ax.text(x0 + 11 * s / 2, 4.9, "microSD card, 11 × 15 mm", ha="center", va="center", size=8.6, color=INK2)
    ax.text(x0 + 11 * s / 2, 3.3, "(the partitions not to scale)", ha="center", va="center", size=8.2,
            color=MUTED)

    # the timeline, not to scale: (y, time, line, second line, third line)
    tx, tt, ta = 39.5, 41.6, 48.6                     # dots, times, text
    rows = [(60.6, "0 s", "power-up: the FPGA starts loading its", "configuration from the flash", ""),
            (54.6, "≈1.5 s", "the FPGA has loaded its configuration from the flash;",
             "the CPU runs its first instruction, and the BIOS", "prints its banner"),
            (48.2, "2.8 s", "the BIOS has tested the memory; no serial", "boot after ¼ s, so it turns to the card", ""),
            (42.9, "3.1 s", "it reads boot.json from partition 1, then", "starts reading Image to 0x40000000", ""),
            (37.6, "17.5 s", "the kernel is in memory (9.1 MB at 633 kB/s),", "then rv32.dtb and opensbi.bin", ""),
            (33.2, "17.9 s", "OpenSBI starts Linux", "", ""),
            (28.6, "27.2 s", "Linux mounts /dev/mmcblk0p2 as /", "and starts /sbin/init", ""),
            (4.6, "86.5 s", "buildroot login:", "61 s with five unused services off", "")]
    ys = [r[0] for r in rows]
    ax.plot([tx, tx], [ys[-1], ys[0]], color=AXIS, lw=2, zorder=1)
    # where the time goes: reading the flash, partition 1, running from partition 2
    for (ya, yb), c in [((ys[0], ys[1]), fl_ec), ((ys[3], ys[4]), p1_ec), ((ys[6], ys[7]), p2_ec)]:
        ax.plot([tx, tx], [ya, yb], color=c, lw=3, zorder=2, solid_capstyle="butt")
    for y, t, a, b, c in rows:
        ax.add_patch(Circle((tx, y), 0.75, fc=INK2, ec=INK2, lw=1.2, zorder=3))
        ax.text(tt, y, t, ha="left", va="center", size=9, weight="bold", color=INK)
        more = [ln for ln in (b, c) if ln]
        label(ax, ta, y, [(a, {"color": INK})] + [(ln, {"color": INK2}) for ln in more],
              size=8.6, ha="left", gap=1.95)

    # what /sbin/init does, between 27.2 s and 86.5 s
    fs, step = 7.8, 1.62
    yl = 25.0
    ax.text(ta, yl, "BusyBox's init: /etc/inittab, then the /etc/init.d/S* scripts", ha="left",
            va="center", size=fs, color=INK2, style="italic")
    items = [("", "mounts /proc, and remounts the card read-write"),
             ("", "mounts /sys, /dev/pts, ...; a dozen small commands"),
             ("S01seedrng", "seeds the random-number generator"),
             ("S01syslogd, S02klogd", "the system log"),
             ("S02sysctl", "kernel settings (there are none)"),
             ("S40network", "networking (fails: no network hardware)"),
             ("S50crond", "scheduled jobs (there are none)"),
             ("getty", "the login prompt")]
    for k, (cmd, what) in enumerate(items):
        y = yl - 1.9 - step * k
        ax.text(ta + 0.3, y, "•", ha="left", va="center", size=fs, color=INK2)
        x = ta + 1.6
        if cmd:
            t = ax.text(x, y, cmd + ":", ha="left", va="center", size=fs - 0.3, family=MONO, color=INK)
            x += text_width(ax, t) + 0.8
        ax.text(x, y, what, ha="left", va="center", size=fs, color=INK2)
    # the measured 17 s, from the remount to seedrng (3.04's Try this)
    y_a, y_b = yl - 1.9 - step * 0.75, yl - 1.9 - step * 2.25
    bx = 86.0
    ax.plot([bx - 0.6, bx, bx, bx - 0.6], [y_a, y_a, y_b, y_b], color=INK2, lw=0.9)
    ax.text(bx + 0.6, (y_a + y_b) / 2, "17 s", ha="left", va="center", size=fs, color=INK, weight="bold")

    # what is read when
    arrow(ax, (30.6, 60.6), (tx - 1.2, 60.6), color=fl_ec, ms=9)
    arrow(ax, (bx1 + 0.6, 40.2), (tx - 1.2, 42.6), color=p1_ec, ms=9)
    arrow(ax, (bx1 + 0.6, 26.0), (tx - 1.2, 28.3), color=p2_ec, ms=9)
    finish(fig, "sd_card.png")


# ==== 4.10: a chirp sonar (computed) ==========================================================
def fig_chirp_sonar():
    rng = np.random.default_rng(4)
    fs = 50e6 / 64                     # 4.10: awgcap played one sample every 64 clocks...
    n = 16384                          # ...a 21 ms loop
    t = np.arange(n) / fs
    T, f0, f1 = 3e-3, 2e3, 20e3        # the chirp: 2 to 20 kHz (4.10), 3 ms (a choice)
    c, d = 343.0, 1.5                  # sound, and the wall
    tc = np.arange(int(T * fs)) / fs
    chirp = np.sin(2 * np.pi * (f0 * tc + (f1 - f0) * tc ** 2 / (2 * T)))
    taper = np.ones_like(tc)           # 0.2 ms fade in and out
    k = int(0.2e-3 * fs)
    taper[:k] = taper[-k:][::-1] = 0.5 - 0.5 * np.cos(np.pi * np.arange(k) / k)
    chirp *= taper
    t_direct = 1.0e-3                  # the microphone sits beside the speaker
    t_echo = t_direct + 2 * d / c
    mic = rng.normal(0, 0.6, n)       # echo strength and noise: choices
    for t_arr, a in [(t_direct, 1.0), (t_echo, 0.3)]:
        i = int(round(t_arr * fs))
        mic[i:i + len(chirp)] += a * chirp
    # cross-correlation with the chirp, by FFT; lag 0 = the chirp starting at t = 0
    L = 2 * n
    xc = np.fft.irfft(np.fft.rfft(mic, L) * np.conj(np.fft.rfft(chirp, L)), L)[:n]
    xc /= np.sum(chirp ** 2)           # 1 = a full-strength copy of the chirp

    fig = plt.figure(figsize=(9, 5.4))
    gs = fig.add_gridspec(3, 2, width_ratios=[1.35, 1], height_ratios=[1, 1, 1.1])
    a0 = fig.add_subplot(gs[0, 0])
    a0.plot(tc * 1e3, chirp, color=C2, lw=1.0)
    a0.set_xlim(0, T * 1e3)
    a0.set_ylim(-1.5, 1.5)
    a0.set_xlabel("time (ms)")
    a0.set_ylabel("speaker")
    a0.set_title("Send a chirp: 2 kHz to 20 kHz in 3 ms")
    # the scene
    s_ax = fig.add_subplot(gs[0, 1])
    s_ax.set_xlim(0, 10)
    s_ax.set_ylim(0, 4)
    s_ax.axis("off")
    s_ax.add_patch(Rectangle((2.1, 2.45), 0.45, 0.8, fc=C2, ec="none"))
    s_ax.add_patch(Polygon([(2.55, 2.45), (2.55, 3.25), (3.0, 3.6), (3.0, 2.1)], closed=True, fc=C2, ec="none"))
    s_ax.text(1.85, 2.85, "speaker", ha="right", va="center", size=8.5, color=INK2)
    s_ax.add_patch(Circle((2.55, 0.9), 0.27, fc=C1, ec="none"))
    s_ax.text(1.85, 0.9, "microphone", ha="right", va="center", size=8.5, color=INK2)
    s_ax.add_patch(Rectangle((8.6, 0.2), 0.45, 3.6, fc="#c9c6bb", ec="none"))
    s_ax.text(9.55, 2.0, "wall", ha="center", va="center", size=8.5, color=INK2, rotation=90)
    s_ax.annotate("", (8.5, 2.85), (3.2, 2.85), arrowprops=dict(arrowstyle="-|>", color=C2, lw=1.3))
    s_ax.annotate("", (3.0, 1.0), (8.5, 2.3), arrowprops=dict(arrowstyle="-|>", color=C1, lw=1.3))
    s_ax.annotate("", (8.55, 3.75), (2.6, 3.75), arrowprops=dict(arrowstyle="<->", color=INK2, lw=0.8))
    s_ax.text(5.6, 3.85, "1.5 m", ha="center", va="bottom", size=8.5, color=INK2)
    s_ax.text(6.2, 1.25, "echo", ha="center", va="center", size=8.5, color=C1)

    a1 = fig.add_subplot(gs[1, :])
    a1.plot(t * 1e3, mic, color=C1, lw=0.6)
    a1.axvspan(t_echo * 1e3, (t_echo + T) * 1e3, color=C1, alpha=0.10, lw=0)
    a1.text((t_echo + T / 2) * 1e3, 3.55, "the echo is in here", ha="center", va="top",
            size=8.5, color=INK2)
    a1.set_xlim(0, t[-1] * 1e3)
    a1.set_ylim(-3.2, 3.8)
    a1.set_xlabel("time (ms)")
    a1.set_ylabel("microphone")
    a1.set_title("Record: the chirp, then a weak echo, in noise")
    a2 = fig.add_subplot(gs[2, :], sharex=a1)
    a2.plot(t * 1e3, xc, color=C3, lw=0.8)
    a2.set_ylim(-0.75, 1.3)
    a2.set_xlabel("delay (ms)")
    a2.set_ylabel("correlation")
    a2.set_title("Cross-correlate with the chirp: each copy becomes one sharp peak")
    i_d = np.argmax(xc[: int(5e-3 * fs)])
    i_e = int(5e-3 * fs) + np.argmax(xc[int(5e-3 * fs):])
    td, te = t[i_d] * 1e3, t[i_e] * 1e3
    a2.annotate("", (te, 0.62), (td, 0.62), arrowprops=dict(arrowstyle="<->", color=INK2, lw=0.9))
    a2.text((td + te) / 2, 0.72, f"{te - td:.2f} ms:  343 m/s × {te - td:.2f} ms / 2 = "
            f"{343 * (te - td) / 2e3:.2f} m", ha="center", va="bottom", size=9, color=INK)
    a2.text(td + 0.35, 0.3, "direct sound", ha="left", va="center", size=8.5, color=INK2)
    a2.text(te + 0.35, 0.3, "echo from the wall", ha="left", va="center", size=8.5, color=INK2)
    fig.text(0.995, 0.005, "computed, not measured", ha="right", va="bottom", size=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(os.path.join(IMG, "chirp_sonar.png"), dpi=DPI)
    plt.close(fig)
    print("wrote chirp_sonar.png", f"(peaks at {td:.3f} and {te:.3f} ms)")


# ==== 5.08: thermal noise by cross-correlation (computed) ======================================
def fig_xcorr_noise():
    rng = np.random.default_rng(5)
    fs, L = 25e6, 1024                 # the ADC's 25 MS/s (2.03); 1024-sample records (a choice)
    common = 0.1                       # the resistor's noise power, against each ADC's own = 1
    Ns = [1, 10, 100, 1000]
    f = np.fft.rfftfreq(L, 1 / fs) / 1e6
    acc = np.zeros(L // 2 + 1, complex)
    curves, k = {}, 0
    for N in Ns:                       # keep averaging the same running sum
        while k < N:
            sc = rng.normal(0, np.sqrt(common), L)
            a = sc + rng.normal(0, 1, L)
            b = sc + rng.normal(0, 1, L)
            if k == 0:
                rec = (a, b, sc)
            A, Bf = np.fft.rfft(a), np.fft.rfft(b)
            acc += A * np.conj(Bf) / L     # per bin: 1 = one ADC's own noise
            k += 1
        curves[N] = np.abs(acc / N)

    fig = plt.figure(figsize=(9, 5.3))
    gs = fig.add_gridspec(2, 4, height_ratios=[1, 1.1], hspace=0.56, wspace=0.10)
    a0 = fig.add_subplot(gs[0, :])
    m = 80                                        # samples shown: 3.2 us
    t_us = np.arange(m) / fs * 1e6
    a, b, sc = rec
    for y, off, c, name in [(a, 3.6, C1, "ADC A: the resistor + A's own noise"),
                            (b, 0.0, C2, "ADC B: the resistor + B's own noise"),
                            (sc, -3.2, C3, "the resistor alone, hidden in both")]:
        a0.plot(t_us, y[:m] + off, color=c, lw=0.9)
        a0.plot(t_us, y[:m] + off, "o", color=c, markersize=2.8, markeredgecolor=SURFACE, markeredgewidth=0.5)
        a0.text(t_us[-1] + 0.12, off, name, ha="left", va="center", size=8.6, color=INK2)
    a0.set_xlim(0, 5.0)
    a0.spines["bottom"].set_bounds(0, 3.2)
    a0.set_xticks([0, 1, 2, 3])
    a0.set_yticks([])
    a0.set_xlabel("time (µs), 25 MS/s", loc="left")
    a0.set_title("One record from each ADC: it all looks like noise")
    a0.grid(False)
    a0.spines["left"].set_visible(False)
    axes = [fig.add_subplot(gs[1, j]) for j in range(4)]
    for j, (ax, N) in enumerate(zip(axes, Ns)):
        ax.semilogy(f, curves[N], color=INK2, lw=0.55)
        ax.axhline(1 + common, color=MUTED, lw=1.2, ls="--")
        ax.axhline(common, color=C3, lw=1.6, ls="--")
        ax.set_ylim(0.01, 8)
        ax.set_xlim(0, 12.5)
        ax.set_xticks([0, 5, 10])
        ax.text(0.04, 0.965, f"N = {N}" + (" record" if N == 1 else " records"), transform=ax.transAxes,
                ha="left", va="top", size=9.5, weight="bold", color=INK,
                bbox=dict(fc=SURFACE, ec="none", pad=1.5))
        ax.set_xlabel("frequency (MHz)")
        if j:
            ax.tick_params(labelleft=False)
        else:
            ax.set_ylabel("cross-spectrum\n(one ADC's noise = 1)")
    axes[3].text(12.2, (1 + common) * 1.2, "one ADC alone", ha="right", va="bottom", size=8.2, color=MUTED)
    axes[3].text(12.2, common / 3.2, "the resistor's part", ha="right", va="top", size=8.2, color=C3)
    fig.subplots_adjust(left=0.085, right=0.985, top=0.93, bottom=0.10)
    y_hdr = axes[0].get_position().y1 + 0.025
    fig.text(axes[0].get_position().x0, y_hdr, "Average the cross-spectrum A × B* over N records: "
             "the ADCs' own noise averages away", ha="left", va="bottom", size=11, weight="bold")
    fig.text(0.995, 0.995, "computed, not measured", ha="right", va="top", size=8, color=MUTED)
    fig.savefig(os.path.join(IMG, "xcorr_noise.png"), dpi=DPI)
    plt.close(fig)
    print("wrote xcorr_noise.png")


# ==== 6.00: from a cable to the air ==========================================================
def mixer(ax, cx, cy, r=2.4, color=INK2):
    ax.add_patch(Circle((cx, cy), r, fc="white", ec=color, lw=1.4, zorder=4))
    for sx in (-1, 1):
        ax.plot([cx - 0.7 * r, cx + 0.7 * r], [cy - sx * 0.7 * r, cy + sx * 0.7 * r], color=color, lw=1.4, zorder=5)


def antenna(ax, x, y, h=5.0, color=INK2, waves=True):
    ax.plot([x, x], [y, y + h], color=color, lw=1.5, zorder=4)
    ax.add_patch(Polygon([(x - 1.6, y + h + 2.2), (x + 1.6, y + h + 2.2), (x, y + h)], closed=True,
                         fc="none", ec=color, lw=1.5, zorder=4))
    for r in ((2.4, 4.0, 5.6) if waves else ()):
        ax.add_patch(Arc((x, y + h + 1.2), 2 * r, 2 * r, theta1=-40, theta2=40, color=C2, lw=1.1, zorder=3))


def fig_hdr():
    """6.00: this chapter's link (the DAC, a cable, the ADC, at a 6.25 MHz carrier), and the
    same link through the air with an RF front end at each end: mixer and local oscillator
    (an ADF4351 synthesizer), band filter, amplifier, antenna.  Part names from 6.00's list."""
    fig, ax = canvas(10, 4.6)
    # this chapter
    ax.text(1.0, 44.0, "this chapter: through a cable", ha="left", va="center", size=9.5, color=INK2, style="italic")
    node(ax, 11.5, 36.0, 19, 6.4, [("psk.py", {"family": MONO, "weight": "bold"}), "builds the waveform"],
         fc=GREEN_BG, ec=C3, size=9)
    node(ax, 33.0, 36.0, 15, 6.4, [("DAC", {"weight": "bold"}), "50 MS/s"], fc=ORANGE_BG, ec=C2, size=9)
    node(ax, 67.0, 36.0, 15, 6.4, [("ADC", {"weight": "bold"}), "25 MS/s"], fc=BLUE_BG, ec=C1, size=9)
    node(ax, 88.5, 36.0, 19, 6.4, [("psk.py", {"family": MONO, "weight": "bold"}), "finds clock, carrier, bits"],
         fc=GREEN_BG, ec=C3, size=9)
    arrow(ax, (21.2, 36.0), (25.3, 36.0))
    arrow(ax, (74.7, 36.0), (78.8, 36.0))
    ax.plot([40.7, 59.3], [36.0, 36.0], color="#6d6d6d", lw=3.4, solid_capstyle="round", zorder=2)
    ax.text(50.0, 37.6, "coax: 6.25 MHz carrier", ha="center", va="bottom", size=8.6, color=INK2)
    # through the air
    ax.text(1.0, 26.5, "with RF parts at each end: through the air at 915 MHz or 2.4 GHz", ha="left",
            va="center", size=9.5, color=INK2, style="italic")
    y = 15.0
    node(ax, 6.5, y, 10, 6.0, [("DAC", {"weight": "bold"}), "6.25 MHz"], fc=ORANGE_BG, ec=C2, size=8.6)
    mixer(ax, 17.0, y)
    node(ax, 17.0, y - 9.5, 10.5, 5.0, [("LO", {"weight": "bold"}), ("ADF4351", {"size": 8})], size=8.6)
    node(ax, 28.0, y, 10, 6.0, ["band", "filter"], size=8.6)
    node(ax, 39.0, y, 9, 6.0, ["amp"], size=8.6)
    antenna(ax, 45.0, y)
    antenna(ax, 56.0, y, waves=False)
    node(ax, 61.0, y, 9, 6.0, ["LNA"], size=8.6)
    node(ax, 72.0, y, 10, 6.0, ["band", "filter"], size=8.6)
    mixer(ax, 83.0, y)
    node(ax, 83.0, y - 9.5, 10.5, 5.0, [("LO", {"weight": "bold"}), ("ADF4351", {"size": 8})], size=8.6)
    node(ax, 94.0, y, 10, 6.0, [("ADC", {"weight": "bold"}), "6.25 MHz"], fc=BLUE_BG, ec=C1, size=8.6)
    for x0, x1 in [(11.5, 14.6), (19.4, 23.0), (33.0, 34.5), (43.5, 45.0)]:
        arrow(ax, (x0, y), (x1, y))
    for x0, x1 in [(56.0, 56.5), (65.5, 67.0), (77.0, 80.6), (85.4, 89.0)]:
        arrow(ax, (x0, y), (x1, y))
    for mx in (17.0, 83.0):
        arrow(ax, (mx, y - 7.0), (mx, y - 2.4))
    ax.text(50.5, y - 2.0, "915 MHz", ha="center", va="center", size=8.6, color=C2)
    ax.text(50.0, y - 7.5, "the FPGA, the Python and the\nalgorithms stay exactly the same", ha="center",
            va="center", size=8.6, color=INK)
    finish(fig, "hdr.png")


if __name__ == "__main__":
    for name, f in [("toolchain", fig_toolchain), ("soc", fig_soc),
                    ("bios_banner", fig_bios_banner), ("memory_map", fig_memory_map),
                    ("linux_boot", fig_linux_boot),
                    ("c_flow", fig_c_flow), ("uartbone", fig_uartbone), ("linux_files", fig_linux_files),
                    ("driver_stack", fig_driver_stack), ("linux_build", fig_linux_build),
                    ("sd_card", fig_sd_card), ("hdr", fig_hdr), ("chirp_sonar", fig_chirp_sonar),
                    ("xcorr_noise", fig_xcorr_noise)]:
        if want(name):
            f()
