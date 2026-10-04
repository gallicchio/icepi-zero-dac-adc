"""Chapter 6 figures: pulse compression (chirp.py), and Zadoff-Chu sequences.

comms_compression.png  the five waveforms and their spectra; each one's matched-filter
                       output over the whole loop; the peaks side by side (and the
                       chirp's with a Hamming window); the ambiguity function along the
                       Doppler axis (the peak's height and delay against a frequency
                       offset applied to the record); and all five under noise 15 dB
                       above the signal's peak power
comms_zc.png           Zadoff-Chu roots 1, 2 and 7: the sequences, their frequency
                       against chip number, the spectrum, measured autocorrelations,
                       cross-correlations between roots and between two GPS Gold
                       codes, and the whole families compared

    python3 fig_compression.py --sim | PORT | PORT_A PORT_B | --replot
"""
import numpy as np
import link
from plotstyle import plt, save, C1, C2, C3, MUTED, INK2, INK, SURFACE
import chirp
import cdma

NAME = "compression"
SNR = -15.0
DFS = np.linspace(-2.5, 2.5, 81) * chirp.F_LOOP
KINDS = chirp.KINDS
COL = {"pulse": MUTED, "chirp": C1, "zc": C2, "m": C3, "gold": INK2}
LABEL = {"pulse": "pulse, 1/B long", "chirp": "chirp, BT = 1023", "zc": "Zadoff–Chu, N = 1021",
         "m": "m-sequence G1, 1023", "gold": "Gold code PRN 1, 1023"}
a = link.args(__doc__)
if not a.replot:
    Lk = link.Link(a)
    out = {"source": Lk.source}
    for kind in KINDS:
        x = chirp.run(kind, Lk.play, Lk.record)
        h, d = chirp.doppler_cut(x["z"], x["ref"], DFS)
        for k in ("rec", "r", "delay", "bw", "width", "sidelobe"):
            out["%s_%s" % (kind, k)] = x[k]
        out[kind + "_dop_h"], out[kind + "_dop_d"] = h, d
        if kind == "chirp":
            out["chirp_r_hamming"] = chirp.compress(x["z"], x["ref"], np.hamming(chirp.L))
        xn = chirp.run(kind, Lk.play, Lk.record, snr=SNR, rng=7, power=0.5)
        out[kind + "_r_noisy"] = xn["r"]
        print("%-6s width %.2f/B, sidelobe %.1f dB, delay %.3f samples; noisy delay %.3f"
              % (kind, x["width"] / chirp.FS_ADC * x["bw"], x["sidelobe"], x["delay"], xn["delay"]), flush=True)
    # Zadoff-Chu roots 2 and 7, and a second Gold code, for the cross-correlations
    zs = {1: chirp.mixdown(out["zc_rec"])}
    for u in (2, 7):
        x = chirp.run("zc", Lk.play, Lk.record, u=u)
        out["zc%d_rec" % u] = x["rec"]; out["zc%d_r" % u] = x["r"]
        zs[u] = x["z"]
    for u1, u2 in ((1, 2), (1, 7), (2, 7)):
        out["zc%dx%d" % (u1, u2)] = chirp.compress(zs[u1], chirp.reference(chirp.envelope("zc", u=u2)))
    out["gold1x2"] = chirp.compress(chirp.mixdown(out["gold_rec"]),
                                    chirp.reference(chirp.held(1.0 - 2 * cdma.ca_code(2))))
    np.savez_compressed(link.data_path(NAME), **out)
d = np.load(link.data_path(NAME))
src = str(d["source"])
L, FS = chirp.L, chirp.FS_ADC
lag_us = ((np.arange(L) + L / 2) % L - L / 2) / FS * 1e6
order = np.argsort(lag_us)


def db(r, peak=None):
    """dB relative to the (clean) correlation peak: compress() gives the amplitude of
    the reference found in the record, 77 ADC codes for a unit envelope at 100 DAC codes."""
    return 20 * np.log10(np.abs(r) / (np.abs(r).max() if peak is None else peak) + 1e-9)


# ---- comms_compression.png -----------------------------------------------------------
fig = plt.figure(figsize=(10, 12.6))
gs = fig.add_gridspec(4, 6, height_ratios=[1.1, 0.9, 1.1, 1.0], hspace=0.55, wspace=0.9)
# (a) the waveforms
ax = fig.add_subplot(gs[0, :3])
chip_us = 1 / chirp.B0 * 1e6
n0 = int(round(0.25 * chirp.N))                         # a window a quarter of the way in
win = slice(n0, n0 + int(round(10 * chip_us * 1e-6 * chirp.FS_DAC)))
t_us = (np.arange(chirp.N) - n0) / chirp.FS_DAC * 1e6
for i, kind in enumerate(KINDS):
    env = chirp.envelope(kind)
    off = 2.5 * (len(KINDS) - 1 - i)
    if kind == "pulse":
        w = slice(0, win.stop - win.start)
        ax.plot(t_us[win], env.real[w] + off, color=COL[kind], lw=1)
        ax.text(-0.15, off + 0.3, "pulse (from t = 0)", ha="right", fontsize=8, color=INK2)
    else:
        ax.plot(t_us[win], env.real[win] + off, color=COL[kind], lw=1)
        ax.text(-0.15, off + 0.3, LABEL[kind].split(",")[0], ha="right", fontsize=8, color=INK2)
    ax.axhline(off, color=MUTED, lw=0.4)
ax.set_yticks([]); ax.set_xlim(-1.4, t_us[win][-1])
ax.set_xlabel("time from the window's start (µs)")
ax.set_title("Ten chips of each (I), a quarter of the way in")
# (b) spectra
ax = fig.add_subplot(gs[0, 3:])
f = np.fft.rfftfreq(L, 1 / FS) / 1e6
for i, kind in enumerate(KINDS):
    rec = d[kind + "_rec"].astype(float)[:L]
    X = np.abs(np.fft.rfft(rec - rec.mean()))
    X = np.sqrt(np.convolve(X**2, np.ones(8) / 8, "same"))
    off = -14 * i
    ax.plot(f, 20 * np.log10(X / X.max() + 1e-6) + off, color=COL[kind], lw=0.6)
    ax.text(6.25, off + 1.5, LABEL[kind].split(",")[0], ha="center", fontsize=8, color=INK2,
            bbox=dict(facecolor=SURFACE, edgecolor="none", pad=1))
ax.set_xlim(0, 12.5); ax.set_ylim(-95, 8); ax.set_yticks([])
ax.set_xlabel("frequency (MHz)")
ax.set_title("Recorded spectra (dB, 14 dB apart)")
# row 2: each waveform's whole loop, five equal panels
sub = gs[1, :].subgridspec(1, 5, wspace=0.25)
for i, kind in enumerate(KINDS):
    ax = fig.add_subplot(sub[0, i])
    r = db(d[kind + "_r"])
    ax.plot(lag_us[order], r[order], color=COL[kind], lw=0.4)
    ax.set_ylim(-70, 5); ax.set_xlim(-164, 164)
    ax.set_title(LABEL[kind].split(",")[0], fontsize=9)
    ax.text(160, -8, "sidelobes\n%.0f dB" % d[kind + "_sidelobe"], ha="right", va="top", fontsize=8, color=INK2,
            bbox=dict(facecolor=SURFACE, edgecolor="none", pad=1))
    if i:
        ax.set_yticklabels([])
    else:
        ax.set_ylabel("matched filter (dB)")
    ax.set_xlabel("delay (µs)", fontsize=8)
    ax.tick_params(labelsize=8)
# (c) the peaks
ax = fig.add_subplot(gs[2, :2])
chip = FS / chirp.B0
for kind in KINDS:
    r = db(d[kind + "_r"])
    ax.plot((lag_us[order] - d[kind + "_delay"] / FS * 1e6) * chirp.B0 / 1e6, r[order], color=COL[kind], lw=1,
            label=LABEL[kind].split(",")[0])
rh = db(d["chirp_r_hamming"])
ax.plot((lag_us[order] - d["chirp_delay"] / FS * 1e6) * chirp.B0 / 1e6, rh[order] - rh.max(), color=C1, lw=1,
        ls="--", label="chirp, Hamming window")
ax.set_xlim(-3, 3); ax.set_ylim(-68, 3)
ax.set_xlabel("delay from the peak (chips, 1/B)"); ax.set_ylabel("matched filter (dB)")
ax.set_title("The peaks: a triangle, or a sinc")
ax.legend(loc="lower center", fontsize=6.5, ncol=2)
# (d) Doppler: height
ax = fig.add_subplot(gs[2, 2:4])
for kind in KINDS:
    ax.plot(DFS / 1e3, d[kind + "_dop_h"], color=COL[kind], lw=1.2, label=LABEL[kind].split(",")[0])
ax.axvline(chirp.F_LOOP / 1e3, color=MUTED, lw=0.6, ls=":"); ax.axvline(-chirp.F_LOOP / 1e3, color=MUTED, lw=0.6, ls=":")
ax.text(chirp.F_LOOP / 1e3 + 0.2, 0.55, "1/T", fontsize=8, color=INK2)
ax.set_ylim(0, 1.1); ax.set_xlabel("frequency offset (kHz)"); ax.set_ylabel("peak height")
ax.set_title("Doppler: the codes' peaks die")
ax.legend(loc="lower left", fontsize=7)
# (e) Doppler: delay
ax = fig.add_subplot(gs[2, 4:])
for kind in KINDS:
    h, dd = d[kind + "_dop_h"], d[kind + "_dop_d"]
    ok = h > 0.5
    ax.plot(DFS[ok] / 1e3, (dd[ok] - d[kind + "_delay"]) / chip, color=COL[kind], lw=1.2)
ax.set_xlabel("frequency offset (kHz)"); ax.set_ylabel("the peak moves by (chips)")
ax.set_title("... the chirps' slide by df T / B")
ax.text(0.1, 7.3, "ZC (a down-chirp)", fontsize=8, color=C2); ax.text(0.1, -8.2, "chirp (up)", fontsize=8, color=C1)
ax.text(0.1, 0.6, "pulse, codes", fontsize=8, color=INK2)
ax.set_ylim(-9, 9)
# (f) with noise
ax = fig.add_subplot(gs[3, :])
for i, kind in enumerate(KINDS):
    r = db(d[kind + "_r_noisy"], np.abs(d[kind + "_r"]).max())        # relative to the CLEAN peak
    off = -35 * i
    ax.plot(lag_us[order], r[order] + off, color=COL[kind], lw=0.4)
    ax.axhline(off, color=MUTED, lw=0.4, ls=":")
    ax.text(-24.6, off + 2, LABEL[kind], fontsize=8, color=INK2, va="bottom",
            bbox=dict(facecolor=SURFACE, edgecolor="none", pad=1))
ax.set_xlim(-25, 25); ax.set_yticks([]); ax.set_xlabel("delay (µs)")
ax.set_ylim(-170, 30)
ax.set_ylabel("dB re each clean peak, 35 dB apart")
ax.set_title("Noise 15 dB above the peak power (in a band B wide): 1023 chips add up to a peak, one chip can't")
fig.suptitle(src, x=0.99, ha="right", fontsize=8, color=MUTED)
fig.savefig(link.img_path(NAME), dpi=130)
plt.close(fig)

# ---- comms_zc.png --------------------------------------------------------------------
Nz = chirp.N_ZC
fig, ax = plt.subplots(2, 3, figsize=(10, 7.2))
# (a) the sequences
n = np.arange(70)
for i, u in enumerate((1, 2, 7)):
    x = chirp.zc(Nz, u)[:70]
    off = 2.5 * (2 - i)
    ax[0, 0].step(n, x.real + off, where="mid", color=(C1, C2, C3)[i], lw=1)
    ax[0, 0].text(69, off + 1.2, "u = %d" % u, ha="right", fontsize=9, color=INK2)
    ax[0, 0].axhline(off, color=MUTED, lw=0.4)
ax[0, 0].set_yticks([]); ax[0, 0].set_xlabel("chip n")
ax[0, 0].set_title("Re x[n], the first 70 chips of 1021")
# (b) frequency per chip
nn = np.arange(Nz)
for i, u in enumerate((1, 2, 7)):
    ph = np.angle(chirp.zc(Nz, u))
    fq = (np.diff(ph) / (2 * np.pi) + 0.5) % 1 - 0.5
    ax[0, 1].plot(nn[1:], fq, color=(C1, C2, C3)[i], lw=0.8, label="u = %d" % u)
ax[0, 1].set_xlabel("chip n"); ax[0, 1].set_ylabel("frequency (cycles per chip)")
ax[0, 1].set_title("Frequency: u sweeps per sequence")
ax[0, 1].legend(loc="upper right", fontsize=8)
ax[0, 1].set_ylim(-0.55, 0.55)
# (c) spectrum
rec = d["zc_rec"].astype(float)[:L]
X = np.abs(np.fft.rfft(rec - rec.mean())); X = np.sqrt(np.convolve(X**2, np.ones(8) / 8, "same"))
fz = np.fft.rfftfreq(L, 1 / FS) / 1e6
bz = Nz * chirp.F_LOOP
ax[0, 2].plot(fz, 20 * np.log10(X / X[(fz > 6) & (fz < 6.5)].mean()), color=C2, lw=0.6, label="recorded, root 1")
ff = np.linspace(0.01, 12.5, 500)
ax[0, 2].plot(ff, 20 * np.log10(np.abs(np.sinc((ff - 6.25) * 1e6 / bz)) + 1e-6), color=INK2, lw=1, ls="--",
              label="sinc: a chip held for 1/B")
ax[0, 2].plot([6.25 - bz / 2e6, 6.25 + bz / 2e6], [0, 0], color=INK, lw=2.5, label="the sequence's own DFT: flat")
ax[0, 2].set_xlim(0, 12.5); ax[0, 2].set_ylim(-45, 6)
ax[0, 2].set_xlabel("frequency (MHz)"); ax[0, 2].set_ylabel("dB")
ax[0, 2].set_title("Spectrum: flat × a sinc")
ax[0, 2].legend(loc="lower left", fontsize=7)
# (d) autocorrelations measured
for i, u in enumerate((1, 2, 7)):
    r = db(d["zc_r" if u == 1 else "zc%d_r" % u])
    ax[1, 0].plot(lag_us[order] * bz / 1e6, r[order] - 20 * i, color=(C1, C2, C3)[i], lw=0.4, label="u = %d" % u)
ax[1, 0].set_xlim(-510, 510); ax[1, 0].set_ylim(-110, 5)
ax[1, 0].set_xlabel("delay (chips)"); ax[1, 0].set_ylabel("correlation (dB, 20 dB apart)")
ax[1, 0].set_title("Autocorrelation, recorded")
for line in ax[1, 0].legend(loc="upper right", fontsize=8).get_lines():
    line.set_linewidth(2)
# (e) cross-correlations
for key, c, lab in (("gold1x2", INK2, "Gold PRN 1 against PRN 2"), ("zc1x7", C2, "ZC root 1 against root 7"),
                    ("zc1x2", C1, "ZC root 1 against root 2")):
    r = db(d[key], np.abs(d["gold_r" if key.startswith("gold") else "zc_r"]).max())
    ax[1, 1].plot(lag_us[order] * chirp.B0 / 1e6, r[order], color=c, lw=0.4, label=lab)
ax[1, 1].axhline(-10 * np.log10(Nz), color=INK, lw=0.8, ls="--", label="1/√N = −30.1 dB")
ax[1, 1].set_xlim(-510, 510); ax[1, 1].set_ylim(-70, 5)
ax[1, 1].set_xlabel("delay (chips)"); ax[1, 1].set_ylabel("correlation (dB re the autocorrelation peak)")
ax[1, 1].set_title("Cross-correlation, recorded")
for line in ax[1, 1].legend(loc="upper right", fontsize=7).get_lines():
    line.set_linewidth(2)
# (f) the families, computed
X1 = np.fft.fft(chirp.zc(Nz, 1))
zc_peaks = np.array([np.abs(np.fft.ifft(X1 * np.conj(np.fft.fft(chirp.zc(Nz, u))))).max() / Nz
                     for u in range(2, Nz)])
codes = {p: np.fft.fft(1.0 - 2 * cdma.ca_code(p)) for p in range(1, 33)}
gold_peaks = np.array([np.abs(np.fft.ifft(codes[p] * np.conj(codes[q]))).max() / 1023
                       for p in range(1, 33) for q in range(p + 1, 33)])
ax[1, 2].plot(np.arange(len(zc_peaks)) / len(zc_peaks), 20 * np.log10(np.sort(zc_peaks)), color=C2, lw=2,
              label="ZC, N = 1021: root 1 against the other 1019")
ax[1, 2].plot(np.arange(len(gold_peaks)) / len(gold_peaks), 20 * np.log10(np.sort(gold_peaks)), color=INK2, lw=2,
              label="GPS's 32 Gold codes: all 496 pairs")
ax[1, 2].set_ylim(-35, -15); ax[1, 2].set_xlabel("fraction of pairs")
ax[1, 2].set_ylabel("worst cross-correlation (dB)")
ax[1, 2].set_title("All pairs, computed")
ax[1, 2].legend(loc="upper left", fontsize=7)
fig.suptitle(src, x=0.99, ha="right", fontsize=8, color=MUTED)
save(fig, link.img_path("zc"))
print("ZC family: worst cross-correlation %.2f dB for every pair; Gold: %.2f to %.2f dB"
      % (20 * np.log10(zc_peaks.max()), 20 * np.log10(gold_peaks.min()), 20 * np.log10(gold_peaks.max())))
