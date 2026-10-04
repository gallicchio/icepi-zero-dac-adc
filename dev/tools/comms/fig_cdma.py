"""Chapter 6 figure: spread spectrum the GPS way (cdma.py).  Two users, PRN 1 and PRN 2,
on one 6.25 MHz carrier at once, user 2's code 300.4 chips later.

comms_cdma.png
  the spectrum, with noise 10 dB stronger than both signals together; acquisition
  (correlation power against delay) for PRN 1, 2, and 3, which isn't sent; the
  correlation peak, a triangle two chips wide (no noise added, for clarity); each
  user's bits, pulled apart (with the noise).

    python3 fig_cdma.py --sim | PORT | PORT_A PORT_B | --replot
"""
import numpy as np
import link
from plotstyle import plt, save, dots, C1, C2, C3, MUTED, INK2
import cdma

NAME = "cdma"
SNR = -10.0
a = link.args(__doc__)
if not a.replot:
    L = link.Link(a)
    users = [(1, cdma.user_bits(0), 0.0, 1.0, 0.3), (2, cdma.user_bits(500), 300.4, 1.0, 2.0)]
    out = {"source": L.source, "bits1": users[0][1], "bits2": users[1][1]}
    # transmit() scales signal + noise to fill the DAC: how much smaller is the
    # signal in the noisy waveform than in the clean one?
    wc, wn = cdma.transmit(users) - 128, cdma.transmit(users, SNR, rng=7) - 128
    out["scale"] = np.dot(wn, wc) / np.dot(wc, wc)
    for tag, snr in (("clean", None), ("noisy", SNR)):
        L.play(cdma.transmit(users, snr, rng=7))
        rec = L.record()
        r = cdma.receive(rec, (1, 2, 3))
        out["rec_" + tag] = rec
        for p in (1, 2, 3):
            for k in ("P", "soft", "bits", "delay", "peak_db", "lag"):
                out["%s_%s%d" % (tag, k, p)] = r[p][k]
    np.savez_compressed(link.data_path(NAME), **out)
d = np.load(link.data_path(NAME))
for tag in ("clean", "noisy"):
    e = [int(np.sum(d["%s_bits%d" % (tag, p)][8:] != d["bits%d" % p][8:])) for p in (1, 2)]
    print("%s: delays %.2f, %.2f chips; peaks %.1f, %.1f, %.1f dB; bit errors %d, %d of 23 each"
          % (tag, d[tag + "_delay1"], d[tag + "_delay2"], d[tag + "_peak_db1"], d[tag + "_peak_db2"],
             d[tag + "_peak_db3"], e[0], e[1]))

fig, ax = plt.subplots(2, 2, figsize=(10, 7))
rec = d["rec_noisy"].astype(float)
x = rec - rec.mean(); w = np.hanning(len(x))
X = np.abs(np.fft.rfft(x * w)) / (w.sum() / 2)
f = np.fft.rfftfreq(len(x), 1 / cdma.FS_ADC) / 1e6
k = 16                                                  # smooth over 16 bins (24 kHz)
Xs = np.sqrt(np.convolve(X**2, np.ones(k) / k, "same"))
rc = d["rec_clean"].astype(float); xc = rc - rc.mean()
Xc = np.sqrt(np.convolve((np.abs(np.fft.rfft(xc * w)) / (w.sum() / 2))**2, np.ones(k) / k, "same"))
ax[0, 0].plot(f, 20 * np.log10(Xs), color=C1, lw=0.7, label="recorded: users + noise 10 dB stronger")
ax[0, 0].plot(f, 20 * np.log10(Xc * float(d["scale"])), color=C2, lw=0.7,
              label="the two users alone, same level")
ax[0, 0].set_xlim(0, 12.5)
ax[0, 0].set_xlabel("frequency (MHz)"); ax[0, 0].set_ylabel("amplitude (dB re 1 code)")
ax[0, 0].set_title("Both users on 6.25 MHz, under the noise")
ax[0, 0].legend(loc="lower center", fontsize=8)
chips = (np.arange(cdma.L) * cdma.CHIPS / cdma.L + 100) % cdma.CHIPS - 100    # -100 .. 923
order = np.argsort(chips)
ref = d["noisy_P1"].max()
for p, c in ((3, C3), (1, C1), (2, C2)):
    ax[0, 1].plot(chips[order], 10 * np.log10(d["noisy_P%d" % p][order] / ref), color=c, lw=0.5,
                  label="PRN %d%s" % (p, " (not sent)" if p == 3 else ""))
ax[0, 1].set_xlabel("delay (chips)"); ax[0, 1].set_ylabel("correlation power (dB)")
ax[0, 1].set_ylim(-16, 1)
ax[0, 1].set_title("Acquisition: each code against every delay")
for line in ax[0, 1].legend(loc="upper right", fontsize=8, ncol=3).get_lines():
    line.set_linewidth(2)
for p, c in ((1, C1), (2, C2)):
    P = d["clean_P%d" % p]; lag = int(d["clean_lag%d" % p])
    i = np.arange(-24, 25)
    dots(ax[1, 0], i * cdma.CHIPS / cdma.L, np.sqrt(P[(lag + i) % cdma.L] / P[lag]), c,
         label="PRN %d: peak at %.2f chips" % (p, d["clean_delay%d" % p]))
ax[1, 0].set_xlabel("delay from the peak (chips)"); ax[1, 0].set_ylabel("correlation (amplitude)")
ax[1, 0].set_title("The peak (no noise): a triangle two chips wide")
ax[1, 0].legend(loc="upper right", fontsize=8)
nb = np.arange(cdma.NBIT)
for p, c, off in ((1, C1, -0.15), (2, C2, 0.15)):
    s = d["noisy_soft%d" % p]; s = s / np.mean(np.abs(s))
    dots(ax[1, 1], nb + off, s, c, label="PRN %d" % p)
    sent = 1 - 2 * d["bits%d" % p]
    ax[1, 1].plot(nb + off, sent, "_", color=c, markersize=9)
ax[1, 1].axvspan(-0.5, 7.5, color=MUTED, alpha=0.1, lw=0)
ax[1, 1].text(3.5, -1.95, "preamble", ha="center", fontsize=8, color=INK2)
ax[1, 1].set_ylim(-2.2, 2.2)
ax[1, 1].set_xlabel("bit"); ax[1, 1].set_ylabel("despread bit (dots), sent (bars)")
ax[1, 1].set_title("Each user's bits, pulled apart (with the noise)")
ax[1, 1].legend(loc="upper right", fontsize=8, ncol=2)
fig.suptitle(str(d["source"]), x=0.99, ha="right", fontsize=8, color=MUTED)
save(fig, link.img_path(NAME))
