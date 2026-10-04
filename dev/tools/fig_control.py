"""4.08: step responses of the proportional loop around an RC plant, computed, not measured.

    python3 fig_control.py          # writes ../../tutorial/img/control_steps.png

The model is the loop 4.08 describes, with 1.07's timing.  The controller runs once per ADC
sample (T = 40 ns): u[k] = G * (setpoint - y[k]), with G = Kp * 0.776 the loop gain in ADC
codes per ADC code (1.07: ADC = 0.776 * DAC + 27.5).  The DAC holds u[k] for one sample.
From 1.07's table of where the 240 ns go: the new code reaches the RC about 55 ns after the
FPGA's register changes (20 ns register, 10 ns DAC latch, the DAC's output stage), the ADC
samples the capacitor 20 ns after that, in the middle of the hold, and the FPGA reads that
sample 240 ns = 6 samples after the register changed.  The RC (time constant tau) follows
its input exactly between those instants.  Nothing saturates and nothing is quantized:
10-code steps keep the DAC far from its rails.

With e1 = exp(-40 ns / tau) and e2 = exp(-20 ns / tau), the capacitor at the ADC's sampling
instants obeys v[k] = e1 v[k-1] + (1 - e2) e2 u[k-1] + (1 - e2) u[k], and y[k] = v[k-6].
The closed loop's poles are the roots of z^7 - e1 z^6 + G (1 - e2) z + G (1 - e2) e2.  The
gain where a root reaches the unit circle is the oscillation threshold; the script prints it
and the frequency.
"""
import os

import numpy as np
from plotstyle import plt, C1, C2, C3, INK, INK2, MUTED

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, "..", "..", "tutorial", "img")
TS = 40e-9                     # one ADC sample
T_STEP = 20e-9                 # the capacitor charges this long before the ADC samples it
DELAY = 6                      # samples from the FPGA's new DAC code to its reading of the result (1.07)


def step(G, tau, n, r=10.0):
    """ADC reading y[k] after a setpoint step to r at k = 0, for loop gain G."""
    e1, e2 = np.exp(-TS / tau), np.exp(-T_STEP / tau)
    v = np.zeros(n)            # the capacitor, in ADC codes, at the ADC's sampling instants
    u = np.zeros(n)            # the DAC, in ADC codes, held from one register change to the next
    y = np.zeros(n)
    for k in range(n):
        y[k] = v[k - DELAY] if k >= DELAY else 0.0
        u[k] = G * (r - y[k])
        v[k] = (e1 * v[k - 1] + (1 - e2) * e2 * u[k - 1] if k else 0.0) + (1 - e2) * u[k]
    return y


def threshold(tau):
    """The loop gain where the closed loop starts to oscillate, and the frequency it does it at."""
    e1, e2 = np.exp(-TS / tau), np.exp(-T_STEP / tau)
    poly = lambda G: [1, -e1, 0, 0, 0, 0, G * (1 - e2), G * (1 - e2) * e2]
    lo, hi = 1.0, 1e5
    for _ in range(60):
        G = np.sqrt(lo * hi)
        lo, hi = (lo, G) if np.max(np.abs(np.roots(poly(G)))) > 1 else (G, hi)
    roots = np.roots(poly(hi))
    w = roots[np.argmax(np.abs(roots))]
    return hi, abs(np.angle(w)) / (2 * np.pi * TS)


G_osc, f_osc = threshold(1e-6)
G_ms, f_ms = threshold(1e-3)
print("tau = 1 us: oscillates from G = %.2f (Kp = %.1f) at %.2f MHz" % (G_osc, G_osc / 0.776, f_osc / 1e6))
print("tau = 1 ms: oscillates from G = %.0f (Kp = %.0f) at %.2f MHz" % (G_ms, G_ms / 0.776, f_ms / 1e6))

fig, ax = plt.subplots(1, 3, figsize=(10.5, 3.9), gridspec_kw=dict(width_ratios=[1.25, 0.9, 1.1]))
gains = [(1, C1), (3, C3), (6, C2)]
for G, c in gains:
    n = 160
    y = step(G, 1e-6, n)
    t = np.arange(n) * TS * 1e6
    ax[0].plot(t, y, color=c, lw=1.4, label="G = %g" % G)
ax[0].axhline(10, color=MUTED, lw=0.8, ls="--")
ax[0].text(6.25, 10.2, "setpoint", ha="right", va="bottom", size=8, color=INK2)
ax[0].set_xlim(0, 6.3)
ax[0].set_ylim(-1, 18)
ax[0].set_xlabel("time after the setpoint step (µs)")
ax[0].set_ylabel("what the ADC reads (codes)")
ax[0].set_title("τ = 1 µs: 240 ns of latency shows")
ax[0].legend(loc="upper right", fontsize=8.5)
ax[0].text(6.2, 0.3, "each settles at G/(1+G) of the setpoint: a\nproportional loop leaves an offset,\n"
           "which is what the integrator is for", ha="right", va="bottom", size=8, color=INK2)

G_last = round(G_osc + 0.05, 1)
n = 220
y = step(G_last, 1e-6, n)
t = np.arange(n) * TS * 1e6
ax[1].plot(t, y, color=INK2, lw=1.0)
ax[1].axhline(10, color=MUTED, lw=0.8, ls="--")
ax[1].set_xlim(0, 8.8)
ax[1].set_ylim(-5, 25)
ax[1].set_xlabel("time after the setpoint step (µs)")
ax[1].set_title("G = %g: oscillates at %.2f MHz" % (G_last, f_osc / 1e6))

for G, c in gains:
    n = 20000
    y = step(G, 1e-3, n)
    t = np.arange(n) * TS * 1e3
    ax[2].plot(t, y, color=c, lw=1.4, label="G = %g" % G)
ax[2].axhline(10, color=MUTED, lw=0.8, ls="--")
ax[2].set_xlim(0, 0.8)
ax[2].set_ylim(-3, 18)
ax[2].set_xlabel("time after the setpoint step (ms)")
ax[2].set_title("τ = 1 ms: the same gains")
ax[2].legend(loc="lower right", fontsize=8.5)
ax[2].text(0.015, 17.3, "no ringing: each settles in τ/(1+G).\nThe latency would first matter\nnear G = %s"
           % format(int(round(G_ms, -2)), ","), ha="left", va="top", size=8, color=INK2)
fig.text(0.995, 0.005, "computed, not measured", ha="right", va="bottom", size=8, color=MUTED)
fig.tight_layout(rect=(0, 0.02, 1, 1))
fig.savefig(os.path.join(IMG, "control_steps.png"), dpi=130)
plt.close(fig)
print("wrote control_steps.png")
