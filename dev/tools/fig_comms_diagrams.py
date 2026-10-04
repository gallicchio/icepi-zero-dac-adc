"""Explanatory diagrams for Chapter 6 (digital communications): block pictures with a
computed sketch under each block, and a few computed illustrations.  No hardware and no
measured data.

    python3 fig_comms_diagrams.py                 # all fourteen, into ../../tutorial/img/
    python3 fig_comms_diagrams.py gardner lora    # only those whose names contain these

Drawn with fig_openers.py's helpers (canvas, node, arrow, ...) and plotstyle's colours.
Every curve is computed here with numpy; pulse shapes come from src/comms/psk.py (rc,
rrc, point, q_to_bits, gardner_gain's formula), so they are the ones the receiver uses;
the FT8-style frame's tones come from src/comms/ft8.py's encode().

  comms_d_rxchain.png         6.02  the receiver chain: ADC -> mix down (x 1, -j, -1, j) ->
                                    matched filter -> Gardner timing loop -> Costas loop ->
                                    decide, unique word -> bits; a sketch under each block.
  comms_d_constellations.png  6.03  BPSK, QPSK, 8PSK, 16-QAM, 64-QAM at the same average
                                    power, Gray-coded bit labels, decision boundaries, and
                                    d_min relative to QPSK's (computed from the points).
  comms_d_gardner.png         6.02  Gardner's timing detector on three raised-cosine
                                    symbols +1 -1 +1, sampled on time, early and late, and
                                    its S-curve S(tau) = sum_j rc(j-1/2+x)(rc(j+x)-rc(j-1+x)).
  comms_d_costas.png          6.02  the Costas loop as a block diagram, the detector's
                                    geometry (Im(z d*) = |z| sin of the angle to the nearest
                                    point), and its characteristic folding every 90 deg.
  comms_d_msk.png             6.04  bits 1 1 0 1 0 0 1 as 5.05's FSK (4 or 2 cycles per bit),
                                    as MSK's phase trellis (+-90 deg per bit), as MSK's I and
                                    Q half-sine pulses one bit apart, and |s(t)| for MSK
                                    against QPSK with root-raised-cosine pulses.
  comms_d_channel.png         6.05  a channel as convolution: x -> h (a main tap and an echo)
                                    -> y, and as multiplication in frequency: X flat, |H| a
                                    comb of notches every 1/D, Y; the two cures: a trained
                                    equalizer (time) and OFDM's divide by H(f_k) (frequency).
  comms_d_ofdm.png            6.07  why subcarriers are orthogonal (8 sincs spaced 1/T, each
                                    peak on the others' zeros) and the cyclic prefix (the
                                    last 32 of 256 samples copied in front, the channel's
                                    smear landing inside it).
  comms_d_cdma.png            6.06  spreading as multiplication: slow bits x fast chips =
                                    a wide signal; x the same code = the bits again; x
                                    another user's code = hiss; the spectra beside, computed
                                    from 31-chip m-sequences and random bits.
  comms_d_chirp.png           6.10  a 1-11 MHz chirp 10 us long, its spectrogram, the
                                    matched-filter outputs of a long tone burst, a short
                                    pulse and the chirp (pulse compression), and the chirp's
                                    delay-Doppler ambiguity, a tilted ridge.
  comms_d_lora.png            6.10  four LoRa symbols (SF 7, 128 chips) as cyclically shifted
                                    up-chirps on a spectrogram, the same after multiplying by
                                    a down-chirp (constant tones), and the FFT bins.
  comms_d_where.png           6.00  what runs where: the laptop ($, >>> CPython, litex_term,
                                    litex_server/RemoteClient), the board under bare metal
                                    or LiteX (awgcap.sv, litex>, adda>), under Linux (#, >>>
                                    MicroPython), and a second board (B#), with the cables.
  comms_d_modem_fpga.png      6.11  the blocks of src/twoboard/qpsk_modem.sv: the transmitter in
                                    one row (serial in -> a byte waits -> frame -> Gray, differential
                                    -> 13-symbol shift register -> 13 pulse tables -> adder trees ->
                                    carrier at fs/8 -> /8, +128 -> DAC) and the receiver in two (ADC
                                    -> x 1, -j, -1, j -> half-band -> [1 2 1] -> droop EQ -> matched
                                    filter -> interpolator, with its NCO and Gardner loop -> rotate
                                    by -phi, with its Costas loop -> un-Gray -> 16-bit register and
                                    frame lock -> FIFO -> serial out); the clock budget under each.
  comms_d_ft8.png             6.12  the FT8-style frame of src/comms/ft8.py: the 79 symbols of
                                    "CQ HMC JASON" (ft8.encode) with the three Costas arrays as dot
                                    grids, the encoding chain with its bit counts, one symbol as one
                                    of 8 tones 1/T apart, the receiver's steps, and the three speeds.
  comms_d_air.png             6.12  the antenna ladder of src/comms/air.py: five rungs from
                                    minigrabber leads to a licence, a sketch and a label each, their
                                    reach on a log distance scale from 1 cm to 10 km, and the near-
                                    and far-field laws beside.
"""
import os
import sys

import numpy as np
from matplotlib.patches import Circle, Rectangle, Polygon, FancyBboxPatch
from plotstyle import plt, C1, C2, C3, INK, INK2, MUTED, AXIS, SURFACE, GRID
from fig_openers import (canvas, box, label, node, arrow, finish, want, NEUTRAL, NEUTRAL_EDGE,
                         BLUE_BG, ORANGE_BG, GREEN_BG, MONO)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src", "comms"))
import psk                                                     # noqa: E402
import ft8                                                     # noqa: E402

BOLD = {"weight": "bold"}
GREY = "#b9b7ae"


def note(fig, text="computed, not measured", top=True):
    fig.text(0.995, 0.995 if top else 0.005, text, ha="right", va="top" if top else "bottom", size=8, color=MUTED)


def inset(fig, x, y, w, h, frame=False):
    """A small bare axes on a canvas, at (x, y) with size (w, h) in the canvas's units."""
    W, H = fig.get_size_inches()
    a = fig.add_axes([x / (10 * W), y / (10 * H), w / (10 * W), h / (10 * H)])
    a.set_xticks([])
    a.set_yticks([])
    a.grid(False)
    a.set_facecolor("none")
    for s in a.spines.values():
        s.set_visible(frame)
        s.set_color(AXIS)
    return a


def bare(ax):
    """Strip a subplot down to a sketch: no ticks, no grid, no spines."""
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)


def circle_op(ax, cx, cy, sym="×", r=2.2):
    """A circled operator (a mixer, an adder) on a canvas."""
    ax.add_patch(Circle((cx, cy), r, fc="white", ec=INK2, lw=1.3, zorder=4))
    ax.text(cx, cy, sym, ha="center", va="center", size=13, color=INK2, zorder=5)


def gray(n):
    """The n-bit Gray code, as strings, in order."""
    return [format(i ^ (i >> 1), "0%db" % n) for i in range(2**n)]


def band_shape(f, R=psk.NSYM * psk.F_LOOP, alpha=psk.ALPHA):
    """|spectrum| of the root-raised-cosine signal, f from the carrier (Hz)."""
    af = np.abs(f)
    lo, hi = (1 - alpha) * R / 2, (1 + alpha) * R / 2
    mid = np.clip((af - lo) / (hi - lo), 0, 1)
    return np.where(af <= lo, 1.0, np.where(af >= hi, 0.0, np.sqrt(0.5 * (1 + np.cos(np.pi * mid)))))


def eye_traces(rng, nsym=60, res=32):
    """Random BPSK symbols as raised-cosine pulses (what the matched filter puts out), cut
    into two-symbol windows centred on the symbol times."""
    a = rng.choice([-1.0, 1.0], nsym)
    t = np.linspace(-1, 1, 2 * res + 1)
    tr = [sum(a[k + j] * psk.rc(t - j) for j in range(-6, 7)) for k in range(6, nsym - 6)]
    return t, np.array(tr)


# ==== 6.02: the receiver chain ================================================================
def fig_rxchain():
    rng = np.random.default_rng(2)
    fig, ax = canvas(10, 4.4)
    y, h = 33.0, 7.6
    widths = [9, 13.5, 14, 13.5, 13, 13.5, 7]
    gap = (97 - sum(widths)) / 6
    xs, left = [], 1.5
    for w in widths:
        xs.append(left + w / 2)
        left += w + gap
    blocks = [
        ([("ADC", BOLD), "25 MS/s"], BLUE_BG, C1),
        ([("mix down", BOLD), "× 1, −j, −1, j"], NEUTRAL, NEUTRAL_EDGE),
        ([("matched filter", BOLD), "root-raised cosine"], NEUTRAL, NEUTRAL_EDGE),
        ([("timing loop", BOLD), "Gardner"], NEUTRAL, NEUTRAL_EDGE),
        ([("Costas loop", BOLD), "carrier phase"], NEUTRAL, NEUTRAL_EDGE),
        ([("decide", BOLD), "unique word"], NEUTRAL, NEUTRAL_EDGE),
        ([("bits", BOLD)], GREEN_BG, C3),
    ]
    for x, w, (lines, fc, ec) in zip(xs, widths, blocks):
        node(ax, x, y, w, h, lines, fc=fc, ec=ec, size=8.8)
    for k in range(6):
        arrow(ax, (xs[k] + widths[k] / 2 + 0.2, y), (xs[k + 1] - widths[k + 1] / 2 - 0.2, y), ms=9)
    # what travels on each wire
    wires = ["8-bit codes", "I + jQ", "raised cosines", "one z per symbol", "squared up", "symbols"]
    for k, t in enumerate(wires):
        ax.text((xs[k] + widths[k] / 2 + xs[k + 1] - widths[k + 1] / 2) / 2, y + h / 2 + 0.6, t,
                ha="center", va="bottom", size=7.4, color=INK2, style="italic")
    # where it runs
    for x0, x1, t in [(xs[0] - widths[0] / 2, xs[0] + widths[0] / 2, "on the board"),
                      (xs[1] - widths[1] / 2, xs[5] + widths[5] / 2, "runs on the laptop, in psk.py")]:
        ax.plot([x0, x0, x1, x1], [39.0, 39.8, 39.8, 39.0], color=MUTED, lw=1)
        ax.text((x0 + x1) / 2, 40.3, t, ha="center", va="bottom", size=9, color=INK2)
    # a sketch under each block
    iy, ih, iw = 9.0, 12.5, 12.5
    caps = ["the 6.25 MHz band", "moved to 0 Hz", "the eye opens", "sample the centres",
            "turn it square", "nearest point → bits"]
    for k, cap in enumerate(caps):
        ax.text(xs[k], iy - 1.6, cap, ha="center", va="top", size=8, color=INK2)
    for k in range(6):
        arrow(ax, (xs[k], y - h / 2 - 0.3), (xs[k], iy + ih + 0.6), color=GREY, lw=0.9, ms=7)
    # 1. the ADC's spectrum: 0 to 12.5 MHz, the band at 6.25
    a = inset(fig, xs[0] - 5.0, iy, 10, ih)
    f = np.linspace(0, 12.5e6, 600)
    a.plot(f / 1e6, band_shape(f - psk.F_C), color=C1, lw=1.3)
    a.fill_between(f / 1e6, 0, band_shape(f - psk.F_C), color=C1, alpha=0.15, lw=0)
    a.axhline(0, color=AXIS, lw=0.8)
    a.set_xlim(0, 12.5)
    a.set_ylim(-0.35, 1.6)
    for fx, t in [(0, "0"), (6.25, "6.25 MHz"), (12.5, "12.5")]:
        a.text(fx, -0.1, t, ha="center", va="top", size=6.5, color=MUTED)
    # 2. after mixing: the band at 0, and a faint copy at +-12.5 MHz (2 x carrier)
    a = inset(fig, xs[1] - iw / 2, iy, iw, ih)
    f = np.linspace(-14e6, 14e6, 800)
    a.plot(f / 1e6, band_shape(f), color=C1, lw=1.3)
    a.fill_between(f / 1e6, 0, band_shape(f), color=C1, alpha=0.15, lw=0)
    for fc in (-12.5e6, 12.5e6):
        a.plot(f / 1e6, band_shape(f - fc), color=GREY, lw=1.0, ls="--")
    a.axhline(0, color=AXIS, lw=0.8)
    a.set_xlim(-14, 14)
    a.set_ylim(-0.35, 1.6)
    for fx, t in [(-12.5, "−12.5"), (0, "0"), (12.5, "12.5")]:
        a.text(fx, -0.1, t, ha="center", va="top", size=6.5, color=MUTED)
    a.text(0, 1.58, "the filter removes\nthe ±12.5 MHz copies", ha="center", va="top", size=6,
           color=MUTED)
    # 3. the eye after the matched filter
    t, tr = eye_traces(rng)
    a = inset(fig, xs[2] - iw / 2, iy, iw, ih)
    for x in tr:
        a.plot(t, x, color=C1, lw=0.5, alpha=0.5)
    a.set_xlim(-1, 1)
    a.set_ylim(-1.6, 1.6)
    # 4. the timing loop: samples on the symbol centres
    a = inset(fig, xs[3] - iw / 2, iy, iw, ih)
    for x in tr:
        a.plot(t, x, color=GREY, lw=0.5, alpha=0.6)
    a.axvline(0, color=C2, lw=0.9, ls=":")
    a.plot([0, 0], [1, -1], "o", color=C2, markersize=6, markeredgecolor=SURFACE, zorder=5)
    a.plot([-0.5, 0.5], [0, 0], "o", markersize=3.5, zorder=5, mfc="none", mec=C2)
    a.text(0, -1.5, "centre", ha="center", va="top", size=6.5, color=C2)
    a.set_xlim(-1, 1)
    a.set_ylim(-1.9, 1.6)
    # 5. the Costas loop turns the constellation square
    a = inset(fig, xs[4] - iw / 2, iy, iw, ih)
    pts = psk.point(np.arange(4), 4)
    cloud = np.repeat(pts, 25) + 0.09 * (rng.standard_normal(100) + 1j * rng.standard_normal(100))
    turned = cloud * np.exp(1j * np.radians(32))
    a.plot(turned.real, turned.imag, ".", color=GREY, markersize=2.5)
    a.plot(cloud.real, cloud.imag, ".", color=C1, markersize=2.5)
    th = np.radians(np.linspace(80, 52, 20))
    a.plot(1.42 * np.cos(th), 1.42 * np.sin(th), color=C2, lw=1.2)
    a.annotate("", (1.42 * np.cos(np.radians(48)), 1.42 * np.sin(np.radians(48))),
               (1.42 * np.cos(np.radians(53)), 1.42 * np.sin(np.radians(53))),
               arrowprops=dict(arrowstyle="-|>", color=C2, lw=1.2, mutation_scale=9))
    a.axhline(0, color=AXIS, lw=0.6)
    a.axvline(0, color=AXIS, lw=0.6)
    a.set_xlim(-1.5, 1.5)
    a.set_ylim(-1.5, 1.5)
    a.set_aspect("equal")
    # 6. decide: four clusters, their bits, the boundaries
    a = inset(fig, xs[5] - iw / 2, iy, iw, ih)
    a.plot(cloud.real, cloud.imag, ".", color=C1, markersize=2.5)
    a.axhline(0, color=INK2, lw=0.8, ls="--")
    a.axvline(0, color=INK2, lw=0.8, ls="--")
    for q in range(4):
        p = pts[q] * 1.6
        a.text(p.real, p.imag, "%d%d" % tuple(psk.q_to_bits([q], 4)), ha="center", va="center",
               size=7.5, color=INK, family=MONO)
    a.set_xlim(-1.9, 1.9)
    a.set_ylim(-1.9, 1.9)
    a.set_aspect("equal")
    # the bits
    ax.text(xs[6], iy + ih / 2, "0 1 1 0\n1 1 0 0\n0 1 …", ha="center", va="center", size=8.5,
            family=MONO, color=C3)
    finish(fig, "comms_d_rxchain.png")


# ==== 6.03: constellations at the same average power =============================================
def constellation(name):
    """Points (complex, average power 1), their Gray-coded bit strings, the decision
    boundaries as a list of (x0, y0, x1, y1), and the pair of points to mark as d_min."""
    if name == "BPSK":
        pts = psk.point(np.arange(2), 2)
        labs = ["%d" % psk.q_to_bits([q], 2)[0] for q in range(2)]
        bounds = [(0, -9, 0, 9)]
        pair = (0, 1)
    elif name == "QPSK":
        pts = psk.point(np.arange(4), 4)
        labs = ["%d%d" % tuple(psk.q_to_bits([q], 4)) for q in range(4)]
        bounds = [(0, -9, 0, 9), (-9, 0, 9, 0)]
        pair = (0, 1)
    elif name == "8PSK":
        pts = np.exp(1j * (np.pi / 8 + np.pi / 4 * np.arange(8)))
        labs = gray(3)
        bounds = [(0, 0, 9 * np.cos(k * np.pi / 4), 9 * np.sin(k * np.pi / 4)) for k in range(8)]
        pair = (0, 1)
    else:
        m = 4 if name == "16-QAM" else 8
        lv = np.arange(-(m - 1), m, 2.0)
        lv = lv / np.sqrt(np.mean(lv**2) * 2)
        g = gray(int(np.log2(m)))
        pts, labs = [], []
        for i, xi in enumerate(lv):
            for j, yj in enumerate(lv):
                pts.append(xi + 1j * yj)
                labs.append(g[i] + g[j])
        pts = np.array(pts)
        edges = (lv[:-1] + lv[1:]) / 2
        bounds = [(e, -9, e, 9) for e in edges] + [(-9, e, 9, e) for e in edges]
        c = m // 2
        pair = ((c - 1) * m + c - 1, c * m + c - 1)
    assert np.isclose(np.mean(np.abs(pts)**2), 1.0)
    return pts, labs, bounds, pair


def fig_constellations():
    names = ["BPSK", "QPSK", "8PSK", "16-QAM", "64-QAM"]
    fig, axes = plt.subplots(1, 5, figsize=(10, 2.75))
    dmins = {}
    for name in names:
        pts = constellation(name)[0]
        d = np.abs(pts[:, None] - pts[None, :])
        dmins[name] = d[d > 1e-9].min()
    for ax, name in zip(axes, names):
        pts, labs, bounds, pair = constellation(name)
        bare(ax)
        ax.set_aspect("equal")
        ax.set_xlim(-1.75, 1.75)
        ax.set_ylim(-1.75, 1.75)
        ax.add_patch(Circle((0, 0), 1.0, fc="none", ec=MUTED, lw=0.8, ls=(0, (3, 3))))
        for x0, y0, x1, y1 in bounds:
            ax.plot([x0, x1], [y0, y1], color=AXIS, lw=0.8)
        i, j = pair
        ax.plot([pts[i].real, pts[j].real], [pts[i].imag, pts[j].imag], color=C2, lw=2.2,
                solid_capstyle="round", zorder=3)
        ax.plot(pts.real, pts.imag, "o", color=C1, markersize=5 if len(pts) < 20 else 3.4,
                markeredgecolor=SURFACE, markeredgewidth=0.6, zorder=4)
        m = int(round(np.sqrt(len(pts))))
        if name == "64-QAM":
            lv = np.unique(np.round(pts.real, 6))
            for k, (v, g) in enumerate(zip(lv, gray(3))):
                ax.text(v, lv[0] - 0.22, g, ha="center", va="top", size=5.2, family=MONO, color=INK2,
                        rotation=90)
                ax.text(lv[0] - 0.2, v, g, ha="right", va="center", size=5.2, family=MONO, color=INK2)
            ax.text(lv[-1] + 0.22, lv[0] - 0.45, "I bits", ha="left", va="center", size=6.5, color=INK2)
            ax.text(lv[0] - 0.45, lv[-1] + 0.22, "Q bits", ha="center", va="bottom", size=6.5, color=INK2)
        elif name == "16-QAM":
            for p, s in zip(pts, labs):
                ax.text(p.real, p.imag + 0.13, s, ha="center", va="bottom", size=5.4, family=MONO, color=INK2)
        else:
            for p, s in zip(pts, labs):
                q = p * 1.3
                ax.text(q.real, q.imag, s, ha="center", va="center", size=7, family=MONO, color=INK2)
        bits = int(round(np.log2(len(pts))))
        ax.set_title("%s, %d bit%s" % (name, bits, "" if bits == 1 else "s"), loc="center", size=10)
        rel = dmins[name] / dmins["QPSK"]
        ax.set_xlabel("d$_{min}$ = %s × QPSK's" % ("1" if name == "QPSK" else "%.2f" % rel), size=9,
                      color=C2, labelpad=2)
    fig.text(0.5, 0.995, "The same average power for all (dashed: the rms radius): more bits per symbol means "
             "closer points, and less noise to push one across a boundary",
             ha="center", va="top", size=9.2, color=INK)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.80, bottom=0.12, wspace=0.08)
    print("  d_min relative to QPSK's:", ", ".join("%s %.3f" % (n, dmins[n] / dmins["QPSK"]) for n in names))
    finish(fig, "comms_d_constellations.png")


# ==== 6.02: Gardner's timing detector ==========================================================
def fig_gardner():
    # the symbols +1, -1, +1 at t = 0, 1, 2, with alternating neighbours either side, so that
    # the signal is symmetric about every half-way point and "on time" gives exactly zero
    # (three symbols alone would not: the third one's tail, rc(1.5) = -0.16, leaks in)
    ks = np.arange(-12, 15)
    syms = (-1.0)**ks
    t = np.linspace(-1.5, 3.5, 1001)
    def yt(tt):
        return sum(a * psk.rc(np.asarray(tt, float) - k) for k, a in zip(ks, syms))
    y = yt(t)
    fig = plt.figure(figsize=(9.5, 5.3))
    gs = fig.add_gridspec(3, 2, width_ratios=[1.4, 1], hspace=0.12, wspace=0.22,
                          left=0.06, right=0.98, top=0.82, bottom=0.11)
    rows = [("on time", 0.0, C1), ("early", -0.25, C3), ("late", +0.25, C2)]
    for r, (name, tau, col) in enumerate(rows):
        ax = fig.add_subplot(gs[r, 0])
        ax.plot(t, y, color=INK2, lw=1.2)
        ax.grid(False)
        ax.axhline(0, color=AXIS, lw=0.8)
        for k, a in zip(ks, syms):
            if -1.5 < k < 3.5:
                ax.plot(k, a, "s", color=GREY, markersize=5, zorder=2)
        tp, tm, tn = tau, 0.5 + tau, 1 + tau
        yp, ym, yn = yt(tp), yt(tm), yt(tn)
        for tt, yy in [(tp, yp), (tn, yn)]:
            ax.plot([tt, tt], [0, yy], color=col, lw=0.9, ls=":")
            ax.plot(tt, yy, "o", color=col, markersize=7, markeredgecolor=SURFACE, zorder=5)
        ax.plot([tm, tm], [0, ym], color=col, lw=0.9, ls=":")
        ax.plot(tm, ym, "D", color=col, markersize=7, markeredgecolor=SURFACE, zorder=5)
        ax.text(tp + (0.1 if tau > 0 else -0.1), yp + 0.08, "prev", ha="left" if tau > 0 else "right",
                va="bottom", size=8, color=col)
        ax.text(tn + 0.12, yn, "now", ha="left", va="center", size=8, color=col)
        ax.text(tm + 0.1, ym + (0.05 if ym >= 0 else -0.05), "mid", ha="left",
                va="bottom" if ym >= 0 else "top", size=8, color=col)
        e = ym * (yn - yp)
        verdict = {0: "e = 0: leave it", -1: "e < 0: sample later", 1: "e > 0: sample earlier"}[int(np.sign(np.round(e, 6)))]
        ax.text(3.45, 1.4, "%s\ne = mid × (now − prev)\n= (%+.2f) × (%+.2f) = %+.2f\n%s"
                % (name, ym, yn - yp, e, verdict), ha="right", va="top", size=8.2, color=INK,
                bbox=dict(fc=SURFACE, ec="none", pad=1))
        ax.set_xlim(-1.5, 3.5)
        ax.set_ylim(-1.55, 1.55)
        ax.set_yticks([-1, 0, 1])
        ax.set_ylabel("y(t)")
        if r < 2:
            ax.tick_params(labelbottom=False)
        else:
            ax.set_xlabel("time (symbols): … +1, −1, +1, … as raised-cosine pulses (squares: the symbols)")
    # the S-curve: the detector's average output against the timing error
    ax = fig.add_subplot(gs[:, 1])
    j = np.arange(-20, 21)
    def S(x):
        return np.sum(psk.rc(j - 0.5 + x) * (psk.rc(j + x) - psk.rc(j - 1 + x)))
    xs = np.linspace(-0.5, 0.5, 201)
    s = np.array([S(x) for x in xs])
    slope = (S(0.01) - S(-0.01)) / 0.02
    ax.plot(xs, s, color=C1, lw=1.8)
    ax.plot(xs, slope * xs, color=MUTED, lw=0.9, ls="--")
    for name, tau, col in rows:
        ax.plot(tau, S(tau), "o", color=col, markersize=7, markeredgecolor=SURFACE, zorder=5)
        ax.text(tau + 0.04, S(tau) - 0.03, name, ha="left", va="top", size=8.5, color=col)
    ax.axhline(0, color=AXIS, lw=0.8)
    ax.axvline(0, color=AXIS, lw=0.8)
    ax.set_xlim(-0.5, 0.5)
    ax.set_xlabel("timing error (symbols): + is sampling late")
    ax.set_ylabel("average e, random data (symbol = 1)")
    ax.set_title("The S-curve: ⟨e⟩ against timing error")
    ax.text(0.03, 0.97, "slope at 0: %.2f per symbol\n(psk.gardner_gain's formula,\nraised cosine, α = %.2f)"
            % (slope, psk.ALPHA), transform=ax.transAxes, ha="left", va="top", size=8.4, color=INK2)
    fig.text(0.06, 0.975, "Gardner's timing detector: half-way between two symbols the signal should be crossing zero",
             ha="left", va="top", size=10.5, weight="bold")
    fig.text(0.06, 0.93, "It uses three samples: the previous symbol's, the half-way one and this symbol's. If the half-way "
             "sample has already crossed, in the\ndirection the signal is going, the samples are late. One symbol's e "
             "scatters with the data; its average over random data is the S-curve.",
             ha="left", va="top", size=8.4, color=INK2)
    note(fig)
    print("  Gardner S-curve slope at 0: %.3f per symbol; e for the three rows: %s"
          % (slope, ", ".join("%s %+.2f" % (n, yt(0.5 + tau) * (yt(1 + tau) - yt(tau))) for n, tau, _ in rows)))
    finish(fig, "comms_d_gardner.png")


# ==== 6.02: the Costas loop ====================================================================
def fig_costas():
    fig, ax = canvas(10, 4.6)
    y1, y0 = 31.0, 13.0                             # the forward path, the return path
    ax.text(1.0, y1, "z$_k$", ha="left", va="center", size=11, color=INK)
    ax.text(1.0, y1 - 2.6, "from the\ntiming loop", ha="left", va="top", size=7.5, color=INK2)
    arrow(ax, (5.0, y1), (8.1, y1))
    circle_op(ax, 10.3, y1, "×")
    bx = 18.5                                          # the branch: z_r goes two ways
    ax.plot([12.5, bx], [y1, y1], color=INK2, lw=1.3)
    ax.plot(bx, y1, "o", color=INK2, markersize=4)
    ax.text(15.5, y1 + 1.0, "z$_r$", ha="center", va="bottom", size=10, color=INK)
    node(ax, 28.0, y1, 14, 7.6, [("decision", BOLD), "d = the nearest", "constellation point"], size=8.6)
    arrow(ax, (bx, y1), (21.0, y1))
    node(ax, 47.0, y1, 15, 7.6, [("phase detector", BOLD), "e = Im(z$_r$ d*)"], size=8.6)
    arrow(ax, (35.0, y1), (39.5, y1))
    ax.text(37.2, y1 + 1.0, "d", ha="center", va="bottom", size=10, color=INK)
    ax.plot([bx, bx, 44.0], [y1, y1 + 8.0, y1 + 8.0], color=INK2, lw=1.3)      # z_r to the detector
    arrow(ax, (44.0, y1 + 8.0), (44.0, y1 + 3.8 + 0.2))
    ax.text(31.0, y1 + 8.6, "z$_r$ = z$_k$ e$^{−jφ}$: the symbol turned back by our phase estimate",
            ha="center", va="bottom", size=8, color=INK2)
    # the output
    ax.plot([bx, bx], [y1, y1 - 5.0], color=INK2, lw=1.3, ls="--")
    arrow(ax, (bx, y1 - 5.0), (bx, y1 - 8.5), ls="--")
    ax.text(bx + 1.0, y1 - 6.8, "z$_r$ out: to decide, unique word", ha="left", va="center", size=7.8, color=INK2)
    # down to the loop filter, back to the accumulator, up to the multiplier
    node(ax, 47.0, y0, 15, 7.6, [("loop filter", BOLD), "K$_p$ e + K$_i$ Σ e"], size=8.6)
    arrow(ax, (47.0, y1 - 3.8), (47.0, y0 + 3.8 + 0.2))
    ax.text(48.0, (y1 + y0) / 2, "e", ha="left", va="center", size=10, color=INK)
    node(ax, 28.0, y0, 14, 7.6, [("phase accumulator", BOLD), "φ ← φ + that"], size=8.6)
    arrow(ax, (39.5, y0), (35.0 + 0.2, y0))
    ax.plot([21.0, 10.3, 10.3], [y0, y0, y1 - 2.2 - 3.0], color=INK2, lw=1.3)
    arrow(ax, (10.3, y1 - 2.2 - 3.0), (10.3, y1 - 2.2 - 0.2))
    ax.text(11.3, y0 + 7.0, "e$^{−jφ}$", ha="left", va="center", size=10, color=INK)
    ax.text(2.0, y0 - 5.2, "K$_i$ Σ e learns the carrier's frequency offset;  K$_p$ e nudges the phase (a PI controller, 4.08)",
            ha="left", va="top", size=8, color=INK2)
    # beside the detector: the angle from z to its nearest point
    a = inset(fig, 56.5, 20.0, 14, 22)
    pts = psk.point(np.arange(4), 4)
    z = 1.05 * np.exp(1j * np.radians(45 + 28))
    d = pts[0]
    a.axhline(0, color=AXIS, lw=0.6)
    a.axvline(0, color=AXIS, lw=0.6)
    a.plot(pts.real, pts.imag, "o", color=GREY, markersize=5)
    a.plot(d.real, d.imag, "o", color=C1, markersize=6)
    a.plot(z.real, z.imag, "o", color=C2, markersize=6)
    a.plot([0, z.real], [0, z.imag], color=C2, lw=1)
    a.plot([0, d.real], [0, d.imag], color=C1, lw=1)
    th = np.radians(np.linspace(45, 73, 30))
    a.plot(0.55 * np.cos(th), 0.55 * np.sin(th), color=INK2, lw=0.9)
    a.text(0.55 * np.cos(np.radians(59)) + 0.07, 0.55 * np.sin(np.radians(59)) + 0.07, "θ", ha="left",
           va="bottom", size=9, color=INK)
    a.text(z.real + 0.08, z.imag + 0.08, "z$_r$", ha="left", va="bottom", size=9, color=C2)
    a.text(d.real + 0.12, d.imag - 0.12, "d", ha="left", va="top", size=9, color=C1)
    a.set_xlim(-1.4, 1.5)
    a.set_ylim(-1.3, 1.6)
    a.set_aspect("equal")
    ax.text(63.5, 18.0, "e = Im(z$_r$ d*) = |z$_r$| sin θ", ha="center", va="top", size=8.4, color=INK)
    ax.text(63.5, 15.2, "choosing the nearest point\nremoves the data: any\nsymbol is a reference",
            ha="center", va="top", size=7.6, color=INK2)
    # the detector's characteristic
    a = inset(fig, 74.0, 10.0, 24.5, 28, frame=True)
    a.spines["top"].set_visible(False)
    a.spines["right"].set_visible(False)
    th = np.linspace(-180, 180, 1441)
    def char(theta, M):
        step = 360 / M
        return np.sin(np.radians(theta - step * np.round(theta / step)))
    a.plot(th, char(th, 2), color=C2, lw=0.9, ls="--", label="BPSK")
    a.plot(th, char(th, 4), color=C1, lw=1.6, label="QPSK")
    a.axhline(0, color=AXIS, lw=0.8)
    for s in (-180, -90, 0, 90, 180):
        a.plot(s, 0, "o", color=C1, markersize=5, markeredgecolor=SURFACE, zorder=5)
    a.set_xlim(-180, 180)
    a.set_ylim(-1.15, 1.15)
    a.set_xticks([-180, -90, 0, 90, 180])
    a.set_xticklabels(["−180°", "−90°", "0", "90°", "180°"], size=7.5)
    a.set_yticks([-1, 0, 1])
    a.set_yticklabels(["−1", "0", "1"], size=7.5)
    a.tick_params(length=2, color=AXIS)
    a.grid(True, color=GRID, lw=0.5)
    a.legend(loc="lower right", fontsize=7.5, frameon=False)
    ax.text(86.0, 40.5, "the detector against the phase error", ha="center", va="bottom", size=8.6,
            weight="bold", color=INK)
    ax.text(86.0, 8.2, "phase error θ (the true phase minus φ)", ha="center", va="top", size=7.8, color=INK2)
    ax.text(86.0, 4.6, "zero every 90° for QPSK (180° for BPSK):\nthe dots are the four places it is happy",
            ha="center", va="top", size=7.4, color=INK2)
    ax.text(1.0, 44.0, "The Costas loop, once per symbol (psk.costas)", ha="left", va="center", size=10.5,
            weight="bold", color=INK)
    finish(fig, "comms_d_costas.png")


# ==== 6.04: MSK ================================================================================
def fig_msk():
    bits = np.array([1, 1, 0, 1, 0, 0, 1])
    nb = len(bits)
    res = 400
    t = np.arange(nb * res) / res                            # time in bits
    k = np.minimum((t).astype(int), nb - 1)
    fig = plt.figure(figsize=(9, 8.2))
    gs = fig.add_gridspec(5, 1, height_ratios=[0.42, 1.15, 1.25, 1.1, 1.0], hspace=0.42,
                          left=0.08, right=0.98, top=0.95, bottom=0.06)
    # the bits
    ax = fig.add_subplot(gs[0])
    ax.step(np.arange(nb + 1), np.r_[bits, bits[-1]], where="post", color=INK2, lw=1.2)
    for i, b in enumerate(bits):
        ax.text(i + 0.5, 0.5, str(b), ha="center", va="center", size=11, weight="bold", color=INK)
    bare(ax)
    ax.set_xlim(0, nb)
    ax.set_ylim(-0.3, 1.3)
    ax.set_title("the bits")
    # (a) 5.05's FSK: 6.25 MHz for a 1, 3.125 MHz for a 0: 4 or 2 cycles per bit
    ax = fig.add_subplot(gs[1])
    f = np.where(bits[k] == 1, 4.0, 2.0)                     # cycles per bit
    phase = 2 * np.pi * np.cumsum(f) / res
    ax.plot(t, np.cos(phase), color=C1, lw=1.0)
    for i in range(1, nb):
        ax.axvline(i, color=AXIS, lw=0.7)
        if bits[i] != bits[i - 1]:
            ax.plot(i, np.cos(phase[i * res]), "o", color=C2, markersize=6, markeredgecolor=SURFACE, zorder=5)
    ax.grid(False)
    ax.set_xlim(0, nb)
    ax.set_ylim(-1.4, 2.0)
    ax.set_yticks([-1, 0, 1])
    ax.tick_params(labelbottom=False)
    ax.set_title("(a) FSK as 5.05's modem: 6.25 MHz for a 1, 3.125 MHz for a 0, i.e. 4 or 2 cycles per bit (h = 2)", size=10)
    ax.text(nb / 2, 1.9, "where the bit changes the frequency switches (dots): the phase is continuous, its slope is not (a kink)",
            ha="center", va="top", size=8, color=INK2)
    # (b) MSK's phase trellis: +90 or -90 deg per bit
    ax = fig.add_subplot(gs[2])
    for i in range(nb):                                      # all the paths, faint
        for p in range(-90 * i, 90 * i + 1, 180):
            for s in (-90, 90):
                ax.plot([i, i + 1], [p, p + s], color=GREY, lw=0.7)
    ph = np.r_[0, np.cumsum(np.where(bits == 1, 90, -90))]
    ax.plot(np.arange(nb + 1), ph, color=C1, lw=2.2, solid_capstyle="round", zorder=4)
    ax.plot(np.arange(nb + 1), ph, "o", color=C1, markersize=5, markeredgecolor=SURFACE, zorder=5)
    for i, b in enumerate(bits):
        ax.text(i + 0.5, (ph[i] + ph[i + 1]) / 2 + (18 if b else -18), "+90°" if b else "−90°",
                ha="center", va="bottom" if b else "top", size=8, color=C1, rotation=0)
    ax.grid(False)
    ax.set_xlim(0, nb)
    ax.set_ylim(-220, 310)
    ax.set_yticks([-180, -90, 0, 90, 180, 270])
    ax.set_yticklabels(["−180°", "−90°", "0", "90°", "180°", "270°"])
    ax.tick_params(labelbottom=False)
    ax.set_ylabel("phase φ")
    ax.set_title("(b) MSK: tones only a quarter cycle per bit apart (h = ½): the phase turns +90° for a 1, −90° for a 0", size=10)
    ax.text(nb - 0.05, -205, "grey: every path the phase could take", ha="right", va="bottom", size=8, color=INK2)
    # (c) the same MSK as I and Q: half-sine pulses two bits long, Q one bit after I
    ax = fig.add_subplot(gs[3])
    phi = np.radians(np.interp(t, np.arange(nb + 1), ph))
    I, Q = np.cos(phi), np.sin(phi)
    ax.plot(t, I, color=C1, lw=1.6, label="I = cos φ")
    ax.plot(t, Q, color=C2, lw=1.6, label="Q = sin φ")
    for c in range(0, nb + 1, 2):
        ax.plot(c, np.cos(np.radians(ph[c])), "o", color=C1, markersize=5, markeredgecolor=SURFACE, zorder=5)
    for c in range(1, nb + 1, 2):
        ax.plot(c, np.sin(np.radians(ph[c])), "o", color=C2, markersize=5, markeredgecolor=SURFACE, zorder=5)
    ax.grid(False)
    for i in range(1, nb):
        ax.axvline(i, color=AXIS, lw=0.7)
    ax.set_xlim(0, nb)
    ax.set_ylim(-1.45, 1.45)
    ax.set_yticks([-1, 0, 1])
    ax.tick_params(labelbottom=False)
    ax.legend(loc="lower left", ncol=2, fontsize=8)
    ax.set_title("(c) the same MSK as I and Q: half-sine pulses two bits long, Q's one bit (half a symbol) after I's", size=10)
    # (d) |s(t)|: MSK constant; QPSK with root-raised-cosine pulses wobbles
    ax = fig.add_subplot(gs[4])
    rng = np.random.default_rng(4)
    nsym = 40
    a = psk.point(rng.integers(0, 4, nsym), 4)
    tt = t + 2 * 16                                          # a stretch well inside the sequence
    env = sum(a[j] * psk.rrc((tt - (2 * j + 1)) / 2) for j in range(nsym))
    env = env / np.sqrt(np.mean(np.abs(env)**2))
    ax.plot(t, np.abs(env), color=C2, lw=1.4, label="QPSK, root-raised-cosine pulses (6.02), 2 bits per symbol")
    ax.plot(t, np.hypot(I, Q), color=C1, lw=2.0, label="MSK")
    ax.grid(False)
    ax.set_xlim(0, nb)
    ax.set_ylim(0, 1.9)
    ax.set_yticks([0, 1])
    ax.set_xlabel("time (bits)")
    ax.set_ylabel("|s(t)|")
    ax.legend(loc="upper left", fontsize=8, ncol=2)
    ax.set_title("(d) |s(t)|: MSK's is constant, so its amplifier can be a switch; QPSK's dips, so its must be linear", size=10)
    note(fig)
    finish(fig, "comms_d_msk.png")


# ==== 6.05: the channel ========================================================================
def fig_channel():
    fig, ax = canvas(10, 5.6)
    D, echo = 10, 0.4                                        # the echo: delay in samples, size
    fs = psk.FS_ADC
    # ---- top row: time (convolution) and frequency (multiplication) ----
    ty, ih, iw = 42.0, 11.0, 11.0
    ax.text(1.0, 54.0, "A channel is a convolution in time, and a multiplication in frequency",
            ha="left", va="center", size=10.5, weight="bold", color=INK)
    ax.text(1.0, 50.6, "time:  y[n] = Σ$_m$ h[m] x[n − m]", ha="left", va="center", size=9, color=INK2)
    ax.text(55.0, 50.6, "frequency:  Y(f) = H(f) X(f)", ha="left", va="center", size=9, color=INK2)
    n = np.arange(40)
    x = psk.rc((n - 8) / 2.0)                                # one short pulse in
    h = np.zeros(40); h[0] = 1; h[D] = echo
    yv = np.convolve(x, h)[:40]
    cols = [(1.5, "x[n]: a pulse in", x, C1), (19.5, "h[n]: a main tap, an echo", h, INK2),
            (37.5, "y[n]: the pulse and its echo", yv, C1)]
    for k, (x0, cap, v, col) in enumerate(cols):
        a = inset(fig, x0, ty - ih / 2, iw, ih)
        if k == 1:
            box(ax, x0 - 1.0, ty - ih / 2 - 1.0, iw + 2.0, ih + 2.0, fc=NEUTRAL, ec=NEUTRAL_EDGE, r=0.8, z=1)
            a.vlines(n[v != 0], 0, v[v != 0], color=col, lw=1.6)
            a.plot(n[v != 0], v[v != 0], "o", color=col, markersize=4)
            a.text(D + 2, echo, "echo, D = %d" % D, ha="left", va="center", size=6.5, color=INK2)
        else:
            a.vlines(n, 0, v, color=col, lw=0.8, alpha=0.6)
            a.plot(n, v, "o", color=col, markersize=2.5)
        a.axhline(0, color=AXIS, lw=0.7)
        a.set_xlim(-1, 40)
        a.set_ylim(-0.3, 1.35)
        ax.text(x0 + iw / 2, ty - ih / 2 - 2.2, cap, ha="center", va="top", size=7.6, color=INK2)
    arrow(ax, (13.4, ty), (17.4, ty))
    arrow(ax, (32.6, ty), (36.6, ty))
    ax.text(15.4, ty + 1.2, "∗", ha="center", va="bottom", size=12, color=INK2)
    ax.text(34.6, ty + 1.2, "=", ha="center", va="bottom", size=11, color=INK2)
    f = np.linspace(0, fs / 2, 2000)
    H = np.abs(1 + echo * np.exp(-2j * np.pi * f * D / fs))
    X = np.ones_like(f)
    cols = [(55.0, "|X(f)|: flat", X, C1), (71.0, "|H(f)|: notches every f$_s$/D", H, INK2),
            (87.0, "|Y(f)| = |H| |X|", H * X, C1)]
    for k, (x0, cap, v, col) in enumerate(cols):
        a = inset(fig, x0, ty - ih / 2, iw, ih)
        a.plot(f / 1e6, 20 * np.log10(v), color=col, lw=1.2)
        a.axhline(0, color=AXIS, lw=0.7)
        a.set_xlim(0, 12.5)
        a.set_ylim(-9.5, 4.5)
        for fx, s in [(0, "0"), (12.5, "12.5 MHz")]:
            a.text(fx, -9.4, s, ha="center" if fx else "left", va="bottom", size=6, color=MUTED)
        if k == 0:
            a.text(0.3, 0.3, "0 dB", ha="left", va="bottom", size=6, color=MUTED)
        if k == 1:
            f1, f2 = 0.5 * fs / D / 1e6, 1.5 * fs / D / 1e6
            a.annotate("", (f2, -5.6), (f1, -5.6), arrowprops=dict(arrowstyle="<->", color=C2, lw=0.9, mutation_scale=7))
            a.text((f1 + f2) / 2, -6.0, "f$_s$/D = %.1f MHz" % (fs / D / 1e6), ha="center", va="top", size=6.3, color=C2)
        ax.text(x0 + iw / 2, ty - ih / 2 - 2.2, cap, ha="center", va="top", size=7.6, color=INK2)
    arrow(ax, (66.9, ty), (70.9, ty))
    arrow(ax, (82.9, ty), (86.9, ty))
    ax.text(68.9, ty + 1.2, "×", ha="center", va="bottom", size=12, color=INK2)
    ax.text(84.9, ty + 1.2, "=", ha="center", va="bottom", size=11, color=INK2)
    ax.text(76.5, 31.0, "an echo D samples late adds e$^{−j2πfD/f_s}$ to the main tap's 1:\nit cancels it wherever that is −1, every f$_s$/D",
            ha="center", va="top", size=7.4, color=INK2)
    # ---- bottom row: the two cures ----
    by = 18.0
    ax.text(1.0, 25.5, "Cure 1, in time: an equalizer, many taps, trained", ha="left", va="center", size=9.5,
            weight="bold", color=INK)
    ax.text(1.0, by, "y[n]", ha="left", va="center", size=9.5, color=INK)
    arrow(ax, (5.5, by), (8.8, by))
    node(ax, 16.0, by, 14, 6.4, [("FIR filter", BOLD), "Σ$_m$ w$_m$ y[n − m]"], size=8.2)
    arrow(ax, (23.0, by), (27.3, by))
    node(ax, 33.5, by, 12, 6.4, [("decision", BOLD), "nearest point"], size=8.2)
    arrow(ax, (39.5, by), (43.0, by))
    ax.text(43.6, by, "x̂[n]", ha="left", va="center", size=9.5, color=INK)
    cy = by - 7.6                                            # the error: decision minus FIR output
    circle_op(ax, 33.5, cy, "−", r=1.6)
    dash = dict(color=INK2, lw=1.1, ls="--")
    ax.plot([25.2, 25.2, 31.9], [by, cy, cy], **dash)
    ax.plot([33.5, 33.5], [by - 3.2, cy + 1.6], **dash)
    ax.plot([33.5, 33.5, 16.0, 16.0], [cy - 1.6, cy - 3.6, cy - 3.6, by - 5.6], **dash)
    arrow(ax, (16.0, by - 5.6), (16.0, by - 3.2 - 0.2), ls="--")
    ax.text(24.5, cy - 4.2, "the error nudges every w$_m$, symbol by symbol (LMS)", ha="center", va="top", size=7.4, color=INK2)
    ax.text(16.0, by + 4.0, "w ≈ 1, −0.4 at D, +0.16 at 2D, …: h's inverse", ha="center", va="bottom", size=7.2, color=INK2)
    ax.text(52.0, 25.5, "Cure 2, in frequency (OFDM): divide each subcarrier by H(f$_k$)", ha="left",
            va="center", size=9.5, weight="bold", color=INK)
    ax.text(52.0, by, "Y(f$_k$)", ha="left", va="center", size=9.5, color=INK)
    arrow(ax, (58.5, by), (62.3, by))
    node(ax, 70.0, by, 15, 6.4, [("÷ H(f$_k$)", BOLD), "one complex division", "per subcarrier"], size=8.2)
    arrow(ax, (77.5, by), (81.3, by))
    ax.text(81.8, by, "X̂(f$_k$)", ha="left", va="center", size=9.5, color=INK)
    ax.text(70.0, by - 4.5, "a known pilot symbol measures every H(f$_k$) at once", ha="center", va="top", size=7.4, color=INK2)
    k = np.arange(1, 13)
    fk = k * fs / 2 / 13
    Hk = np.abs(1 + echo * np.exp(-2j * np.pi * fk * D / fs))
    for x0, v in [(52.0, Hk), (89.5, Hk / Hk)]:
        a = inset(fig, x0, by + 1.8, 7.0, 4.6)
        a.bar(k, v, width=0.7, color=C1)
        a.set_ylim(0, 1.6)
        a.set_xlim(0, 13)
    finish(fig, "comms_d_channel.png")


# ==== 6.07: OFDM: orthogonal subcarriers, and the cyclic prefix =================================
def fig_ofdm():
    fig = plt.figure(figsize=(9.5, 6.4))
    gs = fig.add_gridspec(2, 1, height_ratios=[1, 1.15], hspace=0.5, left=0.07, right=0.98, top=0.93, bottom=0.07)
    # ---- the spectra of 8 rectangular-windowed subcarriers ----
    ax = fig.add_subplot(gs[0])
    f = np.linspace(-2.5, 9.5, 2401)
    K, hi = 8, 3
    for k in range(K):
        if k != hi:
            ax.plot(f, np.sinc(f - k), color=GREY, lw=0.9)
    ax.plot(f, np.sinc(f - hi), color=C1, lw=2.0, zorder=4)
    ax.fill_between(f, 0, np.sinc(f - hi), color=C1, alpha=0.12, lw=0)
    for k in range(K):
        ax.plot(k, 1, "o", color=C1 if k == hi else GREY, markersize=4.5, markeredgecolor=SURFACE, zorder=5)
    ax.plot(hi, 0, "o", color=C2, markersize=7, markeredgecolor=SURFACE, zorder=6)
    ax.axvline(hi, color=C2, lw=0.9, ls=":")
    ax.axhline(0, color=AXIS, lw=0.8)
    ax.grid(False)
    ax.set_xlim(-2.5, 9.5)
    ax.set_ylim(-0.35, 1.65)
    ax.set_xticks(range(K))
    ax.set_xticklabels(["%d/T" % k if k else "0" for k in range(K)])
    ax.set_yticks([0, 1])
    ax.set_xlabel("frequency, in units of 1/T (T = one symbol, 256 samples: 1/T = 97.66 kHz at 25 MS/s)")
    ax.set_ylabel("spectrum")
    ax.set_title("Orthogonal subcarriers: a T-long piece of a sine has a sinc spectrum, zero every 1/T", size=10.5)
    ax.text(hi + 0.3, 1.6, "at subcarrier %d's centre every other subcarrier is exactly zero:\n"
            "the FFT reads it off alone, however much they overlap" % hi, ha="left", va="top", size=8.4, color=INK)
    ax.text(-2.4, 1.6, "8 subcarriers,\nspaced 1/T", ha="left", va="top", size=8.2, color=INK2)
    # ---- the cyclic prefix ----
    ax = fig.add_subplot(gs[1])
    bare(ax)
    rng = np.random.default_rng(7)
    N, P = 256, 32
    Xk = np.zeros(N, complex)
    used = np.arange(3, 24)                                  # a few subcarriers: a wiggly, readable waveform
    Xk[used] = psk.point(rng.integers(0, 4, len(used)), 4)
    s1 = np.fft.ifft(Xk).real
    s1 = 0.7 * s1 / np.abs(s1).max()
    Xk[used] = psk.point(rng.integers(0, 4, len(used)), 4)
    s2 = np.fft.ifft(Xk).real
    s2 = 0.7 * s2 / np.abs(s2).max()
    yb, hb = 0.0, 2.2                                        # the bars
    def block(x0, w, fc, ec, sig, z=2):
        ax.add_patch(Rectangle((x0, yb), w, hb, fc=fc, ec=ec, lw=1.0, zorder=z))
        ax.plot(x0 + np.arange(len(sig)), yb + hb / 2 + sig, color=INK2, lw=0.8, zorder=z + 1)
    # previous symbol's end, this symbol with its prefix, the next symbol's prefix
    block(-70, 70, NEUTRAL, NEUTRAL_EDGE, s2[-70:])
    block(0, P, ORANGE_BG, C2, s1[-P:])
    block(P, N, NEUTRAL, NEUTRAL_EDGE, s1)
    block(P + N, P, ORANGE_BG, C2, s2[-P:])
    block(2 * P + N, 60, NEUTRAL, NEUTRAL_EDGE, s2[:60])
    ax.add_patch(Rectangle((P + N - P, yb), P, hb, fc="none", ec=C2, lw=1.2, ls="--", zorder=4))
    ax.annotate("", (P / 2, yb + hb + 0.25), (P + N - P / 2, yb + hb + 0.25),
                arrowprops=dict(arrowstyle="-|>", color=C2, lw=1.2, connectionstyle="arc3,rad=0.25", mutation_scale=10))
    ax.text(P + N / 2, yb + hb + 1.25, "copy the last %d samples in front: the cyclic prefix" % P, ha="center",
            va="bottom", size=9, color=C2)
    for x0, w, t in [(0, P, "prefix"), (P, N, "the symbol: %d samples (an inverse FFT of the subcarriers)" % N),
                     (P + N, P, "prefix")]:
        ax.text(x0 + w / 2, yb - 0.25, t, ha="center", va="top", size=7.8, color=INK2)
    ax.text(-35, yb - 0.25, "previous symbol", ha="center", va="top", size=7.8, color=INK2)
    ax.text(2 * P + N + 30, yb - 0.25, "next symbol", ha="center", va="top", size=7.8, color=INK2)
    # the channel's smear: the previous symbol's tail spills into the prefix
    L = 6
    ax.add_patch(Rectangle((0, yb), L, hb, fc=C3, ec="none", alpha=0.5, zorder=5))
    ax.annotate("", (L / 2, yb + 0.4), (-45, yb - 1.9), arrowprops=dict(arrowstyle="-|>", color=C3, lw=1.1, mutation_scale=9))
    ax.text(-128, yb - 1.4, "the channel smears each sample over the next few (1.07: about %d),\n"
            "so the previous symbol's tail lands here, inside the prefix,\nwhich the receiver throws away" % L,
            ha="left", va="top", size=8.2, color=INK)
    # the FFT window
    ax.plot([P, P, P + N, P + N], [yb + hb + 0.2, yb + hb + 0.5, yb + hb + 0.5, yb + hb + 0.2], color=C1, lw=1.2, zorder=6)
    ax.text(P + N / 2, yb + hb + 3.3, "the FFT takes these %d: thanks to the prefix, the smear of this symbol's own start wraps round from its end,\n"
            "so the FFT sees one clean period of a periodic signal, and the channel becomes one multiplication H(f$_k$) per subcarrier" % N,
            ha="center", va="bottom", size=8.4, color=C1)
    ax.set_xlim(-130, 2 * P + N + 70)
    ax.set_ylim(yb - 3.6, yb + hb + 6.2)
    ax.set_title("The cyclic prefix: 32 of 256 samples (6.07's ofdm.py), 1.28 µs at 25 MS/s", size=10.5)
    note(fig)
    finish(fig, "comms_d_ofdm.png")


# ==== 6.06: spreading as multiplication ========================================================
def mseq(taps, n=5):
    """A maximal-length sequence (+-1) from an n-stage shift register with the given taps."""
    reg = [1] * n
    out = []
    for _ in range(2**n - 1):
        out.append(reg[-1])
        fb = 0
        for t in taps:
            fb ^= reg[t - 1]
        reg = [fb] + reg[:-1]
    return 1 - 2 * np.array(out)


def fig_cdma():
    rng = np.random.default_rng(3)
    code1, code2 = mseq((3, 5)), mseq((2, 3, 4, 5))         # x^5 + x^3 + 1,  x^5 + x^4 + x^3 + x^2 + 1
    L = len(code1)                                           # 31 chips per bit
    OS = 4                                                   # samples per chip
    nshow = 4                                                # bits shown
    nbits = 64                                               # bits the spectra are computed from
    def signals(bits):
        d = np.repeat(bits, L)
        return d, np.tile(code1, len(bits)), np.tile(code2, len(bits))
    bits = 1 - 2 * rng.integers(0, 2, nbits)
    d, c1, c2 = signals(bits)
    rows = [("the data: slow bits", d, C1),
            ("user 1's code: fast chips (31 per bit)", c1, INK2),
            ("sent: data × code", d * c1, C2),
            ("received × the same code: the data again", d * c1 * c1, C1),
            ("received × user 2's code: hiss", d * c1 * c2, C3)]
    def spectrum(v):
        acc = 0
        for _ in range(24):                                  # average over random data for a clean shape
            b = 1 - 2 * rng.integers(0, 2, nbits)
            dd, cc1, cc2 = signals(b)
            w = {0: dd, 1: cc1, 2: dd * cc1, 3: dd * cc1 * cc1, 4: dd * cc1 * cc2}[v]
            x = np.repeat(w, OS)
            acc = acc + np.abs(np.fft.rfft(x * np.hanning(len(x))))**2
        f = np.fft.rfftfreq(len(x), 1 / OS)                  # in units of the chip rate
        return f, acc
    f0, S0 = spectrum(0)
    top = S0.max()                                           # the data's peak: 0 dB in every row
    fig = plt.figure(figsize=(9.5, 6.6))
    gs = fig.add_gridspec(5, 2, width_ratios=[2.1, 1], hspace=0.55, wspace=0.12, left=0.03, right=0.985,
                          top=0.92, bottom=0.07)
    tt = np.arange(nshow * L * OS) / (L * OS)                # time in bits
    for r, (name, v, col) in enumerate(rows):
        ax = fig.add_subplot(gs[r, 0])
        ax.step(tt, np.repeat(v[:nshow * L], OS), where="post", color=col, lw=1.0 if r else 1.6)
        ax.fill_between(tt, 0, np.repeat(v[:nshow * L], OS), step="post", color=col, alpha=0.18, lw=0)
        bare(ax)
        for b in range(1, nshow):
            ax.axvline(b, color=AXIS, lw=0.7)
        ax.set_xlim(0, nshow)
        ax.set_ylim(-1.5, 1.5)
        ax.set_title(name, size=9.5)
        if r == 0:
            for b in range(nshow):
                ax.text(b + 0.5, 1.15, "1" if bits[b] > 0 else "0", ha="center", va="bottom", size=9, color=INK)
        if r == 4:
            ax.text(nshow / 2, -1.45, "time: 4 bits = 124 chips", ha="center", va="bottom", size=8, color=INK2)
        ax = fig.add_subplot(gs[r, 1])
        f, S = spectrum(r)
        S = 10 * np.log10(S / top + 1e-9)
        if r == 1:
            # The code repeats every bit, so its own spectrum is a comb of lines one bit rate
            # apart, whose heights depend on the record length: show its envelope instead,
            # the sinc^2 of a square chip, at 1/31 of the data's peak density (both have unit power).
            env = 10 * np.log10(np.sinc(f)**2 / L + 1e-9)
            ax.plot(f, env, color=col, lw=1.0, ls="--")
            ax.text(1.45, 2, "its envelope: a square chip's sinc²,\nout to the chip rate (it repeats every\nbit, so really a comb of lines)",
                    ha="right", va="top", size=7.6, color=INK2)
        else:
            ax.plot(f, S, color=col, lw=0.9)
            ax.fill_between(f, -50, S, color=col, alpha=0.18, lw=0)
        ax.set_xlim(0, 1.5)
        ax.set_ylim(-45, 6)
        ax.set_yticks([-40, -20, 0])
        ax.set_xticks([0, 0.5, 1, 1.5])
        ax.tick_params(labelsize=8)
        if r == 4:
            ax.set_xlabel("frequency (chip rates)")
        else:
            ax.tick_params(labelbottom=False)
        if r == 0:
            ax.set_title("its spectrum (dB, one scale)", size=9.5)
            ax.text(1.45, 2, "narrow and tall", ha="right", va="top", size=8, color=INK2)
        if r in (2, 4):
            ax.text(1.45, 2, "31 × wider, 15 dB lower:\nthe same power", ha="right", va="top", size=8, color=INK2)
        if r == 3:
            ax.text(1.45, 2, "narrow and tall again", ha="right", va="top", size=8, color=INK2)
    fig.text(0.03, 0.985, "Spreading is a multiplication, and so is despreading; the wrong code only adds hiss",
             ha="left", va="top", size=10.5, weight="bold")
    note(fig)
    finish(fig, "comms_d_cdma.png")


# ==== 6.10: chirps and pulse compression =======================================================
def analytic(x):
    """The analytic signal of a real x (its Hilbert pair), by the FFT."""
    X = np.fft.fft(x)
    n = len(x)
    hmask = np.zeros(n)
    hmask[0] = 1
    hmask[1:(n + 1) // 2] = 2
    if n % 2 == 0:
        hmask[n // 2] = 1
    return np.fft.ifft(X * hmask)


def fig_chirp():
    fs = 400e6                                               # a fine "analog" grid
    T, f0, f1 = 10e-6, 1e6, 11e6                             # 10 us, 1 to 11 MHz: B = 10 MHz, TB = 100
    B = f1 - f0
    fc = (f0 + f1) / 2
    t = np.arange(0, 20e-6, 1 / fs)
    on = t < T
    chirp = np.where(on, np.cos(2 * np.pi * (f0 * t + 0.5 * B / T * t**2)), 0.0)
    burst = np.where(on, np.cos(2 * np.pi * fc * t), 0.0)
    tp = 1 / B
    pulse = np.where(t < tp, np.cos(2 * np.pi * fc * (t - tp / 2)) * np.sin(np.pi * t / tp), 0.0)
    fig = plt.figure(figsize=(9.5, 6.6))
    gs = fig.add_gridspec(2, 2, hspace=0.42, wspace=0.26, left=0.08, right=0.98, top=0.9, bottom=0.08)
    # (a) the three signals in time
    ax = fig.add_subplot(gs[0, 0])
    tu = t * 1e6
    show = tu < 15.5
    for off, sig, col, name in [(2.6, burst, GREY, "10 µs tone burst\nat 6 MHz"),
                                (0.0, chirp, C1, "10 µs chirp\n1 to 11 MHz"),
                                (-2.6, pulse, C2, "0.1 µs pulse\n(= 1/B)")]:
        ax.plot(tu[show], off + sig[show], color=col, lw=0.6)
        ax.text(10.5, off, name, ha="left", va="center", size=8.2, color=col if col != GREY else INK2)
    ax.grid(False)
    ax.set_yticks([])
    ax.set_xlim(0, 15.5)
    ax.set_ylim(-4.0, 4.0)
    ax.set_xticks([0, 5, 10])
    ax.set_xlabel("time (µs)")
    ax.set_title("(a) three signals of the same amplitude", size=10)
    # (b) the chirp's spectrogram
    ax = fig.add_subplot(gs[0, 1])
    win, hop, nfft = 400, 40, 4096
    frames = [np.r_[chirp[i:i + win] * np.hanning(win), np.zeros(nfft - win)]
              for i in range(0, int(12e-6 * fs) - win, hop)]
    spec = np.abs(np.fft.rfft(np.array(frames), axis=1))**2
    fr = np.fft.rfftfreq(nfft, 1 / fs) / 1e6
    tf = (np.arange(len(frames)) * hop + win / 2) / fs * 1e6
    keep = fr <= 14
    ax.grid(False)
    ax.pcolormesh(tf, fr[keep], 10 * np.log10(spec[:, keep].T + 1e-9 * spec.max()) - 10 * np.log10(spec.max()),
                  cmap="Blues", vmin=-35, vmax=0, shading="nearest", rasterized=True)
    ax.plot([0, T * 1e6], [f0 / 1e6, f1 / 1e6], color=C2, lw=0.9, ls="--")
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 14)
    ax.set_xlabel("time (µs)")
    ax.set_ylabel("frequency (MHz)")
    ax.set_title("(b) spectrogram: the frequency ramps with time", size=10)
    ax.text(10.2, 1.0, "B = %.0f MHz\nin T = %.0f µs" % (B / 1e6, T * 1e6), ha="right", va="bottom", size=8.2, color=C2)
    # (c) the matched-filter outputs
    ax = fig.add_subplot(gs[1, 0])
    lag = (np.arange(-len(t) + 1, len(t))) / fs * 1e6
    for sig, col, name, lw in [(burst, GREY, "tone burst: long, so tall, but 20 µs wide", 1.1),
                               (pulse, C2, "short pulse: narrow, but 1/100 of the energy", 1.1),
                               (chirp, C1, "chirp: as tall as the burst, as narrow as the pulse", 1.6)]:
        y = np.abs(analytic(np.correlate(sig, sig, mode="full")))
        y = y / (0.5 * np.sum(chirp**2))
        ax.plot(lag, y, color=col, lw=lw)
        ax.text(0.5, 0.1, "", transform=ax.transAxes)
    ax.grid(False)
    ax.set_xlim(-12, 12)
    ax.set_ylim(0, 1.15)
    ax.set_xlabel("delay (µs)")
    ax.set_ylabel("|matched filter output|\n(chirp's peak = 1)")
    ax.set_title("(c) matched-filter outputs: pulse compression", size=10)
    ax.text(0.98, 0.95, "tone burst: 20 µs wide", transform=ax.transAxes, ha="right", va="top", size=8, color=INK2)
    ax.text(0.98, 0.85, "chirp: 1/B = 0.1 µs wide, peak 1", transform=ax.transAxes, ha="right", va="top", size=8, color=C1)
    ax.text(0.98, 0.75, "short pulse: 0.1 µs wide, peak 0.01", transform=ax.transAxes, ha="right", va="top", size=8, color=C2)
    # (d) delay-Doppler coupling: the chirp's ambiguity function
    ax = fig.add_subplot(gs[1, 1])
    fsb = 40e6                                               # baseband grid for the ambiguity function
    tb = np.arange(0, T, 1 / fsb)
    s = np.exp(1j * np.pi * (B / T) * tb**2)                 # the chirp at baseband (from -B/2 to +B/2)
    taus = np.arange(-3e-6, 3e-6 + 1e-9, 0.05e-6)
    nus = np.linspace(-4e6, 4e6, 161)
    amb = np.zeros((len(nus), len(taus)))
    E = np.vdot(s, s).real
    for i, tau in enumerate(taus):
        k = int(round(tau * fsb))
        if k >= 0:
            p = s[k:] * np.conj(s[:len(s) - k]); tt = tb[k:]
        else:
            p = s[:len(s) + k] * np.conj(s[-k:]); tt = tb[:len(s) + k]
        amb[:, i] = np.abs(np.exp(2j * np.pi * nus[:, None] * tt[None, :]) @ p) / E
    ax.grid(False)
    ax.pcolormesh(taus * 1e6, nus / 1e6, amb, cmap="Blues", vmin=0, vmax=1, shading="nearest", rasterized=True)
    ax.plot(taus * 1e6, -(B / T) * taus / 1e6, color=C2, lw=0.9, ls="--")
    ax.set_xlim(-3, 3)
    ax.set_ylim(-4, 4)
    ax.set_xlabel("delay (µs)")
    ax.set_ylabel("Doppler shift (MHz)")
    ax.set_title("(d) delay–Doppler coupling: a tilted ridge", size=10)
    ax.text(2.9, 3.7, "a Doppler shift ν looks like a delay\nof −ν / (B/T) = −ν × 1 µs/MHz:\nthe chirp can't tell them apart",
            ha="right", va="top", size=8, color=INK, bbox=dict(fc="white", ec="none", alpha=0.75, pad=1.5))
    fig.text(0.08, 0.975, "A chirp: the energy of a long pulse with the resolution of a short one (10 µs, 10 MHz: TB = 100)",
             ha="left", va="top", size=10.5, weight="bold")
    note(fig)
    finish(fig, "comms_d_chirp.png")


# ==== 6.10: LoRa ===============================================================================
def fig_lora():
    N = 128                                                  # chips per symbol: spreading factor 7
    vals = [10, 50, 90, 120]                                 # the four symbols' values
    n = np.arange(N)
    def upchirp(v):
        f = ((n + v) % N) / N                                # cycles per chip, 0 .. 1, wrapping: bins 0 .. N
        return np.exp(2j * np.pi * np.cumsum(f))
    base = upchirp(0)
    s = np.concatenate([upchirp(v) for v in vals])
    d = s * np.tile(np.conj(base), len(vals))                # dechirped: one tone per symbol
    def spectrogram(x, win=32, nfft=256):
        w = np.hanning(win)
        frames = np.array([np.r_[x[i:i + win] * w, np.zeros(nfft - win)] for i in range(0, len(x) - win + 1)])
        S = np.abs(np.fft.fft(frames, axis=1))**2
        fr = np.arange(nfft) / nfft                          # cycles per chip, 0 .. 1 (complex samples)
        tc = np.arange(len(frames)) + win / 2
        return tc, fr, S / S.max()
    fig = plt.figure(figsize=(9.5, 6.0))
    gs = fig.add_gridspec(3, 4, height_ratios=[1.3, 1.3, 1], hspace=0.6, wspace=0.25, left=0.08, right=0.98,
                          top=0.9, bottom=0.09)
    for r, (x, title) in enumerate([(s, "(a) four LoRa symbols (SF 7: 128 chips, 7 bits each): an up-chirp started at the symbol's value, wrapping round"),
                                    (d, "(b) multiplied by a down-chirp (the conjugate of the plain up-chirp): each symbol becomes one steady tone")]):
        ax = fig.add_subplot(gs[r, :])
        tc, fr, S = spectrogram(x)
        ax.grid(False)
        ax.pcolormesh(tc, fr * N, 10 * np.log10(S.T + 1e-6), cmap="Blues", vmin=-25, vmax=0, shading="nearest", rasterized=True)
        for k in range(1, len(vals)):
            ax.axvline(k * N, color=INK2, lw=0.8)
        for k, v in enumerate(vals):
            ax.text(k * N + N / 2, N + 4, "symbol value %d" % v, ha="center", va="bottom", size=8.5, color=INK)
            if r == 1:
                ax.plot([k * N, (k + 1) * N], [v, v], color=C2, lw=0.8, ls="--")
        ax.set_xlim(0, len(x))
        ax.set_ylim(0, N + 22)
        ax.set_yticks([0, 64, 128])
        ax.set_ylabel("frequency (bins)")
        ax.set_title(title, size=9.5)
        if r == 1:
            ax.set_xlabel("time (chips): %d per symbol" % N)
        else:
            ax.tick_params(labelbottom=False)
    for k, v in enumerate(vals):
        ax = fig.add_subplot(gs[2, k])
        Y = np.abs(np.fft.fft(d[k * N:(k + 1) * N])) / N
        ax.vlines(np.arange(N), 0, Y, color=C1, lw=0.8)
        ax.plot(v, Y[v], "o", color=C2, markersize=5, zorder=5)
        ax.text(v, Y[v] + 0.05, "bin %d" % v, ha="center", va="bottom", size=8.5, color=C2)
        ax.grid(False)
        ax.set_xlim(-3, N + 12)
        ax.set_ylim(0, 1.3)
        ax.set_xticks([0, 64, 127])
        ax.set_yticks([])
        ax.set_xlabel("FFT bin")
        if k == 0:
            ax.set_title("(c) a %d-point FFT of each dechirped symbol: one peak, at the value" % N, size=10)
    fig.text(0.08, 0.975, "LoRa: a symbol is a chirp with a cyclic shift; one multiplication and one FFT read the shift back",
             ha="left", va="top", size=10.5, weight="bold")
    note(fig)
    finish(fig, "comms_d_lora.png")


# ==== 6.00: what runs where ====================================================================
def prompt(ax, x, y, text, what, size=19, color=INK, w=0):
    """A prompt printed large, with what it belongs to beside it."""
    ax.text(x, y, text, ha="left", va="center", size=size, family=MONO, weight="bold", color=color)
    ax.text(x + w, y, what, ha="left", va="center", size=8.4, color=INK2)


def fig_where():
    fig, ax = canvas(10, 5.2)
    # the laptop
    box(ax, 1.0, 3.0, 36.0, 44.0, fc=GREEN_BG, ec=C3, r=1.5)
    ax.text(3.0, 44.5, "the laptop", ha="left", va="center", size=11, weight="bold", color=INK)
    ax.text(3.0, 41.3, "every script in src/comms, and every figure", ha="left", va="center", size=8.4, color=INK2)
    prompt(ax, 3.0, 35.0, "$", "the shell", w=5.0)
    for k, t in enumerate(["make load-awgcap     (the bitstream, over USB)", "python3 psk.py         (plays, records, decodes)",
                           "litex_term /dev/ttyUSB0      (a terminal)", "litex_server --uart ...      (a bridge, 2.06)"]):
        ax.text(5.0, 31.4 - 2.6 * k, t, ha="left", va="center", size=7.6, family=MONO, color=INK)
    prompt(ax, 3.0, 17.0, ">>>", "CPython, with numpy", w=9.0)
    for k, t in enumerate(["import psk, channel", "from litex import RemoteClient     (2.06)"]):
        ax.text(5.0, 13.2 - 2.6 * k, t, ha="left", va="center", size=7.6, family=MONO, color=INK)
    ax.text(3.0, 6.0, "its serial ports: /dev/ttyUSB0, /dev/ttyUSB1  (macOS: /dev/cu.usbserial-…)", ha="left",
            va="center", size=7.4, color=INK2)
    # board A, bare metal or LiteX
    box(ax, 44.0, 27.0, 29.0, 20.0, fc=BLUE_BG, ec=C1, r=1.5)
    ax.text(46.0, 44.5, "the board, bare metal or LiteX", ha="left", va="center", size=10.5, weight="bold", color=INK)
    ax.text(46.0, 41.3, "Chapters 1, 2, 4, 5 and 6: whatever you loaded", ha="left", va="center", size=8.4, color=INK2)
    ax.text(46.0, 37.3, "awgcap.sv", ha="left", va="center", size=9.5, family=MONO, weight="bold", color=INK)
    ax.text(56.0, 37.3, "no prompt: Python drives it", ha="left", va="center", size=7.8, color=INK2)
    prompt(ax, 46.0, 33.0, "litex>", "the BIOS (2.01)", size=15, w=13.0)
    prompt(ax, 46.0, 29.5, "adda>", "the firmware (2.04)", size=15, w=13.0)
    # board A, Linux
    box(ax, 44.0, 3.0, 29.0, 20.0, fc=BLUE_BG, ec=C1, r=1.5)
    ax.text(46.0, 20.5, "the same board, under Linux", ha="left", va="center", size=10.5, weight="bold", color=INK)
    ax.text(46.0, 17.3, "Chapter 3, and 5.05's modem", ha="left", va="center", size=8.4, color=INK2)
    prompt(ax, 46.0, 12.5, "#", "root's shell (3.01)", w=5.0)
    prompt(ax, 46.0, 6.5, ">>>", "MicroPython (3.01)", w=9.0)
    # board B
    box(ax, 80.0, 3.0, 19.0, 44.0, fc=ORANGE_BG, ec=C2, r=1.5)
    ax.text(82.0, 44.5, "a second board", ha="left", va="center", size=10.5, weight="bold", color=INK)
    ax.text(82.0, 41.3, "Chapters 5 and 6", ha="left", va="center", size=8.4, color=INK2)
    ax.text(82.0, 37.3, "awgcap.sv", ha="left", va="center", size=9.5, family=MONO, weight="bold", color=INK)
    ax.text(82.0, 34.6, "A plays, B records", ha="left", va="center", size=7.8, color=INK2)
    prompt(ax, 82.0, 12.5, "B#", "its Linux shell", size=17, w=8.0)
    ax.text(82.0, 8.5, "(and the first board's is A#)", ha="left", va="center", size=7.6, color=INK2)
    ax.text(82.0, 20.5, "under Linux", ha="left", va="center", size=10.5, weight="bold", color=INK)
    # the cables
    usb = dict(color=INK2, lw=2.4, solid_capstyle="round", zorder=1)
    ax.plot([37.0, 44.0], [37.0, 37.0], **usb)
    ax.plot([37.0, 44.0], [13.0, 13.0], **usb)
    ax.plot([37.0, 80.0], [25.0, 25.0], **usb)
    for x, y in [(40.5, 38.2), (40.5, 14.2), (58.5, 26.2)]:
        ax.text(x, y, "USB", ha="center", va="bottom", size=7.6, color=INK2)
    coax = dict(color="#6d6d6d", lw=3.0, solid_capstyle="round", zorder=1)
    ax.plot([73.0, 80.0], [31.0, 31.0], **coax)
    ax.text(76.5, 32.2, "coax", ha="center", va="bottom", size=7.6, color=INK2)
    ax.text(76.5, 29.8, "DAC → ADC", ha="center", va="top", size=6.6, color=INK2)
    ax.text(50.0, 50.0, "What runs where: the prompt tells you which machine you are typing at", ha="center",
            va="center", size=11, weight="bold", color=INK)
    finish(fig, "comms_d_where.png")


# ==== 6.11: the modem in the FPGA ==============================================================
def chain_row(ax, y, h, left, blocks, gap=1.5, size=7.4):
    """A row of nodes, left to right from `left`, an arrow between each pair.  blocks are
    (width, lines, fc, ec).  Returns the centres and the widths."""
    xs, ws, x = [], [], left
    for w, lines, fc, ec in blocks:
        node(ax, x + w / 2, y, w, h, lines, fc=fc, ec=ec, size=size)
        xs.append(x + w / 2)
        ws.append(w)
        x += w + gap
    for k in range(len(xs) - 1):
        arrow(ax, (xs[k] + ws[k] / 2 + 0.1, y), (xs[k + 1] - ws[k + 1] / 2 - 0.1, y), ms=8)
    return xs, ws


def bracket(ax, x0, x1, y, text, above=True, size=7.6):
    """A bracket from x0 to x1 at y, opening away from a row of blocks, its text beyond it."""
    d = 0.8 if above else -0.8
    ax.plot([x0, x0, x1, x1], [y, y + d, y + d, y], color=MUTED, lw=1)
    ax.text((x0 + x1) / 2, y + d + (0.4 if above else -0.4), text, ha="center",
            va="bottom" if above else "top", size=size, color=INK2)


def fig_modem_fpga():
    N, G, B, O = (NEUTRAL, NEUTRAL_EDGE), (GREEN_BG, C3), (BLUE_BG, C1), (ORANGE_BG, C2)
    fig, ax = canvas(10, 8.2)
    ax.text(1.0, 79.0, "The modem in the FPGA (qpsk_modem.sv): psk.py's modem one clock at a time, in integers and shifts",
            ha="left", va="center", size=10.5, weight="bold", color=INK)
    # ---- the transmitter: one row, one DAC sample per clock ----
    ty, h = 66.0, 9.6
    tx = [(6.0, [("serial in", BOLD), "1 Mbaud"], *G),
          (8.0, [("a byte waits", BOLD), "for the next", "frame"], *N),
          (12.5, [("frame", BOLD), "sync 1110010 | valid |", "byte (or LFSR bits)", "16 bits = 8 symbols"], *N),
          (9.5, [("Gray; q += dq", BOLD), "differential: the", "2 bits say how", "far to turn"], *N),
          (7.5, [("13-symbol", BOLD), "shift register"], *N),
          (9.5, [("13 pulse tables", BOLD), "±, 32 phases", "per symbol"], *N),
          (7.5, [("adder trees", BOLD), "I, Q"], *N),
          (12.5, [("carrier at fs/8", BOLD), "I, 0.707(I−Q), −Q,", "0.707(−I−Q), …", "0.707 = 181/256"], *N),
          (5.5, [("÷8, +128", BOLD)], *N),
          (5.5, [("DAC", BOLD), "50 MS/s"], *O)]
    xs, ws = chain_row(ax, ty, h, 1.5, tx, gap=1.4, size=7.2)
    ax.text(1.0, ty + h / 2 + 2.6, "transmitter", ha="left", va="center", size=9.5, color=INK2, style="italic")
    bracket(ax, xs[4] - ws[4] / 2, xs[6] + ws[6] / 2, ty + h / 2 + 0.5,
            "the pulse shaper: table look-ups and adds, no multipliers")
    bracket(ax, xs[7] - ws[7] / 2, xs[8] + ws[8] / 2, ty + h / 2 + 0.5, "a choice, then × 181")
    bracket(ax, xs[0] - ws[0] / 2, xs[9] + ws[9] / 2, ty - h / 2 - 0.5,
            "1 clock per DAC sample (50 MHz): 32 per symbol, 256 per frame, 195,312 frames a second", above=False)
    # ---- the receiver: two rows ----
    ry, h2 = 46.0, 9.6
    rxa = [(6.5, [("ADC", BOLD), "25 MS/s"], *B),
           (10.0, [("mix down", BOLD), "× 1, −j, −1, j", "(free)"], *N),
           (23.0, [("half-band filter", BOLD), "I = the even sample; Q interpolated", "from its 4 odd neighbours,",
                   "taps −1 0 9 16 9 0 −1 (/32);", "keep the even ones → 12.5 MS/s"], *N),
           (10.5, [("[1 2 1]", BOLD), "keep 1 in 2", "→ 6.25 MS/s"], *N),
           (9.0, [("droop EQ", BOLD), "9/128", "3 taps, shifts"], *N),
           (16.5, [("matched filter", BOLD), "49 taps, symmetric", "8 multipliers × 7 clocks"], *N)]
    xa, wa = chain_row(ax, ry, h2, 1.5, rxa, gap=1.6, size=7.4)
    ax.text(1.0, ry + h2 / 2 + 2.6, "receiver", ha="left", va="center", size=9.5, color=INK2, style="italic")
    bracket(ax, xa[0] - wa[0] / 2, xa[2] + wa[2] / 2, ry - h2 / 2 - 0.5, "2 clocks per ADC sample", above=False)
    bracket(ax, xa[3] - wa[3] / 2, xa[5] + wa[5] / 2, ry - h2 / 2 - 0.5,
            "8 clocks per sample (4 samples per symbol)", above=False)
    ry2 = 25.0
    rxb = [(13.0, [("interpolator", BOLD), "Catmull-Rom's cubic", "6 multipliers"], *N),
           (13.0, [("rotate by −φ", BOLD), "sine table, 1024 entries", "4 multipliers"], *N),
           (13.0, [("quadrant", BOLD), "e = ±Q ∓ I", "→ PI (<<7, <<2) → φ"], *N),
           (12.0, [("dq = q − q_prev", BOLD), "un-Gray → 2 bits"], *N),
           (13.0, [("16-bit register", BOLD), "sync ×3 = lock", "8 misses = unlock"], *N),
           (6.5, [("FIFO", BOLD), "32 bytes"], *N),
           (8.0, [("serial out", BOLD), "1 Mbaud"], *G)]
    xb, wb = chain_row(ax, ry2, h2, 1.5, rxb, gap=1.6, size=7.4)
    # from the matched filter, down and round to the interpolator
    xr, ym = xa[5] + wa[5] / 2, 35.5
    ax.plot([xr, xr + 3.0, xr + 3.0, xb[0]], [ry, ry, ym, ym], color=INK2, lw=1.3)
    arrow(ax, (xb[0], ym), (xb[0], ry2 + h2 / 2 + 0.1))
    ax.text((xr + xb[0]) / 2, ym - 0.7, "I + jQ, 16 bits each, 4 samples per symbol", ha="center", va="top",
            size=7.4, color=INK2, style="italic")
    # the timing loop, under the interpolator: NCO -> interpolator -> Gardner -> NCO
    nco_x, gar_x, sy, sh = 6.0, 22.5, 10.5, 7.0
    node(ax, nco_x, sy, 9.0, sh, [("NCO", BOLD), "τ, μ; symbol", "and mid strobes"], size=7.4)
    node(ax, gar_x, sy, 20.0, sh, [("Gardner", BOLD), "Re(mid · (now − prev)*)", "→ PI (>>7, >>5)"], size=7.4)
    arrow(ax, (nco_x, sy + sh / 2 + 0.1), (nco_x, ry2 - h2 / 2 - 0.1))
    ax.text(nco_x + 0.7, (sy + sh / 2 + ry2 - h2 / 2) / 2, "μ, strobes", ha="left", va="center", size=6.8, color=INK2)
    xg = xb[0] + wb[0] / 2 - 1.0
    arrow(ax, (xg, ry2 - h2 / 2 - 0.1), (xg, sy + sh / 2 + 0.1))
    ax.text(xg + 0.7, (sy + sh / 2 + ry2 - h2 / 2) / 2, "now, mid", ha="left", va="center", size=6.8, color=INK2)
    arrow(ax, (gar_x - 10.0 - 0.1, sy), (nco_x + 4.5 + 0.1, sy))
    # the carrier loop: phi from the quadrant block back to the rotation
    yc = 17.3
    ax.plot([xb[2], xb[2], xb[1]], [ry2 - h2 / 2, yc, yc], color=INK2, lw=1.3)
    arrow(ax, (xb[1], yc), (xb[1], ry2 - h2 / 2 - 0.1))
    ax.text((xb[1] + xb[2]) / 2, yc - 0.6, "φ, 24 bits per turn: the Costas loop", ha="center", va="top",
            size=7.0, color=INK2, style="italic")
    bracket(ax, xb[0] - wb[0] / 2, xb[6] + wb[6] / 2, 5.6, "once per symbol, 32 clocks: Gardner, the Costas loop, "
            "the decision and the frame sync are a pipeline, one clock each", above=False)
    note(fig, "the blocks of qpsk_modem.sv")
    finish(fig, "comms_d_modem_fpga.png")


# ==== 6.12: the FT8-style frame ================================================================
def fig_ft8():
    N, G = (NEUTRAL, NEUTRAL_EDGE), (GREEN_BG, C3)
    text = "CQ HMC JASON"
    tones = ft8.encode(text)
    costas = set(p + c for p in ft8.COSTAS_AT for c in range(7))
    fig, ax = canvas(10, 8.4)
    ax.text(1.0, 81.5, "An FT8-style frame (ft8.py): 12 characters become 79 tones, 8-FSK", ha="left",
            va="center", size=10.5, weight="bold", color=INK)
    # ---- the frame: 79 symbols, 8 tones ----
    x0, sw, sy, sh = 6.0, 92.0 / ft8.NSYM, 64.0, 8.0
    for p in ft8.COSTAS_AT:
        box(ax, x0 + p * sw, sy, 7 * sw, sh, fc=ORANGE_BG, ec=C2, lw=0.9, r=0.3)
        ax.text(x0 + (p + 3.5) * sw, sy + sh + 0.6, "Costas array\n3 1 4 0 6 5 2", ha="center", va="bottom",
                size=7.2, color=C2)
        for c in range(7):
            for r in range(8):
                ax.plot(x0 + (p + c + 0.5) * sw, sy + r + 0.5, ".", color=GREY, markersize=2.0, zorder=3)
    for p in (ft8.DATA_AT[0], ft8.DATA_AT[29]):
        box(ax, x0 + p * sw, sy, 29 * sw, sh, fc=NEUTRAL, ec=NEUTRAL_EDGE, lw=0.9, r=0.3)
        ax.text(x0 + (p + 14.5) * sw, sy + sh + 0.6, "29 data symbols", ha="center", va="bottom", size=7.6, color=INK2)
    for k, t in enumerate(tones):
        ax.plot(x0 + (k + 0.5) * sw, sy + t + 0.5, "o", color=C2 if k in costas else C1, markersize=3.4,
                markeredgecolor=SURFACE, markeredgewidth=0.4, zorder=5)
    for t in (0, 7):
        ax.text(x0 - 0.7, sy + t + 0.5, "tone %d" % t, ha="right", va="center", size=6.8, color=INK2)
    for p in (0, 7, 36, 43, 72, 79):
        ax.text(x0 + p * sw, sy - 0.5, str(p), ha="center", va="top", size=6.8, color=MUTED)
    ax.text(x0 - 0.7, sy - 0.5, "symbol", ha="right", va="top", size=6.8, color=MUTED)
    ax.text(1.0, sy - 3.4, 'the frame for "%s": 79 symbols, one of 8 tones each (ft8.encode); the Costas arrays are the '
            "same in every frame, and the receiver finds them first" % text, ha="left", va="top", size=8.0, color=INK)
    # ---- the encoding chain, with the bit counts on the wires ----
    cy, ch = 50.5, 8.6
    chain = [(15.5, [("12 characters", BOLD), "42-symbol alphabet:", "A–Z 0–9 + − . / ? space"], *G),
             (12.0, [("+ CRC-14", BOLD), "FT8's 0x2757"], *N),
             (17.0, [("convolutional code", BOLD), "K = 7, rate ½ (6.09)", "6 tail bits"], *N),
             (17.0, [("3 bits → Gray → tone", BOLD), "0 1 3 2 5 6 4 7"], *N),
             (15.0, [("58 data symbols", BOLD), "into the two blocks"], *N)]
    xs, ws = chain_row(ax, cy, ch, 1.75, chain, gap=5.0, size=7.6)
    for k, t in enumerate(["65 bits", "79 bits", "170 + 4 pad = 174 code bits", "3 bits per symbol"]):
        ax.text((xs[k] + ws[k] / 2 + xs[k + 1] - ws[k + 1] / 2) / 2, cy + ch / 2 + 0.6, t, ha="center",
                va="bottom", size=7.6, color=INK2, style="italic")
    # ---- (a) one symbol: one of 8 tones, T long ----
    ax.text(1.0, 43.0, "(a) a symbol is one of 8 tones, T long", ha="left", va="center", size=9, weight="bold", color=INK)
    a = inset(fig, 3.0, 12.5, 27.0, 27.0)
    chosen = 3
    for k in range(8):
        if k == chosen:
            tt = np.linspace(0, 1, 400)
            a.plot(tt, k + 0.32 * np.sin(2 * np.pi * 7 * tt), color=C1, lw=1.6)
        else:
            a.plot([0, 1], [k, k], color=GREY, lw=1.0, ls=(0, (4, 3)))
        a.text(1.04, k, "tone %d" % k, ha="left", va="center", size=6.8, color=C1 if k == chosen else MUTED)
    a.annotate("", (1.33, 6), (1.33, 5), arrowprops=dict(arrowstyle="<->", color=C2, lw=1.0, mutation_scale=7))
    a.text(1.37, 5.5, "Δf", ha="left", va="center", size=8, color=C2)
    a.annotate("", (1, -0.7), (0, -0.7), arrowprops=dict(arrowstyle="<->", color=C2, lw=1.0, mutation_scale=7))
    a.text(0.5, -0.95, "T = 1/Δf", ha="center", va="top", size=8, color=C2)
    a.plot([0, 0], [-0.3, 7.4], color=AXIS, lw=0.8)
    a.text(0.0, 7.6, "frequency", ha="left", va="bottom", size=6.8, color=MUTED)
    a.set_xlim(-0.08, 1.6)
    a.set_ylim(-2.0, 8.4)
    ax.text(16.5, 10.8, "tones 1/T apart: orthogonal, like OFDM's subcarriers (6.07):\na sine T long has a sinc spectrum, "
            "zero at every other tone", ha="center", va="top", size=7.6, color=INK2)
    # ---- (b) the receiver ----
    ax.text(35.0, 43.0, "(b) the receiver, both speeds", ha="left", va="center", size=9, weight="bold", color=INK)
    rx1 = [(18.0, [("correlate", BOLD), "every symbol-long window", "with each of the 8 tones"], *N),
           (18.0, [("8 magnitudes", BOLD), "per symbol time"], *N),
           (18.0, [("Costas search", BOLD), "over start time × frequency", "offset: the biggest sum"], *N)]
    rx2 = [(18.0, [("soft bits", BOLD), "best tone with the bit 0", "minus best with it 1"], *N),
           (18.0, [("Viterbi", BOLD), "soft decisions (6.09)"], *N),
           (18.0, [("CRC ok?", BOLD), "→ text"], *G)]
    y1, y2, hh = 36.0, 25.0, 7.6
    x1s, w1s = chain_row(ax, y1, hh, 36.0, rx1, gap=2.5, size=7.4)
    x2s, w2s = chain_row(ax, y2, hh, 36.0, rx2, gap=2.5, size=7.4)
    ym = (y1 - hh / 2 + y2 + hh / 2) / 2
    ax.plot([x1s[2], x1s[2], x2s[0]], [y1 - hh / 2, ym, ym], color=INK2, lw=1.3)
    arrow(ax, (x2s[0], ym), (x2s[0], y2 + hh / 2 + 0.1))
    ax.text(36.0, y1 + hh / 2 + 0.6, "I/Q at baseband (fast: × 1, −j, −1, j on the laptop; slow: ddc.sv's stream)",
            ha="left", va="bottom", size=7.2, color=INK2, style="italic")
    # ---- the three speeds ----
    tx0, ty0 = 58.0, 17.5
    ax.text(tx0, ty0, "the same 79 symbols at three speeds", ha="left", va="center", size=8.2, weight="bold", color=INK)
    cols = [("", tx0, "left"), ("symbol", 76.5, "right"), ("tones apart", 85.5, "right"), ("carrier", 93.0, "right"),
            ("frame", 99.0, "right")]
    speeds = [("fast: awgcap.sv (6.00)", "4 µs", "250 kHz", "6.25 MHz", "316 µs"),
              ("slow: ddc.sv (6.12)", "167.8 ms", "5.96 Hz", "6.78 MHz", "13.25 s"),
              ("real FT8", "160 ms", "6.25 Hz", "7.074 MHz", "12.64 s")]
    for name, x, ha in cols:
        ax.text(x, ty0 - 2.8, name, ha=ha, va="center", size=7.2, color=INK2)
    ax.plot([tx0, 99.0], [ty0 - 4.1, ty0 - 4.1], color=AXIS, lw=0.8)
    for r, vals in enumerate(speeds):
        yy = ty0 - 5.6 - 2.5 * r
        for (name, x, ha), v in zip(cols, vals):
            ax.text(x, yy, v, ha=ha, va="center", size=7.2, color=INK)
    note(fig)
    finish(fig, "comms_d_ft8.png")


# ==== 6.12: the antenna ladder =================================================================
def fig_air():
    fig, ax = canvas(10, 7.8)
    ax.text(1.0, 75.5, "The antenna ladder: how far a whisper from the DAC reaches an ADC, with no radio between (air.py, 6.78 MHz)",
            ha="left", va="center", size=10, weight="bold", color=INK)
    ys = [9.0, 22.0, 35.0, 48.0, 61.0]
    xl, xr, cx = 19.0, 80.0, 27.0                            # the rails, and the sketches' centre
    for x in (xl, xr):
        ax.plot([x, x], [3.0, 69.0], color=INK2, lw=2.4, solid_capstyle="round", zorder=1)
    for y in ys:
        ax.plot([xl, xr], [y - 5.5, y - 5.5], color=INK2, lw=2.0, zorder=1)
    labels = ["1  minigrabber leads on both SMAs (a 10 cm wire each):\n    the electric near field, 1/r³: tens of centimetres",
              "2  a tuned 30 cm loop on each (5.07): the magnetic near field,\n    1/r³ to λ/2π = 7 m, then 1/r: metres with the modem,\n"
              "    tens of metres with the FT8-style frame",
              "3  an active receiving loop, 40 dB of gain before the ADC:\n    the ADC's floor stops mattering, the sky's noise starts:\n"
              "    hundreds of metres",
              "4  a half-wave dipole (22 m at 6.78 MHz, 11 m at 13.56 MHz)\n    at the legal field strength: kilometres",
              "5  a licence, 7.074 MHz and real FT8: the world"]
    for y, t in zip(ys, labels):
        ax.text(37.0, y, t, ha="left", va="center", size=8.0, color=INK)
    # rung 1: two wires, a grabber clip on each, the field lines between them
    y = ys[0]
    for dx in (-3.5, 3.5):
        ax.add_patch(Rectangle((cx + dx - 0.9, y - 4.0), 1.8, 1.4, fc=INK2, ec="none", zorder=3))
        ax.plot([cx + dx, cx + dx], [y - 2.6, y + 1.6], color=INK, lw=1.3, zorder=3)
        ax.plot([cx + dx, cx + dx], [y + 1.6, y + 3.2], color=INK2, lw=3.2, solid_capstyle="round", zorder=3)
        th = np.linspace(0, np.pi, 20)
        ax.plot(cx + dx - 0.5 + 0.5 * np.cos(th), y + 3.2 + 0.5 * np.sin(th), color=INK, lw=1.0, zorder=3)
    for rad in (0.35, 0.6):
        ax.annotate("", (cx + 3.5, y + 3.6), (cx - 3.5, y + 3.6), arrowprops=dict(
            arrowstyle="-", color=C1, lw=0.8, ls="--", connectionstyle="arc3,rad=%.2f" % -rad))
    # rung 2: two loops, a capacitor in each
    y = ys[1]
    for dx in (-4.0, 4.0):
        ax.add_patch(Circle((cx + dx, y + 0.6), 3.0, fc="none", ec=INK, lw=1.5, zorder=3))
        ax.add_patch(Rectangle((cx + dx - 0.55, y - 3.3), 1.1, 1.8, fc=SURFACE, ec="none", zorder=4))
        for s in (-0.3, 0.3):
            ax.plot([cx + dx + s, cx + dx + s], [y - 3.2, y - 1.6], color=INK, lw=1.3, zorder=5)
    # rung 3: a loop, an amplifier, the ADC
    y = ys[2]
    ax.add_patch(Circle((22.5, y), 2.8, fc="none", ec=INK, lw=1.5, zorder=3))
    ax.plot([25.3, 26.3], [y, y], color=INK, lw=1.3, zorder=3)
    ax.add_patch(Polygon([(26.3, y + 2.2), (26.3, y - 2.2), (30.0, y)], closed=True, fc="white", ec=INK, lw=1.3, zorder=3))
    ax.text(28.0, y + 2.8, "+40 dB", ha="center", va="bottom", size=6.8, color=INK2)
    arrow(ax, (30.0, y), (31.6, y), ms=7)
    node(ax, 33.8, y, 4.2, 3.2, [("ADC", {"weight": "bold", "size": 6.8})], fc=BLUE_BG, ec=C1, size=6.8)
    # rung 4: a half-wave dipole, fed in the middle
    y = ys[3]
    for xa, xb in [(20.0, 26.3), (27.7, 34.0)]:
        ax.plot([xa, xb], [y + 1.2, y + 1.2], color=INK, lw=2.0, solid_capstyle="round", zorder=3)
    for x in (26.3, 27.7):
        ax.plot([x, x], [y + 1.2, y - 2.0], color=INK, lw=1.0, zorder=3)
    ax.text(27.0, y - 2.4, "feed", ha="center", va="top", size=6.5, color=INK2)
    ax.annotate("", (34.0, y + 3.0), (20.0, y + 3.0), arrowprops=dict(arrowstyle="<->", color=C2, lw=0.9, mutation_scale=7))
    ax.text(27.0, y + 3.3, "λ/2 = 22 m", ha="center", va="bottom", size=6.8, color=C2)
    # rung 5: the dipole, and the world
    y = ys[4]
    for xa, xb in [(20.0, 23.6), (25.0, 28.6)]:
        ax.plot([xa, xb], [y + 1.2, y + 1.2], color=INK, lw=2.0, solid_capstyle="round", zorder=3)
    for x in (23.6, 25.0):
        ax.plot([x, x], [y + 1.2, y - 1.5], color=INK, lw=1.0, zorder=3)
    th = np.linspace(-0.7, 0.7, 30)
    for r in (3.6, 5.0):
        ax.plot(24.3 + r * np.cos(th), y + 1.2 + r * np.sin(th), color=C1, lw=0.8, ls="--", zorder=2)
    gx, gr = 32.8, 2.8
    ax.add_patch(Circle((gx, y), gr, fc="none", ec=INK, lw=1.3, zorder=3))
    th = np.linspace(0, 2 * np.pi, 80)
    ax.plot(gx + gr * np.cos(th), y + 0.35 * gr * np.sin(th), color=INK2, lw=0.8, zorder=3)
    ax.plot(gx + 0.4 * gr * np.cos(th), y + gr * np.sin(th), color=INK2, lw=0.8, zorder=3)
    ax.plot([gx - gr, gx + gr], [y, y], color=INK2, lw=0.8, zorder=3)
    ax.plot([gx, gx], [y - gr, y + gr], color=INK2, lw=0.8, zorder=3)
    # the two laws, along the left
    ax.text(1.0, 15.5, "near field, within λ/2π:\nfields fall as 1/r³\n(twice as far: 18 dB weaker)", ha="left",
            va="center", size=7.4, color=INK2)
    ax.text(1.0, 48.0, "far field, beyond\nλ/2π = 7 m: 1/r\n(twice as far: 6 dB weaker)", ha="left", va="center",
            size=7.4, color=INK2)
    for y0, y1 in [(3.5, 28.0), (29.5, 69.0)]:
        ax.plot([18.0, 17.5, 17.5, 18.0], [y0, y0, y1, y1], color=MUTED, lw=1)
    # the distance scale, log, on the right
    sx, s0, dec = 92.5, 5.0, 10.0

    def sy(m):
        return s0 + (np.log10(m) + 2) * dec

    ax.plot([sx, sx], [sy(0.01), sy(1e4) + 2.0], color=INK2, lw=1.2)
    arrow(ax, (sx, sy(1e4) + 2.0), (sx, sy(1e4) + 5.0), ms=8)
    for m, t in [(0.01, "1 cm"), (0.1, "10 cm"), (1, "1 m"), (10, "10 m"), (100, "100 m"), (1e3, "1 km"), (1e4, "10 km")]:
        ax.plot([sx - 0.6, sx + 0.6], [sy(m), sy(m)], color=INK2, lw=1.0)
        ax.text(sx + 1.2, sy(m), t, ha="left", va="center", size=7.2, color=INK2)
    ax.text(sx, sy(1e4) + 6.8, "how far (log scale)", ha="center", va="center", size=8, weight="bold", color=INK)
    bars = [(0.1, 1.0, "1", C1), (1.0, 10.0, "2, the modem", C2), (10.0, 100.0, "2, FT8-style", C1),
            (100.0, 1e3, "3", C1), (1e3, 1e4, "4", C1)]
    for lo, hi, t, c in bars:
        ax.plot([sx - 2.2, sx - 2.2], [sy(lo) + 0.3, sy(hi) - 0.3], color=c, lw=5, solid_capstyle="butt", zorder=3)
        ax.text(sx - 3.2, (sy(lo) + sy(hi)) / 2, t, ha="right", va="center", size=7.4, weight="bold", color=c)
    arrow(ax, (sx - 2.2, sy(1e4) + 0.3), (sx - 2.2, sy(1e4) + 5.5), color=C1, lw=3, ms=12)
    ax.text(sx - 3.2, sy(1e4) + 2.5, "5, the world", ha="right", va="center", size=7.4, weight="bold", color=C1)
    ax.plot([sx - 6.0, sx + 6.5], [sy(7), sy(7)], color=C2, lw=0.9, ls="--", zorder=2)
    ax.text(sx + 6.5, sy(7) - 0.5, "λ/2π = 7 m", ha="right", va="top", size=6.8, color=C2)
    note(fig, "computed, not measured: see air.py", top=False)
    finish(fig, "comms_d_air.png")


if __name__ == "__main__":
    for name, f in [("rxchain", fig_rxchain), ("constellations", fig_constellations),
                    ("gardner", fig_gardner), ("costas", fig_costas), ("msk", fig_msk),
                    ("channel", fig_channel), ("ofdm", fig_ofdm), ("cdma", fig_cdma),
                    ("chirp", fig_chirp), ("lora", fig_lora), ("where", fig_where),
                    ("modem_fpga", fig_modem_fpga), ("ft8", fig_ft8), ("air", fig_air)]:
        if want(name):
            f()
