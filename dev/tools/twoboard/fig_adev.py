"""Figure: Allan deviation of two free-running crystals against each other (lockin_log.py data).

    python3 fig_adev.py data/tb_beat_1M_900s.npz [more.npz ...]
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, ".."))
from plotstyle import plt, save, dots, C1, C2, C3
T = os.path.join(HERE, "..", "..")
tau0 = 2**20 / 25e6


def oadev(x, tau0, m):
    """Overlapping Allan deviation from time-error samples x (s) at spacing tau0, for averaging factor m."""
    d = x[2 * m:] - 2 * x[m:-m] + x[:-2 * m]
    return np.sqrt(np.mean(d**2) / (2 * (m * tau0)**2))


if not sys.argv[1:]:
    sys.exit("usage: python3 fig_adev.py RECORD.npz [more.npz ...]   (lockin_log.py files; "
             "the tutorial's figure: data/tb_beat_1M_60s.npz data/tb_beat_1M_900s.npz data/tb_beat_1M_overnight.npz)")
fig, ax = plt.subplots(figsize=(7, 4.6))
for path, c in zip(sys.argv[1:], (C1, C2, C3)):
    z = np.load(path); f0 = float(z["f"])
    tau0 = 2**20 / 25e6 * (int(z["every"]) if "every" in z.files else 1)
    key = [k for k in z.files if k.startswith("board") or k.startswith("JLC")][0]
    d = z[key]; x = np.unwrap(np.angle(d[:, 1] + 1j * d[:, 2])) / (2 * np.pi * f0)     # time error, s
    ms = np.unique(np.round(np.logspace(0, np.log10(len(x) / 3), 30)).astype(int))
    taus = ms * tau0; ad = np.array([oadev(x, tau0, m) for m in ms])
    rec = len(x) * tau0
    dots(ax, taus, ad, c, "a %s record" % ("%.0f s" % rec if rec < 3600 else "%.0f h" % (rec / 3600)), size=5)
    for tt in (0.1, 1, 10, 100, 1000, 5000):
        i = np.argmin(abs(taus - tt)); print("%s: sigma_y(%.3g s) = %.2e" % (os.path.basename(path), taus[i], ad[i]))
ax.set_xscale("log"); ax.set_yscale("log")
ax.set_xlabel("averaging time τ (s)"); ax.set_ylabel("Allan deviation σ_y(τ)")
ax.set_title("Two Icepi Zero crystals, compared at 1 MHz")
ax.legend()
save(fig, os.path.join(T, "..", "tutorial", "img", "tb_adev.png"))
