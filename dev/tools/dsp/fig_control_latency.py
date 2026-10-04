"""7.06, computed, not measured: what latency does to a loop, from control_model.py.

    python3 fig_control_latency.py        # writes ../../../tutorial/img/dsp_control_latency.png

The loop is control.sv's, run bit for bit by control.Sim through the model of 1.07's cable
(gain 0.776, 7 samples = 280 ns around the loop, no noise here), stepped by 20 ADC codes:

  (a) a proportional loop at several Kp: each settles at Kp G / (1 + Kp G) of the step, and
      from about Kp G = 0.5 it rings at 1 / (2 tau), where the delay alone is 180 degrees;
  (b) just above the critical gain Kp = 1 / G: the ringing grows until the DAC's rails stop
      it.  Its period is twice the loop delay: 14 samples, 560 ns.  That is the measurement
      the page is built around;
  (c) a PI loop: the integrator removes the offset; too much of it rings;
  (d) the bandwidth a loop can have against its round-trip delay: 1 / (2 tau) is where a
      proportional loop on a pure delay oscillates, 1 / (4 tau) where the delay alone eats
      the 90 degrees an integrator leaves, 1 / (10 tau) a loop with a comfortable margin.
      The regimes are order-of-magnitude, typical values from the literature (see the
      page), not measurements.
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.join(HERE, "..", "..", "..")
sys.path.insert(0, os.path.join(HERE, ".."))                    # plotstyle
sys.path.insert(0, os.path.join(TOP, "src", "dsp"))             # control, control_model
from plotstyle import plt, C1, C2, C3, INK, INK2, MUTED, GRID   # noqa: E402
import control                                                  # noqa: E402
import control_model as cm                                      # noqa: E402

IMG = os.path.join(TOP, "tutorial", "img")
TS = cm.TS


def run(kp, ki=0.0, kd=0.0, nstep=10):
    dev = control.Sim(cm.Cable(noise=0.0), noise=0.0)
    cfg = control.Config(mode=0, kp=kp, ki=ki, kd=kd, step=20, nstep=nstep)
    r = control.step_response(dev, cfg)
    t = (np.arange(len(r["sp"])) - control.PRE) * TS * 1e6       # us, the step at 0
    return t, r


fig = plt.figure(figsize=(10.5, 7.6))
gs = fig.add_gridspec(2, 3, width_ratios=[1.15, 1.0, 1.0], height_ratios=[1, 1.15])
ax_a = fig.add_subplot(gs[0, 0])
ax_b = fig.add_subplot(gs[0, 1])
ax_c = fig.add_subplot(gs[0, 2])
ax_d = fig.add_subplot(gs[1, :])

# ---- (a) P at several gains --------------------------------------------------------------------
for kp, col in ((0.4, C1), (0.8, C3), (1.1, C2), (1.25, INK2)):
    t, r = run(kp)
    ax_a.plot(t, r["pv"], color=col, lw=1.3, label="Kp = %g (Kp G = %.2f)" % (kp, kp * cm.GAIN))
t, r = run(0.4)
ax_a.step(t, r["sp"], where="post", color=MUTED, lw=0.9, ls="--")
ax_a.text(2.9, 20.4, "setpoint", ha="right", va="bottom", size=8, color=INK2)
ax_a.set_xlim(-0.3, 3.0)
ax_a.set_ylim(-3, 33)
ax_a.set_xlabel("time after the setpoint step (µs)")
ax_a.set_ylabel("what the ADC reads (codes)")
ax_a.set_title("(a) P on the cable: 280 ns around")
ax_a.legend(loc="upper left", fontsize=7.3, ncol=2, columnspacing=0.8)
ax_a.annotate("nothing for 7 samples", xy=(0.28, 0.3), xytext=(1.2, -2.3), size=8, color=INK2,
              arrowprops=dict(arrowstyle="-|>", color=INK2, lw=0.8))

# ---- (b) above the critical gain ----------------------------------------------------------------
t, r = run(1.35, nstep=12)
e = r["e"]
ax_b.plot(t, e, color=C2, lw=1.0)
ax_b.set_xlim(-0.3, 4.2)
ax_b.set_xlabel("time after the setpoint step (µs)")
ax_b.set_ylabel("e (codes)")
f_ring, growth, tail, loud = control.ringing(e, control.Config(mode=0, nstep=12))
ax_b.set_title("(b) Kp = 1.35: it sings at %.2f MHz" % (f_ring / 1e6))
# mark one period on the record, between two late peaks
k = control.PRE + 70
seg = e[k:k + 40]
i0 = k + int(np.argmax(seg))
i1 = i0 + 14
y = e[i0] + 6
ax_b.annotate("", (t[i1], y), (t[i0], y), arrowprops=dict(arrowstyle="<|-|>", color=INK, lw=1.0))
ax_b.text(0.5 * (t[i0] + t[i1]), y + 3, "14 samples = 560 ns\n= twice the loop delay", ha="center", va="bottom", size=8, color=INK)
ax_b.set_ylim(min(e.min(), -140) - 5, max(e.max(), 140) + 35)

# ---- (c) PI -----------------------------------------------------------------------------------------
for kp, ki, col in ((0.6, 0.03, C1), (0.6, 0.12, C2), (0.6, 0.0, MUTED)):
    t, r = run(kp, ki)
    ax_c.plot(t, r["pv"], color=col, lw=1.3, label="Kp = %g, Ki = %g" % (kp, ki) + (" per sample" if ki else ""))
ax_c.step(t, r["sp"], where="post", color=MUTED, lw=0.9, ls="--")
ax_c.set_xlim(-0.3, 6.0)
ax_c.set_ylim(-3, 28)
ax_c.set_xlabel("time after the setpoint step (µs)")
ax_c.set_title("(c) PI finds the setpoint")
ax_c.legend(loc="lower right", fontsize=7.5)
ax_c.text(5.9, 21.3, "setpoint", ha="right", va="bottom", size=8, color=INK2)

# ---- (d) bandwidth against delay ---------------------------------------------------------------------
tau = np.logspace(-8, 1, 200)
ax_d.fill_between(tau, 1 / (10 * tau), 1 / (4 * tau), color=C3, alpha=0.15, lw=0)
ax_d.loglog(tau, 1 / (2 * tau), color=C2, lw=1.2, label="1 / 2τ: a P loop on a pure delay oscillates")
ax_d.loglog(tau, 1 / (4 * tau), color=C3, lw=1.4, label="1 / 4τ: the ceiling once there is an integrator")
ax_d.loglog(tau, 1 / (10 * tau), color=C3, lw=1.0, ls="--", label="1 / 10τ: a comfortable loop")
ax_d.plot([280e-9], [1 / (4 * 280e-9)], "o", color=INK, ms=7, zorder=5)
ax_d.plot([280e-9], [f_ring], "s", color=C2, ms=6, zorder=5)
ax_d.annotate("this board: 280 ns, so\nabout 900 kHz with an integrator,\nand it sings at %.2f MHz in (b)" % (f_ring / 1e6),
              xy=(280e-9, 1 / (4 * 280e-9)), xytext=(1.6e-8, 2.5e1), size=8.5, color=INK, ha="left",
              arrowprops=dict(arrowstyle="-|>", color=INK, lw=0.8))

regimes = [   # (tau low, tau high, label, colour): order of magnitude, typical values
    (1e-7, 1e-6, "PDH laser lock,\ndiode current:\n0.1–1 µs", C1),
    (2e-7, 2e-6, "superconducting-\nqubit feedback:\n0.2–2 µs", C2),
    (1e-5, 1e-4, "a piezo mirror:\n10–100 µs (its\nresonance acts\nas a delay)", C1),
    (5e-4, 5e-3, "a laptop\nover USB:\n0.5–5 ms", INK2),
    (5e-3, 3e-2, "a drone's attitude\nloop (ESC, motor,\nprop): 5–30 ms", C2),
    (1e0, 1e1, "a thermostat,\na TEC:\nseconds", INK2),
]
for k, (lo, hi, text, col) in enumerate(regimes):
    ax_d.axvspan(lo, hi, color=col, alpha=0.09, lw=0)
    y = 2.5e7 if k % 2 == 0 else 2.5e4
    ax_d.text(np.sqrt(lo * hi), y, text, ha="center", va="top", size=7.4, color=col)
ax_d.set_xlim(1e-8, 1e1)
ax_d.set_ylim(1e-3, 1e8)
ax_d.set_xlabel("round-trip delay of the loop, τ (s)")
ax_d.set_ylabel("loop bandwidth (Hz)")
ax_d.set_title("(d) latency sets the speed: nothing else does")
ax_d.legend(loc="lower left", fontsize=8, bbox_to_anchor=(0.0, 0.07))
ax_d.text(1.3e-8, 2e-3, "the regimes are order-of-magnitude, typical published values; the board's point is this page's measurement",
          size=7.5, color=MUTED, ha="left", va="bottom")

fig.text(0.995, 0.005, "computed, not measured (control_model.py)", ha="right", va="bottom", size=8, color=MUTED)
fig.tight_layout(rect=(0, 0.02, 1, 1))
out = os.path.join(IMG, "dsp_control_latency.png")
fig.savefig(out, dpi=130)
plt.close(fig)
kp_c, f_c = cm.critical_gain(cm.Settings(mode=0), cm.Cable())
print("the cable, 7 samples: critical Kp = %.3f at %.3f MHz (theory); the model sang at %.3f MHz" % (kp_c, f_c / 1e6, f_ring / 1e6))
print("1/(4 tau) at 280 ns: %.0f kHz;  1/(10 tau): %.0f kHz" % (1 / (4 * 280e-9) / 1e3, 1 / (10 * 280e-9) / 1e3))
print("wrote", out)
