"""Chapter 7 figure: the 8-bit ADC resolving a sine of a code and a half, with and
without noise to average.

dsp_oversample_adc.png   the record (a staircase of three ADC codes); the same after
                         the low-pass and decimation by 64, stepped without noise and
                         smooth with it; ENOB against OSR for the three ways; and a DC
                         level against the DAC code, whole codes without noise and
                         thousandths with it.

    python3 fig_oversample_adc.py --sim | PORT | --m2k PORT | --replot
"""
import numpy as np
import link
from plotstyle import plt, save, dots, C1, C2, C3, MUTED, INK2
import sigma_delta as sd
import oversample_adc as oa

NAME = "oversample_adc"
AMP, CYCLES, DITHER = 1.5, 3, 2.0
COLORS = dict(none=MUTED, dither=C1, shaped=C2)
LABELS = dict(none="no noise (the ADC's own 0.1 code)", dither="white noise, %.0f codes rms" % DITHER,
              shaped="the same noise, high-passed")
a = link.args(__doc__)
if not a.replot:
    L = oa.Link(a)
    saved = dict(source=L.source, osrs=sd.OSRS, amp=AMP, cycles=CYCLES, dither=DITHER, periodic=L.periodic)
    for way in oa.WAYS:
        rec = oa.measure(L, AMP, CYCLES, way, DITHER, a.seed)
        res = oa.analyze(rec, CYCLES, periodic=L.periodic)
        saved[way + "_rec"] = rec
        saved[way + "_enob"] = [r["enob"] for r in res]
        saved[way + "_amp"] = [r["amp"] for r in res]
        saved[way + "_offset"] = [r["offset"] for r in res]
    saved["dc"] = np.array(oa.dc_sweep(L, range(124, 133), DITHER, a.seed))
    np.savez(link.data_path(NAME), **saved)
d = np.load(link.data_path(NAME))
src = str(d["source"])
osrs = d["osrs"]
periodic = bool(d["periodic"]) if "periodic" in d else True
f0 = CYCLES * sd.F_LOOP
print(src)
for way in oa.WAYS:
    print("%-7s ENOB at OSR %s: %s;  amplitude %.3f, offset %.3f at OSR 256"
          % (way, list(osrs), ", ".join("%.2f" % e for e in d[way + "_enob"]), d[way + "_amp"][-1], d[way + "_offset"][-1]))

fig, ax = plt.subplots(2, 2, figsize=(10.5, 8))
# ---- the record ----------------------------------------------------------------------
a0 = ax[0, 0]
t_us = np.arange(sd.N) / sd.FS * 1e6
sel = t_us < 1.2 / f0 * 1e6
ideal = sd.ADC_GAIN * 128 + 27.5 + sd.ADC_GAIN * AMP * np.sin(2 * np.pi * f0 * t_us / 1e6)
a0.plot(t_us[sel], d["dither_rec"][:sd.N][sel], ".", color=C1, markersize=1.5, alpha=0.25, label=LABELS["dither"])
a0.step(t_us[sel], d["none_rec"][:sd.N][sel], where="mid", color=INK2, lw=0.8, label=LABELS["none"])
if periodic:                                               # on another clock the phase is not known
    a0.plot(t_us[sel], ideal[sel], color=C2, lw=1.0, ls="--", label="the sine sent, in ADC codes")
a0.set_ylim(121, 134); a0.set_xlabel("time (µs)"); a0.set_ylabel("ADC code")
a0.set_title("The record: a code and a half of sine is a staircase")
a0.legend(loc="upper right", fontsize=7.5, frameon=True, framealpha=0.85)

# ---- after the decimation ------------------------------------------------------------
a1 = ax[0, 1]
osr_show = 64
for way in ("none", "dither", "shaped"):
    r = sd.decimate(d[way + "_rec"], osr_show, periodic=periodic)
    t = np.arange(len(r)) * osr_show / sd.FS * 1e6
    sel = t < 1.2 / f0 * 1e6
    a1.plot(t[sel], r[sel], color=COLORS[way], lw=1.2, label=LABELS[way])
    dots(a1, t[sel], r[sel], COLORS[way], size=3)
if periodic:
    a1.plot(t_us[t_us < 1.2 / f0 * 1e6], ideal[t_us < 1.2 / f0 * 1e6], color=INK2, lw=0.8, ls="--", label="the sine sent")
a1.set_xlabel("time (µs)"); a1.set_ylabel("ADC codes")
a1.set_title("Low-passed to %.0f kHz (OSR %d)" % (sd.FS / 2 / osr_show / 1e3, osr_show))
a1.legend(loc="upper right", fontsize=7.5)

# ---- ENOB against OSR ----------------------------------------------------------------
a2 = ax[1, 0]
oo = 2.0**np.arange(0, 8.01, 0.25)
white = np.sqrt(1 / 12 + sd.ADC_NOISE**2 + (sd.ADC_GAIN * DITHER)**2)
a2.plot(np.log2(oo), [sd.enob(white / np.sqrt(o))[1] for o in oo], color=C1, lw=1.0, alpha=0.6,
        label="white error of %.2f codes: + 0.5 bit / octave" % white)
a2.plot(np.log2(oo), [sd.enob(np.sqrt(1 / 12 + sd.ADC_NOISE**2) / np.sqrt(o))[1] for o in oo], color=MUTED,
        lw=1.0, alpha=0.6, ls="--", label="if the ADC's own error were white")
for way in oa.WAYS:
    a2.plot(np.log2(osrs), d[way + "_enob"], "o", color=COLORS[way], markersize=6, markeredgecolor="white",
            label=LABELS[way])
a2.set_xticks(range(0, 9, 2)); a2.set_xticklabels([str(2**k) for k in range(0, 9, 2)])
a2.set_xlim(0, 8.3); a2.set_ylim(5, 13)
a2.set_xlabel("oversampling ratio"); a2.set_ylabel("effective bits (against the ADC's full scale)")
a2.set_title("Averaging buys bits only from noise")
a2.legend(loc="upper left", fontsize=7.5)

# ---- the DC level ----------------------------------------------------------------------
a3 = ax[1, 1]
dc = d["dc"]
codes, plain, noisy, se = dc[:, 0], dc[:, 1], dc[:, 2], dc[:, 3]
a3.plot(codes, sd.ADC_GAIN * codes + 27.5, color=INK2, lw=0.8, ls="--", label="0.776 x code + 27.5 (1.07)")
a3.step(codes, plain, where="mid", color=MUTED, lw=1.2, label="mean of 16384 samples, no noise")
dots(a3, codes, plain, MUTED)
a3.errorbar(codes, noisy, yerr=3 * se, fmt="o", color=C1, markersize=5, capsize=3, lw=1,
            label="with %.0f codes of noise (bars: 3 standard errors)" % DITHER)
a3.set_xlabel("DAC code"); a3.set_ylabel("ADC reading (codes)")
a3.set_title("A DC level: whole codes, or thousandths with noise")
a3.legend(loc="upper left", fontsize=7.5)
fig.suptitle(src, x=0.99, ha="right", fontsize=8, color=MUTED)
save(fig, link.img_path(NAME))
