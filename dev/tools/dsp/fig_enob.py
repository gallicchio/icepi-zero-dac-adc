"""Chapter 7 figure, computed: what oversampling and noise shaping promise.

dsp_enob.png   left: effective bits against the oversampling ratio for a 1-bit and an
               8-bit converter, with white error (+ 0.5 bit per octave) and with
               first-, second- and third-order noise shaping (+ 1.5, 2.5, 3.5), the
               ceiling this module's 8-bit ADC puts on any measurement, and the audio
               16- and 24-bit lines;  right: the noise transfer functions |1 - z^-1|^n.

    python3 fig_enob.py            # no board needed
"""
import numpy as np
import link
from plotstyle import plt, save, C1, C2, C3, MUTED, INK2
import sigma_delta as sd

link.args(__doc__, computed=True)
osr = 2.0**np.arange(0, 10.01, 0.25)                    # 1 .. 1024
orders = [(0, "white error, dithered: + 0.5 bit / octave", C1, "-"),
          (1, "1st order: + 1.5 bit / octave", C2, "-"),
          (2, "2nd order: + 2.5 bit / octave", C3, "-"),
          (3, "3rd order: + 3.5 bit / octave", INK2, ":")]


def curve(bits, order, osr):
    base = np.log2(2**bits - 1)
    if order == 0:
        return base + 0.5 * np.log2(osr) - 0.5 * np.log2(3)
    k = np.pi**(2 * order) / (2 * order + 1)
    return base + (order + 0.5) * np.log2(osr) - 0.5 * np.log2(k)


fig, ax = plt.subplots(1, 2, figsize=(10, 4.6), gridspec_kw=dict(width_ratios=[1.25, 1]))
a = ax[0]
for order, label, color, ls in orders:
    a.plot(np.log2(osr), curve(1, order, osr), color=color, ls=ls, lw=1.8, label=label)
    a.plot(np.log2(osr), curve(8, order, osr), color=color, ls=ls, lw=1.0, alpha=0.45)
ceiling = [sd.floor_enob(sd.ADC_FLOOR, o) for o in osr]
a.fill_between(np.log2(osr), ceiling, 30, color=MUTED, alpha=0.10, lw=0)
a.plot(np.log2(osr), ceiling, color=MUTED, lw=1.2, ls="--", label="this 8-bit ADC's ceiling (0.39 codes of white noise)")
for b, txt in ((16, "CD audio: 16 bits"), (24, "studio: 24 bits")):
    a.axhline(b, color=INK2, lw=0.7, ls="-.")
    a.annotate(txt, (9.9, b + 0.3), fontsize=8, color=INK2, ha="right")
a.annotate("thick: a 1-bit converter; thin: 8 bits", (9.9, -1.5), fontsize=8, color=INK2, ha="right")
a.set_xlim(0, 10); a.set_ylim(-2, 28)
a.set_xticks(range(0, 11, 2)); a.set_xticklabels([str(2**k) for k in range(0, 11, 2)])
a.set_xlabel("oversampling ratio OSR = fs / (2 x bandwidth)"); a.set_ylabel("effective bits (ENOB)")
a.set_title("Bits bought with speed")
a.annotate("ENOB = log2(2^N - 1) + (n + 1/2) log2 OSR - c_n", (9.9, 1.0), fontsize=8, color=INK2, ha="right")
a.legend(loc="upper left", fontsize=7.5)

a = ax[1]
f = np.linspace(1e-4, 0.5, 4000)
for order, label, color, ls in orders:
    H = (2 * np.sin(np.pi * f))**(2 * order)
    a.plot(f, 10 * np.log10(H + 1e-30) if order else np.zeros_like(f), color=color, ls=ls, lw=1.6,
           label="n = %d" % order)
a.axvline(1 / 128, color=MUTED, lw=0.9, ls="--")
a.annotate("band edge\nat OSR 64", (1 / 128 * 1.15, -95), fontsize=8, color=INK2)
a.set_xscale("log"); a.set_xlim(1e-3, 0.5); a.set_ylim(-100, 15)
a.set_xlabel("frequency / fs"); a.set_ylabel("noise power gain |1 - z^-1|^2n (dB)")
a.set_title("Where feedback puts the noise")
a.annotate("|NTF|² = (2 sin πf/fs)^2n", (1.2e-3, 8), fontsize=8, color=INK2)
a.legend(loc="lower right", fontsize=8, title="order n")
fig.suptitle("computed", x=0.99, ha="right", fontsize=8, color=MUTED)
save(fig, link.img_path("enob"))
print("1-bit at OSR 64: order 1 %.1f bits, order 2 %.1f, order 3 %.1f; at OSR 256: %.1f, %.1f, %.1f"
      % tuple(curve(1, o, r) for r in (64, 256) for o in (1, 2, 3)))
print("ADC ceiling at OSR 1, 64, 256: %.1f, %.1f, %.1f bits" % tuple(sd.floor_enob(sd.ADC_FLOOR, o) for o in (1, 64, 256)))
