"""Chapter 6 figure: what the loops' detectors say, against the error they measure.

comms_detectors.png
  left:  timing detectors against timing error, averaged over a record, with the
         symbol-to-symbol spread: Gardner's (psk.py), and learnSDR lesson 18's x * dx/dt
         (GNU Radio's "maximum likelihood" detector).  Lines: theory, for raised-cosine
         pulses.  Both average to a straight line through zero although each symbol's
         value scatters widely: the scatter is the data pattern, and it averages away.
  right: Costas phase detectors against phase error: BPSK's is zero, and pushes back
         towards zero, every 180 degrees, QPSK's every 90: the loop can lock at any of
         those, the "phase ambiguity".

    python3 fig_detectors.py --sim | PORT | PORT_A PORT_B | --replot
"""
import numpy as np
import link
from plotstyle import plt, save, C1, C2, C3, MUTED
import psk

NAME = "detectors"
a = link.args(__doc__)
if not a.replot:
    L = link.Link(a)
    out = {"source": L.source}
    for M in (2, 4):
        q, data = psk.make_frame(M)
        L.play(psk.transmit(q, M))
        rec = L.record()
        r = psk.receive(rec, M, psk.NSYM, q)
        y, sps = r["y"], r["sps"]
        # the right sampling instants, from the converged timing loop and Costas loop
        t_end = r["times"][-1]
        k = np.arange(50, int((t_end - 50) / sps) - 50)
        t_ok = t_end - sps * (k[-1] - k)                    # a grid ending at the last instant
        rot = np.exp(-1j * (r["phi"][-1] + 2 * np.pi * r["rot"][-1] / M))
        yy = y * rot / np.sqrt(np.mean(np.abs(r["zs"])**2))
        offs = np.linspace(-0.5, 0.5, 41) * sps            # timing errors, samples
        g_mean, g_std, m_mean, m_std = [], [], [], []
        for o in offs:
            t = t_ok + o
            now, prev, mid = (psk.channel.cubic(yy, t), psk.channel.cubic(yy, t - sps),
                              psk.channel.cubic(yy, t - sps / 2))
            g = np.real(np.conj(mid) * (now - prev))         # Gardner
            dy = (psk.channel.cubic(yy, t + 0.5) - psk.channel.cubic(yy, t - 0.5))   # per sample
            ml = np.real(np.conj(now) * dy) * sps            # x dx/dt, per symbol
            g_mean.append(g.mean()); g_std.append(g.std()); m_mean.append(ml.mean()); m_std.append(ml.std())
        zc = r["zc"][400:] * np.exp(-2j * np.pi * r["rot"][-1] / M)
        th = np.radians(np.arange(-180, 181, 2))
        dd = [np.mean(np.imag(zc * np.exp(1j * x) * np.conj(psk.point(psk.decide(zc * np.exp(1j * x), M), M))))
              for x in th]
        iq = [np.mean((zc * np.exp(1j * x)).real * (zc * np.exp(1j * x)).imag) for x in th]
        out.update({"offs%d" % M: offs / sps, "g_mean%d" % M: g_mean, "g_std%d" % M: g_std,
                    "m_mean%d" % M: m_mean, "m_std%d" % M: m_std, "th%d" % M: np.degrees(th),
                    "dd%d" % M: dd, "iq%d" % M: iq})
    np.savez(link.data_path(NAME), **out)
d = np.load(link.data_path(NAME))

# theory for raised-cosine pulses, unit-power symbols
x = np.linspace(-0.5, 0.5, 201)
j = np.arange(-30, 31)
g_th = [np.sum(psk.rc(j - 0.5 + s) * (psk.rc(j + s) - psk.rc(j - 1 + s))) for s in x]
h = 1e-4
ml_th = [np.sum(psk.rc(j + s) * (psk.rc(j + s + h) - psk.rc(j + s - h)) / (2 * h)) for s in x]

fig, ax = plt.subplots(1, 2, figsize=(10, 4.2))
o = d["offs4"]
for mean, std, th, c, lab in ((d["g_mean4"], d["g_std4"], g_th, C1, "Gardner (+ = late)"),
                               (d["m_mean4"], d["m_std4"], ml_th, C2, "x · dx/dt, lesson 18 (+ = early)")):
    ax[0].fill_between(o, np.array(mean) - std, np.array(mean) + std, color=c, alpha=0.10, lw=0)
    ax[0].plot(x, th, color=c, lw=1.2)
    ax[0].plot(o, mean, "o", color=c, markersize=3.5, label=lab)
ax[0].axhline(0, color=MUTED, lw=0.6); ax[0].axvline(0, color=MUTED, lw=0.6)
ax[0].set_xlabel("timing error (symbols; + = sampling late)")
ax[0].set_ylabel("detector output (average)")
ax[0].set_title("Timing detectors: average (dots; lines: theory)\nand one symbol's spread (bands)")
ax[0].legend(loc="upper left", fontsize=8)
for M, c, lab in ((2, C1, "BPSK"), (4, C2, "QPSK")):
    ax[1].plot(d["th%d" % M], d["dd%d" % M], color=c, label=lab + ": Im(z · nearest point*)")
ax[1].plot(d["th2"], d["iq2"], color=C3, lw=1, ls="--", label="BPSK: I × Q (Costas's original)")
for lock in (-180, 0, 180):
    ax[1].plot(lock, 0, "o", color=C1, markersize=7, mfc="none")
for lock in (-90, 90):
    ax[1].plot(lock, 0, "o", color=C2, markersize=7, mfc="none")
ax[1].axhline(0, color=MUTED, lw=0.6)
ax[1].set_xticks(np.arange(-180, 181, 45))
ax[1].set_xlabel("phase error (degrees)"); ax[1].set_ylabel("detector output (average, rad)")
ax[1].set_title("Costas phase detectors: the loop can lock\nwherever they cross zero going up (circles)")
ax[1].legend(loc="lower left", fontsize=8)
fig.suptitle(str(d["source"]), x=0.99, ha="right", fontsize=8, color=MUTED)
save(fig, link.img_path(NAME))
print("Gardner slope at 0: measured %.2f, theory %.2f per symbol"
      % (np.polyfit(o[18:23], d["g_mean4"][18:23], 1)[0], np.polyfit(x[95:106], g_th[95:106], 1)[0]))
