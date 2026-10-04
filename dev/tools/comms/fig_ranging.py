"""Chapter 6 figure: ranging through the cable with a chirp, a Zadoff-Chu sequence and
an m-sequence (chirp.py), against the Cramer-Rao bound.

comms_ranging.png
  left    the scatter of the delay estimate against SNR, with the bound for each
          waveform (its own rms bandwidth); hollow markers: some estimates landed on a
          noise peak instead (the threshold effect)
  middle  the delay itself: the cable, measured by three different waveforms
  right   the phase of the chirp's compressed peak and of a plain tone at the same
          power, against loops averaged: the same scatter, falling as 1/sqrt(loops)

Noise is added at the transmitter, white over the ADC's band; the SNR is the signal's
power over the noise's in a band B wide.  Each trial is a fresh upload.

    python3 fig_ranging.py --sim | PORT | PORT_A PORT_B | --replot [--trials 12]
"""
import numpy as np
import link
from plotstyle import plt, save, C1, C2, C3, MUTED, INK2
import chirp

NAME = "ranging"
SNRS = np.arange(-30, 1, 3.0)
KINDS = ("chirp", "zc", "m")
COL = {"chirp": C1, "zc": C2, "m": C3}
LABEL = {"chirp": "chirp", "zc": "Zadoff–Chu", "m": "m-sequence"}
PHASE_SNR = -10.0
KMAX, GROUPS = 8, 20
a = link.args(__doc__, lambda ap: ap.add_argument("--trials", type=int, default=12,
                                                  help="uploads per waveform per SNR"))
if not a.replot:
    Lk = link.Link(a)
    rng = np.random.default_rng(5)
    out = {"source": Lk.source, "snrs": SNRS, "trials": a.trials}
    for kind in KINDS:
        est = np.zeros((len(SNRS), a.trials))
        for i, snr in enumerate(SNRS):
            for j in range(a.trials):
                est[i, j] = chirp.run(kind, Lk.play, Lk.record, snr=snr, rng=rng)["delay"]
            good = np.abs(est[i] - np.median(est[i])) < 2 * chirp.FS_ADC / chirp.B0
            if good.sum() >= 2:
                print("%-5s %5.0f dB: delay %.3f +- %.3f samples (%d of %d on the peak)"
                      % (kind, snr, est[i, good].mean(), est[i, good].std(), good.sum(), a.trials), flush=True)
            else:
                print("%-5s %5.0f dB: lost (%d of %d on the peak)" % (kind, snr, good.sum(), a.trials), flush=True)
        out[kind + "_est"] = est
        out[kind + "_brms"] = chirp.rms_bandwidth(chirp.reference(chirp.envelope(kind)))
        out[kind + "_bw"] = chirp.chip_rate(kind)
    # a tone and a chirp at the same power: the phase of each, loop after loop
    for kind, env in (("tone", np.ones(chirp.N, complex)), ("chirp", chirp.envelope("chirp"))):
        ref = chirp.reference(env)
        Lk.play(chirp.transmit(env))
        z0 = chirp.mixdown(Lk.record())
        phases = np.zeros((GROUPS, KMAX))
        for g in range(GROUPS):
            acc = np.zeros(chirp.L, complex)
            for k in range(KMAX):
                Lk.play(chirp.transmit(env, PHASE_SNR, rng=rng))
                acc += chirp.mixdown(Lk.record())
                if kind == "tone":
                    phases[g, k] = np.angle(np.mean(acc) / np.mean(z0))
                else:
                    phases[g, k] = np.angle(chirp.delay_of(chirp.compress(acc, ref))[1] /
                                            chirp.delay_of(chirp.compress(z0, ref))[1])
        out[kind + "_phase"] = phases
        print("%s at %.0f dB: phase scatter %s deg for 1..%d loops" %
              (kind, PHASE_SNR, np.round(np.degrees(phases.std(axis=0)), 2), KMAX), flush=True)
    np.savez_compressed(link.data_path(NAME), **out)
d = np.load(link.data_path(NAME))
src = str(d["source"])
FS = chirp.FS_ADC

fig, ax = plt.subplots(1, 3, figsize=(10, 4.1))
x = np.linspace(SNRS[0] - 1, SNRS[-1] + 1, 100)
for kind in KINDS:
    est = d[kind + "_est"]
    sig, mean, hollow, shown = [], [], [], []
    for i in range(len(SNRS)):
        good = np.abs(est[i] - np.median(est[i])) < 2 * FS / chirp.B0
        shown.append(good.sum() >= 2 * len(est[i]) // 3)        # else the peak is lost: no estimate
        sig.append(est[i, good].std() if shown[-1] else np.nan)
        mean.append(est[i, good].mean() if shown[-1] else np.nan)
        hollow.append(good.sum() < len(est[i]))
    sig, mean, hollow, shown = np.array(sig), np.array(mean), np.array(hollow), np.array(shown)
    bound = chirp.crb(float(d[kind + "_brms"]), x, float(d[kind + "_bw"])) * 1e9
    ax[0].semilogy(x, bound, color=COL[kind], lw=1, alpha=0.7)
    ok = shown & ~hollow
    ax[0].semilogy(SNRS[ok], sig[ok] / FS * 1e9, "o", color=COL[kind], label="%s, B_rms %.2f MHz"
                   % (LABEL[kind], d[kind + "_brms"] / 1e6))
    ax[0].semilogy(SNRS[shown & hollow], sig[shown & hollow] / FS * 1e9, "o", color=COL[kind], mfc="none")
    ok = shown & (SNRS >= -18)
    ax[1].errorbar(SNRS[ok], mean[ok], sig[ok] / np.sqrt(len(est[0])), fmt="o-", color=COL[kind], lw=0.8,
                   markersize=4, label=LABEL[kind], capsize=2)
ax[0].axhline(1 / FS * 1e9, color=MUTED, lw=0.8, ls=":")
ax[0].text(-29.5, 1 / FS * 1e9 / 1.5, "one ADC sample", fontsize=8, color=INK2)
ax[0].set_ylim(0.1, 200); ax[0].set_xlabel("SNR in a band B wide (dB)")
ax[0].set_ylabel("scatter of the delay estimate (ns)")
ax[0].set_title("Scatter vs the Cramér–Rao bound")
ax[0].legend(loc="upper right", fontsize=7)
ax[0].text(-29.5, 0.13, "hollow: some trials\nlanded on a noise peak", fontsize=7, color=INK2)
ax[1].set_xlabel("SNR in a band B wide (dB)"); ax[1].set_ylabel("delay found (ADC samples of 40 ns)")
ax[1].set_title("The cable's delay, three ways")
ax[1].legend(loc="upper right", fontsize=8)
mid = float(np.median(np.concatenate([d["chirp_est"][-1], d["zc_est"][-1], d["m_est"][-1]]))); ax[1].set_ylim(mid - 0.6, mid + 0.6)
k = np.arange(1, KMAX + 1)
for kind, c, lab in (("tone", INK2, "a 6.25 MHz tone, lock-in over the loops"), ("chirp", C1, "the chirp's compressed peak")):
    ax[2].loglog(k, np.degrees(d[kind + "_phase"].std(axis=0)), "o", color=c, label=lab)
th = np.degrees(1 / np.sqrt(2 * 10**(PHASE_SNR / 10) * chirp.B0 * chirp.T * k))
ax[2].loglog(k, th, color=MUTED, lw=1, label="1 / √(2 E/N0): %.1f° / √loops" % th[0])
ax[2].set_xlabel("loops averaged (fresh noise each)"); ax[2].set_ylabel("phase scatter (degrees)")
ax[2].set_title("Tone vs chirp: phase SNR")
ax[2].set_xticks(k); ax[2].set_xticklabels([str(v) for v in k])
ax[2].set_ylim(0.8, 6)
ax[2].legend(loc="upper right", fontsize=7)
fig.suptitle(src, x=0.99, ha="right", fontsize=8, color=MUTED)
save(fig, link.img_path(NAME))
