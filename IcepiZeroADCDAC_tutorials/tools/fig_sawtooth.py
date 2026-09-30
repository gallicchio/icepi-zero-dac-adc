"""Capture the sawtooth.v output on M2k CH1 and draw the tutorial figure.
Run with sawtooth.bit loaded.  --replot redraws from the saved data."""
import sys, os
import numpy as np
from plotstyle import plt, save, dots, C1, C2, INK2
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data", "sawtooth.npz")
IMG = os.path.join(HERE, "..", "img", "sawtooth.png")

if "--replot" not in sys.argv:
    import m2k
    m = m2k.M2k()
    t, v = m.ch1(1e8, 8192, trigger_level=0.0)
    m.close()
    os.makedirs(os.path.dirname(DATA), exist_ok=True)
    np.savez(DATA, t=t, v=v)
d = np.load(DATA)
t, v = d["t"], d["v"]

# start the plot at a wrap-around (the big downward step)
i0 = int(np.argmax(np.diff(v) < -3.0)) + 1
t = t - t[i0]
fig, (a, b) = plt.subplots(2, 1, figsize=(8, 6.2))

sel = (t >= -1e-6) & (t < 11.5e-6)
a.plot(t[sel] * 1e6, v[sel], color=C1)
a.set_xlabel("time (µs)")
a.set_ylabel("DAC output (V)")
a.set_title("sawtooth.v on the M2k: one 8-bit ramp every 256 × 20 ns = 5.12 µs")
a.axvspan(-0.15, 0.3, color=C2, alpha=0.12, lw=0)
a.annotate("zoomed below", (0.4, -3.2), color=INK2, ha="left", fontsize=9)

sel = (t >= -150e-9) & (t < 300e-9)
b.plot(t[sel] * 1e9, v[sel], color=C1, lw=1.0, alpha=0.5)
dots(b, t[sel] * 1e9, v[sel], C1, label="M2k samples, every 10 ns")
b.set_xlabel("time (ns)")
b.set_ylabel("DAC output (V)")
b.set_title("Zoomed in on the wrap: code 255 → 0 happens in one 20 ns clock period")
b.annotate("the edge takes ~20 ns and rings: the module's output\n"
           "amplifier and the M2k's ~30 MHz bandwidth both smooth it",
           (40, -1.0), color=INK2, fontsize=9)
b.legend(loc="upper right")
save(fig, IMG)
print("wrote", IMG)
