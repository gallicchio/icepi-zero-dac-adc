"""Figure: one board's oscillator disciplined to another's by pll.sv (data/tb_pll_pair.npz)."""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, ".."))
from plotstyle import plt, save, C1, C2, C3
T = os.path.join(HERE, "..", "..")
z = np.load(os.path.join(T, "data", "tb_pll_pair.npz")); A, B, tc = z["A"], z["B"], float(z["t_close"])
ph = np.unwrap(np.angle(A[:, 1] + 1j * A[:, 2])) / (2 * np.pi)
fig, ax = plt.subplots(3, 1, figsize=(7.5, 8), sharex=True)
for a in ax: a.axvline(tc, color="0.5", lw=0.8, ls="--")
ax[0].plot(A[:, 0], ph - ph[0], ".", color=C1, markersize=2.5)
ax[0].set_ylabel("B's sine at A (turns)"); ax[0].set_title("Loop open: B's own crystal beats against A's.  Closed: no beat")
cl = A[:, 0] > tc + 2
r = (ph[cl] - ph[cl].mean()) * 360
ax[1].plot(A[cl, 0], r, ".", color=C1, markersize=2.5)
ax[1].set_ylabel("phase, locked (deg)"); ax[1].set_title("Locked: B's copy of A's clock, seen at A: %.3f° rms = %.2f ns at 1 MHz" % (r.std(), r.std() / 360 * 1e3))
ax[2].plot(B[:, 0], B[:, 1], ".", color=C2, markersize=3)
ax[2].set_ylabel("B's correction (Hz)"); ax[2].set_xlabel("time (s)")
ax[2].set_title("What B had to change: its crystal against A's, at 1 MHz")
save(fig, os.path.join(T, "..", "tutorial", "img", "tb_pllpair.png"))
