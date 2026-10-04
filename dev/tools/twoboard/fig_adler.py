"""Figure: two coupled oscillators, slip rate against detuning (Adler's equation).

Data: data/tb_adler.npz, made by collecting coupled.py runs (see Response 8)."""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, ".."))
from plotstyle import plt, save, dots, C1, C2, C3


def pts(ax, x, y, color, label=None, size=2.5):
    """Dense samples: small solid dots."""
    return ax.plot(x, y, ".", color=color, markersize=size, label=label)
T = os.path.join(HERE, "..", "..")
z = np.load(os.path.join(T, "data", "tb_adler.npz"))
K = float(z["K"])
slip = z["slip"]
D = z["total"]               # detuning f_B - f_A without coupling, Hz (natural part interpolated in time)
x = np.linspace(D.min() - 0.1, D.max() + 0.1, 400)
th = np.sign(x) * np.sqrt(np.clip(x**2 - K**2, 0, None))
fig, ax = plt.subplots(3, 1, figsize=(7.5, 9.6))
ax[0].plot(x, x, color="0.7", lw=0.8, ls="--", label="no coupling: slip = detuning")
ax[0].plot(x, th, color=C2, label="Adler: slip = √(Δ² − K²),  K = %.2f Hz" % K)
dots(ax[0], D, slip, C1, "measured")
ax[0].axvspan(-K, K, color=C3, alpha=0.12, lw=0)
ax[0].set_xlabel("detuning Δ = f_B − f_A without coupling (Hz)"); ax[0].set_ylabel("phase slip rate (Hz)")
ax[0].set_title("Two coupled oscillators lock when |Δ| < K_A + K_B"); ax[0].legend(loc="upper left")
for name, col, lab in (("ex_locked", C3, "locked"), ("ex_slip", C2, "just outside: slow slips")):
    r = z[name]; t = r[:, 0]
    pts(ax[1], t, np.degrees(np.unwrap(r[:, 1])) / 360, col, lab, size=3)
ax[1].set_xlabel("time (s)"); ax[1].set_ylabel("phase of B at A (turns)")
ax[1].set_title("Phase slips: a turn at a time"); ax[1].legend(loc="lower left")
locked = abs(slip) < 0.01
chi = np.degrees(z["chi"])
pts(ax[2], D[locked], chi[locked], C1, "measured: χ = (φ_A − φ_B)/2", size=7)
xx = np.linspace(-K, K, 200)
ax[2].plot(xx, np.degrees(np.arcsin(xx / K)), color=C2, label="Adler: sin χ = Δ / K")
ax[2].set_xlabel("detuning Δ (Hz)"); ax[2].set_ylabel("locked phase χ (deg)")
ax[2].set_title("Inside the range, the lag that makes up the difference"); ax[2].legend(loc="upper left")
save(fig, os.path.join(T, "..", "tutorial", "img", "tb_adler.png"))
