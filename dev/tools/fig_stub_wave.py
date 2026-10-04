"""4.05: the standing wave along the open quarter-wave stub at its notch, computed, not measured.

    python3 fig_stub_wave.py        # writes ../../tutorial/img/stub_wave.png

A lossless 5.0 m line (velocity factor 0.66, as 4.05) with its far end open.  At the notch,
f = 0.66 c / (4 l) = 9.89 MHz, the stub is a quarter wavelength: the open end forces a current
node and a voltage antinode there, and a quarter wave back, at the T, the voltage is zero and
the current is largest.  To the DAC the T looks like a short circuit.  Snapshots of the voltage
at several instants, and the envelopes of voltage and current.
"""
import os

import numpy as np
from plotstyle import plt, C1, C2, INK, INK2, MUTED

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, "..", "..", "tutorial", "img")
L, VF = 5.0, 0.66
f = VF * 3e8 / (4 * L)
lam = VF * 3e8 / f                       # 20 m: the stub is lam / 4
x = np.linspace(0, L, 400)
beta = 2 * np.pi / lam
V = np.cos(beta * (L - x))               # voltage envelope: 0 at the T, 1 at the open end
I = np.sin(beta * (L - x))               # current envelope: 1 at the T, 0 at the open end

fig, ax = plt.subplots(figsize=(5.6, 3.6))
for k, wt in enumerate(np.linspace(0, np.pi, 9)[:-1]):
    ax.plot(x, V * np.cos(wt), color=C1, lw=0.9, alpha=0.18 + 0.6 * abs(np.cos(wt)))
ax.plot(x, V, color=C1, lw=1.8, label="voltage: its envelope, and snapshots")
ax.plot(x, -V, color=C1, lw=1.8)
ax.plot(x, I, color=C2, lw=1.4, ls="--", label="current: its envelope")
ax.plot(x, -I, color=C2, lw=1.4, ls="--")
ax.axhline(0, color=MUTED, lw=0.8)
ax.set_xlim(-0.15, L + 0.15)
ax.set_ylim(-1.3, 1.8)
ax.set_yticks([-1, 0, 1])
ax.set_xlabel("distance along the stub from the T (m)")
ax.set_ylabel("relative to the open end")
ax.set_title("Along the stub at the notch, %.2f MHz: a quarter wave" % (f / 1e6))
ax.text(0.05, 1.72, "the T: V = 0,\na short circuit\nto the DAC", ha="left", va="top", size=8, color=INK)
ax.text(L - 0.05, 1.72, "open end: I = 0,\nV largest", ha="right", va="top", size=8, color=INK)
ax.legend(loc="upper center", bbox_to_anchor=(0.52, 1.0), fontsize=8)
fig.text(0.995, 0.005, "computed, not measured", ha="right", va="bottom", size=8, color=MUTED)
fig.tight_layout(rect=(0, 0.02, 1, 1))
fig.savefig(os.path.join(IMG, "stub_wave.png"), dpi=130)
plt.close(fig)
print("wrote stub_wave.png  (f = %.3f MHz, lambda = %.1f m)" % (f / 1e6, lam))
