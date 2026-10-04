"""Figure: OFDM bit error rate against SNR, with the textbook QAM curves."""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..")); sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "src", "twoboard"))
from plotstyle import plt, save, dots, C1, C2, C3
from ber_curve import ber_theory
T = os.path.join(HERE, "..", "..")
r = np.load(os.path.join(T, "data", "tb_ber_loop.npz"))["rows"]
fig, ax = plt.subplots(figsize=(7, 4.6))
s = np.linspace(0, 32, 300)
for M, c in ((4, C1), (16, C2), (64, C3)):
    sel = (r[:, 0] == M) & (r[:, 3] > 0)
    ax.semilogy(s, ber_theory(M, 10**(s / 10)), color=c, lw=1.2)
    dots(ax, 10 * np.log10(r[sel, 2]), r[sel, 3] / r[sel, 4], c, "QAM-%d" % M, size=6)
    z = (r[:, 0] == M) & (r[:, 3] == 0)
    ax.plot(10 * np.log10(r[z, 2]), 0.5 / r[z, 4], "v", color=c, markersize=5, alpha=0.6)
ax.set_ylim(1e-6, 0.5); ax.set_xlim(0, 32)
ax.set_xlabel("measured SNR per symbol (dB)"); ax.set_ylabel("bit error rate")
ax.set_title("OFDM through the cable: errors against noise (lines: theory)")
ax.text(31.5, 1.2e-6, "▼ no errors: below this", ha="right", fontsize=8, color="0.35")
ax.legend(loc="upper right")
save(fig, os.path.join(T, "..", "tutorial", "img", "tb_ber.png"))
