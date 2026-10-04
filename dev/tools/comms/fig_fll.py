"""Chapter 6 figure: when the carrier offset is too big for the Costas loop (fll.py).

comms_fll.png
  (a) the Costas loop alone against the transmitter's carrier offset: MER, clean and
      at Eb/N0 = 6 dB, with the default loop and a wider one; and with the x^4
      estimate or the band-edge FLL in front of it
  (b) the x^4 spectrum of a record 100 kHz off: the line at 4 x the offset
  (c) the signal's spectrum with the two band-edge filters on its slopes
  (d) the band-edge detector's S-curve: theory, and measured open loop at many offsets
  (e) the FLL converging on 100 kHz: clean, at 6 dB, and with lesson 17's slower loop
  (f) the constellation after the FLL hands over to psk.py's receiver

    python3 fig_fll.py --sim | PORT | PORT_A PORT_B | --replot
"""
import types
import numpy as np
import link
from plotstyle import plt, save, C1, C2, C3, MUTED, INK2
import psk
import fll

NAME = "fll"
M = 4
CFO_BINS = np.arange(0, 41, 2)                       # 0 .. 122 kHz, the Costas loop alone
SC_BINS = np.arange(-700, 701, 35)                    # -2.1 .. 2.1 MHz, the S-curve
NREC = 3                                              # records per point, different data
a = link.args(__doc__)
if not a.replot:
    L = link.Link(a)
    out = {"source": L.source}
    base = dict(sro=0, diff=False, bnt_timing=0.01, skip=400, tau=100)
    # (a) the Costas loop alone, and with help, against the offset
    keys = ("clean", "6db", "clean_wide", "x4_6db", "fll_6db")
    mer = {k: np.full((len(CFO_BINS), NREC), np.nan) for k in keys}
    errs = {k: np.full((len(CFO_BINS), NREC), np.nan) for k in keys}
    for i, bins in enumerate(CFO_BINS):
        for j in range(NREC):
            start = 101 * j
            args = types.SimpleNamespace(cfo=bins * psk.F_LOOP, bnt_carrier=0.02, **base)
            q, data = psk.make_frame(M, start=start)
            for key, ebn0 in (("clean", None), ("6db", 6.0)):
                L.play(psk.transmit(q, M, bins, ebn0=ebn0, rng=10 * j + i))
                rec = L.record()
                r = psk.receive(rec, M, psk.NSYM, q, bnt_carrier=0.02)
                mer[key][i, j], errs[key][i, j] = r["mer"], r["errs"]
                if key == "6db":
                    df4, _, _ = fll.fourth_power(rec, M)
                    r = psk.receive(fll.shift(rec, -df4), M, psk.NSYM, q)
                    mer["x4_6db"][i, j], errs["x4_6db"][i, j] = r["mer"], r["errs"]
                    loop = fll.fll(fll.mixdown(rec), tau=100)
                    r = psk.receive(fll.shift(rec, -loop["df"]), M, psk.NSYM, q)
                    mer["fll_6db"][i, j], errs["fll_6db"][i, j] = r["mer"], r["errs"]
            L.play(psk.transmit(q, M, bins))
            r = psk.receive(L.record(), M, psk.NSYM, q, bnt_carrier=0.05)
            mer["clean_wide"][i, j], errs["clean_wide"][i, j] = r["mer"], r["errs"]
        print("cfo %6.0f Hz: MER clean %5.1f, 6 dB %5.1f, wide %5.1f, x4 %5.1f, fll %5.1f (medians)"
              % ((bins * psk.F_LOOP,) + tuple(np.median(mer[k][i]) for k in keys)), flush=True)
    for k in keys:
        out["mer_" + k] = mer[k]; out["errs_" + k] = errs[k]
    # (b), (e), (f): one record 100 kHz off, clean and at 6 dB
    q, data = psk.make_frame(M)
    for key, ebn0 in (("clean", None), ("6db", 6.0)):
        L.play(psk.transmit(q, M, 33, ebn0=ebn0, rng=7))
        rec = L.record()
        df4, f4, spec4 = fll.fourth_power(rec, M)
        out["x4_f_" + key], out["x4_spec_" + key], out["x4_df_" + key] = f4, spec4, df4
        z = fll.mixdown(rec)
        for tau in (100, 1000):
            loop = fll.fll(z, tau=tau)
            out["fll_w_%s_%d" % (key, tau)] = loop["w"]; out["fll_df_%s_%d" % (key, tau)] = loop["df"]
        r = psk.receive(rec, M, psk.NSYM, q)
        out["z_alone_" + key] = r["zc"][400:]; out["errs_alone_" + key] = r["errs"]
        r = psk.receive(fll.shift(rec, -out["fll_df_%s_100" % key]), M, psk.NSYM, q)
        out["z_after_" + key] = r["zc"][400:] * np.exp(-2j * np.pi * r["rot"][-1] / M)
        out["errs_after_" + key], out["nbits_after_" + key], out["mer_after_" + key] = r["errs"], r["nbits"], r["mer"]
        out["found_after_" + key] = out["fll_df_%s_100" % key] + fll.found_by_costas(r)
        print("100 kHz, %s: x^4 says %.0f Hz; FLL (tau 100) %.0f, (tau 1000) %.0f; after the FLL %d errors, MER %.1f dB"
              % (key, df4, out["fll_df_%s_100" % key], out["fll_df_%s_1000" % key], r["errs"], r["mer"]), flush=True)
    # (c) the spectrum of a record on frequency, and (d) the S-curve, open loop
    hu, hl = fll.band_edge_filters()
    L.play(psk.transmit(q, M, 0))
    z = fll.mixdown(L.record())
    out["spec_f"] = np.fft.fftshift(np.fft.fftfreq(len(z), 1 / psk.FS_ADC))
    out["spec"] = np.fft.fftshift(np.abs(np.fft.fft(z))**2)
    sc = []
    for bins in SC_BINS:
        L.play(psk.transmit(q, M, int(bins)))
        sc.append(fll.band_edge_error(fll.mixdown(L.record()), hu, hl))
    out["sc_bins"], out["sc_meas"] = SC_BINS, np.array(sc)
    np.savez(link.data_path(NAME), **out)
d = np.load(link.data_path(NAME))
src = str(d["source"])
R, fs = psk.NSYM * psk.F_LOOP, psk.FS_ADC
cfo_khz = CFO_BINS * psk.F_LOOP / 1e3

fig, ax = plt.subplots(2, 3, figsize=(11, 7.4))
# (a)
a_ = ax[0, 0]
for key, c, ls, lab in (("clean", C1, "-", "Costas alone, clean"), ("6db", C2, "-", "Costas alone, Eb/N0 6 dB"),
                        ("clean_wide", C1, "--", "Costas alone, clean, loop 0.05"),
                        ("fll_6db", C3, "-", "FLL first, 6 dB"), ("x4_6db", "#8e5bd4", ":", "x⁴ first, 6 dB")):
    m = d["mer_" + key]
    a_.plot(cfo_khz, np.median(m, axis=1), ls, color=c, lw=1.4, label=lab)
    a_.plot(np.repeat(cfo_khz, m.shape[1]), m.ravel(), ".", color=c, markersize=2.5, alpha=0.5)
a_.set_xlabel("transmitter's carrier offset (kHz)"); a_.set_ylabel("MER after the loops (dB)")
a_.set_ylim(-8, 45); a_.set_xlim(-2, 125)
a_.set_title("(a) Pull-in: the Costas loop alone gives up;\nwith a coarse estimate first, it does not", fontsize=9.5)
a_.legend(loc="upper right", fontsize=7)
# (b)
a_ = ax[0, 1]
f = d["x4_f_clean"] / 1e6
a_.plot(f, d["x4_spec_6db"], color=C2, lw=0.5, alpha=0.8, label="Eb/N0 6 dB")
a_.plot(f, d["x4_spec_clean"], color=C1, lw=0.5, label="clean")
line = 4 * 33 * psk.F_LOOP / 1e6
a_.axvline(line, color=INK2, lw=0.8, ls="--")
a_.annotate("4 × 100.7 kHz", (line + 0.1, 1), fontsize=8, color=INK2)
for s in (-1, 1):
    a_.axvline(line + s * R / 1e6, color=MUTED, lw=0.6, ls=":")
a_.annotate("± symbol rate", (line + R / 1e6 + 0.1, -12), fontsize=7.5, color=MUTED)
a_.set_xlim(-3.2, 3.2); a_.set_ylim(-45, 6)
a_.set_xlabel("frequency (MHz)"); a_.set_ylabel("|FFT(y⁴)| (dB re the line)")
a_.set_title("(b) The x⁴ line: the data cancel, leaving\nthe carrier offset, four times over", fontsize=9.5)
a_.legend(loc="upper left", fontsize=7.5)
# (c)
a_ = ax[0, 2]
hu, hl = fll.band_edge_filters()
nfft = 8192
fh = np.fft.fftshift(np.fft.fftfreq(nfft, 1 / fs)) / 1e6
Hu2 = np.fft.fftshift(np.abs(np.fft.fft(hu, nfft))**2); Hl2 = np.fft.fftshift(np.abs(np.fft.fft(hl, nfft))**2)
S = d["spec"]; S = np.convolve(S, np.ones(24) / 24, "same"); S = S / S.max()
a_.plot(d["spec_f"] / 1e6, S, color=C1, lw=0.8, label="the signal, |Z(f)|²")
a_.fill_between(fh, Hu2 / Hu2.max(), color=C2, alpha=0.35, lw=0, label="upper band-edge filter")
a_.fill_between(fh, Hl2 / Hl2.max(), color=C3, alpha=0.35, lw=0, label="lower band-edge filter")
for s in (-1, 1):
    a_.axvline(s * R / 2e6, color=MUTED, lw=0.6, ls=":")
a_.set_xlim(-1.6, 1.6); a_.set_ylim(0, 1.15)
a_.set_xlabel("frequency from the carrier (MHz)"); a_.set_ylabel("power (relative)")
a_.set_title("(c) Two filters on the signal's slopes,\nat ± half the symbol rate", fontsize=9.5)
a_.legend(loc="upper right", fontsize=7)
# (d)
a_ = ax[1, 0]
off = np.linspace(-2.4e6, 2.4e6, 481)
a_.plot(off / 1e6, fll.s_curve(hu, hl, off), color=MUTED, lw=1.2, label="theory, raised-cosine spectrum")
a_.plot(d["sc_bins"] * psk.F_LOOP / 1e6, d["sc_meas"], "o", color=C1, markersize=3.5, label="measured, one record each")
a_.axhline(0, color=MUTED, lw=0.5); a_.axvline(0, color=MUTED, lw=0.5)
a_.set_xlabel("carrier offset (MHz)"); a_.set_ylabel("(upper − lower) / (upper + lower)")
a_.set_title("(d) The detector's S-curve: the right sign over\nthe whole band, a slope within ± 0.3 MHz", fontsize=9.5)
a_.legend(loc="upper left", fontsize=7.5)
# (e)
a_ = ax[1, 1]
us = np.arange(psk.N) / fs * 1e6
for key, tau, c, ls, lab in (("clean", 100, C1, "-", "clean, τ = 100 symbols"),
                             ("6db", 100, C2, "-", "Eb/N0 6 dB, τ = 100"),
                             ("clean", 1000, C3, "-", "clean, τ = 1000 (lesson 17's /100)")):
    w = d["fll_w_%s_%d" % (key, tau)] * fs / (2 * np.pi) / 1e3
    a_.plot(us, w, ls, color=c, lw=0.9, label=lab)
a_.axhline(33 * psk.F_LOOP / 1e3, color=INK2, lw=0.8, ls="--", label="sent: 100.7 kHz")
a_.set_xlabel("time (µs)"); a_.set_ylabel("the FLL's frequency (kHz)")
a_.set_ylim(-10, 130)
a_.set_title("(e) The FLL converging on 100 kHz, then\njittering by several kHz: the data", fontsize=9.5)
a_.legend(loc="lower right", fontsize=7)
# (f)
a_ = ax[1, 2]
z0 = d["z_alone_6db"]
a_.plot(z0.real, z0.imag, ".", color=MUTED, markersize=1.5, alpha=0.5, label="Costas alone: %d errors" % d["errs_alone_6db"])
z = d["z_after_6db"]
a_.plot(z.real, z.imag, ".", color=C2, markersize=2, label="FLL first: %d errors in %d bits" % (d["errs_after_6db"], d["nbits_after_6db"]))
a_.set_aspect("equal"); a_.set_xlim(-1.8, 1.8); a_.set_ylim(-1.8, 1.8)
a_.set_xticks([-1, 0, 1]); a_.set_yticks([-1, 0, 1])
a_.set_xlabel("I"); a_.set_ylabel("Q")
a_.set_title("(f) 100 kHz off at 6 dB, handed over: the\nCostas loop finds the last %.1f kHz" % (abs(d["found_after_6db"] - d["fll_df_6db_100"]) / 1e3), fontsize=9.5)
a_.legend(loc="upper center", fontsize=7, markerscale=3)
fig.suptitle(src, x=0.99, ha="right", fontsize=8, color=MUTED)
save(fig, link.img_path(NAME))
print("saved", link.img_path(NAME))
