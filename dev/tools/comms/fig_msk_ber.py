"""Chapter 6 figure: bit error rate against Eb/N0 for MSK and GMSK (msk.py --ber), with
noise added at the transmitter: the coherent receiver with and without precoding, the
discriminator, and GMSK at BT 0.5 and 0.3 through the same (half-sine) receiver.

comms_msk_ber.png

Each upload carries fresh data and a fresh noise waveform; the loops settle for 400
bits and then one loop's worth of bits is counted (the noise repeats every loop).

    python3 fig_msk_ber.py --sim | PORT | PORT_A PORT_B | --replot
"""
import types
import numpy as np
import link
from plotstyle import plt, save, C1, C2, C3, MUTED, INK2
import psk
import msk

NAME = "msk_ber"
EBN0 = np.arange(0, 11)
CURVES = (("msk", dict(bt=None, disc=False, raw=False), C1, "o", "MSK, coherent (precoded)"),
          ("msk_raw", dict(bt=None, disc=False, raw=True), C1, "s", "MSK, coherent, data = slopes (no precoding)"),
          ("msk_disc", dict(bt=None, disc=True, raw=False), C2, "o", "MSK, discriminator"),
          ("gmsk05", dict(bt=0.5, disc=False, raw=False), C3, "^", "GMSK BT 0.5, coherent, half-sine filter"),
          ("gmsk03", dict(bt=0.3, disc=False, raw=False), "#c0392b", "v", "GMSK BT 0.3, coherent, half-sine filter"),
          ("gmsk03_disc", dict(bt=0.3, disc=True, raw=False), "#c0392b", "x", "GMSK BT 0.3, discriminator"))
a = link.args(__doc__, lambda ap: ap.add_argument("--records", type=int, default=40,
                                                  help="at most this many uploads per point"))
if not a.replot:
    L = link.Link(a)
    rng = np.random.default_rng(3)
    out = {"source": L.source}
    for key, kw, c, m, lab in CURVES:
        opts = types.SimpleNamespace(h=0.5, limit=None, cfo=0, sro=0, bnt_timing=0.01, bnt_carrier=0.02,
                                     skip=400, acquire=True, **kw)
        rows = []
        for eb in EBN0:
            e = nb = 0
            for i in range(a.records):
                r = msk.run_once(opts, L.play, L.record, start=int(rng.integers(0, 1023)),
                                 ebn0=float(eb), rng=rng)
                e += r["errs"]; nb += r["nbits"]
                if e >= 200 and i >= 2:
                    break
            rows.append((eb, e, nb))
            print("%-12s %4.1f dB: %5d errors in %6d bits  (BER %.2e, BPSK theory %.2e)"
                  % (key, eb, e, nb, e / nb, psk.ber_theory(eb)), flush=True)
        out[key] = np.array(rows)
    np.savez(link.data_path(NAME), **out)
d = np.load(link.data_path(NAME))

fig, ax = plt.subplots(figsize=(10, 6))
x = np.linspace(0, 10.5, 200)
ax.semilogy(x, [psk.ber_theory(v) for v in x], color=MUTED, lw=1.2, label="theory: coherent BPSK, Q(√(2 Eb/N0))")
ax.semilogy(x, [psk.ber_theory(v, True) for v in x], color=MUTED, lw=1.2, ls="--", label="theory: twice that (one wrong node, two wrong slopes)")
ax.semilogy(x, 0.5 * np.exp(-10**(x / 10) / 2), color=MUTED, lw=1.2, ls=":", label="theory: non-coherent FSK, ½ exp(−Eb/2N0)")
for key, kw, c, m, lab in CURVES:
    rows = d[key]
    ok = rows[:, 1] > 0
    ax.semilogy(rows[ok, 0], rows[ok, 1] / rows[ok, 2], m, color=c, label=lab, markersize=6,
                mfc="none" if "disc" in key else c)
    for r_ in rows[~ok]:                                     # no errors: an upper limit
        ax.semilogy(r_[0], 1 / r_[2], "v", color=c, mfc="none", markersize=5)
ax.set_xlabel("Eb/N0 (dB): energy per bit / noise power per hertz")
ax.set_ylabel("bit error rate")
ax.set_ylim(1e-5, 0.5); ax.set_xlim(-0.3, 10.5)
ax.grid(True, which="both", alpha=0.6)
ax.set_title("Bit errors with noise added at the transmitter, 1.5625 Mbit/s\n(open triangles: no errors, the BER is below 1 / bits counted)")
ax.legend(loc="lower left", fontsize=8)
fig.suptitle(str(d["source"]), x=0.99, ha="right", fontsize=8, color=MUTED)
save(fig, link.img_path(NAME))

# the penalties at BER 1e-2, by interpolation of log BER against Eb/N0
def at(rows, target=1e-2):
    ok = rows[:, 1] > 0
    eb, ber = rows[ok, 0], rows[ok, 1] / rows[ok, 2]
    i = np.where((ber[:-1] >= target) & (ber[1:] < target))[0]
    if len(i) == 0:
        return float("nan")
    i = i[0]
    return eb[i] + (np.log10(ber[i]) - np.log10(target)) / (np.log10(ber[i]) - np.log10(ber[i + 1])) * (eb[i + 1] - eb[i])
th = at(np.array([(v, psk.ber_theory(v) * 1e6, 1e6) for v in np.arange(0, 11, 0.25)]))
print("Eb/N0 for BER 1e-2: BPSK theory %.2f dB" % th)
for key, kw, c, m, lab in CURVES:
    v = at(d[key])
    print("  %-42s %.2f dB  (%+.2f dB)" % (lab, v, v - th))
