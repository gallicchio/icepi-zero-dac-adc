"""5.03's opening figures.

tt_spacetime.png  the two-way exchange as a space-time diagram, with every symbol the
                  page's equations use (no data)
tt_measure.png    how one delay is measured: awgcap.sv on one board, looped back through
                  the 101.5 cm cable, recording its own multitone (data/tt_loop_1m.npz,
                  recorded with awgcap.upload/record and twoway.multitone(1))
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "src", "twoboard"))
from plotstyle import plt, save, dots, C1, C2, C3, INK, INK2, MUTED   # noqa: E402
import twoway                                                          # noqa: E402

IMG = os.path.join(HERE, "..", "..", "..", "tutorial", "img")

# ---- figure 1: the space-time diagram ------------------------------------------------
TH, DAB, DBA = 0.35, 1.0, 1.15            # theta, d_AB, d_BA, in arbitrary time units
XA, XB = 0.0, 4.0
fig, ax = plt.subplots(figsize=(8.6, 4.9))
ax.axis("off")
ax.set_xlim(-3.0, 7.3)
ax.set_ylim(-0.45, 1.95)
for x, name in [(XA, "board A"), (XB, "board B")]:
    ax.annotate("", (x, 1.85), (x, -0.3), arrowprops=dict(arrowstyle="->", color=INK, lw=1.4))
    ax.text(x, -0.42, name, ha="center", va="center", fontsize=11, weight="bold")
ax.text(XA - 0.1, 1.85, "time", ha="right", va="top", fontsize=9, color=MUTED)


def tick(x, y, text, side, va):
    """A mark on a board's time line, labelled on the inside (side +1: to the right),
    above it (va="bottom") or below it (va="top"), clear of the arrows."""
    ax.plot([x - 0.1, x + 0.1], [y, y], color=INK, lw=2)
    ax.text(x + 0.12 * side, y + (0.04 if va == "bottom" else -0.04), text,
            ha="left" if side > 0 else "right", va=va, fontsize=9, color=INK)


def slanted(x0, y0, x1, y1, frac, text, color, offset):
    """Text along the line (x0, y0)-(x1, y1), at `frac` of the way, shifted sideways by
    `offset` points (positive: above the line)."""
    p0, p1 = ax.transData.transform([(x0, y0), (x1, y1)])
    ang = np.degrees(np.arctan2(p1[1] - p0[1], p1[0] - p0[0]))
    if ang > 90: ang -= 180
    if ang < -90: ang += 180
    ax.annotate(text, (x0 + frac * (x1 - x0), y0 + frac * (y1 - y0)), xytext=(0, offset),
                textcoords="offset points", rotation=ang, rotation_mode="anchor", ha="center",
                va="center", color=color, fontsize=9.5)


tick(XA, 0, "A's loop starts:\nA's \"noon\"", +1, "top")
tick(XB, TH, "B's loop starts:\nB's \"noon\"", -1, "top")
tick(XB, DAB, "A's waveform\narrives at B", -1, "bottom")
tick(XA, TH + DBA, "B's waveform\narrives at A", +1, "bottom")
ax.plot([XA, XB + 0.45], [0, 0], ":", color=MUTED, lw=1)
ax.annotate("", (XB, DAB), (XA, 0), arrowprops=dict(arrowstyle="-|>", color=C1, lw=2, mutation_scale=14))
ax.annotate("", (XA, TH + DBA), (XB, TH), arrowprops=dict(arrowstyle="-|>", color=C2, lw=2, mutation_scale=14))
slanted(XA, 0, XB, DAB, 0.33, "A's waveform takes $d_{AB}$", C1, -10)
slanted(XB, TH, XA, TH + DBA, 0.7, "B's waveform takes $d_{BA}$", C2, 10)


def bracket(x, y0, y1, text, color, side):
    dx = 0.3 * side
    ax.plot([x + dx * 0.5, x + dx, x + dx, x + dx * 0.5], [y0, y0, y1, y1], color=color, lw=1.4)
    ax.text(x + dx * 1.3, (y0 + y1) / 2, text, ha="left" if side > 0 else "right", va="center",
            fontsize=10.5, color=color)


bracket(XA, 0, TH + DBA, "$\\tau_A = \\theta + d_{BA}$:\nwhen B's waveform\narrives, by A's clock", C2, -1)
bracket(XB, TH, DAB, "$\\tau_B = -\\theta + d_{AB}$:\nwhen A's waveform\narrives, by B's clock", C1, +1)
ax.annotate("", (XB + 0.3, TH), (XB + 0.3, 0), arrowprops=dict(arrowstyle="<->", color=INK2, lw=1.2,
                                                                 shrinkA=0, shrinkB=0))
ax.text(XB + 0.4, TH / 2, "$\\theta$: how far B's\nclock lags A's", fontsize=9.5, color=INK2, va="center")
save(fig, os.path.join(IMG, "tt_spacetime.png"))

# ---- figure 2: measuring one delay ---------------------------------------------------
d = np.load(os.path.join(HERE, "..", "..", "data", "tt_loop_1m.npz"))
w, rec = d["wave"], d["recs"][0]
N = len(w)
tau = twoway.delay(rec, w)
fig, (a, b) = plt.subplots(2, 1, figsize=(8, 6.4))
V = lambda c: (np.asarray(c, float) - c.mean()) / 25.35
t_play = np.arange(N) / 50e6 * 1e6
t_rec = np.arange(N) / 25e6 * 1e6
sel_p, sel_r = t_play < 2.0, t_rec < 2.0
a.plot(t_play[sel_p], (w[sel_p] - 128) * 0.0307, color=MUTED, lw=1.0,
       label="what the DAC played, from the loop start (0.0307 V per DAC code)")
dots(a, t_rec[sel_r], V(rec)[sel_r], C1, size=3.5, label="what the ADC recorded, from the same instant")
a.annotate("", (0.2 + tau * 1e6, 3.4), (0.2, 3.4), arrowprops=dict(arrowstyle="->", color=INK2))
a.text(0.2 + tau * 1e6 / 2, 3.65, f"τ = {tau * 1e9:.1f} ns later", ha="center", fontsize=9, color=INK2)
a.set_xlim(0, 2.0)
a.set_ylim(-4, 4.4)
a.set_xlabel("time since the loop start (µs)")
a.set_ylabel("voltage (V)")
a.set_title("A noise-like waveform (tones from 0.2 to 10 MHz) and its echo through the loop")
a.legend(loc="lower left", fontsize=8, ncol=1)
# the cross-spectrum's phase
r = rec.reshape(2, N // 2).mean(0); r = r - r.mean()
ww = w[::2] - w.mean()
C = np.fft.rfft(r) * np.conj(np.fft.rfft(ww))
f = np.fft.rfftfreq(N // 2, 1 / 25e6)
band = (f >= 0.3e6) & (f <= 9.5e6)
ph = np.unwrap(np.angle(C[band]))
fit = np.polyfit(f[band], ph, 1)
b.plot(f[band] / 1e6, ph / (2 * np.pi), ".", color=C1, markersize=2.5, label="phase of each tone, in turns")
b.plot(f[band] / 1e6, np.polyval(fit, f[band]) / (2 * np.pi), color=C2, lw=1.2,
       label=f"straight line: slope = −τ = −{-fit[0] / (2 * np.pi) * 1e9:.1f} ns (turns per GHz)")
b.set_xlabel("frequency f (MHz)")
b.set_ylabel("phase (turns)")
b.set_title("Each tone comes back turned by −fτ turns: the slope is the delay")
b.legend(loc="lower left", fontsize=8.5)
save(fig, os.path.join(IMG, "tt_measure.png"))
print("tau = %.3f ns, slope fit %.3f ns" % (tau * 1e9, -fit[0] / (2 * np.pi) * 1e9))
