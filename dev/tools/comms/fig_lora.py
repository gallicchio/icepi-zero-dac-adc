"""Chapter 6 figure: LoRa's chirp spread spectrum, scaled to the board (lora.py).

comms_lora.png
  top left      one loop of an SF 7 frame, mixed down, as a spectrogram: two up-chirps,
                two down-chirps, four data symbols (sent with the carrier 1.5 bins high)
  top right     the preamble's and the SFD's dechirped FFTs: the carrier offset moves
                both the same way, the timing error moves them apart
  bottom left   the four data symbols' dechirped FFTs, after the correction
  bottom right  bit error rate against SNR per chip for SF 7 to 10: measured, the
                theory for 2^SF orthogonal signals detected by size, and Semtech's
                demodulation SNRs (SX1276 datasheet, table 10)

    python3 fig_lora.py --sim | PORT | PORT_A PORT_B | --replot [--records 60]
"""
import numpy as np
import link
from plotstyle import plt, save, C1, C2, C3, MUTED, INK2, INK
import lora

NAME = "lora"
CFO = 12                                                 # steps of 3051.76 Hz: 1.5 bins at SF 7
SNRS = np.arange(-24, -3, 2.0)
SFS = (7, 8, 9, 10)
COL = {7: C1, 8: C2, 9: C3, 10: INK2}
a = link.args(__doc__, lambda ap: ap.add_argument("--records", type=int, default=60,
                                                  help="at most this many uploads per point"))
if not a.replot:
    Lk = link.Link(a)
    out = {"source": Lk.source}
    tau0, _ = lora.find_timing(Lk.play, Lk.record)
    print("timing from a clean preamble: %.2f samples" % tau0)
    env, vals = lora.frame(7, [5, 77, 100, 127])
    Lk.play(lora.transmit(env, None, CFO))
    rec = Lk.record()
    nu, dtau, up, down = lora.sync(rec, 7, tau0=tau0)
    found, X = lora.receive(rec, 7, tau0 + dtau * lora.SPC, nu)
    print("carrier off by %.2f bins (sent %.2f), timing %.2f chips; data %s -> %s"
          % (nu, CFO * lora.F_LOOP / (lora.B / 128), dtau, vals[4:], found[4:]))
    out.update(rec=rec, vals=vals, found=found, up=up, down=down, X=X, nu=nu, dtau=dtau, tau0=tau0)
    rng = np.random.default_rng(3)
    rows = []
    for sf in SFS:
        M = 1 << sf
        for snr in SNRS:
            se = ns = be = 0
            for i in range(a.records):
                sent = rng.integers(0, M, lora.NCHIP // M)
                Lk.play(lora.transmit(np.concatenate([lora.symbol(int(s), M) for s in sent]), snr, rng=rng))
                got, _ = lora.receive(Lk.record(), sf, tau0)
                se += int(np.sum(got != sent)); ns += len(sent); be += lora.bits_wrong(got, sent, sf)
                if se >= 100 and i >= 4:
                    break
            rows.append((snr, sf, se, ns, be, ns * sf))
            print("SF %2d %5.0f dB: %4d / %5d symbols wrong, %5d / %6d bits  (SER %.3f, theory %.3f)"
                  % (sf, snr, se, ns, be, ns * sf, se / ns, lora.ser_theory(M, snr + 10 * np.log10(M))), flush=True)
    out["rows"] = np.array(rows)
    np.savez_compressed(link.data_path(NAME), **out)
d = np.load(link.data_path(NAME))
src = str(d["source"])
L, FS = lora.L, lora.FS_ADC

fig, ax = plt.subplots(2, 2, figsize=(10, 8.2))
# (a) spectrogram
rec = d["rec"].astype(float)[:L]
z = 2 * (rec - rec.mean()) * np.exp(-2j * np.pi * lora.F_C * np.arange(L) / FS)
nfft, hop = 64, 8
win = np.hanning(nfft)
frames = np.array([np.fft.fftshift(np.fft.fft(z[i:i + nfft] * win)) for i in range(0, L - nfft, hop)])
S = 20 * np.log10(np.abs(frames) + 1e-3)
t_us = (np.arange(len(frames)) * hop + nfft / 2) / FS * 1e6
f_mhz = np.fft.fftshift(np.fft.fftfreq(nfft, 1 / FS)) / 1e6
ax[0, 0].imshow(S.T, origin="lower", aspect="auto", extent=[t_us[0], t_us[-1], f_mhz[0], f_mhz[-1]],
                cmap="Blues", vmin=S.max() - 35, vmax=S.max())
ax[0, 0].set_ylim(-2.2, 2.2)
for i, v in enumerate(d["vals"]):
    ax[0, 0].text((i + 0.5) * 41, 1.85, "up" if i < 2 else "down" if v < 0 else str(v), ha="center", fontsize=8, color=INK)
ax[0, 0].set_xlabel("time (µs)"); ax[0, 0].set_ylabel("frequency from 6.25 MHz (MHz)")
ax[0, 0].set_title("An SF 7 frame, 41 µs per symbol")
# (b) sync
M = 128
bins = np.arange(M)
up, down = d["up"].mean(axis=0), d["down"].mean(axis=0)
sb = (bins + M / 2) % M - M / 2
o = np.argsort(sb)
ax[0, 1].plot(sb[o], up[o] / up.max(), "o-", color=C1, markersize=3, lw=0.8, label="up-chirps (preamble): ν − τ")
ax[0, 1].plot(sb[o], down[o] / up.max(), "s-", color=C2, markersize=3, lw=0.8, label="down-chirps (SFD): ν + τ")
ax[0, 1].set_xlim(-6, 8)
nu, dtau = float(d["nu"]), float(d["dtau"])
ax[0, 1].text(7.8, 0.6, "carrier ν = %+.2f bins (%+.1f kHz)\ntiming τ = %+.2f chips" % (nu, nu * lora.B / M / 1e3, dtau),
              ha="right", fontsize=8, color=INK2)
ax[0, 1].set_xlabel("dechirped FFT bin"); ax[0, 1].set_ylabel("|X|, relative")
ax[0, 1].set_title("Sync: sum → carrier, difference → timing")
ax[0, 1].legend(loc="upper left", fontsize=7)
# (c) data symbols
X = d["X"]
for i in range(4, 8):
    row = X[i] / X[4:].max()
    ax[1, 0].plot(bins, row + (7 - i) * 1.1, color=COL[7], lw=0.8)
    ax[1, 0].text(2, (7 - i) * 1.1 + 0.35, "sent %d, found %d" % (d["vals"][i], d["found"][i]), fontsize=8, color=INK2)
ax[1, 0].set_yticks([]); ax[1, 0].set_xlim(0, M); ax[1, 0].set_xlabel("dechirped FFT bin = symbol value")
ax[1, 0].set_title("The data symbols, dechirped: 7 bits each")
# (d) BER
rows = d["rows"]
x = np.linspace(SNRS[0] - 1, SNRS[-1] + 1, 120)
for sf in SFS:
    Mi = 1 << sf
    th = np.array([lora.ser_theory(Mi, v + 10 * np.log10(Mi)) for v in x]) * Mi / (2 * (Mi - 1))
    ax[1, 1].semilogy(x, th, color=COL[sf], lw=1, alpha=0.8)
    r = rows[rows[:, 1] == sf]
    ok = r[:, 4] > 0
    ax[1, 1].semilogy(r[ok, 0], r[ok, 4] / r[ok, 5], "o", color=COL[sf], markersize=4.5,
                      label="SF %d: %.0f kbit/s" % (sf, sf * (lora.NCHIP >> sf) * lora.F_LOOP / 1e3))
    for r_ in r[~ok]:
        ax[1, 1].semilogy(r_[0], 1 / r_[5], "v", color=COL[sf], mfc="none", markersize=4.5)
for sf in (11, 12):
    Mi = 1 << sf
    th = np.array([lora.ser_theory(Mi, v + 10 * np.log10(Mi)) for v in x]) * Mi / (2 * (Mi - 1))
    ax[1, 1].semilogy(x, th, color=MUTED, lw=0.8, ls="--")
    ax[1, 1].text(x[np.argmax(th < 0.03)] - 1.5, 0.03, "SF %d" % sf, fontsize=7, color=MUTED)
for sf, s in lora.SEMTECH.items():
    ax[1, 1].plot([s, s], [0.55, 0.9], color=COL.get(sf, MUTED), lw=1.5)
ax[1, 1].text(-24.8, 0.68, "Semtech's SNR, SF 12 … 7:", fontsize=7, color=INK2)
ax[1, 1].set_ylim(1e-4, 1); ax[1, 1].set_xlim(SNRS[0] - 1, SNRS[-1] + 1)
ax[1, 1].set_xlabel("SNR per chip: signal / noise in a band B wide (dB)"); ax[1, 1].set_ylabel("bit error rate")
ax[1, 1].set_title("Each spreading factor: half the rate, ~2.7 dB")
ax[1, 1].legend(loc="lower left", fontsize=7)
fig.suptitle(src, x=0.99, ha="right", fontsize=8, color=MUTED)
save(fig, link.img_path(NAME))
