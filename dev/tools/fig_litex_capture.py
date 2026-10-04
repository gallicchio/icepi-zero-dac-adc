"""Part 6 figure: three triggered captures (cap 2 128) of a 137 kHz, 3 V sine
from the LiteX capture peripheral, read with cap_plot.py.  Data were saved
while testing; this only draws them."""
import os
import numpy as np
from plotstyle import plt, save, dots, C1, C2, C3, INK2
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data", "litex_capture.npz")
IMG = os.path.join(HERE, "..", "..", "tutorial", "img", "litex_capture.png")

d = np.load(DATA)
t, caps = d["t"], d["caps"]
volts = (caps - 126.7) / 25.35
fig, ax = plt.subplots(figsize=(8, 3.8))
sel = t < 16e-6
for v, c, lab in zip(volts, (C1, C2, C3), ("capture 1", "capture 2", "capture 3")):
    ax.plot(t[sel] * 1e6, v[sel], color=c, lw=0.8, alpha=0.5)
    dots(ax, t[sel] * 1e6, v[sel], c, label=lab, size=4)
ax.axhline((128 - 126.7) / 25.35, color=INK2, lw=0.8)
ax.annotate("trigger level: code 128", (0.35, -0.55), color=INK2, fontsize=9)
ax.set_xlabel("time after trigger (µs)   — one dot per sample, 160 ns apart")
ax.set_ylabel("ADC input (V)")
ax.set_title("cap 2 128, three times: every capture starts on an upward crossing")
ax.legend(loc="lower right", ncol=3)
ax.set_ylim(-4.0, 3.6)
save(fig, IMG)
print("wrote", IMG)
