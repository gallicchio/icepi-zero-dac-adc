"""1.07's LFSR figures: loopback.sv's 10-bit register as a diagram, and one whole cycle of
what it plays.  No hardware: the sequence is computed with loopback.sv's own arithmetic,

    lfsr <= {lfsr[8:0], lfsr[9] ^ lfsr[2]};      // from SEED = all ones; plays lfsr[9]

and checked against loopback.py's copy of it.

    python3 fig_lfsr.py        # writes tutorial/img/lfsr_diagram.png and lfsr_cycle.png
"""
import os

import numpy as np
from matplotlib.patches import Circle, FancyBboxPatch
from plotstyle import plt, save, C1, C2, C3, INK, INK2, MUTED

IMG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tutorial", "img")
MONO = "DejaVu Sans Mono"
M = 1023


def g1(n=M):
    """loopback.sv's register, one 40 ns step at a time: the bit it plays, and its state."""
    lfsr, out, states = 0x3FF, [], []
    for _ in range(n):
        states.append(lfsr)
        out.append((lfsr >> 9) & 1)                                 # lfsr[9]
        fb = ((lfsr >> 9) ^ (lfsr >> 2)) & 1                        # lfsr[9] ^ lfsr[2]
        lfsr = ((lfsr << 1) & 0x3FF) | fb                           # {lfsr[8:0], fb}
    return np.array(out), states


bits, states = g1()
# loopback.py's version (+-1 instead of 1/0) must agree
state, ref = 0x3FF, []
for _ in range(M):
    ref.append(1 if state & 0x200 else 0)
    state = ((state << 1) | (((state >> 9) ^ (state >> 2)) & 1)) & 0x3FF
assert (bits == np.array(ref)).all()
assert len(set(states)) == M and 0 not in states        # every non-zero state, once: an m-sequence
assert g1(M + 1)[1][M] == 0x3FF                         # and back to the start after 1023 steps

# ---- the diagram -------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(9.6, 3.3))
ax.set_xlim(-8.6, 23.4)
ax.set_ylim(-4.3, 3.6)
ax.set_aspect("equal")
ax.axis("off")
W, H, P = 1.7, 1.25, 2.2                  # box width and height, pitch
xs = {k: (9 - k) * P for k in range(10)}  # lfsr[9] on the left, lfsr[0] on the right, as in {lfsr[8:0], ...}
for k in range(10):
    x = xs[k]
    tap = k in (9, 2)
    ax.add_patch(FancyBboxPatch((x - W / 2, -H / 2), W, H, boxstyle="round,pad=0,rounding_size=0.12",
                                fc="#fdf1dc" if tap else "#f3f1ea", ec=C2 if tap else INK2, lw=1.4))
    ax.text(x, 0, "1", ha="center", va="center", fontsize=14, family=MONO, color=INK)
    ax.text(x, H / 2 + 0.3, f"lfsr[{k}]", ha="center", va="bottom", fontsize=9.5, family=MONO,
            color=C2 if tap else INK)
    ax.text(x, -H / 2 - 0.28, f"stage {k + 1}", ha="center", va="top", fontsize=8.5, color=MUTED)
    if k < 9:                              # each clock, every bit moves one place to the left
        ax.annotate("", (x - P + W / 2, 0), (x - W / 2, 0),
                    arrowprops=dict(arrowstyle="-|>", color=INK2, lw=1.1, shrinkA=0, shrinkB=0))
# the feedback: lfsr[9] XOR lfsr[2], into lfsr[0]
xo = (xs[0] + W / 2 + 1.1, -2.9)
ax.add_patch(Circle(xo, 0.42, fc="white", ec=C2, lw=1.6, zorder=3))
ax.text(*xo, "+", ha="center", va="center", fontsize=17, color=C2, zorder=4)
ax.text(xo[0] + 0.6, xo[1] - 0.15, "XOR", ha="left", va="top", fontsize=8.5, color=C2)
ax.plot([xs[9], xs[9], xo[0]], [-H / 2 - 0.85, -3.75, -3.75], color=C2, lw=1.4)   # from lfsr[9]
ax.annotate("", (xo[0], xo[1] - 0.42), (xo[0], -3.75),
            arrowprops=dict(arrowstyle="-|>", color=C2, lw=1.4, shrinkA=0, shrinkB=0))
ax.plot([xs[2], xs[2], xo[0] - 0.42], [-H / 2 - 0.85, xo[1], xo[1]], color=C2, lw=1.4)  # from lfsr[2]
ax.plot([xo[0], xo[0]], [xo[1] + 0.42, 0], color=C2, lw=1.4)                 # up, then into lfsr[0]
ax.annotate("", (xs[0] + W / 2, 0), (xo[0], 0),
            arrowprops=dict(arrowstyle="-|>", color=C2, lw=1.4, shrinkA=0, shrinkB=0))
for k in (9, 2):                           # the taps leave from under their boxes
    ax.plot([xs[k], xs[k]], [-H / 2, -H / 2 - 0.85], color=C2, lw=1.4)
    ax.plot(xs[k], -H / 2 - 0.85, "o", color=C2, markersize=4)
ax.text(xs[5] + 0.3, -3.75 + 0.18, "lfsr[9] ^ lfsr[2]: the new lfsr[0]", ha="center", va="bottom",
        fontsize=9, color=C2)
# the output
ax.annotate("", (xs[9] - W / 2 - 2.6, 0), (xs[9] - W / 2, 0),
            arrowprops=dict(arrowstyle="-|>", color=C1, lw=1.6, shrinkA=0, shrinkB=0))
ax.text(xs[9] - W / 2 - 2.75, 0, "to the DAC:\nHI if 1,\nLO if 0", ha="right", va="center",
        fontsize=9.5, color=C1)
ax.text(-8.4, 3.5, "loopback.sv:   lfsr <= {lfsr[8:0], lfsr[9] ^ lfsr[2]};   every 40 ns",
        ha="left", va="top", fontsize=10, family=MONO, color=INK)
ax.text(-8.4, 2.75, "GPS's G1: x$^{10}$ + x$^3$ + 1, starting from all ones (SEED); "
        "the stage numbers are GPS's", ha="left", va="top", fontsize=9, color=INK2)
save(fig, os.path.join(IMG, "lfsr_diagram.png"))

# ---- one whole cycle ---------------------------------------------------------------------
ROW = 256
runs = np.flatnonzero(np.diff(np.concatenate([[1], bits, [1]])))
z = max(((runs[i + 1] - runs[i], runs[i]) for i in range(0, len(runs) - 1, 2)))    # longest run of 0s
fig = plt.figure(figsize=(10, 6.8))
gs = fig.add_gridspec(6, 1, height_ratios=[1, 1, 1, 1, 0.25, 2.4], hspace=0.55)
for r in range(4):
    a = fig.add_subplot(gs[r])
    seg = bits[r * ROW:(r + 1) * ROW]
    n = np.arange(r * ROW, r * ROW + len(seg) + 1)
    a.fill_between(n, np.append(seg, seg[-1]), step="post", color=C1, alpha=0.25, lw=0)
    a.step(n, np.append(seg, seg[-1]), where="post", color=C1, lw=0.8)
    a.set_xlim(r * ROW, (r + 1) * ROW)
    a.set_ylim(-0.15, 1.5)
    a.set_yticks([0, 1])
    a.tick_params(axis="x", labelsize=8)
    a.grid(False)
    if r == 0:
        a.axvspan(0, 10, color=C3, alpha=0.3, lw=0)
        a.set_title(f"One whole cycle of lfsr[9]: {M} steps (40.92 µs), then it repeats exactly.\n"
                    f"{bits.sum()} ones and {M - bits.sum()} zeros; shaded: the seed's ten 1s, and the "
                    f"longest run of 0s (nine, at n = {z[1]})", fontsize=10.5)
    if r == z[1] // ROW:
        a.axvspan(z[1], z[1] + z[0], color=C2, alpha=0.3, lw=0)
    if r == 3:
        a.set_xlabel("step n (one per 40 ns sample)", fontsize=9)
# its autocorrelation, as +-1, around the cycle
b = fig.add_subplot(gs[5])
s = 2.0 * bits - 1
lags = np.arange(-60, 61)
ac = np.array([np.dot(s, np.roll(s, k)) for k in lags])
b.vlines(lags, 0, ac, color=C3, lw=1.2)
b.plot(lags, ac, "o", color=C3, markersize=3)
b.set_yscale("symlog", linthresh=2)
b.set_yticks([-1, 0, 1, 10, 100, 1023], ["−1", "0", "1", "10", "100", "1023"])
b.set_xlim(-60.5, 60.5)
b.set_xlabel("shift k (samples)", fontsize=9)
b.set_ylabel("Σ s[n] s[n+k]", fontsize=9)
b.set_title("Its autocorrelation (as ±1, around the cycle): 1023 at k = 0, and −1 at every other shift",
            fontsize=10)
save(fig, os.path.join(IMG, "lfsr_cycle.png"))
print("wrote lfsr_diagram.png, lfsr_cycle.png;", bits.sum(), "ones; longest 0-run", z[0], "at", z[1],
      "; first 20:", "".join(map(str, bits[:20])))
