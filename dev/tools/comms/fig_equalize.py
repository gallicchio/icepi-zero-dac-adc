"""Chapter 6 figures: equalizers at work (equalize.py) on an echo one symbol late, 2/3 the size.

comms_equalize.png
  top left:    the LMS taps converging, one tap per symbol, no noise, towards the
               least-squares answer (dashed): the channel's inverse, as near as 17 taps can
  top middle:  the error power against time at Eb/N0 = 10 dB, two taps per symbol: LMS,
               NLMS and the DFE; the training records shaded
  top right:   the frequency-domain equalizers across the band: |H|, zero forcing |1/H|,
               and the MMSE |W| at 10 dB, which backs off in the notches
  middle row:  constellations at 10 dB: before, after the LMS, after the DFE
  bottom row:  eye diagrams, no noise: before, after the LMS, after dividing by H(f)
comms_equalize_ber.png
  left:  bit error rate against Eb/N0: 6.02's loops and a plain slicer (no equalizer),
         the LMS and the DFE, and theory for no echo
  right: the frequency-domain equalizers, zero forcing against MMSE, with the LMS again

    python3 fig_equalize.py --sim | PORT | PORT_A PORT_B | --replot
    python3 fig_equalize.py --sim --echo 0.375:0.9    # another echo, DELAY:SIZE (symbols, ratio)
    python3 fig_equalize.py --sim --stub 25           # a 25 m open stub instead (echo.py)
    python3 fig_equalize.py PORT --real               # a real T and stub on the board: add nothing
"""
import numpy as np
import link
from plotstyle import plt, save, C1, C2, C3, MUTED, INK2
import echo
import equalize
import psk

NAME = "equalize"
EBN0 = 10.0
BER = (0, 12)


def more(ap):
    ap.add_argument("--echo", default="1:0.67", help="DELAY:SIZE: an echo DELAY symbols late, SIZE the size")
    ap.add_argument("--stub", type=float, default=0.0, help="an open stub of this many metres instead")
    ap.add_argument("--real", action="store_true", help="add nothing: the board has a real T and stub")
    ap.add_argument("--label", default="", help="--real: what is on the board, for the caption")


def fold(y, t0, ks, every=3, n=200):
    """Eye traces: two symbols around each of n symbol centres."""
    return np.array([y[t0 + 16 * k - 16:t0 + 16 * k + 17] for k in ks[::every][:n]])


a = link.args(__doc__, more)
if not a.replot:
    L = link.Link(a)
    T = 1 / (psk.NSYM * psk.F_LOOP)
    D, size = 1.0, 0.0
    if a.real:
        record, desc = L.record, a.label or "with a real T and stub"
    elif a.stub:
        record = lambda: echo.add_stub(L.record(), a.stub)
        D, desc = 2 * a.stub / (echo.VF * echo.C) / T, "plus a simulated %g m stub" % a.stub
    else:
        D, size, b = equalize.parse_echo(a.echo)
        record = lambda: echo.add_echo(L.record(), D * T, size, b)
        desc = "plus a simulated echo %g symbol%s late, %g the size" % (D, "" if D == 1 else "s", size)
    out = {"source": L.source + ", " + desc, "D": D, "size": size, "ebn0": EBN0}
    H = equalize.sound_channel(L.play, record)
    q, _ = psk.make_frame(4)
    wave = psk.transmit(q, 4)
    L.play(wave)
    rng = np.random.default_rng(7)
    # A. one tap per symbol, no noise: the taps against time, and the least-squares answer
    args = equalize.defaults(D, spacing=1, records=4)
    tot, res, st = equalize.run(args, L.play, record, q, H, None, rng)
    s = res["sync"]
    out["W1"] = st["hist"]["W_lms"]
    out["taps1"] = args.taps
    out["wopt1"] = equalize.wiener(s["u"], s["j0"], s["ks"], s["sent"], args.taps, 1)
    # the eyes, from this noise-free run's last record
    y = s["y"] * np.exp(-1j * s["phi"])
    out["eye_none"] = fold(y, s["t0"], s["ks"])
    args2 = equalize.defaults(D, records=6)
    tot0, res0, st0 = equalize.run(args2, L.play, record, q, H, None, rng)
    s0 = res0["sync"]
    y0 = s0["y"] * np.exp(-1j * s0["phi"])
    out["eye_lms"] = fold(equalize.equalized(y0, st0["lms"], s0["step"]), s0["t0"], s0["ks"])
    s2 = equalize.slicer(res0["fd_mmse"]["rec"], q)
    out["eye_fd"] = fold(s2["y"] * np.exp(-1j * s2["phi"]), s2["t0"], s2["ks"])
    # B. two taps per symbol at Eb/N0 = 10 dB: LMS, NLMS, DFE; the last record's constellations
    tot, res, st = equalize.run(args2, L.play, record, q, H, EBN0, rng)
    tot_n, res_n, st_n = equalize.run(equalize.defaults(D, records=6, nlms=True), L.play, record, q, H, EBN0, rng)
    out["taps2"] = args2.taps
    out["per_record"] = len(res["lms"]["ks"])
    out["e_lms"], out["e_dfe"], out["e_nlms"] = st["hist"]["e_lms"], st["hist"]["e_dfe"], st_n["hist"]["e_lms"]
    out["trained"] = args2.train
    for k in ("loops", "none", "lms", "dfe", "fd_zf", "fd_mmse"):
        out["errs_" + k], out["nbits_" + k], out["mer_" + k] = tot[k][0], tot[k][1], np.mean(tot[k][2])
    out["const_none"], out["const_lms"], out["const_dfe"], out["const_fd"] = \
        res["none"]["x"], res["lms"]["y"], res["dfe"]["y"], res["fd_mmse"]["x"]
    out["f"] = np.fft.rfftfreq(2 * equalize.L, 1 / psk.FS_ADC)
    out["H"] = np.interp(out["f"], np.fft.rfftfreq(equalize.L, 1 / psk.FS_ADC), np.nan_to_num(np.abs(H)))
    out["W_zf"], out["W_mmse"] = np.abs(res["fd_zf"]["W"]), np.abs(res["fd_mmse"]["W"])
    # C. bit error rate against Eb/N0
    rows = []
    for eb in np.arange(BER[0], BER[1] + 0.01, 1.0):
        tot, _, _ = equalize.run(args2, L.play, record, q, H, eb, rng, min_errs=100)
        rows.append([eb] + [v for k in equalize.RECEIVERS[:-1] for v in tot[k][:2]])
        print("%4.1f dB: " % eb + "  ".join("%s %d/%d" % (k, tot[k][0], tot[k][1]) for k in equalize.RECEIVERS[:-1]), flush=True)
    out["rows"] = np.array(rows)
    np.savez(link.data_path(NAME), **out)
d = np.load(link.data_path(NAME))
src = str(d["source"])
D, size = float(d["D"]), float(d["size"])
print(src)
for k in ("loops", "none", "lms", "dfe", "fd_zf", "fd_mmse"):
    print("  %-8s %5d errors in %6d bits at %g dB, MER %.1f dB" % (k, d["errs_" + k], d["nbits_" + k], EBN0, d["mer_" + k]))
print("  least-squares taps, one per symbol, -1..+3: %s" % np.round(d["wopt1"][int(d["taps1"]) // 2 - 1:int(d["taps1"]) // 2 + 4].real, 3))

# ---- the equalizers at work --------------------------------------------------------------
fig = plt.figure(figsize=(10, 10.5))
gs = fig.add_gridspec(3, 3, height_ratios=[1.15, 1, 1])
ax = fig.add_subplot(gs[0, 0])
W, wopt = d["W1"], d["wopt1"]
half = int(d["taps1"]) // 2
sym = np.arange(len(W))
for j, c in zip(range(-1, 4), (MUTED, INK2, C1, C2, C3)):
    ax.plot(sym, W[:, half + j].real, color=c, lw=1, label="tap %+d" % j)
    ax.axhline(wopt[half + j].real, color=c, lw=0.8, ls="--")
ax.set_xlabel("symbols since the start (%d records)" % (len(W) // max(1, int(d["per_record"]))))
ax.set_ylabel("tap value (real part)")
ax.set_title("LMS taps, one per symbol, no noise:\ntowards least squares (dashed)", fontsize=10)
ax.legend(loc="center right", fontsize=8)
ax = fig.add_subplot(gs[0, 1])
sym = np.arange(len(d["e_lms"]))
for key, c, lab in (("e_lms", C1, "LMS"), ("e_nlms", C3, "NLMS"), ("e_dfe", C2, "DFE")):
    e2 = np.abs(d[key])**2
    ax.plot(sym, 10 * np.log10(np.convolve(e2, np.ones(64) / 64, mode="same") + 1e-9), color=c, lw=0.9, label=lab)
per = int(d["per_record"])
ax.axvspan(0, int(d["trained"]) * per, color=MUTED, alpha=0.12, lw=0)
ax.text(int(d["trained"]) * per / 2, -1.5, "training:\nsymbols known", ha="center", va="top", fontsize=8, color=INK2)
ax.set_ylim(-16, 0)
ax.set_xlabel("symbols since the start (%d records)" % (len(sym) // per))
ax.set_ylabel("error power |e|² (dB, over 64 symbols)")
ax.set_title("Learning, two taps per symbol,\nat Eb/N0 = %g dB" % EBN0, fontsize=10)
ax.legend(loc="upper right", fontsize=8)
ax = fig.add_subplot(gs[0, 2])
f = d["f"] / 1e6
sel = (f > 4.9) & (f < 7.6)
best = np.nanmax(d["H"][sel])
ax.plot(f[sel], d["H"][sel] / best, color=INK2, lw=1, label="|H(f)|, sounded")
ax.plot(f[sel], d["W_zf"][sel] * best, color=C1, lw=1, label="zero forcing: 1/|H|")
ax.plot(f[sel], d["W_mmse"][sel] * best, color=C2, lw=1, label="MMSE at %g dB" % EBN0)
ax.axvspan(5.2, 7.3, color=C2, alpha=0.08, lw=0)
ax.set_ylim(0, min(12, 1.15 * np.nanmax(d["W_zf"][sel] * best)))
ax.set_xlabel("frequency (MHz)"); ax.set_ylabel("gain (relative to the channel's best)")
ax.set_title("Divide by H(f): zero forcing digs\ninto the notch, MMSE doesn't", fontsize=10)
ax.legend(loc="upper right", fontsize=8)
for j, (key, title) in enumerate((("none", "before: unique-word sync only"), ("lms", "after the LMS"), ("dfe", "after the DFE"))):
    ax = fig.add_subplot(gs[1, j])
    z = d["const_" + key]
    ax.plot(z.real, z.imag, ".", color=C1, ms=1.5)
    ax.set_aspect("equal"); ax.set_xlim(-2.1, 2.1); ax.set_ylim(-2.1, 2.1)
    ax.set_xticks([-1, 0, 1]); ax.set_yticks([-1, 0, 1])
    ax.set_title("%s, at %g dB:\n%d errors in %d bits, MER %.1f dB" % (title, EBN0, d["errs_" + key], d["nbits_" + key], d["mer_" + key]), fontsize=9)
    ax.set_xlabel("I")
    if j == 0:
        ax.set_ylabel("Q")
tau = np.arange(-16, 17) / 16
for j, (key, title) in enumerate((("none", "eye before, no noise"), ("lms", "eye after the LMS, no noise"),
                                  ("fd", "eye after dividing by H(f), no noise"))):
    ax = fig.add_subplot(gs[2, j])
    for tr in d["eye_" + key]:
        ax.plot(tau, tr.real, color=C1, lw=0.3, alpha=0.35)
    ax.set_xlim(-1, 1); ax.set_ylim(-2.1, 2.1)
    ax.set_xlabel("time from the symbol's centre (symbols)")
    ax.set_title(title, fontsize=9)
    if j == 0:
        ax.set_ylabel("I")
fig.suptitle(src, x=0.99, ha="right", fontsize=8, color=MUTED)
save(fig, link.img_path(NAME))

# ---- bit error rate ----------------------------------------------------------------------
rows = d["rows"]
names = equalize.RECEIVERS[:-1]
col = {n: 1 + 2 * i for i, n in enumerate(names)}
fig, ax = plt.subplots(1, 2, figsize=(10, 4.6), sharey=True)
x = np.linspace(BER[0], BER[1], 200)
for a_ in ax:
    a_.semilogy(x, [psk.ber_theory(v) for v in x], color=MUTED, lw=1.2, label="theory, no echo")
    a_.set_xlabel("Eb/N0 (dB), Eb as received, echo included")
    a_.set_ylim(1e-6, 0.5); a_.set_xlim(BER[0] - 0.3, BER[1] + 0.3)
    a_.grid(True, which="both", alpha=0.6)


def curve(a_, name, c, m, lab, ls="-"):
    errs, nbits = rows[:, col[name]], rows[:, col[name] + 1]
    ok = errs > 0
    a_.semilogy(rows[ok, 0], errs[ok] / nbits[ok], m, color=c, ls=ls, ms=4.5, lw=1, label=lab)
    a_.semilogy(rows[~ok, 0], 1 / nbits[~ok], "v", color=c, mfc="none", ms=5)


curve(ax[0], "loops", INK2, "o", "6.02's receiver, no equalizer", ":")
curve(ax[0], "none", INK2, "s", "unique-word sync, no equalizer", "--")
curve(ax[0], "lms", C1, "^", "LMS, %d taps, 2 per symbol" % int(d["taps2"]))
curve(ax[0], "dfe", C2, "D", "DFE")
curve(ax[1], "lms", C1, "^", "LMS, for comparison")
curve(ax[1], "fd_zf", C3, "o", "divide by H(f): zero forcing", "--")
curve(ax[1], "fd_mmse", C3, "s", "divide by H(f): MMSE")
ax[0].set_ylabel("bit error rate")
ax[0].set_title("Many taps, trained: the time domain\n(open triangles: no errors seen)", fontsize=10)
ax[1].set_title("One divide per bin: the frequency domain", fontsize=10)
for a_ in ax:
    a_.legend(loc="lower left", fontsize=8)
fig.suptitle(src, x=0.99, ha="right", fontsize=8, color=MUTED)
save(fig, link.img_path(NAME + "_ber"))
