"""Chapter 7 figure: a 1-bit stream from the 8-bit DAC, and the bits a low-pass gets back.

dsp_sigma_delta.png   the 1-bit second-order stream in time against the sine it
                      encodes; the spectrum of what the instrument records for each
                      method (the noise rising with frequency where it is shaped);
                      the recovered sine after the low-pass at OSR 64; and ENOB
                      against OSR, measured, on the textbook lines.

    python3 fig_sigma_delta.py --sim | PORT | --m2k PORT | --replot
"""
import numpy as np
import link
from plotstyle import plt, save, dots, C1, C2, C3, MUTED, INK2
import sigma_delta as sd

NAME = "sigma_delta"
BITS, AMP, CYCLES = 1, 64, 3
COLORS = dict(plain=MUTED, dither=C3, order1=C2, order2=C1)
LABELS = dict(plain="plain (a comparator)", dither="TPDF dither", order1="1st-order delta-sigma",
              order2="2nd-order delta-sigma")
a = link.args(__doc__)
if not a.replot:
    L = sd.Link(a)
    out = sd.run(L, BITS, sd.METHODS, CYCLES, AMP, sd.OSRS, a.seed)
    floor = L.floor()
    saved = dict(source=L.source, floor=floor, fs=out["plain"]["fs"], periodic=out["plain"]["periodic"],
                 gain=L.gain, osrs=sd.OSRS, amp=AMP, cycles=CYCLES, bits=BITS)
    for m in sd.METHODS:
        saved[m + "_x"] = out[m]["x"]
        saved[m + "_y"] = out[m]["y"]
        saved[m + "_enob"] = [r["enob"] for r in out[m]["res"]]
        saved[m + "_ratio"] = out[m]["res"][0]["ratio"]
    np.savez(link.data_path(NAME), **saved)
d = np.load(link.data_path(NAME))
src, fs, periodic, gain = str(d["source"]), float(d["fs"]), bool(d["periodic"]), float(d["gain"])
osrs = d["osrs"]
f0 = CYCLES * sd.F_LOOP
print(src)
for m in sd.METHODS:
    print("%-7s ENOB at OSR %s: %s" % (m, list(osrs), ", ".join("%.2f" % e for e in d[m + "_enob"])))

fig, ax = plt.subplots(2, 2, figsize=(10.5, 8))
# ---- the stream in time ---------------------------------------------------------------
a0 = ax[0, 0]
y = d["order2_y"]
u = sd.sine(CYCLES, AMP)
seg = slice(0, 200)                                        # 8 µs from the zero crossing going up
t_us = np.arange(len(y)) / sd.FS * 1e6
a0.step(t_us[seg], (y[seg] + 127.5), where="post", color=C1, lw=0.7, label="the 1-bit stream: DAC code 0 or 255")
a0.plot(t_us[seg], u[seg] + 127.5, color=C2, lw=2.0, label="the sine it encodes (%d codes)" % AMP)
yy = np.concatenate([y[-32:], y, y[:32]]) + 127.5         # the loop wraps: no edge at t = 0
dens = np.convolve(yy, np.ones(32) / 32, mode="same")[32:-32]
a0.plot(t_us[seg], dens[seg], color=C3, lw=1.2, ls="--", label="running mean of 32")
a0.set_ylim(-10, 300); a0.set_xlabel("time (µs)"); a0.set_ylabel("DAC code")
a0.set_title("8 µs of the 2nd-order 1-bit stream")
a0.legend(loc="upper left", fontsize=7.5, frameon=True, framealpha=0.9)

# ---- the spectra --------------------------------------------------------------------
a1 = ax[0, 1]
for m in ("plain", "dither", "order1", "order2"):
    x = d[m + "_x"] / gain
    if fs > sd.FS:
        x, _ = sd.prepare(x, fs, periodic)
    n = len(x)
    w = np.ones(n) if periodic else np.hanning(n)
    X = np.abs(np.fft.rfft(x * w)) / (w.sum() / 2)
    f = np.fft.rfftfreq(n, 1 / sd.FS)
    a1.plot(f[1:] / 1e6, 20 * np.log10(X[1:] + 1e-6), color=COLORS[m], lw=0.7, alpha=0.9, label=LABELS[m])
for o, lab in ((64, "band edge, OSR 64"), (256, "OSR 256")):
    a1.axvline(sd.FS / (2 * o) / 1e6, color=INK2, lw=0.8, ls="--")
    a1.annotate(lab, (sd.FS / (2 * o) / 1e6 * 1.1, 62), fontsize=7.5, color=INK2, rotation=90, va="top")
a1.set_xscale("log"); a1.set_xlim(2e-3, 12.5); a1.set_ylim(-70, 70)
a1.set_xlabel("frequency (MHz)"); a1.set_ylabel("amplitude (dB re 1 DAC code)")
a1.set_title("What the instrument records")
a1.annotate("the shaped noise climbs 20 and 40 dB a decade", (0.6, -62), fontsize=8, color=INK2, ha="center")
a1.legend(loc="upper left", fontsize=7.5, frameon=True, framealpha=0.85)

# ---- the recovered sine ---------------------------------------------------------------
a2 = ax[1, 0]
osr_show = 64
for m, lw in (("plain", 0.9), ("order1", 1.0), ("order2", 1.6)):
    x = d[m + "_x"] / gain
    if fs > sd.FS:
        x, _ = sd.prepare(x, fs, periodic)
    r = sd.decimate(x, osr_show, sd.FS, periodic)
    t = np.arange(len(r)) * osr_show / sd.FS * 1e6
    sel = t < 2.2 / f0 * 1e6
    a2.plot(t[sel], r[sel], color=COLORS[m], lw=lw, label=LABELS[m] + (": %.1fx too big, bent" % d["plain_ratio"] if m == "plain" else ""))
    if m != "plain":
        dots(a2, t[sel], r[sel], COLORS[m], size=3)
a2.set_xlabel("time (µs)"); a2.set_ylabel("DAC codes (about mid-scale)")
a2.set_title("After the low-pass to %.0f kHz (OSR %d)" % (sd.FS / 2 / osr_show / 1e3, osr_show))
a2.legend(loc="upper right", fontsize=7.5)

# ---- ENOB against OSR ----------------------------------------------------------------
a3 = ax[1, 1]
oo = 2.0**np.arange(0, 8.01, 0.25)
for m in sd.METHODS:
    a3.plot(np.log2(oo), [sd.theory(BITS, m, o) for o in oo], color=COLORS[m], lw=1.0, alpha=0.6,
            ls="--" if m == "plain" else "-")
    a3.plot(np.log2(osrs), d[m + "_enob"], "o", color=COLORS[m], markersize=6, markeredgecolor="white",
            label=LABELS[m])
ceiling = [sd.floor_enob(float(d["floor"]), o, fs) for o in oo]
a3.plot(np.log2(oo), ceiling, color=INK2, lw=1.2, ls=":", label="the instrument's own ceiling")
a3.set_xticks(range(0, 9, 2)); a3.set_xticklabels([str(2**k) for k in range(0, 9, 2)])
a3.set_xlim(0, 8.3); a3.set_ylim(-2, 19)
a3.set_xlabel("oversampling ratio"); a3.set_ylabel("effective bits")
a3.set_title("Bits recovered from 1 bit")
a3.annotate("dots: measured; lines: the textbook", (8.2, -1.5), fontsize=8, color=INK2, ha="right")
a3.legend(loc="upper left", fontsize=7.5)
fig.suptitle(src, x=0.99, ha="right", fontsize=8, color=MUTED)
save(fig, link.img_path(NAME))
