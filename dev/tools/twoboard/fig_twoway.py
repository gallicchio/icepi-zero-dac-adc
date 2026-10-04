"""Figure: two-way time transfer between two boards (data/tb_twoway_120s.npz)."""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, ".."))
from plotstyle import plt, save, dots, C1, C2, C3


def pts(ax, x, y, color, label=None, size=2.5):
    """Dense samples: small solid dots."""
    return ax.plot(x, y, ".", color=color, markersize=size, label=label)
T = os.path.join(HERE, "..", "..")
z = np.load(os.path.join(T, "data", "tb_twoway_120s.npz")); r = z["rows"]; P = 16384 / 50e6
t, ta, tb = r[:, 0], r[:, 1], r[:, 2]
u = lambda x: np.unwrap(x * 2 * np.pi / P) * P / (2 * np.pi)
ta_u, tb_u = u(ta), u(tb)
s = (ta_u + tb_u); s = s - np.round(s.mean() / P) * P
d = (ta_u - tb_u) / 2
fig, ax = plt.subplots(3, 1, figsize=(7.5, 7.8))
pts(ax[0], t, ta * 1e6, C1, "τ_A: B's signal at A, after A's loop start", size=3)
pts(ax[0], t, tb * 1e6, C2, "τ_B: A's signal at B, after B's loop start", size=3)
ax[0].set_ylabel("delay (µs, mod 327.68 µs)"); ax[0].set_title("What each board sees, by its own clock")
ax[0].legend(loc="center right")
pts(ax[1], t, s * 1e9, C3, size=3)
ax[1].axhline(2 * 212.915, color="0.4", lw=0.8, ls="--")
ax[1].set_ylim(424.6, 426.4)                       # room above the points for the label
ax[1].text(t[-1], 426.3, "dashed: 2 × the loopback delay of one module, 425.83 ns", ha="right", va="top",
           fontsize=8, color="0.3")
ax[1].set_ylabel("τ_A + τ_B (ns)"); ax[1].set_title("Their sum: the round trip, %.2f ns ± %.2f ns rms" % (s.mean() * 1e9, s.std() * 1e9))
p = np.polyfit(t, d, 1)
pts(ax[2], t, (d - d[0]) * 1e6, C1, size=3)
ax[2].set_ylabel("(τ_A − τ_B)/2 − start (µs)"); ax[2].set_xlabel("time (s)")
ax[2].set_title("Half their difference: clock offset, drifting %.1f ns/s = %.3f ppm" % (p[0] * 1e9, p[0] * 1e6))
save(fig, os.path.join(T, "..", "tutorial", "img", "tb_twoway.png"))
print("round trip %.3f ns, scatter %.3f ns; offset slope %.4f ppm" % (s.mean() * 1e9, s.std() * 1e9, p[0] * 1e6))
