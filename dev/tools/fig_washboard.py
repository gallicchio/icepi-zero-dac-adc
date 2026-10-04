"""5.04: Adler's equation as a particle on a tilted washboard, computed, not measured.

    python3 fig_washboard.py        # writes ../../tutorial/img/washboard.png

dpsi/dt = 2 pi (Delta - K sin psi) is an overdamped particle sliding down the potential
U(psi) = -2 pi (Delta psi + K cos psi): a washboard tilted by the detuning Delta, with
ripples of depth set by the coupling K.  |Delta| < K: the tilt is gentle enough that every
ripple still has a dip, and the particle stops in one (locked, at sin psi = Delta / K).
|Delta| > K: no dips are left; it slides, slowly over the near-flat points and quickly down
the steep parts, and psi grows by a turn at a time.  K = 0.5 Hz as 5.04's mutual run; the
detunings, 0.3 Hz and 0.7 Hz, are 5.04's tuned and natural ones.  Dots along each potential
are the particle's positions at equal time steps, from integrating the equation.
"""
import os

import numpy as np
from plotstyle import plt, C1, C2, C3, INK, INK2, MUTED

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, "..", "..", "tutorial", "img")
K = 0.5                                                   # Hz
cases = [(0.3, "locked: |Δ| < K", C1), (0.7, "slipping: |Δ| > K", C2)]


def U(psi, D):
    return -2 * np.pi * (D * psi + K * np.cos(psi))


def run(D, T=12.0, dt=1e-3, psi0=-0.6):
    """Integrate Adler's equation from psi0 for T seconds."""
    n = int(T / dt)
    psi = np.empty(n + 1)
    psi[0] = psi0
    for k in range(n):
        psi[k + 1] = psi[k] + dt * 2 * np.pi * (D - K * np.sin(psi[k]))
    return np.arange(n + 1) * dt, psi


fig, ax = plt.subplots(2, 2, figsize=(9.0, 5.6), gridspec_kw=dict(height_ratios=[1.25, 1]))
grid = np.linspace(-1.5 * np.pi, 5.5 * np.pi, 800)
for j, (D, name, c) in enumerate(cases):
    t, psi = run(D)
    a = ax[0, j]
    a.plot(grid, U(grid, D), color=INK2, lw=1.6)
    every = int(0.25 / (t[1] - t[0]))                    # a dot every quarter second
    a.plot(psi[::every], U(psi[::every], D), "o", color=c, markersize=4.2, alpha=0.75,
           markeredgecolor="none", label="where it is, every 0.25 s")
    a.set_xlim(grid[0], grid[-1])
    a.set_xticks(np.arange(-1, 6) * np.pi)
    a.set_xticklabels(["−π", "0", "π", "2π", "3π", "4π", "5π"])
    a.set_xlabel("phase difference ψ")
    a.set_ylabel("U(ψ) = −2π(Δψ + K cos ψ)" if j == 0 else "")
    a.set_title("%s   (K = %.1f Hz, Δ = %.1f Hz)" % (name, K, D))
    a.legend(loc="lower left", fontsize=8)
    if j == 0:
        p = np.arcsin(D / K)
        a.annotate("trapped in a dip:\nsin ψ = Δ/K", (p, U(p, D)), (p + 4.6, U(p, D) + 7.0),
                   ha="center", va="bottom", size=8.5, color=INK,
                   arrowprops=dict(arrowstyle="-|>", color=INK2, lw=0.9))
    else:
        p = np.pi / 2 + 2 * np.pi
        a.annotate("lingers where the\nslope is gentlest", (p, U(p, D) + 1.5), (p, U(p, D) + 24),
                   ha="center", va="bottom", size=8.5, color=INK,
                   arrowprops=dict(arrowstyle="-|>", color=INK2, lw=0.9))
        p = np.pi / 2 + 3 * np.pi
        a.annotate("then slips a\nwhole turn", (p, U(p, D) + 1.5), (p + 4.0, U(p, D) + 16),
                   ha="center", va="bottom", size=8.5, color=INK,
                   arrowprops=dict(arrowstyle="-|>", color=INK2, lw=0.9))
    b = ax[1, j]
    b.plot(t, psi / (2 * np.pi), color=c, lw=1.6)
    if j == 1:
        slip = np.sqrt(D**2 - K**2)
        b.plot(t, psi[0] / (2 * np.pi) + D * t, color=MUTED, lw=1.0, ls=":", label="uncoupled: Δ = %.1f Hz" % D)
        b.plot(t, psi[0] / (2 * np.pi) + slip * t, color=C3, lw=1.0, ls="--",
               label="average: √(Δ² − K²) = %.2f Hz" % slip)
        b.legend(loc="upper left", fontsize=8)
    else:
        b.text(6, 0.08 + np.arcsin(D / K) / (2 * np.pi), "settles at ψ = arcsin(Δ/K) = %.0f°"
               % np.degrees(np.arcsin(D / K)), ha="center", va="bottom", size=8.5, color=INK2)
        b.set_ylim(-0.25, 0.75)
    b.set_xlim(0, t[-1])
    b.set_xlabel("time (s)")
    b.set_ylabel("ψ (turns)" if j == 0 else "")
    b.set_title("the same, against time")
fig.text(0.995, 0.005, "computed, not measured", ha="right", va="bottom", size=8, color=MUTED)
fig.tight_layout(rect=(0, 0.02, 1, 1))
fig.savefig(os.path.join(IMG, "washboard.png"), dpi=130)
plt.close(fig)
print("wrote washboard.png")
