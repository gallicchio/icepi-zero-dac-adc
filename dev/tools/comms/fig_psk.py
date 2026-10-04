"""Chapter 6 figures: QPSK through the cable, with the loops at work.

comms_psk_wave.png   the transmitted signal: symbols, envelope, carrier; its spectrum
comms_psk_loops.png  constellation before and after the loops, eye, and the timing
                     and Costas loops converging on an imposed offset

The transmitter's carrier is 1 step (3052 Hz) high and its symbols 1 per loop
(1953 ppm) fast, on purpose, so that the loops have something to find.

    python3 fig_psk.py --sim | PORT | PORT_A PORT_B | --replot
"""
import numpy as np
import link
from plotstyle import plt, save, dots, C1, C2, MUTED, INK2
import psk

NAME = "psk"
a = link.args(__doc__)
if not a.replot:
    L = link.Link(a)
    M, cfo_bins, extra = 4, 1, 1
    q, data = psk.make_frame(M, psk.NSYM + extra)
    wave = psk.transmit(q, M, cfo_bins)
    L.play(wave)
    rec = L.record()
    r = psk.receive(rec, M, psk.NSYM + extra, q)
    tau, eye = psk.eye(r, M)
    np.savez(link.data_path(NAME), wave=wave, rec=rec, q=q, M=M, cfo=cfo_bins * psk.F_LOOP,
             sro=extra / psk.NSYM * 1e6, source=L.source, eye_t=tau, eye=eye[:250],
             **{k: r[k] for k in ("times", "period", "ted", "zs", "zc", "phi", "w", "ec", "naive",
                                  "errs", "nbits", "mer", "rot", "starts", "sps")})
d = np.load(link.data_path(NAME))
M, R = int(d["M"]), psk.NSYM * psk.F_LOOP
src = str(d["source"])
print("%s: %d errors in %d bits, MER %.1f dB" % (src, d["errs"], d["nbits"], d["mer"]))

# ---- the transmitted signal ---------------------------------------------------------
fig, ax = plt.subplots(3, 1, figsize=(8, 7.4), gridspec_kw=dict(height_ratios=[1, 1, 1.1]))
q = d["q"]; nsym = len(q)
t_us = np.arange(psk.N) / psk.FS_DAC * 1e6
k0, k1 = 40, 45                                         # five symbols
sel = (t_us >= k0 / (nsym * psk.F_LOOP) * 1e6) & (t_us < k1 / (nsym * psk.F_LOOP) * 1e6)
u = np.arange(psk.N)
t_sym = u * nsym / psk.N
env = np.zeros(psk.N, complex)
for j in range(-8, 9):
    k = np.floor(t_sym).astype(int) + j
    env += psk.point(q[k % nsym], M) * psk.rrc(t_sym - k)
env /= psk.rrc(0)
ax[0].plot(t_us[sel], env.real[sel], color=C1, label="I")
ax[0].plot(t_us[sel], env.imag[sel], color=C2, label="Q")
ks = np.arange(k0, k1)
ts = ks / (nsym * psk.F_LOOP) * 1e6
dots(ax[0], ts, psk.point(q[ks], M).real, C1)
dots(ax[0], ts, psk.point(q[ks], M).imag, C2)
for k, t in zip(ks, ts):
    b = psk.q_to_bits([q[k]], M)
    ax[0].annotate("%d%d" % tuple(b), (t, 1.25), ha="center", fontsize=8, color=INK2)
ax[0].set_ylim(-1.5, 1.5); ax[0].set_ylabel("envelope (symbol units)")
ax[0].set_title("Five QPSK symbols (dots, with their bits) as root-raised-cosine pulses:\nthe sum passes near each symbol, not through it, until the receiver's matched filter")
ax[0].legend(loc="lower right", ncol=2)
w = d["wave"]
ax[1].plot(t_us[sel], w[sel], color=MUTED, lw=0.6)
dots(ax[1], t_us[sel], w[sel], C1, size=2.5)
ax[1].set_xlabel("time (µs)"); ax[1].set_ylabel("DAC code")
ax[1].set_title("I on cos, Q on −sin, at 6.25 MHz: what the DAC plays (8 samples per cycle)")
for a_ in ax[:2]:
    a_.set_xlim(t_us[sel][0], t_us[sel][-1])
rec = d["rec"].astype(float)
x = rec - rec.mean()
win = np.hanning(len(x))
X = np.abs(np.fft.rfft(x * win)) / (win.sum() / 2)
f = np.fft.rfftfreq(len(x), 1 / psk.FS_ADC) / 1e6
ax[2].plot(f, 20 * np.log10(X + 1e-4), color=C1, lw=0.6)
for edge in (psk.F_C - (1 + psk.ALPHA) * R / 2, psk.F_C + (1 + psk.ALPHA) * R / 2):
    ax[2].axvline(edge / 1e6, color=C2, lw=0.8, ls="--")
ax[2].set_xlim(0, 12.5); ax[2].set_ylim(-80, 10)
ax[2].set_xlabel("frequency (MHz)"); ax[2].set_ylabel("amplitude (dB re 1 code)")
ax[2].set_title("What the ADC records: 6.25 ± 1.05 MHz wide (dashed: ± (1 + 0.35) × 1.5625 / 2)")
fig.suptitle(src, x=0.99, ha="right", fontsize=8, color=MUTED)
save(fig, link.img_path("psk_wave"))

# ---- the loops ------------------------------------------------------------------------
fig, ax = plt.subplots(3, 3, figsize=(11, 9.6))
k = np.arange(len(d["zc"]))
us = k / R * 1e6
skip = 400
zn = d["naive"] / np.sqrt(np.mean(np.abs(d["naive"])**2))
ax[0, 0].plot(zn.real, zn.imag, ".", color=C1, markersize=2)
ax[0, 0].set_title("Before: every 16th sample")
zr = d["zc"] * np.exp(-2j * np.pi * d["rot"][-1] / M)
ax[0, 1].plot(zr[:skip].real, zr[:skip].imag, ".", color=MUTED, markersize=2, label="first %d symbols" % skip)
ax[0, 1].plot(zr[skip:].real, zr[skip:].imag, ".", color=C1, markersize=2, label="after")
ax[0, 1].set_title("After: %d errors in %d bits" % (d["errs"], d["nbits"]))
ax[0, 1].legend(loc="center", fontsize=7, markerscale=3)
for a_ in ax[0, :2]:
    a_.set_aspect("equal"); a_.set_xlim(-1.7, 1.7); a_.set_ylim(-1.7, 1.7)
    a_.set_xlabel("I"); a_.set_ylabel("Q")
for tr in d["eye"]:
    ax[0, 2].plot(d["eye_t"], tr.real, color=C1, lw=0.3, alpha=0.35)
ax[0, 2].set_xlabel("time from symbol centre (symbols)"); ax[0, 2].set_ylabel("I")
ax[0, 2].set_title("Eye, after the matched filter")
# timing loop
dt = d["times"] - d["sps"] * k
ax[1, 0].plot(us, dt - dt[0], color=C1, lw=1)
ax[1, 0].set_ylabel("sampling point moved (samples)")
ax[1, 0].set_title("Timing loop: where it samples")
ax[1, 1].plot(us, (d["sps"] / d["period"] - 1) * 1e6, color=C1, lw=0.8)
ax[1, 1].axhline(float(d["sro"]), color=C2, ls="--", lw=1, label="sent: %+.0f ppm" % d["sro"])
ax[1, 1].set_ylabel("symbol-rate offset found (ppm)"); ax[1, 1].legend(loc="lower right")
ax[1, 1].set_title("... and the symbol rate it learns")
ax[1, 2].plot(us, d["ted"], ".", color=C1, markersize=1.5)
ax[1, 2].set_ylabel("Gardner error"); ax[1, 2].set_ylim(-1.5, 1.5)
ax[1, 2].set_title("Gardner detector, each symbol")
# Costas loop
ax[2, 0].plot(us, np.degrees(d["phi"]), color=C1, lw=1)
ax[2, 0].set_ylabel("phase correction (degrees)")
ax[2, 0].set_title("Costas loop: how far it turns")
ax[2, 1].plot(us, d["w"] * R / (2 * np.pi) / 1e3, color=C1, lw=0.8)
ax[2, 1].axhline(float(d["cfo"]) / 1e3, color=C2, ls="--", lw=1, label="sent: %+.0f Hz" % d["cfo"])
ax[2, 1].set_ylabel("carrier offset found (kHz)"); ax[2, 1].legend(loc="lower right")
ax[2, 1].set_title("... and the frequency it learns")
ax[2, 2].plot(us, d["ec"], ".", color=C1, markersize=1.5)
ax[2, 2].set_ylabel("Costas error (rad)"); ax[2, 2].set_ylim(-0.8, 0.8)
ax[2, 2].set_title("Costas detector, each symbol")
for a_ in ax[1:, :].ravel():
    a_.set_xlabel("time (µs)")
    a_.axvspan(0, skip / R * 1e6, color=MUTED, alpha=0.08, lw=0)
fig.suptitle(src, x=0.99, ha="right", fontsize=8, color=MUTED)
save(fig, link.img_path("psk_loops"))
