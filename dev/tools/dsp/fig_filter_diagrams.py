"""7.01-7.03 block diagrams, COMPUTED (no hardware), in the style of fig_comms_diagrams.py
(its canvas/node/arrow helpers copied from fig_openers.py, not imported, so this file stands
alone).

dsp_d_filters.png:
  (a) an FIR as a delay line (z^-1 boxes), taps (triangles) and an adder chain, 5 taps
  (b) the symmetric trick: samples that share a tap are added first, then multiplied once
  (c) an IIR in direct form I, with the feedback path; and the one-tap case y += (x - y)/16
dsp_d_clocks.png:
  (d) what filter.sv does in the two clocks between ADC samples, with its 20 multipliers

    python3 fig_filter_diagrams.py
"""
import os
import sys

from matplotlib.patches import Arc, Circle, Polygon, FancyBboxPatch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from plotstyle import plt, C1, C2, INK, INK2, MUTED, AXIS   # noqa: E402

IMG = os.path.join(HERE, "..", "..", "..", "tutorial", "img")
DPI = 130
NEUTRAL, NEUTRAL_EDGE = "#f3f1ea", INK2
BLUE_BG, ORANGE_BG = "#e4eefb", "#fde9df"
MONO = "DejaVu Sans Mono"
BOLD = {"weight": "bold"}


# ---- drawing helpers, as fig_openers.py: a canvas in units of 0.1 inch ---------------------
def canvas(w, h):
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
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                fc=fc, ec=ec, lw=lw, ls=ls, zorder=z))


def label(ax, x, y, lines, size=9.5, color=INK, z=5, ha="center", va="center", gap=1.55):
    items = [(s, {}) if isinstance(s, str) else s for s in lines]
    heights = [gap * kw.get("size", size) / 10 for s, kw in items]
    top = y + sum(heights) / 2
    for (s, kw), hgt in zip(items, heights):
        top -= hgt
        opts = dict(size=size, color=color, ha=ha, va="baseline", zorder=z)
        opts.update(kw)
        ax.text(x, top + 0.28 * hgt, s, **opts)


def node(ax, cx, cy, w, h, lines, fc=NEUTRAL, ec=NEUTRAL_EDGE, size=9.5, ls="-", lw=1.2):
    box(ax, cx - w / 2, cy - h / 2, w, h, fc=fc, ec=ec, ls=ls, lw=lw)
    label(ax, cx, cy, lines, size=size)


def arrow(ax, p0, p1, color=INK2, lw=1.3, style="-|>", ms=11, ls="-", z=3, both=False, rad=0):
    ax.annotate("", p1, p0, zorder=z, arrowprops=dict(
        arrowstyle="<|-|>" if both else style, color=color, lw=lw, mutation_scale=ms,
        linestyle=ls, shrinkA=0, shrinkB=0, connectionstyle=f"arc3,rad={rad}"))


def wire(ax, pts, color=INK2, lw=1.3, z=3):
    ax.plot([p[0] for p in pts], [p[1] for p in pts], color=color, lw=lw, zorder=z, solid_capstyle="round")


def circle_op(ax, cx, cy, sym="+", r=1.6, color=INK2):
    ax.add_patch(Circle((cx, cy), r, fc="white", ec=color, lw=1.3, zorder=4))
    ax.text(cx, cy, sym, ha="center", va="center", size=12, color=color, zorder=5)


def dot(ax, x, y, color=INK2):
    ax.add_patch(Circle((x, y), 0.45, fc=color, ec=color, zorder=5))


# ---- the parts of a filter diagram ------------------------------------------------------
def delay(ax, cx, cy, w=5.0, h=3.6):
    node(ax, cx, cy, w, h, [("z⁻¹", {"size": 10})], size=10)


def delay_line(ax, xs, y, w=5.0, names=None):
    """Dots at xs on the line y, a z^-1 box between each pair, names above the dots."""
    for k in range(len(xs) - 1):
        mid = (xs[k] + xs[k + 1]) / 2
        delay(ax, mid, y, w=w)
        arrow(ax, (xs[k] + 0.1, y), (mid - w / 2 - 0.1, y))
        arrow(ax, (mid + w / 2 + 0.1, y), (xs[k + 1] - 0.1, y))
    for k, x in enumerate(xs):
        dot(ax, x, y)
        if names:
            ax.text(x, y + 2.8, names[k], ha="center", va="center", size=7.6, color=INK2, family=MONO)


def tap(ax, cx, cy, text, color=INK2, size=2.6):
    """A multiplier: a triangle pointing down, its gain written beside it."""
    s = size
    ax.add_patch(Polygon([(cx - s * 0.8, cy + s * 0.75), (cx + s * 0.8, cy + s * 0.75), (cx, cy - s * 0.75)],
                         closed=True, fc="white", ec=color, lw=1.3, zorder=4))
    ax.text(cx + s * 0.95, cy + 0.1, text, ha="left", va="center", size=8.5, color=color, zorder=5)


def note(fig, text="computed, not measured"):
    fig.text(0.995, 0.995, text, ha="right", va="top", size=8, color=MUTED)


def title(ax, x, y, text, size=10.5):
    ax.text(x, y, text, ha="left", va="center", size=size, weight="bold", color=INK)


def mono(ax, x, y, text, size=8.5, ha="left", va="center"):
    ax.text(x, y, text, ha=ha, va=va, size=size, color=INK, family=MONO)


def italic(ax, x, y, text, size=8, va="top"):
    ax.text(x, y, text, ha="left", va=va, size=size, color=INK2, style="italic")


def fig_filters():
    fig, ax = canvas(10, 10.8)
    note(fig)
    # ================= (a) the FIR: delay line, taps, adder chain =========================
    title(ax, 1.0, 105.5, "(a)  An FIR: a delay line, a tap on every sample, and an adder chain")
    yl, yt, ya = 99.0, 92.0, 85.0                         # the line, the taps, the adders
    xs = [8.0, 18.5, 29.0, 39.5, 50.0]
    mono(ax, 1.0, yl, "x[n]", size=9.5)
    arrow(ax, (5.0, yl), (xs[0] - 0.1, yl))
    delay_line(ax, xs, yl, names=["x[n]", "x[n−1]", "x[n−2]", "x[n−3]", "x[n−4]"])
    for k, x in enumerate(xs):
        arrow(ax, (x, yl - 0.4), (x, yt + 1.9))
        tap(ax, x, yt, "h%d" % k, color=C1)
    for k, x in enumerate(xs):
        if k == 0:
            wire(ax, [(x, yt - 2.0), (x, ya), (xs[1] - 2.2, ya)])
            arrow(ax, (xs[1] - 2.2, ya), (xs[1] - 1.7, ya))
        else:
            arrow(ax, (x, yt - 2.0), (x, ya + 1.7))
            circle_op(ax, x, ya)
            if k < 4:
                arrow(ax, (x + 1.7, ya), (xs[k + 1] - 1.7, ya))
    arrow(ax, (xs[4] + 1.7, ya), (57.0, ya))
    mono(ax, 57.5, ya + 1.4, "y[n] = h0 x[n] + h1 x[n−1] + h2 x[n−2]")
    mono(ax, 57.5, ya - 1.4, "       + h3 x[n−3] + h4 x[n−4]")
    italic(ax, 57.5, ya - 4.0, "a dot product of the taps with the last five samples,\n"
           "slid along one sample at a time: the convolution.\nFive multipliers and four adders, every sample.")
    italic(ax, 57.5, yl + 1.5, "fir.sv: 16 taps, fixed; filter.sv: 16 taps the laptop loads.", va="center")

    # ================= (b) the symmetric trick ===============================================
    title(ax, 1.0, 77.0, "(b)  Symmetric taps (h4 = h0, h3 = h1): add the pair first, multiply once")
    yl, yt, ya = 66.0, 54.5, 47.5
    xs = [8.0, 17.0, 26.0, 35.0, 44.0]
    mono(ax, 1.0, yl, "x[n]", size=9.5)
    arrow(ax, (5.0, yl), (xs[0] - 0.1, yl))
    delay_line(ax, xs, yl, w=4.4)
    for k, x in enumerate(xs):
        ax.text(x, yl - 2.6 if k != 2 else yl - 2.6, ["x[n]", "x[n−1]", "x[n−2]", "x[n−3]", "x[n−4]"][k],
                ha="center", va="center", size=7.2, color=INK2, family=MONO)
    # the outer pair, x[n] + x[n-4], added above the line; the sum goes over the top to h0
    yo = yl + 6.0
    wire(ax, [(xs[0], yl + 0.4), (xs[0], yo), (26.0 - 2.2, yo)])
    arrow(ax, (26.0 - 2.2, yo), (26.0 - 1.7, yo))
    wire(ax, [(xs[4], yl + 0.4), (xs[4], yo), (26.0 + 2.2, yo)])
    arrow(ax, (26.0 + 2.2, yo), (26.0 + 1.7, yo))
    circle_op(ax, 26.0, yo)
    wire(ax, [(26.0, yo + 1.7), (26.0, yo + 3.0), (56.0, yo + 3.0), (56.0, yt + 2.4)])
    arrow(ax, (56.0, yt + 2.4), (56.0, yt + 1.9))
    tap(ax, 56.0, yt, "h0", color=C1)
    # the middle sample, x[n-2], goes over the top too, to h2
    wire(ax, [(xs[2], yl + 0.4), (xs[2], yl + 3.2), (xs[4] - 0.9, yl + 3.2)])
    ax.add_patch(Arc((xs[4], yl + 3.2), 1.8, 1.8, theta1=0, theta2=180, color=INK2, lw=1.3, zorder=3))   # a hop
    wire(ax, [(xs[4] + 0.9, yl + 3.2), (50.0, yl + 3.2), (50.0, yt + 2.4)])
    arrow(ax, (50.0, yt + 2.4), (50.0, yt + 1.9))
    tap(ax, 50.0, yt, "h2", color=C1)
    # the inner pair, x[n-1] + x[n-3], added below the line, to h1
    yp = yl - 5.6
    wire(ax, [(xs[1], yl - 0.4), (xs[1], yp), (26.0 - 2.2, yp)])
    arrow(ax, (26.0 - 2.2, yp), (26.0 - 1.7, yp))
    wire(ax, [(xs[3], yl - 0.4), (xs[3], yp), (26.0 + 2.2, yp)])
    arrow(ax, (26.0 + 2.2, yp), (26.0 + 1.7, yp))
    circle_op(ax, 26.0, yp)
    arrow(ax, (26.0, yp - 1.7), (26.0, yt + 1.9))
    tap(ax, 26.0, yt, "h1", color=C1)
    # the adder chain: h2 + h0 at x = 50, then + h1 at x = 26, then y
    wire(ax, [(56.0, yt - 2.0), (56.0, ya), (50.0 + 2.2, ya)])
    arrow(ax, (50.0 + 2.2, ya), (50.0 + 1.7, ya))
    arrow(ax, (50.0, yt - 2.0), (50.0, ya + 1.7))
    circle_op(ax, 50.0, ya)
    arrow(ax, (50.0 - 1.7, ya), (26.0 + 1.7, ya))
    arrow(ax, (26.0, yt - 2.0), (26.0, ya + 1.7))
    circle_op(ax, 26.0, ya)
    arrow(ax, (26.0 - 1.7, ya), (19.0, ya))
    mono(ax, 18.5, ya, "y[n]", size=9.5, ha="right")
    mono(ax, 62.0, 70.5, "y = h0 (x[n] + x[n−4])\n  + h1 (x[n−1] + x[n−3])\n  + h2 x[n−2]", va="top")
    italic(ax, 62.0, 61.5, "3 multipliers instead of 5; fir.sv's 16 taps need 8.\n"
           "The adders are cheap (LUTs, and the chip has\nthousands); the multipliers are the scarce part\n(28 on the ECP5-25F).")
    italic(ax, 62.0, 52.0, "Why they are symmetric: a mirror-image kernel delays\nevery frequency by the same (N−1)/2 samples, so the\n"
           "phase is a straight line in f (\"linear phase\") and a\nsquare wave comes out rounded but not skewed.")

    # ================= (c) the IIR, direct form I, and the one-tap case =======================
    title(ax, 1.0, 41.0, "(c)  An IIR in direct form I: the feed-forward taps b, then the output fed back through a")
    mono(ax, 1.0, 37.5, "y[n] = b0 x[n] + b1 x[n−1] + b2 x[n−2] − a1 y[n−1] − a2 y[n−2]      (filter.sv: 16 b's, 4 a's, all ÷ 8192)",
         size=8.2)
    yl, yt, ya = 32.0, 25.5, 19.5
    xs = [8.0, 17.0, 26.0]
    mono(ax, 1.0, yl, "x[n]", size=9.5)
    arrow(ax, (5.0, yl), (xs[0] - 0.1, yl))
    delay_line(ax, xs, yl, w=4.4, names=["x[n]", "x[n−1]", "x[n−2]"])
    for k, x in enumerate(xs):
        arrow(ax, (x, yl - 0.4), (x, yt + 1.9))
        tap(ax, x, yt, "b%d" % k, color=C1)
        wire(ax, [(x, yt - 2.0), (x, ya)])
    xa = 36.0                                             # the adder
    wire(ax, [(xs[2], ya), (xs[0], ya)])
    arrow(ax, (xs[2], ya), (xa - 1.7, ya))
    circle_op(ax, xa, ya)
    arrow(ax, (xa + 1.7, ya), (46.0, ya))
    dot(ax, 44.0, ya)
    mono(ax, 47.0, ya, "y[n]", size=9.5)
    # the feedback: y -> z^-1 -> z^-1 (to the right), taps -a1, -a2 back into the adder
    ys = [44.0, 53.0, 62.0]
    yf = ya - 6.0
    wire(ax, [(44.0, ya), (44.0, yf)])
    delay_line(ax, ys, yf, w=4.4)
    for k in (1, 2):
        ax.text(ys[k], yf - 2.6, "y[n−%d]" % k, ha="center", va="center", size=7.2, color=INK2, family=MONO)
        arrow(ax, (ys[k], yf - 3.8), (ys[k], yf - 5.6))
        tap(ax, ys[k], yf - 7.5, "−a%d" % k, color=C2)
        wire(ax, [(ys[k], yf - 9.5), (ys[k], yf - 10.5)])
    wire(ax, [(ys[2], yf - 10.5), (xa, yf - 10.5)])
    arrow(ax, (xa, yf - 10.5), (xa, ya - 1.7))
    ax.text(ys[2] + 3.5, yf - 10.5, "the feedback: a loop.  The output\nhelps make the next output.",
            ha="left", va="center", size=8, color=C2, style="italic")
    # the one-tap case
    ox, oy = 66.0, 29.5
    italic(ax, ox, 36.0, "the one-tap case, y += (x − y)/16:", size=8.5, va="center")
    mono(ax, ox, oy, "x", size=9.5)
    arrow(ax, (ox + 2.0, oy), (ox + 5.6, oy))
    circle_op(ax, ox + 7.3, oy, "−")
    arrow(ax, (ox + 9.0, oy), (ox + 12.0, oy))
    node(ax, ox + 15.0, oy, 5.4, 3.4, ["× 1/16"], size=8.5)
    arrow(ax, (ox + 17.8, oy), (ox + 20.6, oy))
    circle_op(ax, ox + 22.3, oy, "+")
    arrow(ax, (ox + 24.0, oy), (ox + 27.0, oy))
    mono(ax, ox + 27.5, oy, "y", size=9.5)
    dot(ax, ox + 26.0, oy)
    wire(ax, [(ox + 26.0, oy), (ox + 26.0, oy - 6.5), (ox + 15.0, oy - 6.5)])
    node(ax, ox + 15.0, oy - 6.5, 4.4, 3.2, ["z⁻¹"], size=9)
    wire(ax, [(ox + 12.8, oy - 6.5), (ox + 7.3, oy - 6.5)])
    arrow(ax, (ox + 7.3, oy - 6.5), (ox + 7.3, oy - 1.7))
    wire(ax, [(ox + 22.3, oy - 6.5), (ox + 22.3, oy - 4.0)])
    arrow(ax, (ox + 22.3, oy - 4.0), (ox + 22.3, oy - 1.7))
    italic(ax, ox, oy - 10.5, "b0 = 1/16, a1 = −15/16: one pole at 15/16, an RC\nwith τ = 16 samples.  No multiplier at all:\n"
           "÷ 16 is a shift (iir.sv).")
    finish(fig, "dsp_d_filters.png")


def fig_clocks():
    """(d) what filter.sv does per sample: the two clocks, the 20 multipliers."""
    fig, ax = canvas(10, 4.8)
    note(fig, "the clocks of filter.sv, not measured")
    title(ax, 1.0, 45.5, "(d)  What filter.sv does between two ADC samples: 40 ns, two clocks of 20 ns, 20 multipliers")
    # the time axis
    x0, dx, y = 10.0, 16.0, 35.0
    ax.plot([x0 - 2, x0 + 4 * dx + 2], [y, y], color=INK2, lw=1.2)
    for k in range(5):
        x = x0 + k * dx
        ax.plot([x, x], [y - 0.8, y + 0.8], color=INK2, lw=1.2)
        ax.text(x, y - 2.3, "clock %s" % "ABABA"[k], ha="center", va="center", size=8, color=INK2)
    for k in (0, 2, 4):
        x = x0 + k * dx
        ax.add_patch(Polygon([(x - 1.2, y + 4.4), (x + 1.2, y + 4.4), (x, y + 3.0)], fc=C1, ec=C1, zorder=4))
        ax.text(x, y + 6.0, "ADC sample n%s" % ("" if k == 0 else "+%d" % (k // 2)), ha="center", va="center",
                size=8, color=C1)
    ax.text(x0 + dx, y + 1.6, "20 ns", ha="center", va="center", size=7.5, color=MUTED)
    ax.text(x0 + 3 * dx, y + 1.6, "20 ns", ha="center", va="center", size=7.5, color=MUTED)
    N, B, O = (NEUTRAL, NEUTRAL_EDGE), (BLUE_BG, C1), (ORANGE_BG, C2)
    rows = [("feed-forward\n(no loop)", 24.0, [
                (0, [("shift x[n] into", BOLD), "the delay line"], N),
                (1, [("16 multiplies", BOLD), "b_k × x[n−k]"], B),
                (2, [("4 sums of 4", BOLD), "products"], N),
                (3, [("one sum of 4", BOLD), "→ F[n]"], N)]),
            ("feedback\n(a loop)", 11.0, [
                (1, [("4 multiplies", BOLD), "a1 y[n−1]; a2..a4 ×", "y[n−1..n−3] for n+1"], O),
                (2, [("G = F − a2..a4 terms", BOLD), "y[n] = (G − a1 y[n−1])", ">> 13, saturate"], N)])]
    for name, yr, blocks in rows:
        ax.text(1.0, yr + 2.0, name, ha="left", va="center", size=8, color=INK2, style="italic")
        for k, lines, (fc, ec) in blocks:
            cx = x0 + k * dx + dx / 2
            node(ax, cx, yr, 15.0, 8.0, lines, fc=fc, ec=ec, size=7.5)
            arrow(ax, (cx, y - 3.6), (cx, yr + 4.2), color=AXIS, lw=0.8, ms=7)
    # the loop arrow: y[n] (end of clock A at n+1) back to the a1 multiply of the next sample
    xa, xb = x0 + 2 * dx + dx / 2 + 7.5, x0 + 3 * dx + dx / 2
    wire(ax, [(xa, 11.0), (xa + 2.5, 11.0), (xa + 2.5, 3.5), (xb - 12.0, 3.5), (xb - 12.0, 6.0)], color=C2)
    arrow(ax, (xb - 12.0, 5.0), (xb - 12.0, 7.0), color=C2)
    ax.text(xa + 3.5, 6.2, "y[n] is the next sample's y[n−1]: one multiply,\none add, and it is needed again.  "
            "A deeper\npipeline here would be a different filter.", ha="left", va="center", size=7.4, color=C2)
    ax.text(x0 + 4 * dx + 3.0, 24.0, "16 + 4 = 20 of the ECP5-25F's\n28 MULT18X18D blocks, each an\n18 × 18-bit product per clock.\n"
            "(10, time-shared over the two\nclocks, would do: a multiplexer\neach, and no gain in speed.)",
            ha="left", va="center", size=7.4, color=INK2)
    finish(fig, "dsp_d_clocks.png")


if __name__ == "__main__":
    fig_filters()
    fig_clocks()
