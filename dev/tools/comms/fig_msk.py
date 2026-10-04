"""Chapter 6 figures: MSK and GMSK (msk.py): the constant envelope, the spectra, and the
two receivers.

comms_msk_phase.png     theory, no board: the frequency and phase pulses, the phase
                        trellis, MSK as offset QPSK with half-sine pulses, the envelope
                        against QPSK's and OFDM's, and the orthogonality of two tones
                        against their spacing
comms_msk_spectrum.png  six waveforms at 1.5625 Mbit/s through the cable: their spectra
                        and 99% bandwidths; then the same through a hard limiter (done
                        in Python before the DAC: the cable then carries what a
                        saturated amplifier would radiate)
comms_msk_rx.png        the coherent receiver on MSK with the transmitter's carrier
                        3052 Hz high and its bits 7812 ppm fast: the lines of the squared
                        signal, the nodes and the de-rotated constellation, the eyes (the
                        BPSK view, the phase trellis, the discriminator's), the loops

    python3 fig_msk.py --sim | PORT | PORT_A PORT_B | --replot
"""
import numpy as np
import link
from plotstyle import plt, save, dots, C1, C2, C3, MUTED, INK2
import psk
import msk

NAME = "msk"
a = link.args(__doc__)
R, SPS = msk.R, msk.SPS

if not a.replot:
    L = link.Link(a)
    out = {"source": L.source}
    e, q, aa, qa = msk.make_frame()
    q4 = psk.make_frame(4, msk.NBIT // 2)[0]
    # ---- six spectra, as sent and through a hard limiter --------------------------
    names, envs = zip(*msk.waveforms(aa, q4))
    out["names"] = np.array(names)
    out["papr"] = np.array([msk.papr_db(v) for v in envs])
    for limit in (None, "hard"):
        for i, env in enumerate(envs):
            L.play(msk.transmit(aa, env=env, limit=limit))
            out["rec_%s_%d" % (limit or "linear", i)] = L.record()
    # ---- the receivers on MSK with offsets, and on GMSK 0.3 -----------------------
    nbit, cfo_bins = msk.NBIT + 4, 1                       # 7812 ppm fast, 3052 Hz high
    for key, bt in (("msk", None), ("gmsk", 0.3)):
        e, q, aa, qa = msk.make_frame(nbit)
        L.play(msk.transmit(aa, 0.5, bt, cfo_bins))
        rec = L.record()
        r = msk.receive(rec, nbit, q)
        d = msk.discriminator(rec, nbit, qa)
        out["rec_" + key] = rec
        for k in ("f_plus", "f_minus", "cfo_est", "rate_est", "tau_est", "theta_est", "z", "u",
                  "times", "ted", "period", "zs", "zc", "phi", "w", "ec", "errs", "nbits", "mer",
                  "rot", "starts"):
            out["%s_%s" % (key, k)] = r[k]
        for k in ("v", "df", "times", "errs", "nbits"):
            out["%s_disc_%s" % (key, k)] = d[k]
        out["%s_a" % key] = aa
        print("%s: coherent %d errors in %d bits, MER %.1f dB; discriminator %d in %d"
              % (key, r["errs"], r["nbits"], r["mer"], d["errs"], d["nbits"]))
    np.savez(link.data_path(NAME), cfo=cfo_bins * msk.F_LOOP, sro=4 / msk.NBIT * 1e6, **out)
d = np.load(link.data_path(NAME))
src = str(d["source"])

# =====================================================================================
# comms_msk_phase.png: theory
# =====================================================================================
fig, ax = plt.subplots(3, 2, figsize=(10, 10))
t = np.linspace(-2.5, 2.5, 1001)
for bt, c, lab in ((None, C1, "rectangle: MSK, CPFSK"), (0.5, C3, "Gaussian, BT = 0.5 (Bluetooth)"),
                   (0.3, C2, "Gaussian, BT = 0.3 (GSM)")):
    ax[0, 0].plot(t, msk.freq_pulse(t, bt), color=c, label=lab)
    ax[0, 1].plot(t, 2 * 90 * msk.phase_pulse(t, bt), color=c, label=lab)
ax[0, 0].set_ylabel("frequency pulse g(t), area ½")
ax[0, 0].set_title("The frequency pulse g(t) of one bit")
ax[0, 0].legend(loc="upper right")
ax[0, 1].set_ylabel("phase pulse q(t) × 2πh (degrees)")
ax[0, 1].set_title("Its integral q(t): every bit turns the phase by 90° (h = ½)")
ax[0, 1].set_yticks([0, 45, 90])
for a_ in ax[0]:
    a_.set_xlabel("time from the bit's centre (bits)"); a_.set_xlim(-2.5, 2.5)
    a_.axvspan(-0.5, 0.5, color=MUTED, alpha=0.1, lw=0)
# the trellis
nb = 10
e, q, aa, qa = msk.make_frame()
k = np.arange(nb)
tt = np.linspace(0, nb, nb * 64 + 1)
for h, bt, c, lab, lw in ((0.5, None, C1, "MSK: ±90° per bit, straight", 1.8),
                          (0.5, 0.3, C2, "GMSK BT 0.3: the same turns, smoothed", 1.8),
                          (1.0, None, C3, "CPFSK h = 1: ±180° per bit", 0.8)):
    ph = np.degrees(msk.phase(aa, h, bt))
    ax[1, 0].plot(np.arange(msk.N) / 32, ph, color=c, lw=lw, label=lab)
for i in range(-8, 9):                                     # the lattice of allowed nodes
    ax[1, 0].plot([0, nb], [90 * i, 90 * i], color=MUTED, lw=0.4, alpha=0.5)
for kk in range(nb):
    ax[1, 0].text(kk + 0.5, 395, "+" if aa[kk] > 0 else "−", ha="center", fontsize=10, color=INK2)
ax[1, 0].set_xlim(0, nb); ax[1, 0].set_ylim(-450, 450)
ax[1, 0].set_xlabel("time (bits); the bits (slopes) along the top"); ax[1, 0].set_ylabel("phase (degrees)")
ax[1, 0].set_title("The phase trellis: the bits are the slopes; no jumps")
ax[1, 0].legend(loc="lower left", fontsize=8)
# OQPSK view
s = msk.cpm(aa)
s2 = msk.oqpsk(e)
tx = np.arange(msk.N) / 32
sel = tx < nb
ax[1, 1].plot(tx[sel], s.real[sel], color=C1, label="I = cos φ")
ax[1, 1].plot(tx[sel], s.imag[sel], color=C2, label="Q = sin φ")
ax[1, 1].plot(tx[sel], np.abs(s[sel]), color=C3, lw=1, label="|I + jQ| = 1")
ev = k[k % 2 == 0]; od = k[k % 2 == 1]
dots(ax[1, 1], ev, s.real[ev * 32], C1)
dots(ax[1, 1], od, s.imag[od * 32], C2)
ax[1, 1].text(0.02, 0.04, "OQPSK with half-sines − the trellis: max |difference| = %.0e" % np.abs(s - s2).max(),
              transform=ax[1, 1].transAxes, fontsize=8, color=INK2)
ax[1, 1].set_xlim(0, nb); ax[1, 1].set_ylim(-1.3, 1.3)
ax[1, 1].set_xlabel("time (bits)"); ax[1, 1].set_ylabel("envelope")
ax[1, 1].set_title("The same signal: half-sines on I and Q, a bit apart")
ax[1, 1].legend(loc="upper right", fontsize=8, ncol=3)
# envelopes
q4 = psk.make_frame(4, msk.NBIT // 2)[0]
env_rrc = msk.qpsk_env(q4, "rrc")
env_rrc = env_rrc / np.sqrt(np.mean(np.abs(env_rrc)**2))
rng = np.random.default_rng(1)
X = psk.point(rng.integers(0, 4, (8, 64)), 4)
ofdm = np.fft.ifft(X, 256, axis=1).ravel()                 # 8 symbols, 4x oversampled
ofdm = ofdm / np.sqrt(np.mean(np.abs(ofdm)**2))
tb = np.arange(msk.N) / 64                                 # time in QPSK symbols (2 bits)
ns = 24
sel = tb < ns
ax[2, 0].plot(tb[sel], np.abs(env_rrc[sel]), color=C2, label="QPSK, root-raised cosine (PAPR %.1f dB)" % msk.papr_db(env_rrc))
ax[2, 0].plot(np.arange(len(ofdm))[:ns * 64] / 64, np.abs(ofdm[:ns * 64]), color=C3, lw=0.8,
              label="OFDM, 64 subcarriers (PAPR %.1f dB)" % msk.papr_db(ofdm))
ax[2, 0].plot([0, ns], [1, 1], color=C1, lw=2.2, label="MSK, GMSK, CPFSK: 1 (PAPR 0 dB)")
ax[2, 0].set_xlim(0, ns); ax[2, 0].set_ylim(0, 3.6)
ax[2, 0].set_xlabel("time (symbols)"); ax[2, 0].set_ylabel("|envelope| / rms")
ax[2, 0].set_title("The envelope the amplifier has to follow")
ax[2, 0].legend(loc="upper right", fontsize=8)
# orthogonality
hh = np.linspace(0, 2.5, 501)
tau = np.linspace(0, 1, 2001)
coh = np.array([np.mean(np.cos(2 * np.pi * h_ * tau)) for h_ in hh])
non = np.array([np.abs(np.mean(np.exp(2j * np.pi * h_ * tau))) for h_ in hh])
ax[2, 1].plot(hh, coh, color=C1, label="coherent: ∫ cos(2πΔf t) dt over a bit")
ax[2, 1].plot(hh, non, color=C2, label="non-coherent: |∫ e$^{j2πΔf t}$ dt| (any phase)")
ax[2, 1].axhline(0, color=MUTED, lw=0.6)
for h_, lab, y in ((0.5, "h = ½: MSK, BLE, GSM.\nThe least a coherent\nreceiver can use", 1.17),
                   (1.0, "h = 1: the least for a\nnon-coherent receiver (5.05)", 0.75)):
    ax[2, 1].axvline(h_, color=MUTED, lw=0.8, ls="--")
    ax[2, 1].text(h_ + 0.04, y, lab, fontsize=8, color=INK2, va="center")
ax[2, 1].annotate("Bluetooth BR, h = 0.32:\nnot orthogonal, but cheap", (0.32, coh[np.searchsorted(hh, 0.32)]), (0.02, -0.5),
                  fontsize=8, color=INK2, arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.6))
ax[2, 1].set_xlim(0, 2.5); ax[2, 1].set_ylim(-0.6, 1.4); ax[2, 1].set_yticks([-0.5, 0, 0.5, 1])
ax[2, 1].set_xlabel("tone spacing Δf × bit time = h"); ax[2, 1].set_ylabel("correlation of the two tones")
ax[2, 1].set_title("Two tones, one bit: how far apart?")
ax[2, 1].legend(loc="lower right", fontsize=7.5)
fig.suptitle("theory (msk.py)", x=0.99, ha="right", fontsize=8, color=MUTED)
save(fig, link.img_path("msk_phase"))

# =====================================================================================
# comms_msk_spectrum.png
# =====================================================================================
fig = plt.figure(figsize=(10, 9))
gs = fig.add_gridspec(2, 2, height_ratios=[1.25, 1])
ax0 = fig.add_subplot(gs[0, :])
names = list(d["names"])
cols = [MUTED, C2, C3, C1, "#7a4fd1", "#c0392b"]


def smooth_db(Pl, bins=24):
    """Power averaged over `bins` neighbouring bins (37 kHz), in dB, relative to its peak."""
    P = np.convolve(Pl, np.ones(bins) / bins, mode="same")
    return 10 * np.log10(P / P.max() + 1e-12)


bw = {}
for i, (nm, c) in enumerate(zip(names, cols)):
    rec = d["rec_linear_%d" % i].astype(float)
    f, P, Pl = msk.spectrum(rec)
    bw[nm] = msk.bandwidth(f, Pl, msk.F_C) / 1e6
    ax0.plot(f / 1e6, smooth_db(Pl), color=c, lw=1.0, label="%s: 99%% in %.2f MHz" % (nm, bw[nm]))
# theory: sinc^2 for square QPSK at 781 ksymbol/s, MSK's closed form
ff = np.linspace(-4e6, 4e6, 4001)
Ts = 2 / R
sq = 20 * np.log10(np.abs(np.sinc(ff * Ts)) + 1e-9)
T = 1 / R
mskth = 20 * np.log10(np.abs(np.cos(2 * np.pi * ff * T) / (1 - 16 * ff**2 * T**2)) + 1e-9)
ax0.plot((msk.F_C + ff) / 1e6, sq, color=MUTED, lw=0.9, ls=":", label="theory: sinc² for square pulses (1/f²); MSK's cos²(2πfT)/(1−16f²T²)² (1/f⁴)")
ax0.plot((msk.F_C + ff) / 1e6, mskth, color=C1, lw=0.9, ls=":")
ax0.set_xlim(2.25, 10.25); ax0.set_ylim(-80, 3)
ax0.set_xlabel("frequency (MHz)"); ax0.set_ylabel("power (dB, each relative to its own peak)")
ax0.set_title("Six waveforms at 1.5625 Mbit/s, as the ADC records them (16384 samples, smoothed over 37 kHz)")
ax0.legend(loc="lower left", fontsize=7.5, ncol=2)
ax1 = fig.add_subplot(gs[1, 0])
x = np.linspace(0, 2.5, 251)
ax1.plot(x, x, color=MUTED, ls="--", lw=1, label="linear (what a 10 dB back-off buys)")
ax1.plot(x, x / (1 + x**4)**0.25, color=C2, label="soft: Rapp model, p = 2, knee at the rms")
ax1.plot(x, np.ones_like(x), color=C1, label="hard limiter: class C, a switch")
ax1.set_xlim(0, 2.5); ax1.set_ylim(0, 1.6)
ax1.set_xlabel("input amplitude / rms"); ax1.set_ylabel("output amplitude")
ax1.set_title("The amplifier models: phase kept, amplitude bent")
ax1.legend(loc="lower right", fontsize=8)
ax2 = fig.add_subplot(gs[1, 1])
for i, c, lab in ((1, C2, "QPSK, root-raised cosine"), (3, C1, "MSK"), (5, "#c0392b", "GMSK, BT = 0.3")):
    f, P0, Pl0 = msk.spectrum(d["rec_linear_%d" % i].astype(float))
    f, P1, Pl1 = msk.spectrum(d["rec_hard_%d" % i].astype(float))
    outside = lambda Pl: 10 * np.log10(Pl[np.abs(f - msk.F_C) > R].sum())
    ax2.plot(f / 1e6, smooth_db(Pl0), color=c, lw=0.8, alpha=0.4)
    ax2.plot(f / 1e6, smooth_db(Pl1), color=c, lw=1.0,
             label="%s: beyond ±R, %.0f dB → %.0f dB" % (lab, outside(Pl0), outside(Pl1)))
ax2.set_xlim(2.25, 10.25); ax2.set_ylim(-80, 3)
ax2.set_xlabel("frequency (MHz)"); ax2.set_ylabel("power (dB)")
ax2.set_title("Through the hard limiter (pale: as sent)")
ax2.legend(loc="lower left", fontsize=7.5)
fig.suptitle(src, x=0.99, ha="right", fontsize=8, color=MUTED)
save(fig, link.img_path("msk_spectrum"))
print("99% bandwidths (MHz):", {k: round(v, 2) for k, v in bw.items()})

# =====================================================================================
# comms_msk_rx.png
# =====================================================================================
fig, ax = plt.subplots(3, 3, figsize=(11, 10))
skip = 400
z = d["msk_z"]
f, P, _ = msk.spectrum(msk.lowpass(z, R)**2)
P = 10 * np.log10(np.convolve(10**(P / 10), np.ones(4) / 4, mode="same") + 1e-12)
ax[0, 0].plot(f / 1e6, P - P.max(), color=C1, lw=0.6)
for fl in (d["msk_f_plus"], d["msk_f_minus"]):
    ax[0, 0].annotate("%+.1f kHz" % (fl / 1e3), (fl / 1e6, 0), (fl / 1e6, 8), ha="center", fontsize=8, color=INK2,
                      arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.6))
ax[0, 0].set_xlim(-2.5, 2.5); ax[0, 0].set_ylim(-60, 14)
ax[0, 0].set_xlabel("frequency from 2 × 6.25 MHz (MHz)"); ax[0, 0].set_ylabel("power (dB)")
ax[0, 0].set_title("The signal squared: two lines R apart,\naround 2 × the carrier offset (%+.0f Hz found)" % d["msk_cfo_est"], fontsize=10)
# nodes on the circle: sample the matched-filtered, phase-corrected signal at the loop's times
u = d["msk_u"]; times = d["msk_times"]
n = np.arange(len(u))
y = u * np.exp(2j * np.pi * (d["msk_rate_est"] / 4) * (n - d["msk_tau_est"]) / msk.FS_ADC)   # undo the de-rotation
kk = np.arange(skip, len(times))
nodes = np.array([psk.interp(y, t) for t in times[kk]])
nodes = nodes / np.sqrt(np.mean(np.abs(nodes)**2)) * np.exp(-1j * d["msk_phi"][kk])
for m, c, lab in ((0, C1, "even bits"), (1, C2, "odd bits")):
    s_ = (kk % 2) == m
    ax[0, 1].plot(nodes[s_].real, nodes[s_].imag, ".", color=c, markersize=2.5, label=lab)
ax[0, 1].set_title("The nodes y(kT): a quarter turn on every\nbit, so I and Q take turns (the leak: ±2/π)", fontsize=10)
ax[0, 1].legend(loc="center", fontsize=7, markerscale=3)
zc = d["msk_zc"] * np.exp(-2j * np.pi * d["msk_rot"][-1] / 2)
ax[0, 2].plot(zc[:skip].real, zc[:skip].imag, ".", color=MUTED, markersize=2, label="first %d bits" % skip)
ax[0, 2].plot(zc[skip:].real, zc[skip:].imag, ".", color=C1, markersize=2, label="after")
ax[0, 2].set_title("Quarter-turned back: BPSK\n%d errors / %d bits, MER %.0f dB" % (d["msk_errs"], d["msk_nbits"], d["msk_mer"]), fontsize=10)
ax[0, 2].legend(loc="upper center", fontsize=7, markerscale=3)
for a_ in ax[0, 1:]:
    a_.set_aspect("equal"); a_.set_xlim(-1.7, 1.7); a_.set_ylim(-1.7, 1.7)
    a_.set_xlabel("I"); a_.set_ylabel("Q")
# eyes
tau = np.arange(-SPS, SPS + 1)
for kk_ in range(skip, min(skip + 300, len(times))):
    t0 = int(round(times[kk_]))
    if t0 - SPS < 0 or t0 + SPS >= len(u):
        continue
    ax[1, 0].plot(tau / SPS, u[t0 - SPS:t0 + SPS + 1].real, color=C1, lw=0.3, alpha=0.35)
ax[1, 0].set_xlabel("time from the node (bits)"); ax[1, 0].set_ylabel("Re (de-rotated)")
ax[1, 0].set_title("Eye, the BPSK view: a Nyquist pulse", fontsize=10)


def trellis_eye(key, a_, c, lab):
    """The received phase over each bit, relative to its starting node (rounded to 90°)."""
    z = msk.lowpass(d[key + "_z"], 1.25 * R)
    n = np.arange(len(z))
    z = z * np.exp(-2j * np.pi * d[key + "_cfo_est"] * n / msk.FS_ADC - 1j * d[key + "_theta_est"])
    ph = np.unwrap(np.angle(z))
    times = d[key + "_times"]
    first = True
    for kk_ in range(skip, min(skip + 300, len(times))):
        t0 = times[kk_]
        tt = t0 + np.arange(0, SPS + 1)
        if tt[-1] + 2 >= len(ph):
            continue
        seg = np.degrees(np.array([psk.interp(ph, t) for t in tt]))
        seg = seg - 90 * np.round(seg[0] / 90)
        a_.plot(np.arange(SPS + 1) / SPS, seg, color=c, lw=0.6, alpha=0.5, label=lab if first else None)
        first = False


trellis_eye("msk", ax[1, 1], C1, "MSK")
trellis_eye("gmsk", ax[1, 1], C2, "GMSK BT 0.3")
for yv in (-90, 0, 90):
    ax[1, 1].axhline(yv, color=MUTED, lw=0.5)
ax[1, 1].set_ylim(-150, 150); ax[1, 1].set_yticks([-90, 0, 90])
ax[1, 1].set_xlabel("time within the bit (bits)"); ax[1, 1].set_ylabel("phase from the node (degrees)")
ax[1, 1].set_title("Eye, the trellis view: MSK straight to ±90°,\nGMSK 0.3 smeared by its neighbours", fontsize=10)
leg = ax[1, 1].legend(loc="upper left", fontsize=7)
for l_ in leg.get_lines():
    l_.set_linewidth(1.5); l_.set_alpha(1)
for key, c, lab in (("msk", C1, "MSK"), ("gmsk", C2, "GMSK BT 0.3")):
    v = d[key + "_disc_v"]; tm = d[key + "_disc_times"]
    first = True
    for kk_ in range(skip, min(skip + 300, len(tm))):
        t0 = int(round(tm[kk_]))
        if t0 - SPS < 0 or t0 + SPS >= len(v):
            continue
        ax[1, 2].plot(tau / SPS, v[t0 - SPS:t0 + SPS + 1], color=c, lw=0.3, alpha=0.35, label=lab if first else None)
        first = False
ax[1, 2].set_ylim(-1.6, 1.6)
ax[1, 2].set_xlabel("time from the bit's centre (bits)"); ax[1, 2].set_ylabel("phase change over a bit / 90°")
ax[1, 2].set_title("Eye, the discriminator's view:\nGMSK 0.3 doesn't get there", fontsize=10)
leg = ax[1, 2].legend(loc="upper left", fontsize=7)
for l_ in leg.get_lines():
    l_.set_linewidth(1.5); l_.set_alpha(1)
# the loops
k = np.arange(len(d["msk_zc"]))
us = k / R * 1e6
dt = d["msk_times"] - SPS * k
ax[2, 0].plot(us, dt - dt[0], color=C1, lw=1)
ax[2, 0].set_ylabel("sampling point moved (samples)")
ax[2, 0].set_title("Timing loop: from the lines' start,\nit learns the rate (%+.0f ppm sent)" % d["sro"], fontsize=10)
a2 = ax[2, 0].twinx()
a2.plot(us, (SPS / d["msk_period"] - 1) * 1e6, color=C2, lw=0.8)
a2.set_ylabel("bit-rate offset found (ppm)", color=C2); a2.grid(False)
a2.spines["right"].set_visible(True)
# discriminator raw output
nb_show = 16
for key, c, lab in (("msk", C1, "MSK"), ("gmsk", C2, "GMSK BT 0.3")):
    df = d[key + "_disc_df"]
    t0 = int(round(d[key + "_disc_times"][skip])) - SPS // 2
    seg = df[t0:t0 + nb_show * SPS] * msk.FS_ADC / (2 * np.pi) / 1e3
    ax[2, 1].plot(np.arange(len(seg)) / SPS, seg, color=c, lw=0.9, label=lab)
aa = d["msk_a"]
ax[2, 1].axhline(R / 4e3, color=MUTED, lw=0.6, ls="--"); ax[2, 1].axhline(-R / 4e3, color=MUTED, lw=0.6, ls="--")
ax[2, 1].set_ylim(-800, 800); ax[2, 1].set_xlim(0, nb_show)
ax[2, 1].set_xlabel("time (bits)"); ax[2, 1].set_ylabel("frequency from the carrier (kHz)")
ax[2, 1].set_title("The discriminator's output: ±391 kHz for MSK;\nGMSK's Gaussian pulse rounds the corners", fontsize=10)
ax[2, 1].legend(loc="upper right", fontsize=7)
ax[2, 2].plot(us, d["msk_ted"], ".", color=C1, markersize=1.5, label="Gardner (timing)")
ax[2, 2].plot(us, d["msk_ec"], ".", color=C2, markersize=1.5, label="Costas (phase)")
ax[2, 2].set_ylim(-0.5, 0.5)
ax[2, 2].set_ylabel("error signal"); ax[2, 2].legend(loc="upper right", fontsize=7, markerscale=3)
ax[2, 2].set_title("The loops' detectors, bit by bit", fontsize=10)
for a_ in (ax[2, 0], ax[2, 2]):
    a_.set_xlabel("time (µs)")
    a_.axvspan(0, skip / R * 1e6, color=MUTED, alpha=0.08, lw=0)
fig.suptitle(src, x=0.99, ha="right", fontsize=8, color=MUTED)
save(fig, link.img_path("msk_rx"))
