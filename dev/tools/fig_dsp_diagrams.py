"""Wiring diagrams for Chapter 7 (signal processing in gateware): what plugs into what.  No
hardware and no measured data.

    python3 fig_dsp_diagrams.py                 # all three, into ../../tutorial/img/
    python3 fig_dsp_diagrams.py nmr             # only those whose names contain this

Drawn with fig_openers.py's helpers (canvas, node, arrow, laptop, ...) and plotstyle's colours.
The boards are simplified outlines in fig_stack.py's conventions (seen from above: ADC IN on
the left SMA, DAC OUT on the right one, USB at the bottom) with its colours and its cable().

  dsp_d_three_ways.png   7.00  the three ways to measure a filter running in the FPGA, as 7.00
                               lists them: (a) an ADALM2000, its W1 into ADC IN and DAC OUT
                               into its channel 1, both it and the board on the laptop's USB
                               (the scripts' --m2k flag); (b) two boards crossed as 1.08's
                               two-board setup, B's lock-in sweeping A's filter (untested:
                               one converter module); (c) one board looped back, the stimulus
                               (an impulse, a step, noise or a tone) made in gateware.
  dsp_d_nmr.png          7.07  the TeachSpin PS2 pulsed NMR spectrometer's modules and jacks
                               (its manual's connector list, as 7.07's table names them) with
                               this board jacked in: two FPGA pins replace the pulse
                               programmer's I and Q gates into the synthesizer; the receiver's
                               I, Q and Env. outputs, or its 21 MHz RF Out (aliased to 4 MHz
                               at 25 MS/s, then 1.08's lock-in), and the gradient supply's
                               current monitors go to ADC IN one at a time; the synthesizer's
                               ±25 V Pulsed RF Out never does.  The PS2's own RF path is left
                               as it is.  Not built: a plan.
  dsp_d_litex_filter.png 7.04  the same filter loaded three ways: 2.03's SoC in the FPGA
                               (VexRiscv, the Wishbone bus, funcgen, lockin and capture in
                               grey, and the filter's 25 CSRs at 0xf000f800 feeding
                               filter_core.sv, whose output reaches the DAC through the
                               dac_source mux); the C firmware's "adda> filter lowpass" in the
                               CPU, MicroPython's machine.mem32 on the board's Linux, and the
                               laptop's filter_remote.py through litex_server and the UART
                               bridge; 7.04's price-of-the-bus table in a corner; the
                               bitstream and csr.csv from icepi_adda_soc.py --build.
"""
import os
import sys

from matplotlib.patches import Circle, Rectangle
from plotstyle import plt, C1, C2, C3, INK, INK2, MUTED, AXIS, SURFACE
from fig_openers import (canvas, box, label, node, arrow, finish, want, laptop, NEUTRAL, NEUTRAL_EDGE,
                         BLUE_BG, ORANGE_BG, GREEN_BG, MONO)
from fig_stack import cable, ADC_C, DAC_C, CABLE, GOLD, GREEN2

BOLD = {"weight": "bold"}
BOARD_FC, BOARD_EC = "#e3ecdf", GREEN2            # the board, a paler green than fig_stack's
USB = dict(color="#444444", lw=2.2, solid_capstyle="round", zorder=1)
RED = "#d62828"


def note(fig, text, top=True):
    fig.text(0.995, 0.995 if top else 0.005, text, ha="right", va="top" if top else "bottom", size=8, color=MUTED)


def tbox(ax, cx, cy, w, h, lines, fc=NEUTRAL, ec=NEUTRAL_EDGE, size=6.6, gap=1.95, ls="-"):
    """node() with the line spacing opened up: a DejaVu Sans Mono line is taller than a
    sans one at the same size, and label()'s default gap lets the two overprint."""
    box(ax, cx - w / 2, cy - h / 2, w, h, fc=fc, ec=ec, ls=ls)
    label(ax, cx, cy, lines, size=size, gap=gap)


# ---- a board, simplified ------------------------------------------------------------------------
def sma(ax, x, y):
    """An SMA connector standing on a board's top edge at (x, y): the base and the barrel.
    Returns the tip, where a cable attaches."""
    ax.add_patch(Rectangle((x - 1.3, y), 2.6, 1.1, fc=GOLD, ec="none", zorder=4))
    ax.add_patch(Rectangle((x - 0.75, y + 1.1), 1.5, 1.7, fc=GOLD, ec="none", zorder=4))
    return (x, y + 2.8)


def board(ax, cx, y0, w=20, h=20, name=None, dac_used=True):
    """The Icepi Zero with the module on it, seen from above and simplified: ADC IN on the
    left SMA and DAC OUT on the right one (fig_stack's convention), the USB at the bottom, a
    dashed FPGA region inside with the two converters above it.  Returns the points a caller
    needs: the converters' inner ends (adc, dac), the SMA tips, and the USB connector."""
    box(ax, cx - w / 2, y0, w, h, fc=BOARD_FC, ec=BOARD_EC, lw=1.2, r=1.2, z=1)
    box(ax, cx - w / 2 + 1.2, y0 + 1.2, w - 2.4, h - 5.8, fc="none", ec=INK2, lw=0.9, ls=(0, (4, 2.5)), r=0.8, z=2)
    ax.text(cx - w / 2 + 2.0, y0 + h - 5.0, "FPGA", ha="left", va="top", size=6.3, color=INK2, style="italic", zorder=5)
    xa, xd, ya = cx - w / 4, cx + w / 4, y0 + h - 2.2
    node(ax, xa, ya, 6.6, 2.6, [("ADC IN", {"weight": "bold", "color": C1})], fc=BLUE_BG, ec=C1, size=6.3)
    if dac_used:
        node(ax, xd, ya, 7.2, 2.6, [("DAC OUT", {"weight": "bold", "color": C2})], fc=ORANGE_BG, ec=C2, size=6.3)
    else:
        node(ax, xd, ya, 7.2, 2.6, [("DAC OUT", {"weight": "bold", "color": MUTED})], fc=NEUTRAL, ec=AXIS, size=6.3)
    tips = [sma(ax, x, y0 + h) for x in (xa, xd)]
    ax.add_patch(Rectangle((cx - 1.6, y0 - 1.1), 3.2, 1.1, fc="#9a9a9a", ec="none", zorder=2))   # the USB
    if name:
        ax.text(cx - w / 2 + 0.3, y0 - 0.9, name, ha="left", va="top", size=7, weight="bold", color=INK)
    return dict(adc=(xa, ya - 1.3), dac=(xd, ya - 1.3), adc_tip=tips[0], dac_tip=tips[1], usb=(cx, y0 - 1.1))


def usb_down(ax, b, y_end, text="USB"):
    """The board's USB cable straight down to y_end, labelled beside the connector."""
    x, y = b["usb"]
    ax.plot([x, x], [y, y_end], **USB)
    ax.text(x + 0.9, y - 1.1, text, ha="left", va="center", size=6.3, color=INK2)


# ==== 7.00: the three ways to measure a filter ====================================================
def fig_three_ways():
    fig, ax = canvas(10, 5.6)
    ax.text(50, 53.4, "Three ways to measure a filter running in the FPGA", ha="center", va="center",
            size=11, weight="bold", color=INK)
    y0, h = 16.0, 20.0

    # ---- (a) an ADALM2000: W1 into ADC IN, DAC OUT into channel 1, both on the laptop ----
    cx = 14.5
    b = board(ax, cx, y0, 20, h)
    node(ax, cx, 23.5, 10, 5, [("filter", BOLD), "(gateware)"], fc=GREEN_BG, ec=C3, size=6.8)
    arrow(ax, b["adc"], (cx - 2.5, 26.0), ms=8)
    arrow(ax, (cx + 2.5, 26.0), b["dac"], ms=8)
    node(ax, cx, 46.0, 22, 7, [("ADALM2000", BOLD), "function generator + oscilloscope"], size=6.8)
    xa, xd = b["adc_tip"][0], b["dac_tip"][0]
    for x, t in [(xa, "W1 out"), (xd, "Ch1 in")]:
        ax.text(x, 43.3, t, ha="center", va="center", size=6.3, color=INK2, zorder=5)
    cable(ax, (xa, 42.5), b["adc_tip"], bend=-1.5, bend1=1.5, color=ADC_C, lw=2.4, arrow=True)
    cable(ax, b["dac_tip"], (xd, 42.5), bend=1.5, bend1=-1.5, color=DAC_C, lw=2.4, arrow=True)
    laptop(ax, cx, 8.2, w=7.0, lines=[])
    ax.text(cx + 4.3, 9.5, "laptop", ha="left", va="center", size=7.5, color=INK)
    usb_down(ax, b, 12.6)
    ax.plot([3.5, 1.6, 1.6, 11.1], [46.0, 46.0, 9.5, 9.5], **USB)          # the M2k's own USB
    ax.text(0.7, 28.0, "USB", ha="center", va="center", size=6.3, color=INK2, rotation=90)

    # ---- (b) two boards, crossed: B's lock-in sweeps A's filter ----
    xA, xB = 40.5, 61.5
    A = board(ax, xA, y0, 18, h, name="board A")
    B = board(ax, xB, y0, 18, h, name="board B")
    node(ax, xA, 23.5, 9, 5, [("filter", BOLD), "(gateware)"], fc=GREEN_BG, ec=C3, size=6.8)
    node(ax, xB, 23.5, 12.5, 5, [("lock-in sweep", BOLD), "(1.08)"], size=6.8)
    for bb, x in [(A, xA), (B, xB)]:
        arrow(ax, bb["adc"], (x - 2.2, 26.0), ms=8)
        arrow(ax, (x + 2.2, 26.0), bb["dac"], ms=8)
    cable(ax, A["dac_tip"], B["adc_tip"], bend=5, color=DAC_C, lw=2.4, arrow=True)
    cable(ax, B["dac_tip"], A["adc_tip"], bend=11, color=ADC_C, lw=2.4, arrow=True)
    ax.text(51.0, 44.3, "A's DAC OUT → B's ADC IN", ha="center", va="center", size=6.8, color=DAC_C)
    ax.text(51.0, 48.6, "B's DAC OUT → A's ADC IN", ha="center", va="center", size=6.8, color=ADC_C)
    laptop(ax, 51.0, 8.2, w=7.0, lines=[])
    ax.text(55.3, 9.5, "laptop", ha="left", va="center", size=7.5, color=INK)
    ax.plot([xA, xA, 48.1], [A["usb"][1], 10.5, 10.5], **USB)
    ax.plot([xB, xB, 53.9], [B["usb"][1], 10.5, 10.5], **USB)
    ax.text(xA + 0.9, 13.4, "USB", ha="left", va="center", size=6.3, color=INK2)
    ax.text(xB - 0.9, 13.4, "USB", ha="right", va="center", size=6.3, color=INK2)

    # ---- (c) one board looped back, the stimulus made inside ----
    cx = 86.0
    C = board(ax, cx, y0, 22, h)
    xa, xd = C["adc"][0], C["dac"][0]
    node(ax, xa, 27.5, 7.5, 3.4, [("capture", BOLD)], fc=BLUE_BG, ec=C1, size=6.6)
    node(ax, xd, 27.5, 7.5, 3.4, [("filter", BOLD)], fc=GREEN_BG, ec=C3, size=6.6)
    node(ax, 88.0, 20.8, 14, 4.6, [("stimulus:", BOLD), "impulse, step, noise, tone"], size=6.4)
    arrow(ax, C["adc"], (xa, 29.4), ms=8)
    arrow(ax, (xd, 23.3), (xd, 25.6), ms=8)
    arrow(ax, (xd, 29.4), C["dac"], ms=8)
    cable(ax, C["dac_tip"], C["adc_tip"], bend=9, color=CABLE, lw=2.4, arrow=True)
    ax.text(cx, 47.3, "the loopback cable", ha="center", va="center", size=6.8, color=INK2)
    laptop(ax, cx, 8.2, w=7.0, lines=[])
    ax.text(cx + 4.3, 9.5, "laptop", ha="left", va="center", size=7.5, color=INK)
    usb_down(ax, C, 12.6)

    for x, t in [(14.5, "(a) function generator and oscilloscope:\nsweep W1, read Ch1 (--m2k)"),
                 (51.0, "(b) a VNA from two boards\n(untested here)"),
                 (86.0, "(c) the stimulus made in gateware:\nthe impulse response is the filter")]:
        ax.text(x, 3.0, t, ha="center", va="center", size=7.6, color=INK, linespacing=1.25)
    note(fig, "what plugs into what")
    finish(fig, "dsp_d_three_ways.png")


# ==== 7.07: the PS2 with this board jacked in ======================================================
def module(ax, x0, y0, w, h, lines, fc=NEUTRAL, ec=NEUTRAL_EDGE, size=7.0, ls="-", top=1.2, color=INK):
    """A PS2 module: a box with its name (bold) and a line or two under it, up against the top
    edge, leaving the rest for its jacks."""
    box(ax, x0, y0, w, h, fc=fc, ec=ec, ls=ls, z=2)
    n = len(lines)
    label(ax, x0 + w / 2, y0 + h - top - n * 1.55 * size / 20, lines, size=size, color=color)


def jack(ax, x, y, text, side, color=INK2, size=6.6):
    """A jack on a module's edge at (x, y), its name just inside the box (side: which edge)."""
    ax.add_patch(Circle((x, y), 0.5, fc=SURFACE, ec=color, lw=1.0, zorder=5))
    dx, dy, ha, va = {"left": (0.9, 0, "left", "center"), "right": (-0.9, 0, "right", "center"),
                      "top": (0, -0.9, "center", "top"), "bottom": (0, 0.9, "center", "bottom")}[side]
    ax.text(x + dx, y + dy, text, ha=ha, va=va, size=size, color=color, zorder=5)


def fig_nmr():
    fig, ax = canvas(10, 6.8)
    ax.text(1.0, 65.3, "The TeachSpin PS2 pulsed NMR spectrometer", ha="left", va="center", size=10.5,
            weight="bold", color=INK)
    ax.text(1.0, 62.2, "with this board jacked in", ha="left", va="center", size=8.8, color=INK2)

    # ---- the magnet, across the top ----
    module(ax, 44, 59, 54, 7.0, [("Magnet 0.49 T, permanent", BOLD),
                                 "the probe with the sample coil, a 10 mm vial; gradient coils x, y, z, z²"], size=7.0)

    # ---- the synthesizer and the receiver, the PS2's own RF path between them ----
    sx0, sx1, rx0, rx1, my0, my1 = 2.0, 30.0, 40.0, 70.0, 36.0, 54.0
    module(ax, sx0, my0, sx1 - sx0, my1 - my0, [("Synthesizer", BOLD), "1–30 MHz; 21 MHz here"], top=3.2)
    jack(ax, sx1, 50.0, "REF Out", "right")
    jack(ax, sx1, 45.0, "Pulsed RF Out", "right")
    ax.text(sx1 - 0.9, 43.5, "(±25 V)", ha="right", va="center", size=6.2, color=INK2, zorder=5)
    jack(ax, sx1, 39.8, "CW Out", "right")
    jack(ax, 16.0, my0, "Pulse In I", "bottom")
    jack(ax, 25.0, my0, "Pulse In Q", "bottom")
    module(ax, rx0, my0, rx1 - rx0, my1 - my0, [("Receiver", BOLD), "I, Q and envelope out"], top=3.2)
    jack(ax, rx0, 50.0, "REF In", "left")
    jack(ax, rx0, 45.0, "RF Pulse In", "left")
    jack(ax, 64.0, my1, "Sample coil", "top")
    for x, t in [(44.0, "RF Out"), (52.0, "Env. Out"), (59.0, "I Out"), (66.0, "Q Out")]:
        jack(ax, x, my0, t, "bottom")
    ax.text(44.0, 38.4, "(21 MHz)", ha="center", va="bottom", size=6.2, color=INK2, zorder=5)
    arrow(ax, (sx1 + 0.5, 50.0), (rx0 - 0.5, 50.0), ms=9)
    arrow(ax, (sx1 + 0.5, 45.0), (rx0 - 0.5, 45.0), color=INK, lw=2.2, ms=11)
    ax.text(35.0, 47.5, "the PS2's own\npath, unchanged", ha="center", va="center", size=6.2, color=INK2,
            linespacing=1.15)
    arrow(ax, (64.0, my1 + 0.5), (64.0, 58.8), both=True, ms=9)

    # ---- the gradient supply, beside the receiver, its coils in the magnet ----
    gx0, gx1 = 76.0, 98.0
    module(ax, gx0, my0, gx1 - gx0, my1 - my0, [("Gradient supply", BOLD), "x, y, z, z² coils"], top=3.2)
    jack(ax, 87.0, my1, "to the coils", "top")
    arrow(ax, (87.0, my1 + 0.5), (87.0, 58.8), ms=9)
    jack(ax, 87.0, my0, "current monitors", "bottom")
    ax.text(87.0, 38.4, "(2.5 Ω, 1.25 Ω)", ha="center", va="bottom", size=6.2, color=INK2, zorder=5)

    # ---- the pulse programmer, greyed: its gates are now the FPGA's ----
    module(ax, 1.0, 20.0, 12.0, 11.0, [("Pulse Programmer", {"weight": "bold", "color": MUTED}),
                                       ("A and B pulses,", {"color": MUTED}), ("0.2 to 20 µs", {"color": MUTED}),
                                       ("replaced by", {"style": "italic"}), ("the FPGA", {"style": "italic"})],
            fc="#f7f6f2", ec=AXIS, ls=(0, (4, 2.5)), size=6.6, top=0.9, color=INK2)
    for x, t in [(5.0, "I"), (9.0, "Q")]:                           # its outputs, unplugged
        ax.plot([x, x], [31.0, 33.3], color=MUTED, lw=1.0, ls=(0, (2, 2)), zorder=3)
        ax.add_patch(Circle((x, 33.6), 0.45, fc=SURFACE, ec=MUTED, lw=1.0, zorder=4))
        ax.text(x + 0.9, 33.6, t, ha="left", va="center", size=6.2, color=MUTED)

    # ---- this board, at the bottom ----
    bx0, bx1, by0, by1 = 42.0, 80.0, 3.0, 20.0
    box(ax, bx0, by0, bx1 - bx0, by1 - by0, fc=BOARD_FC, ec=BOARD_EC, lw=1.2, r=1.2, z=1)
    ax.text((bx0 + bx1) / 2, 4.0, "Icepi Zero + ADC/DAC module", ha="center", va="center", size=6.8, color=INK, zorder=5)
    box(ax, bx0 + 1.5, 5.0, bx1 - bx0 - 3.0, 12.5, fc="none", ec=INK2, lw=0.9, ls=(0, (4, 2.5)), r=0.8, z=2)
    ax.text(bx0 + 2.3, 17.0, "inside the FPGA", ha="left", va="top", size=6.3, color=INK2, style="italic", zorder=5)
    node(ax, 49.5, 10.0, 10.5, 6.0, [("pulse sequencer", BOLD), "(gates, lengths)"], fc=GREEN_BG, ec=C3, size=6.4)
    node(ax, 65.0, 10.0, 16.0, 6.0, [("capture", BOLD), "or 1.08's lock-in at 4 MHz"], fc=BLUE_BG, ec=C1, size=6.4)
    adc_tip = sma(ax, 60.0, by1)
    dac_tip = sma(ax, 74.0, by1)
    ax.text(58.2, by1 + 1.4, "ADC IN", ha="right", va="center", size=6.5, weight="bold", color=C1, zorder=5)
    ax.text(75.8, by1 + 1.4, "DAC OUT\n(not used)", ha="left", va="center", size=6.0, weight="bold", color=MUTED,
            zorder=5, linespacing=1.0)
    arrow(ax, (60.0, by1 - 0.2), (60.0, 13.2), color=C1, ms=8)
    for y in (8.5, 11.5):                                           # the two pins, on the left edge
        ax.add_patch(Rectangle((bx0 - 0.7, y - 0.5), 1.4, 1.0, fc="#9a9a9a", ec="none", zorder=4))

    # ---- the FPGA's two pins to the synthesizer's gates ----
    pin = dict(color=C3, lw=1.5, solid_capstyle="round", solid_joinstyle="round", zorder=3)
    ax.plot([44.25, 16.0, 16.0], [8.5, 8.5, my0 - 0.6], **pin)
    ax.plot([44.25, 25.0, 25.0], [11.5, 11.5, my0 - 0.6], **pin)
    for x in (16.0, 25.0):
        arrow(ax, (x, my0 - 3.0), (x, my0 - 0.6), color=C3, lw=1.5, ms=8)
    ax.text(26.5, 15.2, "two 3.3 V pins:\nany sequence, 20 ns steps", ha="left", va="center", size=6.8,
            color=C3, linespacing=1.2)

    # ---- the receiver's outputs, and the gradient's monitors, to ADC IN one at a time ----
    bus = dict(color=C1, lw=1.3, solid_capstyle="round", zorder=3)
    ax.plot([44.0, 87.0], [27.0, 27.0], **bus)
    for x in (44.0, 52.0, 59.0, 66.0, 87.0):
        ax.plot([x, x], [my0 - 0.6, 27.0], **bus)
        ax.add_patch(Circle((x, 27.0), 0.45, fc=C1, ec="none", zorder=4))
    arrow(ax, (60.0, 27.0), (60.0, adc_tip[1] + 0.2), color=C1, lw=1.3, ms=9)
    ax.text(76.5, 28.0, "one at a time, BNC to SMA", ha="center", va="bottom", size=6.4, color=C1)
    ax.text(88.5, 31.2, "for imaging:\nread the currents", ha="left", va="center", size=6.6, color=INK2, linespacing=1.2)
    ax.text(63.5, 24.3, "RF Out: 21 MHz sampled at 25 MS/s lands at 4 MHz,\naliasing on purpose; then 1.08's lock-in",
            ha="left", va="center", size=6.6, color=INK2, linespacing=1.2)

    # ---- never: the ±25 V pulse, not to this board ----
    ax.plot([33.0, 33.0], [45.0, 24.0], color=INK2, lw=1.1, ls=(0, (4, 2.5)), zorder=3)
    arrow(ax, (33.0, 24.0), (33.0, 21.0), ls=(0, (4, 2.5)), lw=1.1, ms=9)
    ax.plot([31.4, 34.6], [33.9, 37.1], color=RED, lw=2.6, solid_capstyle="round", zorder=6)
    ax.plot([31.4, 34.6], [37.1, 33.9], color=RED, lw=2.6, solid_capstyle="round", zorder=6)
    ax.text(35.4, 36.0, "never", ha="left", va="center", size=8.5, weight="bold", color=RED)
    ax.text(35.4, 34.0, "to this board", ha="left", va="center", size=6.4, color=RED)

    note(fig, "not built: a plan", top=False)
    finish(fig, "dsp_d_nmr.png")


# ==== 7.04: the filter as a LiteX peripheral, loaded three ways ===================================
def fig_litex_filter():
    fig, ax = canvas(10, 5.6)
    ax.text(1.0, 53.0, "The same filter, loaded three ways", ha="left", va="center", size=10.5,
            weight="bold", color=INK)
    ax.text(1.0, 50.2, "every way ends at the same twenty-five registers", ha="left", va="center", size=8, color=INK2)

    # ---- the FPGA: 2.03's SoC, with the filter added ----
    fx0, fx1, fy0, fy1 = 28.0, 74.0, 3.0, 49.0
    box(ax, fx0, fy0, fx1 - fx0, fy1 - fy0, fc="none", ec=INK2, lw=1.3, ls=(0, (5, 3)), r=1.5, z=1)
    ax.text(fx0 + 1.5, fy1 - 1.2, "inside the FPGA: 2.03's SoC, with the filter added", ha="left", va="top",
            size=7.5, color=INK2, style="italic")
    by = 30.0                                                        # the bus
    ax.plot([30.0, 72.0], [by, by], color=INK2, lw=4, solid_capstyle="round", zorder=1)
    ax.text(30.5, by + 0.9, "Wishbone bus: the CSRs", ha="left", va="bottom", size=6.6, color=INK2)
    node(ax, 39.0, 38.6, 17, 12, [("VexRiscv CPU", BOLD), "RISC-V, 50 MHz:", "the firmware, bare metal,", "or Linux"], size=7)
    ax.plot([44.0, 44.0], [by, 32.6], color=INK2, lw=2.0, zorder=1)
    node(ax, 63.0, 38.5, 15, 6, [("UART bridge", BOLD), "2.06: the laptop on the bus"], size=7)
    ax.plot([63.0, 63.0], [by, 35.5], color=INK2, lw=2.0, zorder=1)
    stub = dict(color=MUTED, lw=1.3, zorder=1)
    tbox(ax, 39.0, 22.0, 19, 7.5, [("filter: 25 CSRs", {"weight": "bold", "size": 7}),
                                   ("at 0xf000f800", {"family": MONO, "size": 6.4}),
                                   "b0 … b15, a1 … a4, src, out,", "tone, dac_source, status"],
         fc=GREEN_BG, ec=C3, size=6.2, gap=1.85)
    ax.plot([33.0, 33.0], [25.75, by], **stub)
    for x, t in [(54.5, "funcgen"), (62.0, "lockin"), (69.5, "capture")]:
        node(ax, x, 22.5, 6.5, 4, [(t, {"color": MUTED})], fc="#f7f6f2", ec=AXIS, size=6.4)
        ax.plot([x, x], [24.5, by], **stub)
    # the datapath under the registers, and the mux to the DAC
    tbox(ax, 39.5, 11.0, 16, 6, [("filter_core.sv", {"family": MONO, "weight": "bold", "size": 6.6}),
                                 "the same datapath", "as 7.03's filter.sv"], size=6.2)
    arrow(ax, (39.0, 18.25), (39.0, 14.2), ms=8)
    ax.text(40.0, 16.2, "the settings, as ports", ha="left", va="center", size=6.0, color=INK2)
    tbox(ax, 58.0, 11.0, 9, 7, [("dac_source", {"family": MONO, "weight": "bold", "size": 6.4}), "0: funcgen", "1: filter"],
         size=6.2)
    arrow(ax, (47.5, 11.0), (53.3, 11.0), ms=8)
    arrow(ax, (54.5, 20.5), (54.5, 14.7), ms=8)
    ax.text(55.3, 17.6, "its waveform", ha="left", va="center", size=6.0, color=INK2)
    for x, t, c in [(38.0, "ADC IN", C1), (58.0, "DAC OUT", C2)]:          # the pins, the converters beyond
        ax.add_patch(Rectangle((x - 0.7, fy0 - 0.6), 1.4, 1.2, fc="#9a9a9a", ec="none", zorder=4))
        ax.text(x, fy0 - 1.5, t, ha="center", va="top", size=6.5, weight="bold", color=c)
    arrow(ax, (38.0, fy0 + 0.6), (38.0, 7.8), color=C1, ms=8)
    arrow(ax, (58.0, 7.5), (58.0, fy0 + 0.8), color=C2, ms=8)

    # ---- the three writers ----
    tbox(ax, 13.0, 42.0, 24, 8, [("C firmware in the CPU", BOLD), ("adda> filter lowpass", {"family": MONO, "size": 6.4}),
                                 "tens of ns per register"])
    arrow(ax, (25.0, 42.0), (30.3, 42.0), ms=10)
    tbox(ax, 13.0, 33.0, 24, 8, [("MicroPython on the board's Linux", BOLD),
                                 ("machine.mem32[0xf000f800 + …]", {"family": MONO, "size": 6.2}),
                                 "microseconds; no laptop"])
    arrow(ax, (25.0, 34.0), (30.3, 34.0), ms=10)
    tbox(ax, 89.0, 38.5, 20, 11, [("the laptop", BOLD), ("filter_remote.py → litex_server", {"family": MONO, "size": 6.2}),
                                  "a few ms per register;", "scipy designs the filter"])
    arrow(ax, (79.0, 38.5), (70.7, 38.5), ms=10)
    ax.text(74.8, 39.4, "USB serial", ha="center", va="bottom", size=6.0, color=INK2)

    # ---- where the bitstream and csr.csv come from ----
    tbox(ax, 89.0, 10.0, 20, 6.5, [("$ python3 icepi_adda_soc.py --build", {"family": MONO, "size": 5.9}),
                                   "LiteX builds the SoC (2.03)"], size=6.4)
    thin = dict(ls=(0, (3, 2)), lw=0.9, ms=7, color=MUTED)
    arrow(ax, (79.0, 10.0), (fx1 + 0.2, 10.0), **thin)
    arrow(ax, (89.0, 13.25), (89.0, 32.8), **thin)
    ax.text(89.8, 23.6, "csr.csv", ha="left", va="center", size=6.2, family=MONO, color=INK2)
    ax.text(89.8, 21.9, "the names", ha="left", va="center", size=6.0, color=INK2)
    ax.text(89.0, 5.9, "the bitstream and csr.csv\nare generated together", ha="center", va="top", size=6.2,
            color=INK2, linespacing=1.2)

    # ---- the price of the bus (7.04's table) ----
    ax.text(1.0, 24.0, "the price of the bus", ha="left", va="center", size=7, weight="bold", color=INK)
    cols = [1.0, 10.5, 17.5]
    rows = [("", "per register", "per new design"), ("firmware", "tens of ns", "compile + upload"),
            ("bridge", "a few ms", "rerun"), ("MicroPython", "µs", "rerun")]
    for k, r in enumerate(rows):
        y = 21.0 - 2.4 * k
        for x, t in zip(cols, r):
            ax.text(x, y, t, ha="left", va="center", size=6.3, color=INK2 if k == 0 else INK,
                    style="italic" if k == 0 else "normal")
    ax.plot([1.0, 26.5], [19.8, 19.8], color=AXIS, lw=0.8)
    note(fig, "the contract is csr.csv")
    finish(fig, "dsp_d_litex_filter.png")


if __name__ == "__main__":
    for name, f in [("three_ways", fig_three_ways), ("nmr", fig_nmr), ("litex_filter", fig_litex_filter)]:
        if want(name):
            f()
