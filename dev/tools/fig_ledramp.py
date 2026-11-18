"""1.11's figure, worked out from ledramp.sv (no measurement): the DAC's voltage against the four LEDs' photon
energies, and which of the five LEDs is on when.

    python3 dev/tools/fig_ledramp.py      # writes tutorial/img/ledramp_code.png
"""
import os
import numpy as np
from plotstyle import plt, save, C1, INK, INK2, MUTED, GRID

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, "..", "..", "tutorial", "img", "ledramp_code.png")
LEDS = [("red", 630, "#c8352e"), ("yellow", 596, "#b8860b"), ("green", 525, "#1e8f4e"), ("blue", 469, "#2f5bc8")]
HC_E = 1239.84                                  # h c / e, in volt-nanometres


def volts(code):
    return 0.0307 * code - 3.95                 # 1.02's measured DAC


step = 2**24 * 20e-9                            # ledramp.sv: v = t[30:24], one step every 2^24 clocks of 20 ns
tmax = 50.0
t = np.arange(0, tmax, step / 8)
v = np.floor(t / step).astype(int) % 128        # 7 bits: wraps to 0 after 127 (42.95 s)
fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 6.0), sharex=True, gridspec_kw=dict(height_ratios=[1.4, 1]))
a1.plot(t, volts(128 + v), color=INK, lw=1.6, drawstyle="steps-post")
for (name, nm, col), dy in zip(LEDS, (-0.1, 0.03, 0, 0)):     # red and yellow's labels apart
    e = HC_E / nm
    a1.axhline(e, color=col, lw=1.2, ls=(0, (5, 3)))
    a1.text(tmax + 0.4, e + dy, f"{name} {nm} nm: hc/λe = {e:.2f} V", va="center", fontsize=8.5, color=INK2)
a1.annotate("the top: code 255, +3.88 V", (42.9, volts(255)), (27.0, 3.55), fontsize=8.5, color=INK2,
            arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
a1.set_ylim(-0.1, 4.2)
a1.set_ylabel("DAC OUT (V)")
a1.set_title("ledramp.sv, worked out from the code: 0 to +3.88 V in 128 steps over 43 s, then back to 0 V")
for k in range(5):
    half = step * 2**(k + 2)                    # led[k] = v[k + 2]
    bars, j = [], 1
    while j * half < tmax:
        bars.append((j * half, min(half, tmax - j * half)))
        j += 2
    a2.broken_barh(bars, (k - 0.32, 0.64), facecolors=C1, edgecolors="none", zorder=3)
    a2.text(tmax + 0.4, k, f"{0.0307 * 4 * 2**k:.3f} V", va="center", fontsize=8.5, color=INK2)
a2.set_yticks(range(5))
a2.set_yticklabels(["led[0] (right)", "led[1]", "led[2]", "led[3]", "led[4] (left)"])
a2.set_ylim(-0.7, 4.7)
a2.set_xlim(0, tmax)
a2.set_xlabel("time after the design loads (s)")
a2.set_title("a bar where each LED is on; at the right, what each is worth", fontsize=10)
a2.grid(axis="y", visible=False)
a2.set_axisbelow(True)
a2.spines["left"].set_visible(False)
a2.tick_params(axis="y", length=0)
fig.subplots_adjust(right=0.8)
save(fig, IMG)
print("wrote", os.path.normpath(IMG))
