"""Chapter 6 figure: bit error rate against Eb/N0 for QPSK, 8PSK, 16-QAM and 64-QAM
(qam.py --ber), measured against theory, and what each extra bit per symbol costs.

comms_qam_ber.png
  left:  BER against Eb/N0, measured (noise added at the transmitter) and the exact
         Gray-coded theory curves
  right: bits per symbol against the Eb/N0 each needs for a BER of 1e-4, from theory
         and from the measurements (interpolated), with Shannon's limit for the same
         bits per symbol (6.08)

    python3 fig_qam_ber.py --sim | PORT | PORT_A PORT_B | --replot
"""
import types
import numpy as np
import link
from plotstyle import plt, save, C1, C2, C3, MUTED, INK2
import qam

NAME = "qam_ber"
RANGES = {4: (0, 11), 8: (2, 14), 16: (3, 15), 64: (7, 20)}
C4 = "#8e5bd4"
STYLE = {4: (C3, "o"), 8: (C4, "D"), 16: (C2, "s"), 64: (C1, "^")}
a = link.args(__doc__, lambda ap: ap.add_argument("--records", type=int, default=40,
                                                  help="at most this many uploads per point"))
if not a.replot:
    L = link.Link(a)
    rng = np.random.default_rng(3)
    out = {"source": L.source}
    opts = types.SimpleNamespace(sro=0, cfo=0, amp=None, bnt_timing=0.01, bnt_carrier=0.02, skip=400)
    for M, (lo, hi) in RANGES.items():
        rows = []
        for eb in range(lo, hi + 1):
            e = nb = 0
            for i in range(a.records):
                r = qam.run_once(opts, M, L.play, L.record, start=int(rng.integers(0, 1023)),
                                 ebn0=float(eb), rng=rng)
                e += r["errs"]; nb += r["nbits"]
                if e >= 200 and i >= 2:
                    break
            rows.append((eb, e, nb))
            print("%-6s %4.1f dB: %5d errors in %6d bits  (BER %.2e, theory %.2e)"
                  % (qam.name_of(M), eb, e, nb, e / nb, qam.ber_theory(eb, M)), flush=True)
        out["ber%d" % M] = np.array(rows)
    np.savez(link.data_path(NAME), **out)
d = np.load(link.data_path(NAME))
src = str(d["source"])


def ebn0_measured(rows, target=1e-4):
    """Where the measured BER crosses `target`: linear in log(BER), between the points."""
    ok = rows[:, 1] > 0
    x, y = rows[ok, 0], np.log10(rows[ok, 1] / rows[ok, 2])
    for i in range(len(x) - 1):
        if y[i] >= np.log10(target) >= y[i + 1]:
            return x[i] + (y[i] - np.log10(target)) / (y[i] - y[i + 1]) * (x[i + 1] - x[i])
    return np.nan


fig = plt.figure(figsize=(10, 5))
gs = fig.add_gridspec(1, 2, width_ratios=[1.6, 1])
ax = fig.add_subplot(gs[0])
x = np.linspace(0, 20, 300)
need, meas = {}, {}
for M in (4, 8, 16, 64):
    c, m = STYLE[M]
    ax.semilogy(x, [qam.ber_theory(v, M) for v in x], color=c, lw=1.1, alpha=0.6)
    rows = d["ber%d" % M]
    ok = rows[:, 1] > 0
    ax.semilogy(rows[ok, 0], rows[ok, 1] / rows[ok, 2], m, color=c, markersize=5,
                label="%s, %.2g Mbit/s" % (qam.name_of(M), 1.5625 * np.log2(M)))
    for r_ in rows[~ok]:
        ax.semilogy(r_[0], 1 / r_[2], "v", color=c, mfc="none", markersize=5)
    need[M] = qam.ebn0_for(1e-4, M)
    meas[M] = ebn0_measured(rows)
ax.axhline(1e-4, color=MUTED, lw=0.6, ls=":")
ax.set_xlabel("Eb/N0 (dB): energy per bit / noise power per hertz")
ax.set_ylabel("bit error rate")
ax.set_ylim(1e-5, 0.5); ax.set_xlim(-0.3, 20.3)
ax.grid(True, which="both", alpha=0.6)
ax.set_title("Bit errors with noise added at the transmitter\n(lines: exact theory, Gray-coded; open triangles: no errors seen)")
ax.legend(loc="lower left", fontsize=8)

bx = fig.add_subplot(gs[1])
ks = np.linspace(1, 6.5, 100)
bx.plot(qam.shannon_ebn0(ks), ks, color=MUTED, lw=1, ls="--", label="Shannon's limit (6.08)")
for M in (4, 8, 16, 64):
    c, m = STYLE[M]
    k = np.log2(M)
    bx.plot(need[M], k, m, color=c, markersize=7, mfc="none", mew=1.5)
    if not np.isnan(meas[M]):
        bx.plot(meas[M], k, m, color=c, markersize=6)
    bx.annotate("%s\n%.1f dB" % (qam.name_of(M), need[M]), (need[M], k), (8, -4), textcoords="offset points",
                fontsize=8, color=INK2)
bx.plot([], [], "o", color=INK2, mfc="none", label="theory, BER 1e-4")
bx.plot([], [], "o", color=INK2, label="measured, BER 1e-4")
bx.plot([need[4], need[16]], [2.3, 2.3], color=C2, lw=0.8)
bx.annotate("+%.1f dB for 2 more bits" % (need[16] - need[4]), ((need[4] + need[16]) / 2, 2.4), ha="center",
            fontsize=8, color=C2)
bx.plot([need[4], need[64]], [1.5, 1.5], color=C1, lw=0.8)
bx.annotate("+%.1f dB for 4 more bits" % (need[64] - need[4]), ((need[4] + need[64]) / 2, 1.6), ha="center",
            fontsize=8, color=C1)
bx.set_xlabel("Eb/N0 needed for a bit error rate of 1e-4 (dB)")
bx.set_ylabel("bits per symbol")
bx.set_xlim(0, 20); bx.set_ylim(1, 7); bx.set_yticks([1, 2, 3, 4, 5, 6])
bx.set_title("The cost of each extra bit")
bx.legend(loc="upper left", fontsize=8)
fig.suptitle(src, x=0.99, ha="right", fontsize=8, color=MUTED)
save(fig, link.img_path(NAME))
print("saved", link.img_path(NAME))
for M in (4, 8, 16, 64):
    print("%-6s needs %.2f dB (theory) %s for BER 1e-4" % (qam.name_of(M), need[M],
          "" if np.isnan(meas[M]) else ", measured %.2f dB" % meas[M]))
