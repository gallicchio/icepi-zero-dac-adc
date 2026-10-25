"""Chapter 6 figures: pulse compression (chirp.py), and Zadoff-Chu sequences.  One figure
per idea, each placed in 6.10 next to the text about it:

comms_chirp.png        the chirp itself, the whole loop: recorded, mixed down with the
                       band's lower edge, and its spectrogram
comms_waves.png        ten chips of each waveform, held (as played) and filtered (as a
                       digital up-converter would make them); their recorded spectra,
                       held and filtered, on one scale (dB re the chirp's in-band level)
comms_compression.png  each one's matched-filter output over the whole loop, and all
                       five under noise 15 dB above the signal's peak power
comms_shape.png        held against filtered: the spectra, the five peaks once they share
                       one spectrum (with the whole-chip lags marked), and the held
                       Zadoff-Chu's ghost
comms_peaks.png        the held peaks side by side, a triangle or a sinc, and the chirp
                       with a Hamming window
comms_doppler.png      a frequency offset: the codes' peaks die, the chirps' slide
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
        for k in ("rec", "r", "delay", "bw", "width", "sidelobe", "on_chips"):
            out["%s_%s" % (kind, k)] = x[k]
        out[kind + "_dop_h"], out[kind + "_dop_d"] = h, d
        if kind == "chirp":
            out["chirp_r_hamming"] = chirp.compress(x["z"], x["ref"], np.hamming(chirp.L))
        xn = chirp.run(kind, Lk.play, Lk.record, snr=SNR, rng=7, power=0.5)
        out[kind + "_r_noisy"] = xn["r"]
        xf = chirp.run(kind, Lk.play, Lk.record, shape="filtered")
        for k in ("rec", "r", "delay", "width", "sidelobe", "on_chips"):
            out["f_%s_%s" % (kind, k)] = xf[k]
        print("%-6s held: width %.2f/B, sidelobe %.1f dB (on chips %.1f), delay %.3f; noisy delay %.3f;"
              " filtered: width %.2f/B, sidelobe %.1f dB (on chips %.1f)"
              % (kind, x["width"] / chirp.FS_ADC * x["bw"], x["sidelobe"], x["on_chips"], x["delay"], xn["delay"],
                 xf["width"] / chirp.FS_ADC * x["bw"], xf["sidelobe"], xf["on_chips"]), flush=True)
    out["f_chirp_at_dac"] = True     # the filtered chirp was filtered at the DAC (older data: not)
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
chip = FS / chirp.B0                                     # ADC samples per chip


def db(r, peak=None):
    """dB relative to the (clean) correlation peak: compress() gives the amplitude of
    the reference found in the record, 77 ADC codes for a unit envelope at 100 DAC codes."""
    return 20 * np.log10(np.abs(r) / (np.abs(r).max() if peak is None else peak) + 1e-9)


def spectrum(rec, own=True):
    """A recording's spectrum (one loop, so no window), smoothed over 8 bins, in dB.
    own=True: re the trace's OWN mean level 5 to 7.5 MHz, so that the shapes of waveforms
    played at different powers compare like with like (every waveform is played at the
    same PEAK swing, and their PAPRs differ by up to 8 dB, so their in-band powers do too:
    level() gives that offset, re the held chirp).  own=False: re REF, the held chirp's."""
    rec = rec.astype(float)[:L]
    X = np.abs(np.fft.rfft(rec - rec.mean()))
    X = np.sqrt(np.convolve(X**2, np.ones(8) / 8, "same"))
    f, s = np.fft.rfftfreq(L, 1 / FS) / 1e6, 20 * np.log10(X + 1e-6)
    return f, s - (inband(f, s) if own else REF)


def inband(f, s):
    """The mean power of a spectrum (dB) between 5 and 7.5 MHz, in dB."""
    return 10 * np.log10(np.mean(10**(s[(f > 5) & (f < 7.5)] / 10)))


def level(rec):
    """A recording's in-band level re the held chirp's, in dB: what the same peak swing
    at the DAC leaves of each waveform's power."""
    f, s = spectrum(rec, own=False)
    return inband(f, s)


def brickwall(rec, bw=chirp.B0):
    """A recording through a band-pass bw wide about the carrier, after the ADC."""
    X = np.fft.rfft(rec.astype(float)[:L])
    X[np.abs(np.fft.rfftfreq(L, 1 / FS) - chirp.F_C) > bw / 2] = 0
    return np.fft.irfft(X, L)


# Data recorded before chirp.py filtered the chirp at the DAC (its wrap's skirts) holds the
# held chirp as f_chirp_rec: filter that one after the ADC instead, and say so.
F_CHIRP_AT_DAC = "f_chirp_at_dac" in d
# Filtered, the chirp's peak grows where it wraps; transmit() scales every waveform to the
# same peak, so the DAC would play it this much quieter:
_g = lambda shape: (chirp.transmit(chirp.envelope("chirp", shape=shape)) - 128).std()
CHIRP_LOSS = 20 * np.log10(_g("held") / _g("filtered"))
f_chirp_rec = d["f_chirp_rec"] if F_CHIRP_AT_DAC else brickwall(d["chirp_rec"]) * 10**(-CHIRP_LOSS / 20)
REF = 0.0
REF = level(d["chirp_rec"])


def fine(r, up=16):
    """The correlation's magnitude, upsampled (its spectrum zero-padded), and its lags in chips
    from the peak."""
    R = np.fft.fftshift(np.fft.fft(r))
    f = np.abs(np.fft.ifft(np.fft.ifftshift(np.concatenate(
        [np.zeros((up - 1) * L // 2), R, np.zeros((up - 1) * L // 2)])))) * up
    k = int(np.argmax(f))
    f = np.roll(f, len(f) // 2 - k)
    return (np.arange(len(f)) - len(f) // 2) / up / chip, 20 * np.log10(f / f.max() + 1e-9)


# ---- comms_chirp.png: the chirp, the whole loop -----------------------------------------
rec = d["chirp_rec"].astype(float)[:L]
rec -= rec.mean()
t = np.arange(L) / FS * 1e6
lo = chirp.F_C - chirp.B0 / 2                            # the band's lower edge, 4.69 MHz
z = rec * np.exp(-2j * np.pi * lo * np.arange(L) / FS)
ff = np.fft.fftfreq(L, 1 / FS)
Z = np.fft.fft(z)
Z[(ff < -0.2e6) | (ff > chirp.B0 + 0.2e6)] = 0           # keep 0 .. B: the chirp, not its image
z = np.fft.ifft(Z)
fig, ax = plt.subplots(2, 1, figsize=(10, 5.4), gridspec_kw=dict(height_ratios=[1, 1.15], hspace=0.5))
ax[0].plot(t, z.real / np.abs(z).max(), color=C1, lw=0.35)
ax[0].set_xlim(0, t[-1]); ax[0].set_yticks([]); ax[0].grid(False)
ax[0].set_xlabel("time (µs)")
ax[0].set_title("The chirp for one whole loop, recorded: 0 Hz to 3.12 MHz above the band's lower edge")
nper = 128
ax[1].specgram(rec, NFFT=nper, Fs=FS / 1e6, noverlap=nper - 16, cmap="magma", vmin=-60)
ax[1].grid(False)
ax[1].set_xlim(0, t[-1]); ax[1].set_ylim(2.5, 10)
ax[1].set_ylabel("frequency (MHz)"); ax[1].set_xlabel("time (µs)")
ax[1].set_title("Its spectrogram: 4.69 MHz rising to 7.81 MHz in 327.68 µs")
ax[1].annotate("a third harmonic (the DAC's or the\nADC's), aliased: 25 MHz − 3f", xy=(250, 25 - 3 * (4.69 + 3.12 * 250 / 327.68)),
               xytext=(150, 3.0), color="white", fontsize=8,
               arrowprops=dict(arrowstyle="->", color="white", lw=0.8))
fig.suptitle(src, x=0.99, ha="right", fontsize=8, color=MUTED)
save(fig, link.img_path("chirp"))

# ---- comms_waves.png: ten chips of each, and their spectra ------------------------------
fig = plt.figure(figsize=(10, 6.4))
gs = fig.add_gridspec(2, 2, wspace=0.22, hspace=0.4, right=0.86)
ax = fig.add_subplot(gs[:, 0])
chip_us = 1 / chirp.B0 * 1e6
n0 = int(round(0.25 * chirp.N))                          # a window a quarter of the way in
win = slice(n0, n0 + int(round(10 * chip_us * 1e-6 * chirp.FS_DAC)))
t_us = (np.arange(chirp.N) - n0) / chirp.FS_DAC * 1e6
for i, kind in enumerate(KINDS):
    off = 2.6 * (len(KINDS) - 1 - i)
    for shape, ls, lw in (("held", "-", 1.0), ("filtered", "--", 0.8)):
        env = chirp.envelope(kind, shape=shape)
        env = env / np.abs(env).max()
        w = slice(0, win.stop - win.start) if kind == "pulse" else win
        ax.plot(t_us[win], env.real[w] + off, color=COL[kind], lw=lw, ls=ls)
    ax.text(-0.15, off + 0.3, ("pulse (from t = 0)" if kind == "pulse" else LABEL[kind].split(",")[0]),
            ha="right", fontsize=8, color=INK2)
    ax.axhline(off, color=MUTED, lw=0.4)
ax.set_yticks([]); ax.set_xlim(-1.5, t_us[win][-1])
ax.set_xlabel("time from the window's start (µs)")
ax.set_title("Ten chips of each (I): held —, filtered - -")
lo, hi = (chirp.F_C - chirp.B0 / 2) / 1e6, (chirp.F_C + chirp.B0 / 2) / 1e6
# Each trace re its OWN in-band level, so that the shapes compare (the same peak swing at the
# DAC leaves the high-PAPR waveforms up to 8 dB less power: that offset is printed instead).
LEVELS = {}
for row, (pre, name) in enumerate((("", "Held, as played: chips at B; the chirp is smooth"),
                                   ("f_", "Filtered to B at the DAC, all five"))):
    ax = fig.add_subplot(gs[row, 1])
    ax.axvspan(lo, hi, color=MUTED, alpha=0.12, lw=0)
    for kind in KINDS[::-1]:
        rec = f_chirp_rec if pre + kind == "f_chirp" else d[pre + kind + "_rec"]
        f, s = spectrum(rec)
        LEVELS[pre + kind] = level(rec)
        ax.plot(f, s, color=COL[kind], lw=0.6, label=LABEL[kind].split(",")[0])
    ax.set_xlim(0, 12.5); ax.set_ylim(-62, 8)
    ax.set_ylabel("dB re each one's in-band level")
    ax.text(6.25, 4, "B", ha="center", fontsize=8, color=INK2)
    ax.text(12.3, -58, "at the same peak swing, re the held chirp:\n" + ", ".join(
        "%s %+.1f" % (LABEL[k].split(",")[0].replace("m-sequence G1", "m-seq.").replace("Gold code PRN 1", "Gold"),
                      LEVELS[pre + k]) for k in KINDS) + " dB",
        ha="right", va="bottom", fontsize=6.5, color=INK2, bbox=dict(facecolor=SURFACE, edgecolor="none", pad=1))
    if row == 0:
        ax.set_title("Recorded spectra, each re its own in-band level\n" + name, fontsize=9)
        h, lab = ax.get_legend_handles_labels()
        for line in ax.legend(h[::-1], lab[::-1], loc="upper right", fontsize=7, ncol=1,
                              framealpha=0.95, bbox_to_anchor=(1.42, 1.02)).get_lines():
            line.set_linewidth(2)
    else:
        ax.set_title(name, fontsize=9)
        ax.set_xlabel("frequency (MHz)")
        if not F_CHIRP_AT_DAC:
            ax.text(8.1, -40, "chirp: the held recording,\nfiltered after the ADC and\n%.1f dB down, as the DAC\nwould play it (filtered at\nthe DAC, board to board:\n4.35 dB down)"
                    % CHIRP_LOSS, fontsize=7, color=C1, va="bottom")
fig.suptitle(src, x=0.99, ha="right", fontsize=8, color=MUTED)
save(fig, link.img_path("waves"))
print("in-band levels at the same peak swing, re the held chirp (dB):",
      ", ".join("%s %+.2f" % (k, v) for k, v in LEVELS.items()))
print("filtering's cost at the same peak swing (dB):",
      ", ".join("%s %+.2f" % (k, LEVELS["f_" + k] - LEVELS[k]) for k in KINDS))

# ---- comms_compression.png: the whole loop, and under noise -----------------------------
fig = plt.figure(figsize=(10, 6.6))
gs = fig.add_gridspec(2, 1, height_ratios=[0.8, 1.2], hspace=0.45)
sub = gs[0].subgridspec(1, 5, wspace=0.25)
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
ax = fig.add_subplot(gs[1])
for i, kind in enumerate(KINDS):
    r = db(d[kind + "_r_noisy"])          # each to its own highest point: transmit() scaled the noisy
                                          # waveform, noise and all, to the DAC's range
    off = -35 * i
    ax.plot(lag_us[order], r[order] + off, color=COL[kind], lw=0.4)
    ax.axhline(off, color=MUTED, lw=0.4, ls=":")
    ax.text(-24.6, off + 1, LABEL[kind], fontsize=8, color=INK2, va="bottom",
            bbox=dict(facecolor=SURFACE, edgecolor="none", pad=1))
ax.set_xlim(-25, 25); ax.set_yticks([]); ax.set_xlabel("delay (µs)")
ax.set_ylim(-185, 12)
ax.set_ylabel("dB re each trace's highest point, 35 dB apart")
ax.set_title("Noise 15 dB above the peak power (in a band B wide): 1023 chips add up to a peak, one chip can't")
fig.suptitle("held chips; " + src, x=0.99, ha="right", fontsize=8, color=MUTED)
fig.savefig(link.img_path(NAME), dpi=130)
plt.close(fig)

# ---- comms_shape.png: held against filtered -------------------------------------------
fig = plt.figure(figsize=(10, 7.6))
gs = fig.add_gridspec(2, 2, height_ratios=[1, 1], hspace=0.45, wspace=0.25)
sub = gs[0, 0].subgridspec(2, 1, hspace=0.12)
for i, kind in enumerate(("zc", "m")):
    ax = fig.add_subplot(sub[i])
    for pre, lw, c, lab in (("", 0.5, MUTED, "held"), ("f_", 0.8, COL[kind], "filtered")):
        f, s = spectrum(d[pre + kind + "_rec"])
        ax.plot(f, s, color=c, lw=lw, label="%s (%+.1f dB at the same peak)" % (lab, level(d[pre + kind + "_rec"]) - level(d[kind + "_rec"])))
    ax.text(0.3, -2, LABEL[kind].split(",")[0], fontsize=8, color=INK2, va="top")
    ax.set_xlim(0, 12.5); ax.set_ylim(-60, 6); ax.set_yticks([0, -20, -40])
    ax.tick_params(labelsize=8)
    ax.legend(loc="upper right", fontsize=6.5)
    if i == 0:
        ax.set_xticklabels([])
        ax.set_title("Recorded spectra, each re its own in-band level")
    else:
        ax.set_xlabel("frequency (MHz)")
ax = fig.add_subplot(gs[0, 1])
for kind in KINDS:
    x, y = fine(d["f_" + kind + "_r"])
    ax.plot(x, y, color=COL[kind], lw=1, label=LABEL[kind].split(",")[0])
    k = np.round(x) == x
ax.plot(np.arange(-6, 7), np.full(13, -66), "v", color=INK, ms=4)
ax.text(0, -61, "whole chips", ha="center", fontsize=8, color=INK)
ax.set_xlim(-6, 6); ax.set_ylim(-70, 3)
ax.set_xlabel("delay from the peak (chips, 1/B)"); ax.set_ylabel("matched filter (dB)")
ax.set_title("Filtered: one spectrum, one peak")
ax.legend(loc="upper right", fontsize=7)
ax = fig.add_subplot(gs[1, :])
for kind in ("m", "zc"):
    r = db(d[kind + "_r"])
    sh = d[kind + "_delay"] / FS * 1e6
    ax.plot(lag_us[order] - sh, r[order], color=COL[kind], lw=0.5, label=LABEL[kind].split(",")[0] + ", held")
ghost = -chirp.T * (FS - 8 * chirp.N_ZC * chirp.F_LOOP) / (chirp.N_ZC * chirp.F_LOOP) * 1e6
r = db(d["zc_r"]); lz = lag_us - d["zc_delay"] / FS * 1e6
gh = [r[np.abs(lz - g) < 0.15].max() for g in (ghost, -ghost)]   # each ghost's height, from the record
ax.annotate("ghosts %.1f µs either side: the chips' 8th images land %.0f kHz\nfrom the carrier after the 25 MS/s ADC, and a chirp\nturns a frequency offset into a delay"
            % (-ghost, (FS - 8 * chirp.N_ZC * chirp.F_LOOP) / 1e3), xy=(ghost, gh[0] + 0.5), xytext=(-58, -16),
            fontsize=8, color=INK2, arrowprops=dict(arrowstyle="->", color=INK2, lw=0.8))
ax.annotate("", xy=(-ghost, gh[1] + 0.5), xytext=(-20, -18), arrowprops=dict(arrowstyle="->", color=INK2, lw=0.8))
ax.set_xlim(-60, 60); ax.set_ylim(-75, 3)
ax.set_xlabel("delay from the peak (µs)"); ax.set_ylabel("matched filter (dB)")
ax.set_title("Held chips, ±60 µs of the loop: Zadoff–Chu's worst sidelobe is a ghost")
ax.legend(loc="upper right", fontsize=8)
fig.suptitle(src, x=0.99, ha="right", fontsize=8, color=MUTED)
save(fig, link.img_path("shape"))

# ---- comms_peaks.png: the held peaks ------------------------------------------------------
fig, ax = plt.subplots(figsize=(6, 4.2))
for kind in KINDS:
    x, y = fine(d[kind + "_r"])
    ax.plot(x, y, color=COL[kind], lw=1, label=LABEL[kind].split(",")[0])
x, y = fine(d["chirp_r_hamming"])
ax.plot(x, y, color=C1, lw=1, ls="--", label="chirp, Hamming window")
ax.set_xlim(-3, 3); ax.set_ylim(-68, 3)
ax.set_xlabel("delay from the peak (chips, 1/B)"); ax.set_ylabel("matched filter (dB)")
ax.set_title("Held: a triangle, or a sinc")
ax.legend(loc="lower center", fontsize=7, ncol=2)
fig.suptitle(src, x=0.99, ha="right", fontsize=8, color=MUTED)
save(fig, link.img_path("peaks"))

# ---- comms_doppler.png ------------------------------------------------------------------
# the filtered ZC, its record cut half a loop later: where its sweep wraps, as the chirp's does
zf = np.roll(chirp.mixdown(d["f_zc_rec"]), L // 2)
fh, fd = chirp.doppler_cut(zf, np.roll(chirp.reference(chirp.envelope("zc", shape="filtered")), L // 2), DFS)
fig, axs = plt.subplots(1, 2, figsize=(10, 3.8), gridspec_kw=dict(wspace=0.3))
ax = axs[0]
for kind in KINDS:
    ax.plot(DFS / 1e3, d[kind + "_dop_h"], color=COL[kind], lw=1.2, label=LABEL[kind].split(",")[0])
ax.plot(DFS / 1e3, fh, color=C2, lw=1.2, ls="--", label="Zadoff–Chu, filtered*")
ax.axvline(chirp.F_LOOP / 1e3, color=MUTED, lw=0.6, ls=":"); ax.axvline(-chirp.F_LOOP / 1e3, color=MUTED, lw=0.6, ls=":")
ax.text(chirp.F_LOOP / 1e3 + 0.2, 0.55, "1/T", fontsize=8, color=INK2)
ax.set_ylim(0, 1.1); ax.set_xlabel("frequency offset (kHz)"); ax.set_ylabel("peak height")
ax.set_title("Doppler: the codes' peaks die")
ax.legend(loc="lower left", fontsize=7)
ax = axs[1]
for kind in KINDS:
    h, dd = d[kind + "_dop_h"], d[kind + "_dop_d"]
    ok = h > 0.5
    ax.plot(DFS[ok] / 1e3, (dd[ok] - d[kind + "_delay"]) / chip, color=COL[kind], lw=1.2)
ax.plot(DFS / 1e3, (fd - fd[np.argmin(np.abs(DFS))]) / chip, color=C2, lw=1.2, ls="--")
ax.set_xlabel("frequency offset (kHz)"); ax.set_ylabel("the peak moves by (chips)")
ax.set_title("... the chirps' slide by Δf T / B")
ax.text(-7.5, 2.75, "ZC, held: whole chips", fontsize=8, color=C2)
ax.text(-7.5, 0.6, "ZC, filtered* (a down-chirp)", fontsize=8, color=C2)
ax.text(7.6, -3.0, "* the record cut where ZC's sweep wraps,\n   as the chirp's loop is", fontsize=7, color=INK2,
        ha="right")
ax.text(2.5, 1.2, "chirp (up)", fontsize=8, color=C1)
ax.text(2.2, 0.15, "pulse, codes", fontsize=8, color=INK2)
ax.set_ylim(-3.2, 3.2)
fig.suptitle(src, x=0.99, ha="right", fontsize=8, color=MUTED)
save(fig, link.img_path("doppler"))

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
