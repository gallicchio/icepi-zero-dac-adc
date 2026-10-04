"""Chapter 6 figure: 8PSK, 16-QAM and 64-QAM through the cable (qam.py).

comms_qam.png
  top:    the received constellations after the loops, with the Gray-coded bits written
          on 16-QAM's points; MER in each title
  bottom: left, the rings of |z| for 16-QAM and 64-QAM against the constellation's radii
          (the AGC's check); middle, two carrier phase detectors on the 16-QAM symbols
          against phase error: the decision-directed one and the classic polarity
          (sign(I) Q - sign(Q) I) one, averages and one symbol's spread; right, MER
          against the DAC waveform's rms for QPSK, 16-QAM and 64-QAM: quantisation
          noise at the bottom, the loops' jitter in the middle, clipping at the top

    python3 fig_qam.py --sim | PORT | PORT_A PORT_B | --replot
"""
import types
import numpy as np
import link
from plotstyle import plt, save, C1, C2, C3, MUTED, INK2
import qam

NAME = "qam"
AMPS = (2, 3, 4.5, 7, 10, 15, 22, 33, 50, 70, 90)
a = link.args(__doc__)
if not a.replot:
    L = link.Link(a)
    out = {"source": L.source}
    opts = types.SimpleNamespace(sro=0, cfo=0, amp=None, bnt_timing=0.01, bnt_carrier=0.02, skip=400)
    for M in (8, 16, 64):
        r = qam.run_once(opts, M, L.play, L.record)
        out["z%d" % M] = r["z"]; out["mer%d" % M] = r["mer"]; out["errs%d" % M] = r["errs"]
        out["nbits%d" % M] = r["nbits"]; out["papr%d" % M] = r["papr"]
        print("%s: %d errors in %d bits, MER %.1f dB, PAPR %.1f dB" % (qam.name_of(M), r["errs"], r["nbits"],
                                                                      r["mer"], r["papr"]), flush=True)
    # the two phase detectors on the 16-QAM symbols
    z = out["z16"]
    th = np.radians(np.arange(-45, 46, 1.5))
    dd_m, dd_s, pol_m, pol_s = [], [], [], []
    for x in th:
        zr = z * np.exp(1j * x)
        d = qam.point(qam.decide(zr, 16), 16)
        e = np.imag(zr * np.conj(d))
        p = np.sign(zr.real) * zr.imag - np.sign(zr.imag) * zr.real
        dd_m.append(e.mean()); dd_s.append(e.std()); pol_m.append(p.mean()); pol_s.append(p.std())
    out.update(th=np.degrees(th), dd_m=dd_m, dd_s=dd_s, pol_m=pol_m, pol_s=pol_s)
    # MER against the DAC's rms
    for M in (4, 16, 64):
        rows = []
        for amp in AMPS:
            o = types.SimpleNamespace(sro=0, cfo=0, amp=amp, bnt_timing=0.01, bnt_carrier=0.02, skip=400)
            r = qam.run_once(o, M, L.play, L.record)
            rows.append((amp, r["mer"], r["clipped"], r["errs"]))
        out["sweep%d" % M] = np.array(rows)
        print("%s: best MER %.1f dB at rms %.0f codes" % (qam.name_of(M), max(x[1] for x in rows),
                                                          max(rows, key=lambda x: x[1])[0]), flush=True)
    np.savez(link.data_path(NAME), **out)
d = np.load(link.data_path(NAME))
src = str(d["source"])

fig, ax = plt.subplots(2, 3, figsize=(10, 7.2))
for a_, M in zip(ax[0], (8, 16, 64)):
    z = d["z%d" % M]
    a_.plot(z.real, z.imag, ".", color=C1, markersize=2.2 if M < 64 else 1.6, alpha=0.8)
    if M == 16:
        for q, p in enumerate(qam.POINTS[M]):
            a_.annotate(format(q, "04b"), (p.real, p.imag + 0.13), ha="center", va="bottom", fontsize=7.5,
                        color=INK2)
    a_.set_aspect("equal"); a_.set_xlim(-1.75, 1.75); a_.set_ylim(-1.75, 1.75)
    a_.set_xticks([-1, 0, 1]); a_.set_yticks([-1, 0, 1])
    a_.set_xlabel("I"); a_.set_ylabel("Q")
    a_.set_title("%s\n%d errors in %d bits, MER %.1f dB" % (qam.name_of(M), d["errs%d" % M], d["nbits%d" % M],
                                                            d["mer%d" % M]), fontsize=9.5)
# rings
a_ = ax[1, 0]
for M, c, off in ((16, C2, 0), (64, C1, 0)):
    z = d["z%d" % M]
    a_.hist(np.abs(z), bins=np.linspace(0, 1.75, 141), color=c, alpha=0.75, label=qam.name_of(M), lw=0)
    for rr in np.unique(np.round(np.abs(qam.POINTS[M]), 6)):
        a_.axvline(rr, color=c, lw=0.7, ls="--", alpha=0.8)
a_.set_xlabel("|z| after the AGC"); a_.set_ylabel("symbols")
a_.set_title("The rings of |z|: dashed, the radii\nthe constellation should have", fontsize=9.5)
a_.legend(loc="upper left", fontsize=8)
# detectors
a_ = ax[1, 1]
th = d["th"]
for m, s, c, lab in ((d["dd_m"], d["dd_s"], C1, "decision-directed, Im(z d*)"),
                     (d["pol_m"], d["pol_s"], C2, "polarity, sign(I) Q − sign(Q) I")):
    a_.fill_between(th, np.array(m) - s, np.array(m) + s, color=c, alpha=0.12, lw=0)
    a_.plot(th, m, color=c, lw=1.4, label=lab)
a_.axhline(0, color=MUTED, lw=0.6); a_.axvline(0, color=MUTED, lw=0.6)
a_.set_xlabel("phase error (degrees)"); a_.set_ylabel("detector output (rad)")
a_.set_xticks([-45, -30, -15, 0, 15, 30, 45]); a_.set_ylim(-1.25, 1.25)
a_.set_title("Two phase detectors on 16-QAM:\naverage (line), one symbol's spread (band)", fontsize=9.5)
a_.legend(loc="upper left", fontsize=7.5)
# amplitude sweep
a_ = ax[1, 2]
for M, c, m in ((4, C3, "o"), (16, C2, "s"), (64, C1, "^")):
    s = d["sweep%d" % M]
    a_.semilogx(s[:, 0], s[:, 1], m + "-", color=c, markersize=4.5, lw=1.2,
                label="%s, PAPR %.1f dB" % (qam.name_of(M), d["papr%d" % M]) if M != 4 else "QPSK, PAPR 6.7 dB")
    clip = 127 / 10**(float(d["papr%d" % M]) / 20) if M != 4 else 127 / 10**(6.7 / 20)
    a_.axvline(clip, color=c, lw=0.7, ls=":")
x = np.array(AMPS[:4])
a_.semilogx(x, 22.2 + 20 * np.log10(x / 2), color=MUTED, lw=0.8, ls="--")
a_.annotate("6 dB per\ndoubling", (4.8, 21), fontsize=8, color=MUTED)
a_.annotate("the loops'\njitter", (14, 41.3), fontsize=8, color=MUTED)
a_.annotate("clipping", (62, 24), fontsize=8, color=MUTED)
a_.set_xlabel("DAC rms (codes; dotted: peaks reach 127)")
a_.set_ylabel("MER (dB)"); a_.set_ylim(18, 44)
a_.set_xticks([2, 5, 10, 20, 50, 100]); a_.set_xticklabels(["2", "5", "10", "20", "50", "100"])
a_.set_title("MER against the DAC's amplitude:\n8 bits, from quantisation to clipping", fontsize=9.5)
a_.legend(loc="upper left", fontsize=7.5)
fig.suptitle(src, x=0.99, ha="right", fontsize=8, color=MUTED)
save(fig, link.img_path(NAME))
print("saved", link.img_path(NAME))
