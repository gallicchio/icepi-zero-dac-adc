"""Opening figures for 5.04, 5.05, 5.06, 5.07 and 6.07.

tb_coupled_intro.png  two boards nudging each other (a sketch), and two runs of coupled.py
                      from data/tb_adler.npz: one locked, one just outside the locking range
tb_modem_intro.png    modem.sv's arithmetic on the letter "H": the serial line, the tones the
                      DAC plays, and the receiver's two energies and its decision, with dots
                      where the receiving laptop's UART reads it (mid-bit) and the 16 samples
                      each of those readings came from.  Computed with exactly the design's
                      numbers (sine table of +-100, tuning words, 16-sample windows,
                      threshold); the cable is a 6-sample delay.
"""
import os
import sys

import numpy as np
from matplotlib.patches import FancyBboxPatch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from plotstyle import plt, save, dots, C1, C2, C3, INK, INK2, MUTED   # noqa: E402

IMG = os.path.join(HERE, "..", "..", "..", "tutorial", "img")
DATA = os.path.join(HERE, "..", "..", "data")

# ---- 5.04 ---------------------------------------------------------------------------------
z = np.load(os.path.join(DATA, "tb_adler.npz"))
fig, (a, b) = plt.subplots(1, 2, figsize=(10, 3.4), gridspec_kw=dict(width_ratios=[1, 1.35]))
a.axis("off")
a.set_xlim(0, 10)
a.set_ylim(0, 6)
for x, name in [(0.3, "board A"), (6.2, "board B")]:
    a.add_patch(FancyBboxPatch((x, 2.2), 3.5, 1.9, boxstyle="round,pad=0,rounding_size=0.2",
                               fc="#eef3fb", ec=C1, lw=1.2))
    a.text(x + 1.75, 3.6, name, ha="center", fontsize=10, weight="bold")
    a.text(x + 1.75, 2.75, "a sine (DDS)\n+ a phase meter", ha="center", fontsize=8.5, color=INK2)
a.annotate("", (6.2, 3.55), (3.8, 3.55), arrowprops=dict(arrowstyle="-|>", color=C1, lw=1.6))
a.annotate("", (3.8, 2.7), (6.2, 2.7), arrowprops=dict(arrowstyle="-|>", color=C2, lw=1.6))
a.text(5.0, 3.75, "A's sine", ha="center", fontsize=8.5, color=C1)
a.text(5.0, 2.25, "B's sine", ha="center", fontsize=8.5, color=C2, va="top")
a.text(5.0, 0.9, "each nudges its own frequency\ntowards the other's phase:\n"
       "f$_A$ = f$_0$ + K$_A$ sin(φ$_A$ − c/2)", ha="center", fontsize=8.5, color=INK)
a.text(5.0, 5.3, "Huygens' two clocks, in silicon", ha="center", fontsize=10, color=INK, weight="bold")
for name, col, lab in (("ex_locked", C3, "detuned by less than K: they lock"),
                       ("ex_slip", C2, "detuned by a little more: they slip, a turn at a time")):
    r = z[name]
    b.plot(r[:, 0], np.unwrap(r[:, 1]) / (2 * np.pi), ".", color=col, markersize=2.5, label=lab)
b.set_xlabel("time (s)")
b.set_ylabel("phase of B at A (turns)")
b.set_title("Two boards, coupled through the laptop (measured)")
b.legend(loc="lower left", fontsize=8.5, markerscale=4)
save(fig, os.path.join(IMG, "tb_coupled_intro.png"))

# ---- 5.05 ---------------------------------------------------------------------------------
BAUD = 1e6               # fast enough to draw, slow enough that a 16-sample window fits in a bit
bits = [1, 1, 0] + [(0x48 >> i) & 1 for i in range(8)] + [1, 1, 1]   # idle, start, 'H', stop, idle
T = len(bits) / BAUD
n50 = np.arange(int(T * 50e6))                # 50 MHz clocks
line = np.array([bits[int(k / 50e6 * BAUD)] for k in n50])
table = np.floor(100 * np.sin(2 * np.pi * np.arange(256) / 256) + 0.5)
tw = np.where(line == 1, 0x2000_0000, 0x1000_0000)
phase = np.concatenate([[0], np.cumsum(tw)[:-1]]) % 2**32
dac = table[(phase >> 24).astype(int)]        # minus 128: the DAC's signed value
x = np.concatenate([np.zeros(12), dac])[: len(dac)][::2].round()   # 6 ADC samples of delay, 25 MS/s
n = np.arange(len(x))
c = 181 / 256
mi = np.choose(n % 4, [x, 0 * x, -x, 0 * x]); mq = np.choose(n % 4, [0 * x, x, 0 * x, -x])
si = np.choose(n % 8, [x, c * x, 0 * x, -c * x, -x, -c * x, 0 * x, c * x])
sq = np.choose(n % 8, [0 * x, c * x, x, c * x, 0 * x, -c * x, -x, -c * x])
run = lambda p: np.convolve(p, np.ones(16))[: len(p)]
em, es = run(mi) ** 2 + run(mq) ** 2, run(si) ** 2 + run(sq) ** 2
out = (em >= es) | (em + es < 40000)
fig, ax = plt.subplots(3, 1, figsize=(9, 5.6), sharex=True, gridspec_kw=dict(height_ratios=[1, 1.6, 1.6]))
t50, t25 = n50 / 50e6 * 1e6, n / 25e6 * 1e6
ax[0].step(t50, line, where="post", color=INK, lw=1.4)
for k, bt in enumerate(bits):
    ax[0].text((k + 0.5) / BAUD * 1e6, 1.25, str(bt), ha="center", fontsize=9, color=INK2)
ax[0].set_ylim(-0.3, 1.6)
ax[0].set_yticks([0, 1])
ax[0].set_title('1. The laptop sends "H" (start bit, 0x48 lowest bit first, stop bit), at 1 Mbaud')
ax[1].step(t50, dac / 100 * 3.07, where="post", color=INK2, lw=0.9)
ax[1].set_ylabel("volts")
ax[1].set_ylim(-3.6, 3.6)
ax[1].set_title("2. The DAC plays 6.25 MHz for each 1 and 3.125 MHz for each 0, never jumping in phase")
ax[2].plot(t25, em / em.max(), ".-", color=C1, lw=1, markersize=3, label="energy at 6.25 MHz (a 1)")
ax[2].plot(t25, es / em.max(), ".-", color=C2, lw=1, markersize=3, label="energy at 3.125 MHz (a 0)")
ax[2].step(t25, out * 1.0 + 0.0, where="post", color=INK, lw=1.2, alpha=0.6, label="the decision: the other laptop's line")
# The receiving laptop's UART finds the start bit's falling edge, then reads the line in the
# middle of each bit.  Each reading is the decision made from the 16 samples just before it.
fall = np.flatnonzero(np.diff(out.astype(int)) == -1)[0] + 1
reads = t25[fall] + (np.arange(10) + 0.5) / BAUD * 1e6
on = np.interp(reads, t25, out.astype(float)).round()
for k, tr in enumerate(reads):
    ax[2].axvspan(tr - 16 / 25, tr, color=C3, alpha=0.13, lw=0)
ax[2].plot(reads, on, "o", color=C3, markersize=7, markeredgecolor="white", zorder=5,
           label="where the receiving laptop reads it: mid-bit")
ax[2].annotate("each reading is the decision\nfrom the 16 ADC samples\n(0.64 µs) shaded before it",
               (reads[9] - 0.2, 0.45), xytext=(12.35, 0.3), fontsize=8, color=INK2, va="center",
               arrowprops=dict(arrowstyle="->", color=INK2, lw=0.8))
ax[2].set_ylabel("energy (relative)")
ax[2].set_xlabel("time (µs)")
ax[2].set_title("3. The other board's receiver: which tone has more energy in the last 0.64 µs?")
ax[2].set_ylim(-0.08, 1.75)
ax[2].legend(loc="upper center", fontsize=8, ncol=2)
save(fig, os.path.join(IMG, "tb_modem_intro.png"))
print("wrote tb_coupled_intro.png, tb_modem_intro.png")

# ---- 5.06 ---------------------------------------------------------------------------------
# What the receiver gets: the modem's two tones (MARK 6.25 MHz = 1, SPACE 3.125 MHz = 0) at
# 25 MS/s, for four bit patterns, with white noise added at three SNRs per sample,
# A^2 / 2 sigma^2 (the x axis of 5.06's results).  Bits drawn 16 samples long so the tones
# show; the error rate in the inset was measured at 115,200 baud (5.06's table).
rng = np.random.default_rng(3)
SPB = 16
pats = [("0000", "zeros: SPACE"), ("1111", "ones: MARK"), ("1010", "alternating"),
        ("0010", "mixed")]
bitstr = "".join(p for p, _ in pats)
ph, x = 0.0, []
for b in bitstr:
    for _ in range(SPB):
        x.append(np.cos(ph))
        ph += 2 * np.pi * (0.25 if b == "1" else 0.125)
x = np.array(x)
n = np.arange(len(x))
fig, ax = plt.subplots(3, 1, figsize=(10, 5.6), sharex=True)
for a, snr_db in zip(ax, [10, 0, -8.4]):
    sigma = 1 / np.sqrt(2 * 10 ** (snr_db / 10))
    y = x + rng.normal(0, sigma, len(x))
    for j, (p, lab) in enumerate(pats):
        a.axvspan(j * 4 * SPB, (j + 1) * 4 * SPB, color=[C1, C2, C3, MUTED][j], alpha=0.07, lw=0)
        if a is ax[0]:
            a.text((j + 0.5) * 4 * SPB, 1.0, f"{p}  ({lab})", ha="center", va="bottom", fontsize=8.5,
                   color=INK2, transform=a.get_xaxis_transform())
    a.plot(n, x, color=MUTED, lw=1.0, alpha=0.8)
    a.plot(n, y, ".-", color=C1, lw=0.6, markersize=3)
    lim = 1 + 3.2 * sigma
    a.set_ylim(-lim, lim)
    a.set_yticks([])
    # E/N0 of the receiver's whole window: W * SNR / 2 (5.06's "What to expect")
    per_window = snr_db + 10 * np.log10(128 / 2)
    a.text(0.005, 0.96, f"SNR {snr_db:g} dB per sample,  ".replace("-", "−")
           + f"{per_window:.1f} dB per 128-sample window (E/N$_0$)", transform=a.transAxes, fontsize=9.5,
           weight="bold", va="top", color=INK, bbox=dict(fc="white", ec="none", alpha=0.8))
ax[2].set_xlabel("ADC sample number (25 MS/s; each bit drawn 16 samples long; grey: without noise)")
ax[2].set_xlim(0, len(x))
ax[0].set_title("The modem's two tones, as the receiver samples them, with noise", pad=18)
ax[2].text(0.99, 0.06, "Even at this noise level, the modem's 128-sample receiver\n"
           "gets only 3 bits in 1000 wrong (BER 3.1 × 10$^{-3}$, measured)",
           transform=ax[2].transAxes, ha="right", va="bottom", fontsize=9.5, color=INK,
           bbox=dict(fc="#fff6d6", ec=C2, lw=1.2, boxstyle="round,pad=0.4"))
save(fig, os.path.join(IMG, "tb_noise_intro.png"))
print("wrote tb_noise_intro.png")

# ---- 5.07 ---------------------------------------------------------------------------------
# Left: the link.  Right: the estimate the page works through -- a 30 cm one-turn loop at
# each end, both tuned to 6.78 MHz, on a common axis; the transmitter's current is the DAC's
# amplitude over 50 ohm; the receiving loop's EMF is multiplied by its Q (30) at resonance.
from matplotlib.patches import Circle, Ellipse
fig, (a, b) = plt.subplots(1, 2, figsize=(10, 3.6), gridspec_kw=dict(width_ratios=[1.25, 1]))
a.axis("off")
a.set_xlim(0, 12)
a.set_ylim(0, 6)
for x, name, what in [(0.2, "board A", "radio.sv\nyou type here"), (8.6, "board B", "radio.sv\nthe text appears here")]:
    a.add_patch(FancyBboxPatch((x, 0.5), 3.2, 1.5, boxstyle="round,pad=0,rounding_size=0.15",
                               fc="#eef3fb", ec=C1, lw=1.2))
    a.text(x + 1.6, 1.55, name, ha="center", fontsize=10, weight="bold")
    a.text(x + 1.6, 0.95, what, ha="center", fontsize=8, color=INK2, va="center")
for xc, lab, src in [(3.3, "DAC → C → loop", (1.8, 2.0)), (8.7, "loop ∥ C → ADC", (10.2, 2.0))]:
    a.add_patch(Ellipse((xc, 3.9), 0.7, 2.6, fc="none", ec="#b87333", lw=3))
    a.plot([src[0], src[0], xc], [src[1], 2.4, 2.6], color=INK2, lw=1)
    a.text(xc, 5.45, lab, ha="center", fontsize=8.5, color=INK2)
for k, h in enumerate([0.5, 1.0, 1.5]):            # field lines between the loops
    a.add_patch(Ellipse((6.0, 3.9), 5.4 + 0.6 * k, 0.4 + 1.1 * h, fc="none", ec=C2, lw=0.9, ls="--"))
a.text(6.0, 2.25, "6.78 MHz magnetic field\nabout 1 m", ha="center", fontsize=8.5, color=C2)
a.text(6.0, 5.75, "One board talks, one listens", ha="center", fontsize=10, weight="bold", color=INK)
mu0, f, A_loop, Q = 4e-7 * np.pi, 6.78e6, np.pi * 0.15 ** 2, 30
r = np.logspace(np.log10(0.2), np.log10(4), 200)
for amp, col in [(100, C1), (25, C3)]:
    I = amp * 0.0307 / 50                              # DAC volts / 50 ohm
    emf = 2 * np.pi * f * mu0 * I * A_loop / (2 * np.pi * r ** 3) * A_loop
    b.loglog(r, emf * Q * 25.35, color=col, label=f"AMP = {amp} ({I * 1e3:.0f} mA in the loop)")
b.axhline(0.78, color=MUTED, ls="--", lw=1)
b.text(0.21, 0.9, "0.78 codes: the weakest signal tested\n(through a cable), 0 errors", fontsize=8, color=INK2)
b.set_xlabel("distance between the loops (m)")
b.set_ylabel("amplitude at the ADC (codes)")
b.set_title("An estimate, not measured: falling as 1/r³")
b.axhline(128, color=MUTED, lw=0.8)
b.text(3.9, 140, "the ADC's full scale", fontsize=8, color=INK2, ha="right")
b.set_xticks([0.2, 0.5, 1, 2, 4], ["0.2", "0.5", "1", "2", "4"])
b.set_ylim(0.005, 400)
b.legend(loc="lower left", fontsize=8)
save(fig, os.path.join(IMG, "radio_intro.png"))
print("wrote radio_intro.png")

# ---- 6.07 ---------------------------------------------------------------------------------
# OFDM: a QAM-64 constellation on every subcarrier, stacked along frequency.  Measured: the
# received, equalized points of data/tb_ofdm_loop_64.npz (one board, 4 runs of 27 symbols);
# each plane pools 8 neighbouring subcarriers, so its 64 clusters show.
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401,E402
z = np.load(os.path.join(DATA, "tb_ofdm_loop_64.npz"))
Z, fk = z["Z"], z["fk"]
fig = plt.figure(figsize=(12, 4.6))
ax = fig.add_subplot(111, projection="3d")
pick = np.arange(0, Z.shape[2] - 7, 8)
cols = plt.cm.viridis(np.linspace(0.05, 0.85, len(pick)))
for c, k in zip(cols, pick):
    pts = Z[:, :, k:k + 8].ravel()             # this subcarrier and its 7 neighbours
    f = fk[k + 4] / 1e6
    ax.scatter(np.full(pts.shape, f), pts.real, pts.imag, s=1.2, color=c, depthshade=False)
    sq = 1.25
    ax.plot([f] * 5, [-sq, sq, sq, -sq, -sq], [-sq, -sq, sq, sq, -sq], color=c, lw=0.6, alpha=0.6)
ax.set_xlabel("subcarrier frequency (MHz)", labelpad=16)
ax.set_ylabel("in phase", labelpad=-8)
ax.set_zlabel("quadrature", labelpad=-8)
ax.set_yticks([])
ax.set_zticks([])
ax.view_init(elev=14, azim=-67)
ax.set_box_aspect((4.6, 1, 1))
ax.set_position([-0.2, -0.36, 1.4, 1.6])     # the 3D box is drawn small inside its axes: enlarge them
fig.suptitle("OFDM: a QAM-64 constellation on every subcarrier\n(measured; each plane is 8 neighbouring subcarriers)",
             y=0.97, fontsize=11, weight="bold")
fig.text(0.5, 0.04, "In each 11.5 µs symbol (256 samples and a 32-sample cyclic prefix), every subcarrier carries one of these 64 "
         "amplitude-and-phase points: 6 bits each, 113 at once", ha="center", fontsize=9, color=INK2)
fig.savefig(os.path.join(IMG, "tb_ofdm_intro.png"), dpi=130)
plt.close(fig)
print("wrote tb_ofdm_intro.png")
