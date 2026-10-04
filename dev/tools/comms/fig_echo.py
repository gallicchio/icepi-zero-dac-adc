"""Chapter 6 figure: an echo in the cable: a T with an open stub, simulated (echo.py).

comms_echo.png
  top left:    h[n] through 5, 10 and 25 m stubs (sound.py's m-sequence): the direct
               signal, the echo, and the echo's echo
  top middle:  |H(f)| for the same (the multitone): a comb of notches 1/tau apart,
               where the stub is an odd number of quarter waves; the QPSK band shaded
  top right:   bit error rate at Eb/N0 = 10 dB against the size of a one-symbol echo,
               without an equalizer and with one (equalize.py)
  middle row:  QPSK constellations with a one-symbol echo 0.3, 0.67 and 0.9 the size
               of the signal, no noise: 4 x 4 points, the margin shrinking
  bottom row:  the eye diagrams of the same

    python3 fig_echo.py --sim | PORT | PORT_A PORT_B | --replot

With a board the cable is real and the stub or echo is added to each record; with
a real T and stub on the board, use fig_sound.py and fig_equalize.py --real.
"""
import numpy as np
import link
from plotstyle import plt, save, dots, C1, C2, C3, MUTED, INK2
import echo
import equalize
import psk
import sound

NAME = "echo"
STUBS = (5.0, 10.0, 25.0)                                   # metres
SIZES = (0.3, 0.67, 0.9)                                     # one-symbol echoes, for the pictures
SWEEP = np.arange(0, 0.91, 0.1)                              # ... and for the error rates
EBN0 = 10.0
T = 1 / (psk.NSYM * psk.F_LOOP)                              # one symbol, 0.64 us
a = link.args(__doc__)
if not a.replot:
    L = link.Link(a)
    out = {"source": L.source + ", plus a simulated stub or echo", "stubs": STUBS, "sizes": SIZES, "sweep": SWEEP}
    # the stubs, sounded
    for Lm in STUBS:
        s = sound.sound(L.play, lambda: echo.add_stub(L.record(), Lm), ("mseq", "multitone"), records=2,
                        align=len(a.ports) == 2)
        out["h_%g" % Lm] = s["h_mseq"][:64]
        out["H_%g" % Lm] = s["H_multitone"]
        out["f"] = s["f"]
    s = sound.sound(L.play, L.record, ("mseq",), records=2, align=len(a.ports) == 2)
    out["h_0"] = s["h_mseq"][:64]
    # the pictures: one record each, no noise
    q, _ = psk.make_frame(4)
    wave = psk.transmit(q, 4)
    L.play(wave)
    for size in SIZES:
        rec = echo.add_echo(L.record(), T, size)
        s = equalize.slicer(rec, q)
        out["const_%g" % size] = s["x"][~s["is_uw"]]
        k = s["ks"][::3][:200]
        out["eye_%g" % size] = np.array([s["y"][s["t0"] + 16 * kk - 16:s["t0"] + 16 * kk + 17] for kk in k])
    # the error rates: equalize.py's receivers at each echo size
    rows = []
    rng = np.random.default_rng(5)
    for size in SWEEP:
        record = lambda: echo.add_echo(L.record(), T, size)
        H = equalize.sound_channel(L.play, record)
        L.play(wave)
        args = equalize.defaults(1.0)
        tot, _, _ = equalize.run(args, L.play, record, q, H, EBN0, rng, min_errs=50)
        rows.append([size] + [v for k in ("loops", "none", "lms", "dfe") for v in tot[k][:2]])
        print("echo %.1f at %g dB: " % (size, EBN0) + ", ".join("%s %d/%d" % (k, tot[k][0], tot[k][1])
                                                                 for k in ("loops", "none", "lms", "dfe")), flush=True)
    out["rows"] = np.array(rows)
    np.savez(link.data_path(NAME), **out)
d = np.load(link.data_path(NAME))
src = str(d["source"])
print(src)

fig = plt.figure(figsize=(10, 10))
gs = fig.add_gridspec(3, 3, height_ratios=[1.15, 1, 1])
f = d["f"] / 1e6
cols = (C1, C2, C3)
ax = fig.add_subplot(gs[0, 0])
n = np.arange(40)
ax.plot(n, d["h_0"][:40], color=MUTED, lw=1, label="no stub")
for Lm, c in zip(STUBS, cols):
    ax.plot(n, d["h_%g" % Lm][:40], "-", color=c, lw=1, label="%g m stub" % Lm)
    dots(ax, n, d["h_%g" % Lm][:40], c, size=3)
ax.set_xlabel("delay (ADC samples of 40 ns)"); ax.set_ylabel("h[n] (ADC codes per DAC code)")
ax.set_title("Impulse response: the echo,\n2L/v late, then its own echo", fontsize=10)
ax.legend(loc="upper right", fontsize=8)
ax = fig.add_subplot(gs[0, 1])
for Lm, c in zip(STUBS, cols):
    ax.plot(f, np.abs(d["H_%g" % Lm]), color=c, lw=0.9, label="%g m: notches at %s MHz" %
            (Lm, ", ".join("%.1f" % (x / 1e6) for x in echo.notches(Lm)[:3])))
ax.axvspan(5.2, 7.3, color=C2, alpha=0.08, lw=0)
ax.text(6.25, 0.03, "QPSK band", ha="center", fontsize=8, color=INK2)
ax.set_xlim(0, 12.5); ax.set_ylim(0, 1.3)
ax.set_xlabel("frequency (MHz)"); ax.set_ylabel("|H(f)| (ADC codes per DAC code)")
ax.set_title("Gain: a comb of notches 1/τ apart,\nτ = 2L/v the round trip", fontsize=10)
ax.legend(loc="upper left", fontsize=7)
ax = fig.add_subplot(gs[0, 2])
rows = d["rows"]
for i, (name, c, m, lab) in enumerate((("loops", MUTED, "o", "6.02's receiver, no equalizer"),
                                       ("none", INK2, "s", "unique-word sync, no equalizer"),
                                       ("lms", C1, "^", "LMS equalizer, 33 taps"),
                                       ("dfe", C2, "D", "decision feedback"))):
    errs, nbits = rows[:, 1 + 2 * i], rows[:, 2 + 2 * i]
    ok = errs > 0
    ax.semilogy(rows[ok, 0], errs[ok] / nbits[ok], m + "-", color=c, ms=4, lw=1, label=lab)
    ax.semilogy(rows[~ok, 0], 1 / nbits[~ok], "v", color=c, mfc="none", ms=5)
ax.axhline(psk.ber_theory(EBN0), color=MUTED, ls="--", lw=0.8)
ax.text(0.9, psk.ber_theory(EBN0) * 1.5, "theory, no echo", ha="right", fontsize=8, color=INK2)
ax.set_ylim(1e-6, 0.5); ax.set_xlim(-0.03, 0.93)
ax.set_xlabel("echo size a (one symbol late)"); ax.set_ylabel("bit error rate at Eb/N0 = 10 dB")
ax.set_title("Errors against the echo's size\n(open triangles: none seen)", fontsize=10)
ax.legend(loc="upper left", fontsize=7)
for j, size in enumerate(SIZES):
    ax = fig.add_subplot(gs[1, j])
    z = d["const_%g" % size]
    ax.plot(z.real, z.imag, ".", color=C1, ms=2)
    ax.set_aspect("equal"); ax.set_xlim(-2.1, 2.1); ax.set_ylim(-2.1, 2.1)
    ax.set_xticks([-1, 0, 1]); ax.set_yticks([-1, 0, 1])
    ax.axhline(0, color=MUTED, lw=0.6); ax.axvline(0, color=MUTED, lw=0.6)
    ax.set_title("echo %g: $s_k + %g\\,s_{k-1}$, no noise" % (size, size), fontsize=9)
    if j == 0:
        ax.set_ylabel("Q")
    ax.set_xlabel("I")
    ax = fig.add_subplot(gs[2, j])
    tau = np.arange(-16, 17) / 16
    for tr in d["eye_%g" % size]:
        ax.plot(tau, tr.real, color=C1, lw=0.3, alpha=0.35)
    ax.set_xlim(-1, 1); ax.set_ylim(-2.1, 2.1)
    ax.set_xlabel("time from the symbol's centre (symbols)")
    if j == 0:
        ax.set_ylabel("I, after the matched filter")
    ax.set_title("eye, echo %g" % size, fontsize=9)
fig.suptitle(src, x=0.99, ha="right", fontsize=8, color=MUTED)
save(fig, link.img_path(NAME))
