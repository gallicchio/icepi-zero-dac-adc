"""1.09's figures: spectra of loopback.sv's square wave through the 101.5 cm cable, computed
with src/verilog/spectrum.py's spectrum().  Data: data/spectrum_loop.npz, 64 records of
loopback.py s (and 16 of p), recorded with loopback.record().

    python3 fig_spectrum.py    # writes tutorial/img/spectrum_square.png, spectrum_leakage.png,
                               # spectrum_average.png
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src", "verilog"))
from plotstyle import plt, save, dots, C1, C2, C3, INK2, MUTED   # noqa: E402
from spectrum import spectrum, CODES_PER_VOLT                     # noqa: E402

IMG = os.path.join(HERE, "..", "..", "tutorial", "img")
d = np.load(os.path.join(HERE, "..", "data", "spectrum_loop.npz"))
x = d["s"] / CODES_PER_VOLT                 # 64 records, volts
FS = 25e6
dB = lambda a: 20 * np.log10(a + 1e-9)


def bin_axis(ax, hz_per_unit, df, ticks):
    """A second x axis, on top: the FFT bin number k = f / df, with the given ticks."""
    sec = ax.secondary_xaxis("top", functions=(lambda x: x * hz_per_unit / df, lambda k: k * df / hz_per_unit))
    sec.set_xticks(ticks)
    sec.set_xlabel("FFT bin k", fontsize=9)
    return sec


# ---- figure 1: a square wave's Fourier series --------------------------------------------
f, a = spectrum(x, FS)
half = np.std(x[0])          # the half-swing: a square wave's rms is its half-swing
n = np.arange(1, 512, 2)
f_n = n * FS / 1024                                     # odd harmonics of 25 MHz / 1024
fig, (ax, bx) = plt.subplots(2, 1, figsize=(8, 7.0))
ax.plot(f / 1e6, dB(a), color=C1, lw=0.7, label="measured: 64 records, Hann window, power averaged")
ax.plot(f_n / 1e6, dB(4 / np.pi / n * half), "o", mfc="none", mec=C2, mew=1, markersize=5,
        label="Fourier series: (4/π)(1/n) × the half-swing, odd n")
ax.set_xlim(0, 1.0)
ax.set_ylim(-100, 20)
ax.set_xlabel("frequency (MHz)")
ax.set_ylabel("amplitude (dB re 1 V)")
ax.set_title("A 24.4 kHz square wave through the cable: odd harmonics, falling as 1/n", pad=28)
bin_axis(ax, 1e6, FS / 16384, [0, 128, 256, 512])
ax.annotate("even harmonics: 77 dB down", (2 * 25e6 / 1024 / 1e6, -66), xytext=(0.12, -50),
            arrowprops=dict(arrowstyle="->", color=INK2, lw=0.8), color=INK2, fontsize=9)
ax.text(0.55, -93, "the noise floor of an 8-bit ADC, averaged", color=INK2, fontsize=9)
ax.legend(loc="upper right", fontsize=8.5)
peaks = np.array([a[np.argmin(abs(f - fn))] for fn in f_n])
ratio = peaks / (4 / np.pi / n * half)
dots(bx, f_n / 1e6, dB(ratio), C1, size=3.5, label="each odd harmonic ÷ its Fourier-series value")
alias = (np.pi * n / 1024) / np.sin(np.pi * n / 1024)  # a perfect square wave, sampled: aliases add up
bx.plot(f_n / 1e6, dB(alias), color=C2, lw=1.2,
        label="a perfect square wave, sampled: (πn/1024) / sin(πn/1024)")
bx.set_xlabel("frequency (MHz)")
bx.set_ylabel("measured ÷ series (dB)")
bx.set_title("Every harmonic at once: aliasing, plus the loop's own frequency response", pad=28)
bin_axis(bx, 1e6, FS / 16384, [0, 1024, 2048, 4096, 8192])
bx.set_xlim(0, 12.5)
bx.legend(loc="upper left", fontsize=8.5)
save(fig, os.path.join(IMG, "spectrum_square.png"))

# ---- figure 2: leakage, and windows ------------------------------------------------------
fig, ax = plt.subplots(figsize=(8, 4.0))
for rec, win, col, lab in [(x[:1], "rect", C1, "16384 samples = 16 whole periods, no window"),
                           (x[:1, :10000], "rect", C2, "10000 samples = 9.77 periods, no window: leakage"),
                           (x[:1, :10000], "hann", C3, "the same 10000 samples, Hann window")]:
    ff, aa = spectrum(rec, FS, win)
    ax.plot(ff / 1e3, dB(aa), ".-", color=col, lw=0.8, markersize=3, label=lab)
ax.set_xlim(0, 200)
ax.set_ylim(-110, 20)
ax.set_xlabel("frequency (kHz)")
ax.set_ylabel("amplitude (dB re 1 V)")
ax.set_title("Leakage: a record that cuts a period short smears every line", pad=28)
bin_axis(ax, 1e3, FS / 16384, [0, 16, 32, 64, 128])
ax.legend(loc="upper right", fontsize=8.5)
save(fig, os.path.join(IMG, "spectrum_leakage.png"))

# ---- figure 3: averaging -----------------------------------------------------------------
fig, ax = plt.subplots(figsize=(8, 3.8))
for k, col, lab in [(1, MUTED, "one record"), (64, C1, "64 records, power averaged")]:
    ff, aa = spectrum(x[:k], FS)
    sel = (ff > 1.0e6) & (ff < 1.25e6)
    ax.plot(ff[sel] / 1e6, dB(aa[sel]), color=col, lw=0.8, label=lab)
ax.set_xlabel("frequency (MHz)")
ax.set_ylabel("amplitude (dB re 1 V)")
ax.set_title("Averaging smooths the noise floor, so that small lines stand out", pad=28)
bin_axis(ax, 1e6, FS / 16384, [656, 704, 768, 816])
ax.set_ylim(top=0)                 # room above the traces for the legend
ax.legend(loc="upper right", fontsize=8.5, ncol=2)
save(fig, os.path.join(IMG, "spectrum_average.png"))

# numbers for the page
i1 = np.argmin(abs(f - 25e6 / 1024))
print("fundamental %.4f V (series %.4f V)" % (a[i1], 4 / np.pi * half))
for nn in (3, 99, 255):
    i = np.argmin(abs(f - nn * 25e6 / 1024))
    print("harmonic %d: %.4f V, series %.4f V, ratio %.3f" % (nn, a[i], 4 / np.pi / nn * half, a[i] / (4 / np.pi / nn * half)))
for nn in (2, 4):
    i = np.argmin(abs(f - nn * 25e6 / 1024))
    print("even harmonic %d: %.1f dB below the fundamental" % (nn, dB(a[i1]) - dB(a[i])))
sel = (f > 1.0e6) & (f < 1.25e6)
floor = a[sel][np.argsort(a[sel])[: sel.sum() // 2]]
print("noise floor between lines: %.1f dBV per bin" % dB(np.sqrt(np.mean(floor ** 2))))
i = np.argmin(abs(f_n - 12.48e6))
print("at %.2f MHz: measured/series %.2f dB, aliasing alone %.2f dB" % (f_n[i] / 1e6, dB(ratio[i]), dB(alias[i])))
i = np.argmin(abs(f_n - 2.7e6))
print("at %.2f MHz: measured/series %.2f dB, aliasing alone %.2f dB" % (f_n[i] / 1e6, dB(ratio[i]), dB(alias[i])))

# ---- figure 4: the FPGA's own FFT (fft.sv), on its 781.25 kHz square wave --------------
# data/fft_hw_square.npz: python3 fft.py --once -a 8 --volts -o ..., through the 101.5 cm cable
h = np.load(os.path.join(HERE, "..", "data", "fft_hw_square.npz"))
dbv = h["db_full_scale"] + 20 * np.log10(128 / CODES_PER_VOLT)
fk = h["freq_hz"]
nn = np.arange(1, 16, 2)
pred = 4 / np.pi / nn * half * (np.pi * nn / 32) / np.sin(np.pi * nn / 32)   # series x aliasing (32 samples a period)
fig, ax = plt.subplots(figsize=(8, 4.0))
ax.plot(fk / 1e6, dbv, color=C1, lw=0.8)
dots(ax, fk / 1e6, dbv, C1, size=3, label="the FPGA's spectrum: 1024-point FFT, 256 frames averaged")
ax.plot(nn * 25e6 / 32 / 1e6, dB(pred), "o", mfc="none", mec=C2, mew=1.2, markersize=8,
        label="Fourier series of a sampled square wave: (4/π)(1/n)(πn/32)/sin(πn/32)")
ax.set_xlim(0, 12.5)
ax.set_ylim(-90, 20)
ax.set_xlabel("frequency (MHz)")
ax.set_ylabel("amplitude (dB re 1 V)")
ax.set_title("fft.sv on the FPGA: its own 781 kHz square wave, through the cable", pad=28)
bin_axis(ax, 1e6, 25e6 / 1024, [0, 64, 128, 256, 511])
ax.legend(loc="upper right", fontsize=8.5)
save(fig, os.path.join(IMG, "fft_hw.png"))
for n_, p_ in zip(nn, pred):
    print("n=%2d  FPGA %6.2f dBV  predicted (series x aliasing) %6.2f dBV" % (n_, dbv[32 * n_], dB(p_)))
