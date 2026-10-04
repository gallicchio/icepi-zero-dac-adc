"""Where things plug in: the stack seen from above, USB connectors at the bottom and the
module's two SMA connectors at the top.  ADC IN is the LEFT SMA and DAC OUT the RIGHT one
(the module's ACLK and DCLK pins, and the adapter's silkscreen, agree).

    python3 fig_stack.py        # writes tutorial/img/stack_*.png
"""
import os

import matplotlib.patches
import numpy as np
from matplotlib.patches import FancyBboxPatch, Rectangle, Circle, PathPatch, Ellipse
from matplotlib.path import Path
from plotstyle import plt, save, C1, C2, C3, INK, INK2, MUTED

IMG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tutorial", "img")
GREEN, GREEN2, BLACK, GOLD = "#2f8f4e", "#257341", "#1d1d1f", "#c9a227"
ADC_C, DAC_C = C1, C2                      # blue for ADC IN, orange for DAC OUT
CABLE = "#6d6d6d"


def rbox(ax, x, y, w, h, fc, ec="none", r=1.5, lw=1, z=1):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                fc=fc, ec=ec, lw=lw, zorder=z))


PROG = 24       # the x of the USB-C marked "Flash": the FT231X, to the laptop


def stack(ax, x0=0, y0=0, name=None, unused=(), usb=True):
    """One stack at (x0, y0).  Returns the tips of the two SMA connectors, ADC IN first.
    usb=True draws the PROG USB cable and its label; usb=False leaves that to the caller."""
    for dy, c in [(-1.2, GREEN2), (0, GREEN)]:              # the Icepi Zero, and the adapter on it
        rbox(ax, x0, y0 + dy, 65, 30, c, r=3)
    # along the bottom edge: mini-HDMI, then three USB-C (Flash, 1, 2)
    for i, xc in enumerate([10, PROG, 37, 50]):
        ax.add_patch(Rectangle((x0 + xc - 4, y0 - 4.5), 8, 5, fc="#d0d0d0" if i else "#9a9a9a", ec="none", zorder=2))
    if usb:
        ax.add_patch(Rectangle((x0 + PROG - 2.5, y0 - 9), 5, 4.5, fc="#333", ec="none", zorder=2))   # the plug
        ax.plot([x0 + PROG] * 2, [y0 - 9, y0 - 12], color="#333", lw=3, solid_capstyle="butt", zorder=2)
        ax.text(x0 + PROG + 4, y0 - 9.5, "PROG USB (marked Flash)\n→ laptop", ha="left", va="center",
                fontsize=10, color=INK2, linespacing=1.0)
    rbox(ax, x0 + 15, y0 + 8, 35, 50, BLACK, r=1.2, z=3)    # the ADC/DAC module
    ax.text(x0 + 32.5, y0 + 22, "ADC/DAC\nmodule", ha="center", va="center", fontsize=10, color="#bbbbbb", zorder=4)
    tips = []
    for xc, lab, col in [(21, "ADC IN", ADC_C), (44, "DAC OUT", DAC_C)]:
        ax.add_patch(Rectangle((x0 + xc - 3, y0 + 56), 6, 4.5, fc=GOLD, ec="none", zorder=4))
        ax.add_patch(Rectangle((x0 + xc - 1.8, y0 + 60.5), 3.6, 5, fc=GOLD, ec="none", zorder=4))
        faded = lab in unused
        # beside its connector, above the module (whose top edge is at y0 + 58)
        ax.text(x0 + xc + (-4.5 if xc < 30 else 4.5), y0 + 59, lab + ("\n(not used)" if faded else ""),
                ha="right" if xc < 30 else "left", va="bottom", fontsize=13 if not faded else 10,
                weight="bold", color=MUTED if faded else col, zorder=5, linespacing=1.0)
        tips.append((x0 + xc, y0 + 65.5))
    if name:
        ax.text(x0 + 32.5, y0 - 16, name, ha="center", va="top", fontsize=13, weight="bold", color=INK, zorder=5)
    return tips


def cable(ax, p0, p1, bend=12, bend1=None, color=CABLE, lw=3.2, z=6, arrow=False):
    """A coax from p0 to p1, leaving p0 upward by `bend` (downward if negative) and arriving
    at p1 from `bend1` above it (default: the same as bend); with arrow=True, an arrowhead
    halfway shows which way the signal goes (from p0 to p1)."""
    (x0, y0), (x1, y1) = p0, p1
    pts = [(x0, y0), (x0, y0 + bend), (x1, y1 + (bend if bend1 is None else bend1)), (x1, y1)]
    path = Path(pts, [Path.MOVETO, Path.CURVE4, Path.CURVE4, Path.CURVE4])
    ax.add_patch(PathPatch(path, fc="none", ec=color, lw=lw, capstyle="round", zorder=z))
    if arrow:
        P = np.array(pts, float)
        bez = lambda t: ((1 - t) ** 3) * P[0] + 3 * ((1 - t) ** 2) * t * P[1] + 3 * (1 - t) * t * t * P[2] + t ** 3 * P[3]
        a, b = bez(0.5), bez(0.56)
        ax.annotate("", b, a, arrowprops=dict(arrowstyle="-|>", color=color, lw=0, mutation_scale=16), zorder=z + 1)


def thing(ax, x, y, w, h, text, fc="#f3f1ea", ec=INK2, fontsize=11):
    """A box at least w by h around the text, centred at (x, y)."""
    t = ax.text(x, y, text, ha="center", va="center", fontsize=fontsize, color=INK, zorder=7)
    bb = t.get_window_extent(ax.figure.canvas.get_renderer()).transformed(ax.transData.inverted())
    w, h = max(w, bb.width + 8), max(h, bb.height + 5)
    rbox(ax, x - w / 2, y - h / 2, w, h, fc, ec=ec, r=1.5, lw=1.2, z=6)
    return y - h / 2                     # the bottom edge, where a cable attaches


def figure(w, h, xlim, ylim):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax


def finish(fig, ax, name, caption):
    ax.set_title(caption.replace("Seen from above: ", "Seen from above:\n") if fig.get_figwidth() < 5 else caption,
                 fontsize=12)
    save(fig, os.path.join(IMG, name))
    print("wrote", name)


def main():
    # ---- the loopback cable: DAC OUT -> ADC IN ------------------------------------------------------
    fig, ax = figure(3.8, 4.1, (-12, 77), (-16, 100))
    adc, dac = stack(ax)
    cable(ax, dac, adc, bend=22)
    ax.text(32.5, 90, "a coax cable, SMA to SMA", ha="center", fontsize=11, color=INK2)
    finish(fig, ax, "stack_loopback.png", "Seen from above: the loopback cable")


    # ---- something into ADC IN -------------------------------------------------------------------------
    def into_adc(name, text, caption, w=34, h=12):
        fig, ax = figure(3.8, 4.3, (-12, 77), (-16, 104))
        adc, dac = stack(ax, unused=("DAC OUT",))
        bottom = thing(ax, 26, 90, w, h, text)
        cable(ax, (21, bottom), adc, bend=-6, bend1=6, color=ADC_C, arrow=True)
        finish(fig, ax, name, caption)


    into_adc("stack_mp3.png", "phone or MP3 player\n(headphone output)", "Seen from above: music into ADC IN")
    into_adc("stack_funcgen.png", "function generator\n(±5 V at most)", "Seen from above: a signal into ADC IN")
    into_adc("stack_reference.png", "10 MHz reference\nthrough a 10 dB\nattenuator (§4.09)", "Seen from above: a reference into ADC IN", h=16)


    # ---- a scope on DAC OUT -----------------------------------------------------------------------------
    fig, ax = figure(3.8, 4.1, (-12, 77), (-16, 100))
    adc, dac = stack(ax, unused=("ADC IN",))
    bottom = thing(ax, 44, 88, 30, 12, "oscilloscope\n(1 MΩ input)")
    cable(ax, dac, (44, bottom), bend=6, bend1=-6, color=DAC_C, arrow=True)
    finish(fig, ax, "stack_scope.png", "Seen from above: a scope on DAC OUT")


    # ---- a circuit between DAC OUT and ADC IN ------------------------------------------------------------
    def circuit(name, text, caption):
        fig, ax = figure(3.8, 4.3, (-12, 77), (-16, 106))
        adc, dac = stack(ax)
        bottom = thing(ax, 32.5, 92, 34, 12, text)
        cable(ax, dac, (44, bottom), bend=6, bend1=-6, color=DAC_C, arrow=True)
        cable(ax, (21, bottom), adc, bend=-6, bend1=6, color=ADC_C, arrow=True)
        finish(fig, ax, name, caption)


    for fname, text in [("stack_circuit.png", "your circuit"),
                        ("stack_rc.png", "R, C or L\n(§4.02)"),
                        ("stack_crystal.png", "4 MHz crystal\n+ 50 Ω (§4.03)"),
                        ("stack_diodes.png", "1 kΩ + two diodes\n(§4.04)"),
                        ("stack_stub.png", "SMA T + 5 m stub\n(§4.05)"),
                        ("stack_sound.png", "40 kHz transmitter\n→ air → receiver (§4.06)"),
                        ("stack_optical.png", "LED → light →\nphotodiode (§4.07)"),
                        ("stack_plant.png", "1 kΩ + 1 µF\n(§4.08)")]:
        circuit(fname, text, "Seen from above: DAC OUT → circuit → ADC IN")

    # ---- two boards, cross-connected ---------------------------------------------------------------------
    fig, ax = figure(7.6, 4.3, (-12, 187), (-24, 112))
    a_adc, a_dac = stack(ax, 0, 0, "board A")
    b_adc, b_dac = stack(ax, 110, 0, "board B")
    cable(ax, a_dac, b_adc, bend=16, color=DAC_C, arrow=True)
    cable(ax, b_dac, a_adc, bend=34, color=ADC_C, arrow=True)
    ax.text(87.5, 80.5, "A's DAC OUT → B's ADC IN", ha="center", fontsize=11, color=DAC_C)
    ax.text(87.5, 96, "B's DAC OUT → A's ADC IN", ha="center", fontsize=11, color=ADC_C)
    finish(fig, ax, "stack_two_boards.png", "Seen from above: two boards, two cables, crossed")


    # ---- radio: a loop on A's DAC OUT, a loop on B's ADC IN ----------------------------------------------
    def loop(ax, x, y, r, col, capacitor_text):
        ax.add_patch(Circle((x, y), r, fc="none", ec="#b87333", lw=3, zorder=6))
        ax.text(x, y, capacitor_text, ha="center", va="center", fontsize=10, color=col, zorder=7)


    fig, ax = figure(7.6, 4.6, (-12, 187), (-24, 120))
    a_adc, a_dac = stack(ax, 0, 0, "board A", unused=("ADC IN",))
    b_adc, b_dac = stack(ax, 110, 0, "board B", unused=("DAC OUT",))
    loop(ax, 44, 97, 18, DAC_C, "transmitting\nloop, with C\nin series")
    loop(ax, 131, 97, 18, ADC_C, "receiving\nloop, with C\nin parallel")
    cable(ax, a_dac, (44, 79), bend=4, color=DAC_C, arrow=True)
    cable(ax, (131, 79), b_adc, bend=-4, bend1=4, color=ADC_C, arrow=True)
    ax.annotate("", (111, 97), (64, 97), arrowprops=dict(arrowstyle="<->", color=INK2, lw=1))
    ax.text(87.5, 100, "about 1 m", ha="center", va="bottom", fontsize=10.5, color=INK2)
    finish(fig, ax, "stack_radio.png", "Seen from above: board A transmits, board B listens")

    # ---- AM radio: DAC OUT to a wire near a radio; ADC IN from an antenna ---------------------------------
    fig, ax = figure(4.6, 4.3, (-30, 100), (-16, 112))
    adc, dac = stack(ax)
    ax.plot([dac[0], dac[0] + 4, dac[0] + 22], [dac[1], dac[1] + 18, dac[1] + 22], color=DAC_C, lw=1.5, zorder=6)
    for r in (3, 5.5, 8):
        ax.add_patch(matplotlib.patches.Arc((dac[0] + 22, dac[1] + 22), 2 * r, 2 * r, theta1=-30, theta2=60, color=DAC_C, lw=1))
    thing(ax, 84, 103, 20, 10, "AM radio", fc="#fbe9df", ec=DAC_C)
    ax.text(dac[0] + 8, dac[1] + 10, "a short wire,\nnear the radio", fontsize=10.5, color=DAC_C, va="center")
    ax.plot([adc[0], adc[0] - 6, adc[0] - 40], [adc[1], adc[1] + 30, adc[1] + 42], color=ADC_C, lw=1.5, zorder=6)
    ax.text(adc[0] - 22, adc[1] + 22, "a long wire\nantenna", fontsize=10.5, color=ADC_C, ha="right")
    finish(fig, ax, "stack_am.png", "Seen from above: transmit on DAC OUT, listen on ADC IN")


if __name__ == "__main__":
    main()
