"""Chapter 6 figure: bit error rate against Eb/N0, BPSK and QPSK, with noise added at the
transmitter (psk.py --ber), and QPSK's constellation at three noise levels.

comms_psk_ber.png

Each upload carries fresh data and a fresh noise waveform; the loops settle for 400
symbols and then one loop's worth of symbols is counted (the noise repeats every loop).

    python3 fig_psk_ber.py --sim | PORT | PORT_A PORT_B | --replot
"""
import types
import numpy as np
import link
from plotstyle import plt, save, C1, C2, C3, MUTED
import psk

NAME = "psk_ber"
EBN0 = np.arange(0, 10)
SHOW = (2, 6, 10)                                   # constellations at these Eb/N0
a = link.args(__doc__, lambda ap: ap.add_argument("--records", type=int, default=40,
                                                  help="at most this many uploads per point"))
if not a.replot:
    L = link.Link(a)
    rng = np.random.default_rng(3)
    out = {"source": L.source}
    for key, M, diff in (("bpsk", 2, False), ("qpsk", 4, False), ("dqpsk", 4, True)):
        opts = types.SimpleNamespace(sro=0, cfo=0, diff=diff, bnt_timing=0.01, bnt_carrier=0.02, skip=400)
        rows = []
        for eb in EBN0:
            e = nb = 0
            for i in range(a.records):
                r = psk.run_once(opts, M, L.play, L.record, start=int(rng.integers(0, 1023)),
                                 ebn0=float(eb), rng=rng)
                e += r["errs"]; nb += r["nbits"]
                if e >= 200 and i >= 2:
                    break
            rows.append((eb, e, nb))
            print("%s %4.1f dB: %5d errors in %6d bits  (BER %.2e, theory %.2e)"
                  % (key, eb, e, nb, e / nb, psk.ber_theory(eb, diff)), flush=True)
        out[key] = np.array(rows)
    opts = types.SimpleNamespace(sro=0, cfo=0, diff=False, bnt_timing=0.01, bnt_carrier=0.02, skip=400)
    for eb in SHOW:
        r = psk.run_once(opts, 4, L.play, L.record, ebn0=float(eb), rng=rng)
        out["z%d" % eb] = r["zc"][400:] * np.exp(-2j * np.pi * r["rot"][-1] / 4)
        out["mer%d" % eb] = r["mer"]
    np.savez(link.data_path(NAME), **out)
d = np.load(link.data_path(NAME))

fig = plt.figure(figsize=(10, 5.2))
gs = fig.add_gridspec(3, 2, width_ratios=[2.2, 1])
ax = fig.add_subplot(gs[:, 0])
x = np.linspace(0, 10, 200)
ax.semilogy(x, [psk.ber_theory(v) for v in x], color=MUTED, lw=1.2, label="theory: BPSK and Gray-coded QPSK")
ax.semilogy(x, [psk.ber_theory(v, True) for v in x], color=MUTED, lw=1.2, ls="--",
            label="theory: with differential coding, 2p(1 − p)")
for key, c, m, lab in (("bpsk", C1, "o", "BPSK, 1.56 Mbit/s"), ("qpsk", C2, "s", "QPSK, 3.13 Mbit/s"),
                       ("dqpsk", C3, "^", "QPSK, differential")):
    rows = d[key]
    ok = rows[:, 1] > 0
    ax.semilogy(rows[ok, 0], rows[ok, 1] / rows[ok, 2], m, color=c, label=lab, markersize=5)
    for r_ in rows[~ok]:                                     # no errors: an upper limit
        ax.semilogy(r_[0], 1 / r_[2], "v", color=c, mfc="none", markersize=5)
ax.set_xlabel("Eb/N0 (dB): energy per bit / noise power per hertz")
ax.set_ylabel("bit error rate")
ax.set_ylim(1e-5, 0.5); ax.set_xlim(-0.3, 10.3)
ax.grid(True, which="both", alpha=0.6)
ax.set_title("Bit errors with noise added at the transmitter\n(open triangles: no errors; the BER is below 1 / bits counted)")
ax.legend(loc="lower left", fontsize=8)
for i, eb in enumerate(SHOW):
    b = fig.add_subplot(gs[i, 1])
    z = d["z%d" % eb]
    b.plot(z.real, z.imag, ".", color=C2, markersize=1.5)
    b.set_aspect("equal"); b.set_xlim(-2, 2); b.set_ylim(-2, 2)
    b.set_xticks([-1, 0, 1]); b.set_yticks([-1, 0, 1])
    b.set_title("QPSK, %d dB: MER %.1f dB" % (eb, d["mer%d" % eb]), fontsize=9)
fig.suptitle(str(d["source"]), x=0.99, ha="right", fontsize=8, color=MUTED)
save(fig, link.img_path(NAME))
