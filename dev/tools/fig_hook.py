"""0.00's opening strip: three things Chapter 1 builds, from data the other scripts saved.

    python3 fig_hook.py      # writes tutorial/img/hook.png

  1.03  a 1 MHz sine from the DAC, as the M2k recorded it      (data/sine.npz)
  1.08  85 cm of cable timed by the lock-in's phase: 0.73 c    (data/cable_1m.npz, cable_16cm.npz)
  1.10  a tune sent as AM at 1 MHz and received by the ADC     (data/am_radio.npz)
"""
import os

import numpy as np
from plotstyle import plt, C1, C2, INK2, MUTED

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
IMG = os.path.join(HERE, "..", "..", "tutorial", "img", "hook.png")

fig, ax = plt.subplots(1, 3, figsize=(11.5, 3.6), gridspec_kw=dict(width_ratios=[1, 1, 1.25]))
fig.subplots_adjust(left=0.06, right=0.99, bottom=0.16, top=0.80, wspace=0.32)

# ---- 1.03: the sine ------------------------------------------------------------------------
d = np.load(os.path.join(DATA, "sine.npz"))
t, v = d["t"] * 1e6, d["v"]
k = t < t[0] + 2.0
ax[0].plot(t[k] - t[0], v[k], ".", color=C1, ms=2.5)
ax[0].set_xlabel("time (µs)"); ax[0].set_ylabel("DAC OUT (V)")
ax[0].set_title("1.03: a 1 MHz sine,\nmade by logic", fontsize=10.5)

# ---- 1.08: the cable, timed --------------------------------------------------------------------
a = np.load(os.path.join(DATA, "cable_1m.npz"))
b = np.load(os.path.join(DATA, "cable_16cm.npz"))
f = a["f"]
za, zb = a["z"].mean(0), b["z"].mean(0)
bad = np.zeros(len(f), bool)
for q in np.arange(1, 11) * 2.5e6:                      # as fig_cable.py: skip simple fractions of fs
    bad |= abs(f - q) < 60e3
fit = ~bad & (f <= 8e6)
dph = np.degrees(np.unwrap(np.angle(za)) - np.unwrap(np.angle(zb)))
p = np.polyfit(f[fit], dph[fit], 1)
tau = -p[0] / 360.0                                     # seconds for the extra 85 cm
ax[1].plot(f[fit] / 1e6, dph[fit], ".", color=C2, ms=4)
ax[1].plot(f[fit] / 1e6, np.polyval(p, f[fit]), color=INK2, lw=1)
ax[1].set_xlabel("frequency (MHz)"); ax[1].set_ylabel("extra phase (degrees)")
ax[1].set_title("1.08: 85 cm of cable timed, %.2f ns:\nlight in it goes at %.2f c" % (tau * 1e9, 0.85 / tau / 299792458.0),
                fontsize=10.5)

# ---- 1.10: the tune, over AM -------------------------------------------------------------------
d = np.load(os.path.join(DATA, "am_radio.npz"))
x = d["melody"] / 473.1
x = x - x.mean()
FS, NFFT, HOP = 25_000, 4096, 512
w = np.hanning(NFFT)
S = 20 * np.log10(np.array([np.abs(np.fft.rfft(w * x[i:i + NFFT])) for i in range(0, len(x) - NFFT, HOP)]).T + 1e-6)
fr = np.fft.rfftfreq(NFFT, 1 / FS)
tt = (np.arange(S.shape[1]) * HOP + NFFT / 2) / FS
sel = (fr > 200) & (fr < 450)
ax[2].grid(False)
ax[2].pcolormesh(tt, fr[sel], S[sel], shading="auto", cmap="magma", vmin=S[sel].max() - 50, vmax=S[sel].max())
ax[2].set_xlabel("time (s)"); ax[2].set_ylabel("frequency (Hz)")
ax[2].set_title("1.10: a tune sent as AM at 1 MHz\nand received, by radios made of logic", fontsize=10.5)

fig.suptitle("measured", x=0.995, ha="right", fontsize=8, color=MUTED)
fig.savefig(IMG, dpi=130)
print("wrote", IMG, " tau = %.2f ns, v = %.3f c" % (tau * 1e9, 0.85 / tau / 299792458.0))
