"""Appendix D's sketches of the AMOD, an idea, not a design: three 100 x 100 mm boards of
20 mm tiles, each tile one circuit, numbered and named, the powered ones framed in colour
with their supply, SMA jacks as circles (two on a tile, in opposite corners; a circuit with
more jacks gets a 40 x 20 tile).

    python3 fig_amod.py      # writes tutorial/img/amod_sketch.png and amod_rf.png
"""
import os

from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle
from plotstyle import plt, C1, C2, C3, INK, INK2, MUTED, SURFACE

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, "..", "..", "tutorial", "img")

# (number, name, width in tiles, SMA jacks, supply or None), in the order they pack, four
# tiles to a row
PASSIVE = [("P1", "π pad\n−20 dB", 1, 2, None), ("P2", "RC\nlow-pass", 1, 2, None),
           ("P3", "RC\nhigh-pass", 1, 2, None), ("P4", "series RLC\n~1 MHz, trimmer", 1, 2, None),
           ("P5", "LC low-pass\n9 MHz", 1, 2, None), ("P6", "LC low-pass\n100 kHz", 1, 2, None),
           ("P7", "LC band-pass\n4.7–7.8 MHz", 1, 2, None), ("P8", "crystal\n4 MHz", 1, 2, None),
           ("P9", "ceramic filter\n455 kHz", 1, 2, None), ("P10", "diode\nclipper", 1, 2, None),
           ("P11", "delay line: 20 × 20 ns,\ntapped every 100 ns", 2, 5, None),
           ("P12", "LEDs, 4 colours\nDIP switch", 1, 1, None),
           ("P13", "AM loopstick and tuning capacitor", 3, 1, None)]
ACTIVE = [("A1", "power: USB-C,\n−5 V pump", 1, 0, "±5"), ("A2", "gain ×10\n20 MHz", 1, 2, "±5"),
          ("A3", "gain ×100", 1, 2, "±5"), ("A4", "HF LNA\n40 dB", 1, 2, "+5"),
          ("A5", "Johnson\nnoise ×1000", 1, 1, "±5"), ("A6", "ΔΣ ADC: pin\n+ comparator", 1, 1, "+5"),
          ("A7", "1-bit DAC\n→ headphones", 1, 0, None), ("A8", "heat: R,\nNTC, TMP36", 1, 1, "+5"),
          ("A9", "mixer MC1496:\nRF, LO, IF", 2, 3, "±5"), ("A10", "light: LED, laser,\nphotodiode + TIA", 2, 3, "+5"),
          ("A11", "40 kHz ultrasound:\ndriver, receiver", 2, 2, "+5"), ("A12", "speaker,\nelectret mic", 2, 2, "+5")]
RF = [("R1", "power, 25 MHz\nTCXO, ref in/out", 1, 1, "+5"), ("R2", "TX PLL\nMAX2870", 1, 2, "+3.3"),
      ("R3", "RX PLL\nMAX2870", 1, 2, "+3.3"), ("R4", "LNA 0.1–6 GHz\nQPL9547", 1, 2, "+5"),
      ("R5", "gain block\nGALI-84+", 1, 2, "+8"), ("R6", "915 MHz\nSAW", 1, 2, None),
      ("R7", "2.45 GHz\nband-pass", 1, 2, None), ("R8", "λ/4 stub\n2.4 GHz", 1, 2, None),
      ("R9", "TX mixer LTC5510:\nIF in, LO, RF out", 2, 3, "+5"), ("R10", "RX mixer LTC5510:\nRF in, LO, IF out", 2, 3, "+5"),
      ("R11", "2.4 GHz front end RFX2401C:\nPA, LNA, switch", 2, 3, "+3.3"),
      ("R12", "calibration: open,\nshort, load, thru", 2, 5, None)]
SUPPLY = {"±5": C2, "+5": C1, "+3.3": C3, "+8": INK}
T, GAP, INSET = 20.0, 1.5, 3.4                           # mm: tile, gap between tiles, jack centre


def jacks(n, wt):
    """Jack centres on a tile wt wide: one in the bottom-left corner, two in opposite
    corners, more spread along the tile, alternately low and high."""
    if n == 1:
        return [(INSET, INSET)]
    return [(INSET + i * (wt - 2 * INSET) / (n - 1), INSET if i % 2 == 0 else T - INSET) for i in range(n)]


def board(ax, x0, tiles, title, pmod=False, colour="#1f5f3a"):
    ax.add_patch(FancyBboxPatch((x0, 0), 100, 100, boxstyle="round,pad=0,rounding_size=3", fc=colour,
                                ec="#16452a", lw=1.5, zorder=1))
    ax.text(x0 + 50, 104, title, ha="center", va="bottom", size=10, weight="bold", color=INK)
    col, row = 0, 0
    for num, name, w, n, supply in tiles:
        if col + w > 4:
            col, row = 0, row + 1
        x, y = x0 + 7.75 + col * (T + GAP), 100 - 7.75 - (row + 1) * T - row * GAP
        wt = w * T + (w - 1) * GAP
        ec, lw = ("#f6f4ec", 0.8) if supply is None else (SUPPLY[supply], 2.6)
        ax.add_patch(Rectangle((x, y), wt, T, fc="#f6f4ec", ec=ec, lw=lw, zorder=2))
        ax.text(x + 1.2, y + T - 1.2, num, ha="left", va="top", size=6.5, weight="bold", color=INK, zorder=3)
        if supply:
            ax.text(x + 1.2 + 2.2 * len(num), y + T - 1.2, supply, ha="left", va="top", size=6, weight="bold",
                    color=SUPPLY[supply], zorder=3)
        ax.text(x + wt / 2, y + T / 2 - 0.3, name, ha="center", va="center", size=5.2, color=INK2, zorder=3,
                linespacing=1.1)
        for jx, jy in jacks(n, wt):
            ax.add_patch(Circle((x + jx, y + jy), 1.9, fc="#d8c46a", ec="#8a7a30", lw=0.6, zorder=3))
        col += w
    if pmod:
        ax.add_patch(Rectangle((x0 + 30, -0.5), 40, 5, fc="#222222", ec="none", zorder=3))
        ax.text(x0 + 50, -2.5, "Pmod: 3.3 V and 8 FPGA pins", ha="center", va="top", size=7, color=INK2)


# ---- amod_sketch.png: the two HF boards --------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 5.6))
ax.set_xlim(-2, 222); ax.set_ylim(-18, 110); ax.set_aspect("equal"); ax.axis("off")
board(ax, 0, PASSIVE, "AMOD-P: passive, nothing to power")
board(ax, 120, ACTIVE, "AMOD-A: active, each tile behind a jumper", pmod=True)
ax.text(0, -15, "SMA jacks: the gold circles, every circuit its own.  Frames: none = passive, blue = +5 V, "
        "orange = ±5 V.  An idea, drawn to scale, not a layout.", size=7.5, color=INK2, ha="left")
fig.text(0.995, 0.99, "a sketch (Appendix D)", ha="right", va="top", size=8, color=MUTED)
fig.savefig(os.path.join(IMG, "amod_sketch.png"), dpi=150, facecolor=SURFACE, bbox_inches="tight")
plt.close(fig)


# ---- amod_rf.png: the RF board, and one way to cable it ---------------------------------
def block(ax, x, y, text, w=17, h=9, dashed=False, fc="#f6f4ec"):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0,rounding_size=1.2",
                                fc=fc, ec=INK2, lw=0.9, ls="--" if dashed else "-", zorder=2))
    ax.text(x, y, text, ha="center", va="center", size=6.3, color=INK, zorder=3, linespacing=1.1)


def arrow(ax, a, b, colour=INK2):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=8, color=colour, lw=0.9, zorder=1,
                                 shrinkA=0, shrinkB=0))


fig, ax = plt.subplots(figsize=(10, 5.0))
ax.set_xlim(-2, 232); ax.set_ylim(-14, 110); ax.set_aspect("equal"); ax.axis("off")
board(ax, 0, RF, "AMOD-RF: 915 MHz, 2.4 GHz, and a stretch to 5.8", pmod=True, colour="#1b4f6b")
# the signal chain, cabled with SMA, transmitter above and receiver below
X0, YT, YR = 128, 78, 22
xs = [X0, X0 + 22, X0 + 44, X0 + 66, X0 + 88]
block(ax, xs[0], YT, "DAC\n6.25 MHz", fc="#e8eef6")
block(ax, xs[1], YT, "R9\nmixer")
block(ax, xs[2], YT, "R6 or R7\nfilter")
block(ax, xs[3], YT, "R5 or R11\nPA", dashed=True)
block(ax, xs[0], YR, "ADC", fc="#e8eef6")
block(ax, xs[1], YR, "A3\n×100")
block(ax, xs[2], YR, "R10\nmixer")
block(ax, xs[3], YR, "R6 or R7\nfilter")
block(ax, xs[4], YR, "R4 or R11\nLNA")
for i in range(3):
    arrow(ax, (xs[i] + 8.5, YT), (xs[i + 1] - 8.5, YT))
for i in range(4, 0, -1):
    arrow(ax, (xs[i] - 8.5, YR), (xs[i - 1] + 8.5, YR))
# antennas, or a cable and a pad between them
ax.plot([xs[3] + 8.5, xs[4] + 2], [YT, YT], color=INK2, lw=0.9)
ax.plot([xs[4] + 2, xs[4] + 2], [YT, YT + 7], color=INK2, lw=0.9)
ax.plot([xs[4] - 1, xs[4] + 2, xs[4] + 5], [YT + 11, YT + 7, YT + 11], color=INK2, lw=0.9)
ax.plot([xs[4], xs[4]], [YR + 4.5, YR + 20], color=INK2, lw=0.9)
ax.plot([xs[4] - 3, xs[4], xs[4] + 3], [YR + 24, YR + 20, YR + 24], color=INK2, lw=0.9)
ax.annotate("", xy=(xs[4] + 0.5, YR + 27), xytext=(xs[4] + 2, YT + 4),
            arrowprops=dict(arrowstyle="->", color=C1, lw=1, ls=":"))
ax.text(xs[4] + 4, (YT + YR) / 2 + 6, "the air, or\na cable and\n−30 dB of\npads", size=6, color=C1, va="center")
# the two synthesizers, one reference
block(ax, xs[1], 50 + 8, "R2 TX PLL", w=19, h=6)
block(ax, xs[2], 50 - 8, "R3 RX PLL", w=19, h=6)
arrow(ax, (xs[1], 50 + 11), (xs[1], YT - 4.5))
arrow(ax, (xs[2], 50 - 11), (xs[2], YR + 4.5))
block(ax, xs[0], 50, "R1 25 MHz\nreference", w=17, h=8)
ax.plot([xs[0] + 8.5, xs[1] - 9.5], [50, 50 + 8], color=C3, lw=0.9)
ax.plot([xs[0] + 8.5, xs[2] - 9.5], [50, 50 - 8], color=C3, lw=0.9)
ax.text(xs[0], 50 - 7, "to both PLLs, and\nthe FPGA board's clock", size=5.5, color=C3, ha="center", va="top")
ax.text(xs[2], YT + 8, "transmit", size=7, color=INK2, ha="center", weight="bold")
ax.text(xs[2], YR - 8.5, "receive", size=7, color=INK2, ha="center", weight="bold")
ax.text(0, -11, "Frames: blue = +5 V, green = +3.3 V, black = +8 V; the RF tiles' jacks are the same SMAs.  "
        "Dashed: optional.  An idea, not a layout.", size=7.5, color=INK2, ha="left")
fig.text(0.995, 0.99, "a sketch (Appendix D)", ha="right", va="top", size=8, color=MUTED)
fig.savefig(os.path.join(IMG, "amod_rf.png"), dpi=150, facecolor=SURFACE, bbox_inches="tight")
plt.close(fig)
print("wrote", os.path.join(IMG, "amod_sketch.png"), "and amod_rf.png")
