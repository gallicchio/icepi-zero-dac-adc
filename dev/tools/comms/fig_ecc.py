"""Chapter 6 figure: error-correcting codes on QPSK through the cable (ecc.py).

comms_ecc.png   left: bit error rate per INFORMATION bit against Eb/N0, uncoded against
                Hamming(7,4) (hard and soft decisions) and the K = 7 convolutional code
                with Viterbi decoding (hard and soft), with the coding gains at 1e-4;
                top right: a Viterbi decoder at work on the small K = 3 code, every path
                metric; bottom right: a 40-symbol dropout, with and without an interleaver.

Each frame carries fresh information bits and a fresh noise waveform; a point stops
after 100 errors for every decoder, or after --records frames.  In --sim the whole
sweep is about 5500 frames, eight or nine minutes.

    python3 fig_ecc.py --sim | PORT | PORT_A PORT_B | --replot
    python3 fig_ecc.py PORT --records 100           # a quicker sweep on the board
"""
import math
import numpy as np
import link
from plotstyle import plt, save, C1, C2, INK, INK2, MUTED, SURFACE
import ecc
import psk

NAME = "ecc"
BURST = 40
a = link.args(__doc__, lambda ap: (ap.add_argument("--records", type=int, default=300, help="at most this many frames per point"),
                                   ap.add_argument("--errors", type=int, default=100, help="stop a point after this many errors")))
if not a.replot:
    L = link.Link(a)
    out = {"source": L.source}
    ranges = {"uncoded": np.arange(0, 10.0), "hamming": np.arange(0, 10.0),
              "conv": np.array([0, 1, 2, 3, 3.5, 4, 4.5, 5, 5.5, 6, 7.0])}
    for key, ebs in ranges.items():
        res, raw = ecc.ber_run(L.play, L.record, ebs, a.records, a.errors, seed=3,
                               schemes={key: ecc.SCHEMES[key]})
        for d, rows in res[key].items():
            out["%s_%s" % (key, d)] = np.array(rows)
        out["raw_%s" % key] = np.array(raw[key])
    # the dropout: the convolutional code, straight and interleaved, no added noise
    rng = np.random.default_rng(11)
    s = ecc.SCHEMES["conv"]
    for inter in (False, True):
        info, values, r = ecc.run_frame(s, L.play, L.record, None, rng, burst=BURST, inter=inter)
        tag = "inter" if inter else "straight"
        z = ecc.collect(r)
        code = s.pad(s.encode(info))                              # what was sent, in information order
        sent = ecc.interleave(code) if inter else code             # ... in transmitted order
        got = ecc.soft_bits(z) * (1 - 2 * ecc.SCRAMBLE)            # received, unscrambled, in transmitted order
        out["z_" + tag] = z
        out["wrong_tx_" + tag] = np.flatnonzero(ecc.hard(got) != sent)                # wrong code bits, as sent
        out["wrong_info_" + tag] = np.flatnonzero(ecc.hard(values) != code)           # ... in the code's order
        out["errs_hard_" + tag] = int(np.sum(s.decoders["hard"](values) != info))
        out["errs_soft_" + tag] = int(np.sum(s.decoders["soft"](values) != info))
        print("dropout of %d symbols, %s: %d code bits wrong; Viterbi hard %d, soft %d information bits wrong"
              % (BURST, tag, len(out["wrong_tx_" + tag]), out["errs_hard_" + tag], out["errs_soft_" + tag]))
    np.savez(link.data_path(NAME), **out)
d = np.load(link.data_path(NAME))
src = str(d["source"])

# ---- the small trellis, decoded step by step (as ecc.py --demo) -------------------
small = ecc.ConvCode(3, (0o7, 0o5))
info = np.array([1, 0, 1, 1, 0])
code = small.encode(info)
v = 1.0 - 2 * code
v[3] = -v[3]; v[8] = -v[8]
bits, hist, surv = small.viterbi(v, trace=True)
T = len(hist)

fig = plt.figure(figsize=(11.5, 7.4))
gs = fig.add_gridspec(2, 2, width_ratios=[1.1, 1], height_ratios=[1, 1.1])

# ---- BER ---------------------------------------------------------------------------
A = fig.add_subplot(gs[:, 0])
x = np.linspace(0, 10, 200)
A.semilogy(x, [psk.ber_theory(v_) for v_ in x], color=MUTED, lw=1.2, label="theory, uncoded QPSK: Q(√(2Eb/N0))")
series = [("uncoded_hard", INK2, "o", "-", "uncoded (measured)"),
          ("hamming_hard", C1, "s", "--", "Hamming(7,4), hard decisions"),
          ("hamming_soft", C1, "s", "-", "Hamming(7,4), soft (16 codewords, pick the nearest)"),
          ("conv_hard", C2, "D", "--", "conv K=7 r=1/2, Viterbi, hard decisions"),
          ("conv_soft", C2, "D", "-", "conv K=7 r=1/2, Viterbi, soft decisions")]
gains = {}
for key, c, m, ls, lab in series:
    rows = d[key]
    ok = rows[:, 1] > 0
    mfc = c if ls == "-" else SURFACE
    A.semilogy(rows[ok, 0], rows[ok, 1] / rows[ok, 2], marker=m, color=c, ls=ls, lw=1, markersize=5.5,
               markerfacecolor=mfc, markeredgewidth=1.3, label=lab)
    for r_ in rows[~ok]:                                        # no errors: an upper limit
        A.semilogy(r_[0], 1 / r_[2], "v", color=c, mfc="none", markersize=5)
    if key != "uncoded_hard":
        gains[key] = ecc.coding_gain(d["uncoded_hard"], rows, 1e-4)
A.axhline(1e-4, color=MUTED, lw=0.8, ls=":")
A.text(0.1, 1.25e-4, "BER 10⁻⁴", fontsize=8, color=INK2)
txt = "coding gain at BER 10⁻⁴, per information bit:\n" + "\n".join(
    "  %s %s  %+.1f dB" % (("Hamming" if k.startswith("hamming") else "Viterbi"), k.split("_")[1], g)
    for k, g in gains.items() if not math.isnan(g))
A.text(0.97, 0.97, txt, transform=A.transAxes, fontsize=8.5, color=INK, va="top", ha="right", family="monospace")
A.set_xlabel("Eb/N0 (dB), per INFORMATION bit: a rate-r code spends 1/r code bits on each")
A.set_ylabel("bit error rate, information bits")
A.set_ylim(1e-6, 0.5); A.set_xlim(-0.3, 9.3)
A.grid(True, which="both", alpha=0.6)
A.set_title("Errors against energy per bit: what the codes buy\n(open triangles: no errors in the bits counted)")
A.legend(loc="lower left", fontsize=7.5)

# ---- the trellis --------------------------------------------------------------------
B = fig.add_subplot(gs[0, 1])
S = small.S
ys = {s: S - 1 - s for s in range(S)}                              # state 00 at the top
for t in range(T):
    for s in range(S):
        if t == 0 and s != 0:
            continue                                               # the encoder starts at 0
        if t > 0 and np.isinf(hist[t - 1][s]):
            continue
        for b in range(2):
            n = small.next[s, b]
            B.plot([t, t + 1], [ys[s], ys[n]], color=MUTED, lw=0.7, ls="-" if b == 0 else "--", alpha=0.7)
# survivors: the cheaper of the two paths into each state
for t in range(T):
    for s in range(S):
        if np.isinf(hist[t][s]):
            continue
        p = small.pred[s, surv[t, s]]
        if t == 0 and p != 0:
            continue
        B.plot([t, t + 1], [ys[p], ys[s]], color=INK2, lw=1.4)
# the path traced back from state 0
path = [0]
s = 0
for t in range(T - 1, -1, -1):
    s = small.pred[s, surv[t, s]]
    path.append(s)
path = path[::-1]
B.plot(range(T + 1), [ys[s] for s in path], color=C2, lw=3, alpha=0.9, solid_capstyle="round")
for t in range(T):
    for s in range(S):
        pm = hist[t][s]
        if not np.isinf(pm):
            B.text(t + 1.02, ys[s] + 0.2, "%g" % pm, ha="center", fontsize=7.5, color=INK2,
                   bbox=dict(boxstyle="round,pad=0.1", fc=SURFACE, ec="none"))
B.text(0, ys[0] + 0.2, "0", ha="center", fontsize=7.5, color=INK2)
for t in range(T):
    rx = (v[2 * t:2 * t + 2] < 0).astype(int)
    B.text(t + 0.5, -0.75, "%d%d" % tuple(rx), ha="center", fontsize=8, color=INK2 if t not in (1, 4) else C2,
           fontweight="normal" if t not in (1, 4) else "bold")
B.text(-0.1, -0.75, "received:", ha="right", fontsize=8, color=INK2)
for t in range(T):
    B.text(t + 0.5, -1.2, str(bits[t]) if t < len(bits) else "tail", ha="center", fontsize=8, color=C2)
B.text(-0.1, -1.2, "decoded:", ha="right", fontsize=8, color=C2)
B.set_yticks([ys[s] for s in range(S)]); B.set_yticklabels([np.binary_repr(s, 2) for s in range(S)])
B.set_xticks(range(T + 1)); B.set_xlim(-1.6, T + 0.4); B.set_ylim(-1.5, S - 0.3)
B.set_ylabel("state (last two bits)")
B.set_xlabel("step.   Thin: every branch (solid: input 0, dashed: 1).  Dark: the survivor into each state.\n"
             "Orange: the path traced back from state 00.  Numbers: path metrics (4 per wrong bit).", fontsize=7.5)
B.grid(False)
B.set_title("Viterbi on the K = 3 code: 10110 sent, two code bits flipped")

# ---- the dropout --------------------------------------------------------------------
C = fig.add_subplot(gs[1, 1])
k = np.arange(ecc.NSYM - ecc.NUW)
C.plot(k, np.abs(d["z_straight"]), color=INK2, lw=0.8)
C.set_ylabel("|symbol| received"); C.set_ylim(0, 2.0); C.set_xlim(0, 480)
C.set_xlabel("data symbol in the frame (0..479); a tick: a wrong code bit")
C.set_yticks([0, 1])
C.text(240, 0.5, "the DAC off for %d symbols:\nthe receiver gets nothing" % BURST, ha="center", fontsize=8, color=INK2)
wt = d["wrong_tx_straight"]
C.vlines(wt / 2, 1.28, 1.42, color=C1, lw=0.8)
C.text(272, 1.35, "sent straight: %d wrong code bits in a clump\n→ Viterbi hard %d, soft %d information bits wrong"
       % (len(wt), d["errs_hard_straight"], d["errs_soft_straight"]), fontsize=7.5, va="center", color=INK2)
wi = d["wrong_info_inter"]
C.vlines(wi / 2, 1.58, 1.72, color=C2, lw=0.8)
C.text(4, 1.8, "interleaved: the same clump, de-interleaved, lands %d bits apart\n→ Viterbi hard %d, soft %d information bits wrong"
       % (ecc.NBITS // ecc.ROWS, d["errs_hard_inter"], d["errs_soft_inter"]), fontsize=7.5, va="bottom", color=INK2)
C.set_title("A %d-symbol dropout: a clump of errors, unless interleaved" % BURST)
fig.suptitle(src, x=0.99, ha="right", fontsize=8, color=MUTED)
save(fig, link.img_path(NAME))
