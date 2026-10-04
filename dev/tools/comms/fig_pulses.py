"""6.01's explanatory figure: pulse shapes, their spectra, and Nyquist's zero crossings.
Computed, no hardware.

    python3 fig_pulses.py        # writes tutorial/img/comms_pulses.png

left:   one symbol as a square pulse, a root-raised-cosine pulse (alpha 0.35) and the
        raised cosine that two RRCs in a row make, with the neighbouring symbol
        instants marked: the raised cosine is exactly zero at every other symbol's centre
middle: their spectra, in dB: the square pulse's sinc sidelobes fall as 1/f; the RRC
        stops at (1 + alpha) R / 2
right:  a train of raised-cosine pulses with random +-1 symbols: the sum passes exactly
        through each symbol's value at its centre (no intersymbol interference), and
        wobbles anywhere else, which is why timing matters (6.02)
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "src", "comms"))
from plotstyle import plt, save, C1, C2, C3, INK, INK2, MUTED   # noqa: E402
from psk import rrc, rc, ALPHA                                   # noqa: E402

IMG = os.path.join(HERE, "..", "..", "..", "tutorial", "img")
t = np.linspace(-4, 4, 1601)                     # symbol periods
sq = (np.abs(t) < 0.5).astype(float)
h_rrc = rrc(t) / rrc(np.array([0.0]))[0]
h_rc = rc(t)

fig, ax = plt.subplots(1, 3, figsize=(12, 3.8), gridspec_kw=dict(width_ratios=[1, 1, 1.25]))
a = ax[0]
a.plot(t, sq, color=MUTED, lw=1.2, label="square")
a.plot(t, h_rrc, color=C2, lw=1.4, label="root-raised cosine, α = 0.35")
a.plot(t, h_rc, color=C1, lw=1.4, label="raised cosine (RRC twice)")
for k in range(-3, 4):
    a.axvline(k, color=INK2, lw=0.5, ls=":")
a.plot(np.arange(-3, 4), rc(np.arange(-3, 4.0)), "o", color=C1, markersize=5, zorder=5)
a.set_xlim(-4, 4)
a.set_ylim(-0.3, 1.15)
a.set_xlabel("time (symbols)")
a.set_title("One symbol's pulse: the raised cosine\nis zero at every other symbol's centre")
a.legend(loc="upper right", fontsize=8)

# spectra: long zero-padded transforms, per symbol rate R = 1
n = 2 ** 16
dt = t[1] - t[0]
f = np.fft.rfftfreq(n, dt)
b = ax[1]
for h, c, lab in [(sq, MUTED, "square"), (h_rrc, C2, "root-raised cosine"), (h_rc, C1, "raised cosine")]:
    H = np.abs(np.fft.rfft(h, n)) * dt
    b.plot(f, 20 * np.log10(H / H[0] + 1e-9), color=c, lw=1.2, label=lab)
b.axvline((1 + ALPHA) / 2, color=INK2, lw=0.8, ls="--")
b.text((1 + ALPHA) / 2 + 0.05, -8, "(1 + α) R / 2:\nthe RRC stops here", fontsize=8, color=INK2)
b.set_xlim(0, 3)
b.set_ylim(-70, 3)
b.set_xlabel("frequency / symbol rate R")
b.set_ylabel("spectrum (dB)")
b.set_title("Their spectra: the square pulse's\nsidelobes fall only as 1/f")
b.legend(loc="upper right", fontsize=8)

# a train of raised-cosine pulses
rng = np.random.default_rng(4)
sym = rng.choice([-1.0, 1.0], 12)
tt = np.linspace(-1, 12, 2601)
train = np.zeros_like(tt)
cc = ax[2]
for k, s in enumerate(sym):
    pulse = s * rc(tt - k)
    train += pulse
    cc.plot(tt, pulse, color=C1, lw=0.6, alpha=0.35)
cc.plot(tt, train, color=INK, lw=1.4, label="the sum: what the receiver sees")
cc.plot(np.arange(12), sym, "o", color=C2, markersize=5, zorder=5, label="the symbols, at their centres")
cc.set_xlim(-0.5, 11.5)
cc.set_ylim(-1.6, 1.6)
cc.set_xlabel("time (symbols)")
cc.set_title("Twelve raised-cosine symbols: their sum hits\nevery symbol exactly, at its centre only")
cc.legend(loc="lower right", fontsize=8)
save(fig, os.path.join(IMG, "comms_pulses.png"))
print("wrote comms_pulses.png")
