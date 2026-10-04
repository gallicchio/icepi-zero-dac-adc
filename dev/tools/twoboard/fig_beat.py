"""Figure: two crystals beating (data/tb_beat_1M_60s.npz, lockin_log.py on both boards)."""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, ".."))
from plotstyle import plt, save, dots, C1, C2, C3


def pts(ax, x, y, color, label=None, size=2.5):
    """Dense samples: small solid dots."""
    return ax.plot(x, y, ".", color=color, markersize=size, label=label)
T = os.path.join(HERE, "..", "..")
z = np.load(os.path.join(T, "data", "tb_beat_1M_60s.npz")); Ts = 2**20 / 25e6
fig, ax = plt.subplots(2, 1, figsize=(7.5, 6.2))
for n, c, lab in (("board0", C1, "board A sees B"), ("board1", C2, "board B sees A")):
    d = z[n]; zz = d[:, 1] + 1j * d[:, 2]; t = np.arange(len(zz)) * Ts
    ph = np.unwrap(np.angle(zz)) / (2 * np.pi)
    p = np.polyfit(t, ph, 1)
    pts(ax[0], t, ph - ph[0], c, "%s: %+.4f Hz" % (lab, p[0]), size=3)
    r = (ph - np.polyval(np.polyfit(t, ph, 2), t)) * 360
    pts(ax[1], t, r, c, lab, size=3)
ax[0].set_ylabel("phase of the other board's 1 MHz (turns)"); ax[0].set_xlabel("time (s)")
ax[0].set_title("Two 50 MHz crystals, compared at 1 MHz: a 0.76 Hz beat (0.76 ppm)")
ax[0].legend()
ax[1].set_ylabel("phase − quadratic fit (deg)"); ax[1].set_xlabel("time (s)")
ax[1].set_title("What is left: slow wander (1° at 1 MHz = 2.8 ns)")
ax[1].legend()
save(fig, os.path.join(T, "..", "tutorial", "img", "tb_beat.png"))
