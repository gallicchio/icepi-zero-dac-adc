"""7.01/7.02 figure, COMPUTED (no hardware): what a filter's taps do.

dsp_fir_intuition.png: four rows, one per kernel.  Left: the taps.  Middle: the kernel
sliding along a test signal (a square wave plus noise plus a slow ramp, in ADC codes) and
what comes out.  Right: the frequency response in dB.
  1. a 16-sample moving average            (fir.sv SET 0)
  2. a 15-tap windowed-sinc low-pass, 2 MHz (fir.sv SET 1, the taps as fir.sv rounds them)
  3. the edge detector [-1 2 -1]           (fir.sv SET 2)
  4. the one-tap IIR y += (x - y)/16       (iir.sv K = 4): its impulse response, its step
     response beside an RC's, and its response beside 1/(1 + j f/fc)

    python3 fig_fir_intuition.py
"""
import os
import sys

import numpy as np
from scipy import signal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from plotstyle import plt, save, dots, C1, C2, C3, INK, INK2, MUTED, GRID, SURFACE   # noqa: E402

IMG = os.path.join(HERE, "..", "..", "..", "tutorial", "img", "dsp_fir_intuition.png")
FS = 25e6
K = 4                                           # the one-pole's 2^K

# ---- the kernels, as the gateware holds them (integers / 256) ---------------------------
avg = np.full(16, 16) / 256
lpf = np.round(256 * signal.firwin(15, 2e6, fs=FS)) / 256
edge = np.array([-1, 2, -1])

# ---- the test signal: a square wave + noise + a ramp, 320 samples -------------------------
rng = np.random.default_rng(3)
n = np.arange(320)
sig = 40 * np.sign(np.sin(2 * np.pi * n / 80 + 0.3)) + 6 * rng.standard_normal(len(n)) + 0.1 * n - 16


def run(h, x):
    """y[n] = sum_k h[k] x[n-k], the gateware's way (no samples before the start)."""
    return np.convolve(x, h)[:len(x)]


def show_kernel(ax, h, x, y, n0, color, name):
    """The input, the output, and the kernel sitting at position n0 (its taps drawn
    inside the window, scaled to fit)."""
    N = len(h)
    ax.plot(n, x, color=MUTED, lw=0.9, label="in")
    ax.plot(n, y, color=color, lw=1.6, label="out")
    lo, hi = n0 - N + 1, n0
    ax.axvspan(lo - 0.5, hi + 0.5, color=color, alpha=0.12, lw=0)
    base, scale = 68, 22 / np.abs(h).max()
    for k in range(N):
        ax.plot([n0 - k, n0 - k], [base, base + scale * h[k]], color=color, lw=1.4)
    ax.plot([lo - 0.5, hi + 0.5], [base, base], color=color, lw=0.8)
    ax.annotate("", (n0, y[n0]), (n0, base - 3), arrowprops=dict(arrowstyle="-|>", color=color, lw=1,
                                                                mutation_scale=9))
    ax.text((lo + hi) / 2, base + 25, "the kernel, h, slid to n = %d:\n%s" % (n0, name), ha="center",
            va="bottom", size=7.5, color=INK2)
    ax.set_xlim(0, len(n))
    ax.set_ylim(-75, 115)
    ax.set_ylabel("ADC codes")
    ax.legend(loc="lower right", ncol=2, fontsize=8)


def freq_response(ax, h, color, label, a=(1.0,)):
    f = np.geomspace(1e5, FS / 2, 600)
    _, H = signal.freqz(h, a, worN=f, fs=FS)
    ax.semilogx(f / 1e6, 20 * np.log10(np.abs(H) + 1e-9), color=color, label=label)
    ax.set_xlim(0.1, 12.5)
    ax.set_ylim(-62, 16)
    ax.set_ylabel("|H| (dB)")
    ax.grid(True, which="both")


fig, axs = plt.subplots(4, 3, figsize=(10, 12.6), gridspec_kw=dict(width_ratios=[1, 1.9, 1.3]))
fig.subplots_adjust(hspace=0.62)
rows = [(avg, C1, "16 taps of 1/16", "A moving average: a dot product that slides"),
        (lpf, C2, "windowed sinc, 15 taps", "A windowed sinc: a sophisticated average"),
        (edge, C3, "[−1  2  −1]", "An edge detector: the second difference")]
for r, (h, color, name, title) in enumerate(rows):
    a, b, c = axs[r]
    a.stem(np.arange(len(h)), h, linefmt=color, markerfmt="o", basefmt=" ")
    a.plot(np.arange(len(h)), h, "o", color=color, ms=4.5, mec=SURFACE, mew=0.8)
    a.set_xlim(-1, 16)
    a.set_ylim(min(-1.1, 1.3 * h.min()) if h.min() < 0 else -0.02, 2.2 if h.max() > 1 else 0.21)
    a.set_xlabel("tap k")
    a.set_ylabel("h[k]")
    a.set_title("the taps: %s" % name, fontsize=9.5)
    y = run(h, sig)
    show_kernel(b, h, sig, y, 150, color, name)
    b.set_title(title)
    b.set_xlabel("sample n")
    freq_response(c, h, color, name)
    c.set_title("frequency response", fontsize=9.5)
    c.set_xlabel("frequency (MHz)")
# row notes
axs[0, 2].annotate("nulls at k × fs/16\n= 1.56 MHz, 3.1, ...", (1.56, -40), (0.17, -45), fontsize=7.5, color=INK2,
                   arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=0.8))
axs[1, 2].annotate("−6 dB at the 2 MHz\ncutoff, then down\nlike a cliff", (2, -5), (0.13, -30), fontsize=7.5, color=INK2,
                   arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=0.8))
axs[1, 2].semilogx(np.geomspace(0.1, 12.5, 300), 20 * np.log10(np.abs(np.sinc(np.geomspace(0.1, 12.5, 300) / 1.5625)) + 1e-9),
                   color=C1, lw=0.8, ls=":", label="the moving average")
axs[1, 2].legend(fontsize=7.5, loc="upper right")
axs[2, 2].annotate("4 sin²(πf/fs): rises as f²,\n+12 dB at fs/2", (2, -12), (0.13, 2), fontsize=7.5, color=INK2,
                   arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=0.8))

# ---- row 4: the one-tap IIR -----------------------------------------------------------------
alpha = 2.0**-K
fc = FS * alpha / (2 * np.pi)                   # the RC's cutoff: 249 kHz
tau = 2**K                                      # samples
a, b, c = axs[3]
k = np.arange(48)
h_iir = alpha * (1 - alpha)**k
a.stem(k, h_iir, linefmt=C2, markerfmt="o", basefmt=" ")
a.plot(k, h_iir, "o", color=C2, ms=3.5, mec=SURFACE, mew=0.8)
tt = np.linspace(0, 47, 300)
a.plot(tt, alpha * np.exp(-tt / tau), color=MUTED, lw=1, ls="--", label="e$^{-t/\\tau}$, τ = 16 samples")
a.set_xlim(-1, 48)
a.set_ylim(-0.004, 0.072)
a.set_xlabel("sample k")
a.set_ylabel("h[k]")
a.set_title("impulse response: (1/16)(15/16)$^k$", fontsize=9.5)
a.legend(fontsize=7.5, loc="upper right")
# the step response, beside an RC's
kk = np.arange(-5, 70)
step_in = (kk >= 0) * 1.0
y_step = signal.lfilter([alpha], [1, -(1 - alpha)], step_in)
b.step(kk, step_in, where="post", color=MUTED, lw=0.9, label="the step in")
dots(b, kk, y_step, C2, label="y += (x − y)/16, each sample", size=3.5)
tt = np.linspace(0, 70, 400)
b.plot(tt, 1 - np.exp(-tt / tau), color=INK2, lw=1, ls="--", label="an RC charging, 1 − e$^{-t/\\tau}$")
b.axvline(tau, color=GRID, lw=1)
b.text(tau + 1.5, 0.30, "τ = 16 samples\n= 640 ns", fontsize=7.5, color=INK2)
b.set_xlim(-5, 70)
b.set_ylim(-0.05, 1.15)
b.set_xlabel("sample n")
b.set_ylabel("output")
b.set_title("An RC in one line: y += (x − y)/16")
b.legend(fontsize=7.5, loc="lower right")
# the frequency response, beside 1/(1 + j f/fc)
f = np.geomspace(1e4, FS / 2, 600)
freq_response(c, [alpha], C2, "y += (x − y)/16", a=[1, -(1 - alpha)])
Hrc = 1 / (1 + 1j * f / fc)
c.semilogx(f / 1e6, 20 * np.log10(np.abs(Hrc)), color=INK2, lw=1, ls="--", label="an RC, 1/(1 + jf/f$_c$)")
c.axvline(fc / 1e6, color=GRID, lw=1)
c.text(fc / 1e6 * 1.1, 8, "f$_c$ = fs/(2π·16)\n= %.0f kHz" % (fc / 1e3), fontsize=7.5, color=INK2)
c.set_xlim(0.01, 12.5)
c.set_ylim(-42, 16)
c.set_xlabel("frequency (MHz)")
c.legend(fontsize=7.5, loc="lower left")
_, Hd = signal.freqz([alpha], [1, -(1 - alpha)], worN=[2e6, FS / 2], fs=FS)
dev2, devn = 20 * np.log10(np.abs(Hd)) - 20 * np.log10(np.abs(1 / (1 + 1j * np.array([2e6, FS / 2]) / fc)))
c.set_title("vs an RC: %+.1f dB at 2 MHz,\n%+.1f dB at fs/2" % (dev2, devn), fontsize=9.5)

fig.text(0.995, 0.995, "computed, not measured", ha="right", va="top", size=8, color=MUTED)
fig.suptitle("Four kernels: the taps, the taps at work on a square wave + noise + a ramp, and |H|",
             x=0.01, ha="left", fontsize=11.5, weight="bold", y=0.995)
save(fig, IMG)
print("wrote", IMG, "  one-pole vs RC: %+.2f dB at 2 MHz, %+.2f dB at fs/2; fc = %.1f kHz" % (dev2, devn, fc / 1e3))
