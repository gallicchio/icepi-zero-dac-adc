"""Appendix D's sketches of the AMOD and RF-MOD boards, an idea, not a design: 100 x 100 mm
boards of 20 mm tiles, each tile one circuit, numbered and named, the powered ones framed in
colour with their supply, SMA jacks as circles (two on a tile, in opposite corners; a circuit
with more jacks gets a 40 x 20 tile).  The Pmod plug sits at the LEFT end of the board's
bottom edge (seen with the plug pointing down), so that the host board's second Pmod socket,
0.9 inch away, stays free for a second module: a speaker, a microphone, an audio codec.

    python3 fig_amod.py      # writes tutorial/img/amod_sketch.png, amod_rf.png and amod_adv.png
"""
import os

from matplotlib.patches import Arc, Circle, FancyArrowPatch, FancyBboxPatch, Rectangle
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
          ("A7", "PLL 74HC4046:\nin, VCO out", 1, 2, "+5"), ("A8", "heat: R,\nNTC, TMP36", 1, 1, "+5"),
          ("A9", "mixer MC1496:\nRF, LO, IF", 2, 3, "±5"), ("A10", "light: LED, laser,\nphotodiode + TIA", 2, 3, "+5"),
          ("A11", "40 kHz ultrasound:\ndriver, receiver", 2, 2, "+5"),
          ("A12", "audio: speaker, electret\nmic, 1-bit DAC jack", 2, 2, "+5")]
RF = [("R1", "915 MHz antenna:\nprinted inverted-F (TI DN023)", 2, 1, "ant"), ("R2", "2.45 GHz\nband-pass", 1, 2, None),
      ("R3", "2.4 GHz\nantenna", 1, 1, "ant"),
      ("R4", "915 MHz\nSAW", 1, 2, None), ("R5", "LNA 0.1–6 GHz\nQPL9547", 1, 2, "+5"),
      ("R6", "2.4 GHz front end RFX2401C:\nPA, LNA, switch", 2, 3, "+3.3"),
      ("R7", "TX mixer LTC5510:\nIF in, LO, RF out", 2, 3, "+5"), ("R8", "RX mixer LTC5510:\nRF in, LO, IF out", 2, 3, "+5"),
      ("R9", "power, 25 MHz\nTCXO, ref in/out", 1, 1, "+5"), ("R10", "TX PLL\nMAX2871", 1, 2, "+3.3"),
      ("R11", "RX PLL\nMAX2871", 1, 2, "+3.3"), ("R12", "gain block\nGALI-84+", 1, 2, "+8")]
# the two advanced boards (ordered so that each row of four tiles fills)
ADV = [("Y1", "power: USB-C 5 V in, ±15 V,\n±5 V, and a 0–60 V rail", 2, 0, "±15"),
       ("Y4", "laser diode driver: 0–500 mA,\nmod in, bias-T, TTL pulse", 2, 3, "+5"),
       ("Y3", "piezo cantilever and\nshadow sensor: a plant", 2, 2, "+5"),
       ("Y8", "NMR duplexer, OPA847\npreamp, tune/match, coil", 2, 3, "±5"),
       ("Y2", "piezo driver:\nOPA454 ×30\n0–60 V", 1, 2, "HV"),
       ("Y5", "TEC / heater:\nH-bridge,\nNTC bridge", 1, 1, "+5"),
       ("Y6", "fast photodiode:\nPIN + TIA\n20 MHz", 1, 1, "+5"),
       ("Y7", "NMR pulse amp:\nTHS3491\n1.5 W, gated", 1, 2, "±15"),
       ("Y9", "coil / motor:\nH-bridge,\ncurrent sense", 1, 1, "+5"),
       ("Y10", "slow I/O: I2C\n8 × 16-bit ADC\n8 × 12-bit DAC", 1, 0, "+5"),
       ("Y11", "INA849 bridge\namp; Hall\nsensor", 1, 2, "±15"),
       ("Y12", "varactor-pulled\ncrystal: an\nelectronic cavity", 1, 3, "±15")]
RF2 = [("X11", "2.87 GHz\nsplit ring (NV)", 1, 1, "ring"),
       ("X1", "I/Q modulator ADL5375:\nI, Q, LO in, RF out", 2, 4, "+5"),
       ("X3", "RX PLL\nMAX2871 on\na VCXO; REF IN", 1, 2, "+3.3"),
       ("X2", "I/Q demodulator ADL5380:\nRF, LO in, I, Q out", 2, 4, "+5"),
       ("X4", "hardware Costas loop: I/Q arms,\nsign(I)·Q, PI → VCXO; monitors", 2, 4, "+3.3"),
       ("X5", "RX chain: LNA QPL9547,\nDSA PE43711, ADL5611", 2, 2, "+5"),
       ("X7", "T/R switch SKY13351:\nTX, RX, ANT", 2, 3, "+3.3"),
       ("X6", "TX gain\nADL5611,\nTX MON", 1, 2, "+5"),
       ("X8", "detectors:\nAD8318 RF,\nAD8310 BB", 1, 2, "+5"),
       ("X9", "power: USB-C\n1.5 A, ideal\ndiode, LDOs", 1, 0, "+5"),
       ("X10", "slow I/O: I2C\nDAC, ADC;\nPCA9555 lines", 1, 0, "+3.3")]
SUPPLY = {"±5": C2, "+5": C1, "+3.3": C3, "+8": INK, "±15": "#8e44ad", "HV": "#c0392b"}
T, GAP, INSET = 20.0, 1.5, 3.4                           # mm: tile, gap between tiles, jack centre
COPPER = "#b87333"


def jacks(n, wt):
    """Jack centres on a tile wt wide: one in the bottom-left corner, two in opposite
    corners, more spread along the tile, alternately low and high."""
    if n == 1:
        return [(INSET, INSET)]
    return [(INSET + i * (wt - 2 * INSET) / (n - 1), INSET if i % 2 == 0 else T - INSET) for i in range(n)]


def draw_antenna(ax, x, y, wt, left):
    """A printed inverted-F along the board's top edge: the arm parallel to the edge, the
    shorting stub to ground and the feed (a sketch, not the design note's dimensions)."""
    top = y + T + 5.5
    if left:                                   # the 915 MHz one: a long arm, folded once
        xs = [x + wt - 6, x + wt - 6, x - 4, x - 4, x + 4]
        ys = [y + T - 1, top, top, top - 4, top - 4]
        ax.plot([x + wt - 9, x + wt - 9], [y + T - 1, top], color=COPPER, lw=1.4, zorder=3)
    else:                                      # the 2.4 GHz one: short, meandered
        xs = [x + 4, x + 4, x + 7, x + 7, x + 10, x + 10, x + 13, x + 13, x + 16, x + 16]
        ys = [y + T - 1, top, top, top - 4, top - 4, top, top, top - 4, top - 4, top]
        ax.plot([x + 2, x + 2], [y + T - 1, top], color=COPPER, lw=1.4, zorder=3)
    ax.plot(xs, ys, color=COPPER, lw=1.4, zorder=3, solid_joinstyle="miter")


def draw_ring(ax, x, y, wt):
    """A split-ring resonator: a copper ring with one gap, fed from a microstrip; the
    diamond sits in the gap's field (a sketch)."""
    cx, cy = x + wt / 2 + 1.5, y + T / 2 + 4
    ax.add_patch(Arc((cx, cy), 9, 9, theta1=20, theta2=340, color=COPPER, lw=2.2, zorder=3))
    ax.plot([x + INSET + 2, cx - 4.5], [y + INSET, cy], color=COPPER, lw=1.4, zorder=3)


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
        if supply in ("ant", "ring"):             # an antenna or a resonator: bare board, no copper
            left, right = (7.75 if col == 0 else 0), (7.75 if col + w == 4 else 0)   # out to the edges
            ax.add_patch(Rectangle((x - left, y), wt + left + right, T + 7.75, fc="#cdbf94", ec="none",
                                   zorder=2))
            if supply == "ant":
                draw_antenna(ax, x, y, wt, left=(col == 0))
                jack = [(wt - INSET, INSET) if col == 0 else (INSET, INSET)]
            else:
                draw_ring(ax, x, y, wt)
                jack = [(INSET, INSET)]
            for jx, jy in jack:
                ax.add_patch(Circle((x + jx, y + jy), 1.9, fc="#d8c46a", ec="#8a7a30", lw=0.6, zorder=3))
            ax.text(x + (1.2 if col else wt - 1.2), y + T - 4, num, ha="left" if col else "right", va="top",
                    size=6.5, weight="bold", color=INK, zorder=3)
            ax.text(x + wt / 2, y + T / 2 - 1.5 - (3 if supply == "ring" else 0), name, ha="center",
                    va="center", size=5.2, color=INK2, zorder=3, linespacing=1.1)
            col += w
            continue
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
        # a 2 x 6 right-angle plug, 18 mm wide, at the LEFT end of the bottom edge: the host's
        # second socket, 22.9 mm (0.9 inch) to its right, stays free for a second module
        ax.add_patch(Rectangle((x0 + 6, -0.5), 18, 5, fc="#222222", ec="none", zorder=3))
        ax.add_patch(Rectangle((x0 + 6 + 22.86, -0.5), 18, 5, fc="none", ec=MUTED, lw=0.7, ls=":", zorder=3))
        ax.text(x0 + 6, -6.5, "Pmod plug (3.3 V, 8 FPGA pins) at the left end; the host's second socket,\n"
                "dotted, 0.9 inch away, stays free for a speaker, microphone or audio-codec module",
                ha="left", va="top", size=6.2, color=INK2)


# ---- amod_sketch.png: the two HF boards --------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 5.8))
ax.set_xlim(-2, 222); ax.set_ylim(-21, 110); ax.set_aspect("equal"); ax.axis("off")
board(ax, 0, PASSIVE, "AMOD-P: passive, nothing to power")
board(ax, 120, ACTIVE, "AMOD-A: active, each tile behind a jumper", pmod=True)
ax.text(0, -18, "SMA jacks: the gold circles, every circuit its own.  Frames: none = passive, blue = +5 V, "
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


fig, ax = plt.subplots(figsize=(10, 5.2))
ax.set_xlim(-2, 232); ax.set_ylim(-20, 110); ax.set_aspect("equal"); ax.axis("off")
board(ax, 0, RF, "RF-MOD: 915 MHz, 2.4 GHz, and a stretch to 5.8", pmod=True, colour="#1b4f6b")
# the signal chain, cabled with SMA, transmitter above and receiver below
X0, YT, YR = 128, 78, 22
xs = [X0, X0 + 22, X0 + 44, X0 + 66, X0 + 88]
block(ax, xs[0], YT, "DAC\n6.25 MHz", fc="#e8eef6")
block(ax, xs[1], YT, "R7\nmixer")
block(ax, xs[2], YT, "R4 or R2\nfilter")
block(ax, xs[3], YT, "R12 or R6\nPA", dashed=True)
block(ax, xs[0], YR, "ADC", fc="#e8eef6")
block(ax, xs[1], YR, "P5 low-pass,\nA2·A3 ×1000", w=19)
block(ax, xs[2], YR, "R8\nmixer")
block(ax, xs[3], YR, "R4 or R2\nfilter")
block(ax, xs[4], YR, "R5 or R6\nLNA")
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
ax.text(xs[4] + 4, (YT + YR) / 2 + 6, "R1 or R3 to\nR1 or R3, or\na cable and\n−30 dB of pads", size=6, color=C1, va="center")
# the two synthesizers, one reference
block(ax, xs[1], 50 + 8, "R10 TX PLL", w=19, h=6)
block(ax, xs[2], 50 - 8, "R11 RX PLL", w=19, h=6)
arrow(ax, (xs[1], 50 + 11), (xs[1], YT - 4.5))
arrow(ax, (xs[2], 50 - 11), (xs[2], YR + 4.5))
block(ax, xs[0], 50, "R9 25 MHz\nreference", w=17, h=8)
ax.plot([xs[0] + 8.5, xs[1] - 9.5], [50, 50 + 8], color=C3, lw=0.9)
ax.plot([xs[0] + 8.5, xs[2] - 9.5], [50, 50 - 8], color=C3, lw=0.9)
ax.text(xs[0], 50 - 7, "to both PLLs, and\nthe FPGA board's clock", size=5.5, color=C3, ha="center", va="top")
ax.text(xs[2], YT + 8, "transmit", size=7, color=INK2, ha="center", weight="bold")
ax.text(xs[2], YR - 8.5, "receive", size=7, color=INK2, ha="center", weight="bold")
ax.text(0, -17, "Frames: blue = +5 V, green = +3.3 V, black = +8 V.  Tan: bare board under the antennas, no copper on any layer.  "
        "Dashed: optional.  An idea, not a layout.", size=7.5, color=INK2, ha="left")
fig.text(0.995, 0.99, "a sketch (Appendix D)", ha="right", va="top", size=8, color=MUTED)
fig.savefig(os.path.join(IMG, "amod_rf.png"), dpi=150, facecolor=SURFACE, bbox_inches="tight")
plt.close(fig)


# ---- amod_adv.png: the two advanced boards ------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 5.8))
ax.set_xlim(-2, 222); ax.set_ylim(-21, 110); ax.set_aspect("equal"); ax.axis("off")
board(ax, 0, ADV, "AMOD-2: lasers, piezos, spins, slow I/O", pmod=True, colour="#4a3a6b")
board(ax, 120, RF2, "RF-MOD-2: quadrature, a hardware loop, detectors", pmod=True, colour="#1b4f6b")
ax.text(0, -18, "Frames: blue = +5 V, orange = ±5 V, green = +3.3 V, purple = ±15 V, red = the 0–60 V rail.  "
        "Tan: bare board under the resonator.  An idea, drawn to scale, not a layout.", size=7.5, color=INK2, ha="left")
fig.text(0.995, 0.99, "a sketch (Appendix D)", ha="right", va="top", size=8, color=MUTED)
fig.savefig(os.path.join(IMG, "amod_adv.png"), dpi=150, facecolor=SURFACE, bbox_inches="tight")
plt.close(fig)
print("wrote", os.path.join(IMG, "amod_sketch.png"), "amod_rf.png and amod_adv.png")
