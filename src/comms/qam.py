#!/usr/bin/env python3
"""8PSK, 16-QAM and 64-QAM through the cable: more bits per symbol, and what each one costs.

    python3 qam.py                      # 16-QAM, one board looped back (finds its port)
    python3 qam.py PORT_A PORT_B        # board A plays, board B records
    python3 qam.py --sim                # no board: the channel model of channel.py
    python3 qam.py -M 64                # 64-QAM (6 bits per symbol); -M 8 is 8PSK, -M 4 QPSK
    python3 qam.py --ebn0 14            # add noise at the transmitter: Eb/N0 = 14 dB
    python3 qam.py --ber 6:18           # bit error rate against Eb/N0, 6 to 18 dB
    python3 qam.py --amp 40             # the DAC waveform's rms, in codes (default: its
                                        #   peaks at 100 codes, as psk.py); above 255 clips
    python3 qam.py --amp-sweep          # MER against the DAC's rms: quantisation, then clipping
    python3 qam.py --cfo 3000 --sro 2000    # offsets for the loops to find, as psk.py
    python3 qam.py -o qam.npz --no-plot

Everything psk.py built stays: the frame (a 32-symbol unique word, then 480 data symbols
per loop), root-raised-cosine pulses at 1.5625 Msymbol/s, the 6.25 MHz carrier, the
matched filter and Gardner's timing loop are imported from it.  What changes:

  symbols  a bigger alphabet.  8PSK: 8 phases, 3 bits.  16-QAM: I and Q each take one
           of 4 levels (-3 -1 1 3), 4 bits.  64-QAM: 8 levels each, 6 bits.  Gray-coded
           along each axis, so a neighbour differs in one bit.  Average power 1.
  gain     PSK only needed the phase right.  QAM needs the AMPLITUDE right too: an AGC
           scales the symbols to rms 1 (coarse), the nearest-point decisions then trim
           the scale (fine), and the rings of |z| show whether it worked.
  carrier  psk.py's Costas loop again: the error is the angle to the NEAREST point.
           For 64-QAM the nearest point is the wrong one once the phase is more than
           about 5 degrees off, and the loop has false resting points at 12-20
           degrees, so it can only TRACK.  Three things make sure it never has to
           acquire: for square QAM the carrier offset is first measured from the x^4
           line (6.02's fll.py) and removed; the loop waits 300 symbols for the timing
           loop to settle; and it starts from the phase the x^4 trick gives.
           The classic Costas detector, I x Q or sign(I) Q - sign(Q) I, still averages
           to zero for square QAM, but every off-diagonal symbol kicks it even when the
           phase is perfect: pattern noise of 0.45 rad rms per symbol for 16-QAM.
  noise    each extra bit per symbol costs Eb/N0: the points sit closer together for
           the same average power.  At a bit error rate of 1e-4, 16-QAM needs 3.8 dB
           more than QPSK, 64-QAM 8.1 dB more (ber_theory, below).
  the DAC  has 8 bits.  QAM's waveform has bigger peaks for its average power (its
           PAPR), so for the same peaks it uses fewer codes (quantisation noise), and
           for the same rms it clips.  --amp-sweep finds the best amplitude.
"""
import argparse
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import psk                                                  # noqa: E402
from psk import (N, FS_DAC, FS_ADC, F_LOOP, F_C, NSYM, NUW, UW_START, SPAN, AMP,   # noqa: E402
                 g1, g2, rrc, noise_for, matched, timing_loop, loop_gains, find_port,
                 make_link)
from fll import fourth_power, shift                        # noqa: E402

ORDERS = (2, 4, 8, 16, 64)


# ---- constellations ---------------------------------------------------------------
def gray(i):
    """The Gray code of i: i and i + 1 differ in one bit."""
    return i ^ (i >> 1)


def constellation(M):
    """The M points, indexed by the bits each carries (as a number).  Average power 1."""
    k = int(math.log2(M))
    pts = np.zeros(M, complex)
    if M <= 8:                                        # PSK: Gray code around the circle
        for i in range(M):
            pts[gray(i)] = np.exp(1j * (2 * np.pi * i / M + (np.pi / M if M > 2 else 0)))
        return pts
    L, n = int(round(math.sqrt(M))), k // 2           # square QAM: L levels, n bits each axis
    lev = 2 * np.arange(L) - (L - 1)                  # -3 -1 1 3, or -7 ... 7
    for i in range(L):
        for j in range(L):
            # ######################################################################
            # ##  KEY LINE: Gray code along each axis.  The first n bits pick the
            # ##  I level, the last n the Q level; a wrong neighbour costs one bit.
            # ######################################################################
            pts[(gray(i) << n) | gray(j)] = lev[i] + 1j * lev[j]
    return pts / np.sqrt(np.mean(np.abs(pts)**2))     # sqrt(10) for 16-QAM, sqrt(42) for 64


POINTS = {M: constellation(M) for M in ORDERS}


def symmetry(M):
    """How many ways the constellation looks the same when turned: M for PSK, 4 for
    square QAM.  The carrier loop can settle in any of them."""
    return M if M <= 8 else 4


def point(q, M):
    """Symbol numbers q (the bits, as numbers) -> complex points."""
    return POINTS[M][np.asarray(q)]


def decide(z, M):
    """The symbol number of the nearest constellation point to each z."""
    z = np.asarray(z)
    if M <= 8:
        off = np.pi / M if M > 2 else 0
        return gray(np.round((np.angle(z) - off) / (2 * np.pi / M)).astype(int) % M)
    L, n = int(round(math.sqrt(M))), int(math.log2(M)) // 2
    g = np.sqrt(2 * (L * L - 1) / 3)                  # the points' scale: sqrt(10), sqrt(42)
    # ##########################################################################
    # ##  KEY LINE: for square QAM the nearest point is found one axis at a
    # ##  time: round I, and Q, to the nearest odd level.
    # ##########################################################################
    i = np.clip(np.round((z.real * g + L - 1) / 2), 0, L - 1).astype(int)
    j = np.clip(np.round((z.imag * g + L - 1) / 2), 0, L - 1).astype(int)
    return (gray(i) << n) | gray(j)


def bits_to_q(bits, M):
    """Bits (0/1, log2 M per symbol) -> symbol numbers."""
    k = int(math.log2(M))
    return np.asarray(bits).reshape(-1, k) @ (1 << np.arange(k)[::-1])


def q_to_bits(q, M):
    """Symbol numbers -> the bits they carry."""
    k = int(math.log2(M))
    return ((np.asarray(q)[:, None] >> np.arange(k)[::-1]) & 1).ravel()


def make_frame(M, nsym=NSYM, start=0):
    """One loop's symbols, as psk.py's: a unique word from G2, then data from G1."""
    k = int(math.log2(M))
    uw = bits_to_q(g2(NUW * k, start=UW_START), M)
    data = g1((nsym - NUW) * k, start=start)
    return np.concatenate([uw, bits_to_q(data, M)]), data


# ---- transmitter ------------------------------------------------------------------
def transmit(q, M, cfo_bins=0, ebn0=None, rng=None, amp=None):
    """The DAC waveform for one loop of symbols q: root-raised-cosine pulses on the
    carrier, with optional noise, as psk.transmit.  By default the peaks reach 100 codes
    from mid-scale; with `amp` the rms is set instead, and the DAC's 8 bits clip the rest."""
    nsym = len(q)
    a = point(q, M)
    u = np.arange(N)
    t = u * nsym / N
    k0 = np.floor(t).astype(int)
    env = np.zeros(N, complex)
    for j in range(-SPAN - 2, SPAN + 3):
        k = k0 + j
        env += a[k % nsym] * rrc(t - k)
    fc = F_C + cfo_bins * F_LOOP
    s = np.real(env * np.exp(2j * np.pi * fc * u / FS_DAC))
    if ebn0 is not None:
        s = s + noise_for(s, ebn0, M, nsym, fc, rng)
    if amp is None:
        return 128 + AMP * s / np.abs(s).max()
    # ##########################################################################
    # ##  KEY LINE: a fixed rms instead of fixed peaks.  Whatever sticks out of
    # ##  the DAC's 0..255 is clipped: that is the price of a high PAPR.
    # ##########################################################################
    return np.clip(128 + amp * s / s.std(), 0, 255)


def papr(x):
    """Peak-to-average power ratio, dB: the biggest sample's power over the mean."""
    x = np.asarray(x, float)
    return 10 * np.log10(np.max(np.abs(x)**2) / np.mean(np.abs(x)**2))


# ---- receiver ---------------------------------------------------------------------
def phase_start(z, M, n=100):
    """A first guess of the carrier phase from the first n symbols, before any
    decision.  Raised to the Mth power (4th for square QAM) a symbol forgets its data:
    QPSK's four points all become -1, 16-QAM's average -0.68, 64-QAM's -0.62, times
    e^(j M theta).  The angle of the sum, divided by M, is theta."""
    p = M if M <= 8 else 4
    # ##########################################################################
    # ##  KEY LINE: the same trick as fll.py's x^4 line, for the phase.
    # ##########################################################################
    return np.angle((1 if M == 2 else -1) * np.sum(z[:n]**p)) / p


def costas(z, M, bnt=0.02, phi0=0.0, hold=0):
    """psk.costas with a bigger constellation: the error is the angle from each symbol
    to the NEAREST point of the M.  Starts at phase phi0, and only starts moving at
    symbol `hold` (until then the timing loop is still settling, and 64-QAM's
    decisions are not worth listening to).  Returns the turned symbols, phase,
    frequency, error."""
    k1, k2 = loop_gains(bnt, 1.0)
    phi, w = phi0, 0.0
    out, phis, ws, errs = [], [], [], []
    for k, zk in enumerate(z):
        zr = zk * np.exp(-1j * phi)
        d = point(decide(zr, M), M)
        # ######################################################################
        # ##  KEY LINE: decision-directed.  Im(z d*) = |z||d| sin(angle from z
        # ##  to its nearest point): exactly zero when the phase is right, for
        # ##  every point of the constellation.  (I x Q would not be.)
        # ######################################################################
        e = np.imag(zr * np.conj(d)) if k >= hold else 0.0
        w += k2 * e
        out.append(zr); phis.append(phi); ws.append(w); errs.append(e)
        phi += w + k1 * e
    return np.array(out), np.array(phis), np.array(ws), np.array(errs)


def score(zc, M, nsym, q_tx, skip=400):
    """Find each frame's unique word, undo the leftover turn, trim the gain, count bit
    errors in one loop's worth of symbols after `skip`.  Returns a dict."""
    uw = point(q_tx[:NUW], M)
    K = len(zc)
    c = np.array([np.vdot(uw, zc[k:k + NUW]) for k in range(K - NUW)]) / np.sum(np.abs(uw)**2)
    p0 = int(np.argmax(np.abs(c[skip // 2:]))) + skip // 2
    starts, seen = [], []
    for p in range(p0 - nsym, K, nsym):
        if 2 <= p < len(c) - 2:
            p = p - 2 + int(np.argmax(np.abs(c[p - 2:p + 3])))
            seen.append(len(starts))
        starts.append(p)
    starts = np.array(starts)
    sym = symmetry(M)
    rot = np.round(np.angle(c[starts[seen]]) / (2 * np.pi / sym)).astype(int)
    rot = rot[np.clip(np.searchsorted(seen, np.arange(len(starts))), 0, len(seen) - 1)]
    k = np.arange(skip, min(skip + nsym, K))
    f = np.searchsorted(starts, k, side="right") - 1
    i = k - starts[np.maximum(f, 0)]
    ok = (f >= 0) & (i >= NUW) & (i < nsym)
    k, f, i = k[ok], f[ok], i[ok]
    z = zc[k] * np.exp(-2j * np.pi * rot[f] / sym)
    # ##########################################################################
    # ##  KEY LINE: the fine AGC.  Scale so that the symbols sit ON their nearest
    # ##  points on average: g = <Re(z d*)> / <|d|^2>.  PSK never needed this.
    # ##########################################################################
    d = point(decide(z, M), M)
    gain = np.mean(np.real(z * np.conj(d))) / np.mean(np.abs(d)**2)
    z = z / gain
    q_rx, q_want = decide(z, M), q_tx[i]
    errs = int(np.sum(q_to_bits(q_rx, M) != q_to_bits(q_want, M)))
    mer = -10 * np.log10(np.mean(np.abs(z - point(q_want, M))**2))
    return dict(errs=errs, nbits=len(k) * int(math.log2(M)), mer=mer, starts=starts, rot=rot,
                gain=gain, z=z, q_rx=q_rx, q_want=q_want, uwcorr=c)


def rings(z, M):
    """The AGC's check: for each radius the constellation has, the mean |z| of the
    symbols decided onto it.  Returns (expected radii, measured radii, counts)."""
    r_pt = np.abs(point(decide(z, M), M))
    radii = np.unique(np.round(np.abs(POINTS[M]), 6))
    meas = np.array([np.mean(np.abs(z)[np.isclose(r_pt, r)]) if np.any(np.isclose(r_pt, r)) else np.nan
                     for r in radii])
    cnt = np.array([int(np.sum(np.isclose(r_pt, r))) for r in radii])
    return radii, meas, cnt


def receive(rec, M, nsym_tx=NSYM, q_tx=None, bnt_timing=0.01, bnt_carrier=0.02, skip=400, hold=300):
    """The whole receiver: for square QAM the x^4 line first, then psk.py's matched
    filter and timing loop, the AGC, the carrier loop for M points (held for the
    first `hold` symbols while the timing loop settles: timing first, then carrier),
    and the score."""
    sps = FS_ADC * N / FS_DAC / NSYM
    coarse = 0.0
    if M >= 16:
        # ######################################################################
        # ##  KEY LINE: QAM's carrier loop cannot pull in even 3 kHz, so it is
        # ##  told the frequency first: the x^4 line of fll.py, to about 20 Hz.
        # ######################################################################
        coarse = fourth_power(rec, 4)[0]
        rec = shift(rec, -coarse)
    y = matched(rec)
    zs, times, ted, period = timing_loop(y, sps, bnt_timing)
    # ##########################################################################
    # ##  KEY LINE: the coarse AGC.  The constellation has average power 1, so
    # ##  scale the symbols to rms 1.  (With noise they come out a little big.)
    # ##########################################################################
    zs = zs / np.sqrt(np.mean(np.abs(zs)**2))
    # 64-QAM's nearest-point detector only works within about 5 degrees, and has
    # false resting points at 12-20 degrees: the loop waits for the timing loop,
    # then starts from the x^4 guess, so it only ever has to track.
    zc, phi, w, ec = costas(zs, M, bnt_carrier, phase_start(zs[hold:], M), hold)
    out = dict(y=y, sps=sps, times=times, ted=ted, period=period, zs=zs, zc=zc, phi=phi, w=w, ec=ec,
               coarse=coarse, naive=y[np.arange(int(sps), len(y) - 1, sps).astype(int)])
    if q_tx is not None:
        out.update(score(zc, M, nsym_tx, q_tx, skip))
    return out


# ---- theory -----------------------------------------------------------------------
_erf, _erfc = np.vectorize(math.erf), np.vectorize(math.erfc)


def ber_theory(ebn0_db, M):
    """Bit error rate against Eb/N0 for Gray-coded M-PSK and square M-QAM, exact.
    PSK: the probability that noise turns the symbol's angle into each neighbour's
    sector (Proakis' phase density), times the bits that neighbour differs in.  Square
    QAM: I and Q are two independent PAMs; for each level and each decision region,
    a difference of two Q functions, times the bits that differ."""
    k = int(math.log2(M))
    es = k * 10**(ebn0_db / 10)                       # Es/N0 = (bits per symbol) x Eb/N0
    if M <= 8:
        th = np.linspace(-np.pi, np.pi, 8001)
        c = np.cos(th)
        p = np.exp(-es) / (2 * np.pi) * (1 + np.sqrt(np.pi * es) * c * np.exp(es * c**2)
                                         * (1 + _erf(np.sqrt(es) * c)))
        sector = np.round(th / (2 * np.pi / M)).astype(int) % M
        wrong = np.array([np.mean([bin(gray((i0 + i) % M) ^ gray(i0)).count("1") for i0 in range(M)])
                          for i in range(M)])
        return float(np.trapz(p * wrong[sector], th) / k)
    L, n = int(round(math.sqrt(M))), k // 2
    lev = 2 * np.arange(L) - (L - 1)
    sigma = np.sqrt((L * L - 1) / (3 * es))           # noise per axis, in level units
    t = np.concatenate([[-np.inf], lev[:-1] + 1, [np.inf]])        # decision thresholds
    cdf = lambda x: 0.5 * _erfc(-x / np.sqrt(2))      # noqa: E731
    errs = 0.0
    for i in range(L):
        P = cdf((t[1:] - lev[i]) / sigma) - cdf((t[:-1] - lev[i]) / sigma)   # lands in region j
        wrong = np.array([bin(gray(i) ^ gray(j)).count("1") for j in range(L)])
        errs += np.sum(P * wrong)
    return float(errs / L / n)


def ebn0_for(ber, M, lo=-2.0, hi=30.0):
    """The Eb/N0 (dB) at which ber_theory reaches `ber`: bisection."""
    for _ in range(50):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if ber_theory(mid, M) > ber else (lo, mid)
    return (lo + hi) / 2


def shannon_ebn0(bits_per_symbol):
    """Shannon's limit for a channel used at `bits_per_symbol` bit/s/Hz (6.08):
    Eb/N0 >= (2^k - 1) / k, in dB."""
    k = bits_per_symbol
    return 10 * np.log10((2.0**k - 1) / k)


# ---- one run ----------------------------------------------------------------------
def run_once(args, M, play, record, start=0, ebn0=None, rng=None):
    """Make a frame, play it, record it, receive it.  args: sro, cfo, amp, bnt_timing,
    bnt_carrier, skip (as the command line's)."""
    nsym_tx = NSYM + int(round(args.sro * 1e-6 * NSYM))
    q, data = make_frame(M, nsym_tx, start=start)
    cfo_bins = int(round(args.cfo / F_LOOP))
    wave = transmit(q, M, cfo_bins, ebn0=ebn0, rng=rng, amp=args.amp)
    play(wave)
    rec = record()
    r = receive(rec, M, nsym_tx, q, args.bnt_timing, args.bnt_carrier, args.skip)
    r.update(rec=rec, wave=wave, q_tx=q, nsym_tx=nsym_tx, cfo=cfo_bins * F_LOOP,
             sro=(nsym_tx / NSYM - 1) * 1e6, M=M, papr=papr(wave - 128),
             clipped=float(np.mean((wave <= 0) | (wave >= 255))))
    return r


def name_of(M):
    return {2: "BPSK", 4: "QPSK", 8: "8PSK"}.get(M, "%d-QAM" % M)


def plot(r, M, title, skip=400):
    """Constellation with its bits, the rings of |z|, the DAC's codes, and the loops."""
    import matplotlib.pyplot as plt
    R = NSYM * F_LOOP
    k = np.arange(len(r["zc"]))
    us = k / R * 1e6
    fig, ax = plt.subplots(2, 3, figsize=(13, 8))
    a = ax[0, 0]
    zn = r["naive"] / np.sqrt(np.mean(np.abs(r["naive"])**2))
    a.plot(zn.real, zn.imag, ".", markersize=2)
    a.set_title("before the loops: one sample every 16")
    a = ax[0, 1]
    z = r["z"]
    a.plot(z.real, z.imag, ".", markersize=2)
    pts = POINTS[M]
    for q, p in enumerate(pts):
        a.annotate(format(q, "0%db" % int(math.log2(M))), (p.real, p.imag), ha="center", va="center",
                   fontsize=8 if M <= 16 else 5, color="0.3")
    a.set_title("after: %d errors in %d bits, MER %.1f dB" % (r["errs"], r["nbits"], r["mer"]))
    for a in ax[0, :2]:
        a.set_aspect("equal"); a.set_xlim(-1.8, 1.8); a.set_ylim(-1.8, 1.8)
        a.set_xlabel("I"); a.set_ylabel("Q"); a.grid(True)
    a = ax[0, 2]
    a.hist(np.abs(z), bins=120, range=(0, 1.8), color="C0")
    radii, meas, cnt = rings(z, M)
    for rr in radii:
        a.axvline(rr, color="C1", lw=0.8, ls="--")
    a.set_xlabel("|z| after the AGC"); a.set_ylabel("symbols")
    a.set_title("rings: dashed = the constellation's radii")
    a = ax[1, 0]
    a.plot(us, r["times"] - r["sps"] * k, ".", markersize=1.5)
    a.set_xlabel("time (us)"); a.set_ylabel("sampling time - k x 16 (samples)")
    a.set_title("timing loop"); a.grid(True)
    a = ax[1, 1]
    a.plot(us, np.degrees(r["phi"]), lw=1)
    a.set_xlabel("time (us)"); a.set_ylabel("phase correction (deg)")
    a.set_title("carrier loop (decision-directed)"); a.grid(True)
    a2 = a.twinx()
    a2.plot(us, r["w"] * R / (2 * np.pi) / 1e3, color="C1", lw=1)
    a2.set_ylabel("carrier offset it found (kHz)", color="C1")
    a = ax[1, 2]
    a.hist(r["wave"], bins=np.arange(-0.5, 256.5, 2), color="C0")
    a.set_xlabel("DAC code"); a.set_ylabel("samples per loop")
    a.set_title("the DAC's codes: PAPR %.1f dB, %.2f%% clipped" % (r["papr"], 100 * r["clipped"]))
    fig.suptitle(title)
    fig.tight_layout()
    plt.show()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ports", nargs="*", help="one port: looped back; two: A plays, B records")
    ap.add_argument("--sim", action="store_true", help="use channel.py's model, not a board")
    ap.add_argument("--ppm", type=float, default=0.0, help="--sim: pretend to be two boards, A this many ppm fast")
    ap.add_argument("-M", type=int, default=16, choices=ORDERS, help="points in the constellation (default 16)")
    ap.add_argument("--cfo", type=float, default=0.0, help="transmitter's carrier offset, Hz (3051.76 Hz steps)")
    ap.add_argument("--sro", type=float, default=0.0, help="transmitter's symbol-rate offset, ppm (1953 ppm steps)")
    ap.add_argument("--ebn0", type=float, help="add noise at the transmitter: Eb/N0 in dB")
    ap.add_argument("--ber", help="measure BER at Eb/N0 = LO:HI dB (1 dB steps)")
    ap.add_argument("--records", type=int, default=40, help="--ber: at most this many uploads per point")
    ap.add_argument("--amp", type=float, help="the DAC waveform's rms in codes (default: peaks at 100)")
    ap.add_argument("--amp-sweep", action="store_true", help="MER against the DAC's rms")
    ap.add_argument("--bnt-timing", type=float, default=0.01, help="timing loop bandwidth x symbol time")
    ap.add_argument("--bnt-carrier", type=float, default=0.02, help="carrier loop bandwidth x symbol time")
    ap.add_argument("--skip", type=int, default=400, help="symbols to let the loops settle")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("-o", "--out", help="save the results (.npz)")
    ap.add_argument("--no-plot", action="store_true")
    args = ap.parse_args()
    M = args.M
    name = name_of(M)
    play, record = make_link(args)
    R = NSYM * F_LOOP
    bits = int(math.log2(M))

    if args.ber:
        lo, hi = (float(x) for x in args.ber.split(":"))
        rng = np.random.default_rng(args.seed)
        rows = []
        print("%s, %.4g Msymbol/s, %.4g Mbit/s: Eb/N0 (dB), bit errors, bits, BER, theory, MER (dB)"
              % (name, R / 1e6, R * bits / 1e6))
        for eb in np.arange(lo, hi + 0.01, 1.0):
            e = nb = 0; mers = []
            for i in range(args.records):
                r = run_once(args, M, play, record, start=int(rng.integers(0, 1023)), ebn0=eb, rng=rng)
                e += r["errs"]; nb += r["nbits"]; mers.append(r["mer"])
                if e >= 200 and i >= 2:
                    break
            rows.append((eb, e, nb, e / nb, ber_theory(eb, M), np.mean(mers)))
            print("%5.1f %6d %8d  %.2e  %.2e  %5.1f" % rows[-1], flush=True)
        if args.out:
            np.savez(args.out, rows=np.array(rows), M=M)
        if not args.no_plot:
            import matplotlib.pyplot as plt
            rows = np.array(rows)
            ebs = np.linspace(lo, hi, 100)
            plt.semilogy(ebs, [ber_theory(x, M) for x in ebs], label="theory")
            ok = rows[:, 1] > 0
            plt.semilogy(rows[ok, 0], rows[ok, 3], "o", label="measured")
            plt.xlabel("Eb/N0 (dB)"); plt.ylabel("bit error rate"); plt.grid(True, which="both")
            plt.legend(); plt.title("%s through the cable" % name); plt.show()
    elif args.amp_sweep:
        print("%s: DAC rms (codes), PAPR (dB), clipped (%%), bit errors, MER (dB)" % name)
        rows = []
        for amp in (2, 3, 4.5, 7, 10, 15, 22, 33, 50, 70, 90):
            args.amp = amp
            r = run_once(args, M, play, record, ebn0=args.ebn0, rng=args.seed)
            rows.append((amp, r["papr"], 100 * r["clipped"], r["errs"], r["mer"]))
            print("%5.1f  %5.1f  %6.2f  %5d  %5.1f" % rows[-1], flush=True)
        if args.out:
            np.savez(args.out, rows=np.array(rows), M=M)
    else:
        r = run_once(args, M, play, record, ebn0=args.ebn0, rng=args.seed)
        print("%s at %.4g Msymbol/s (%.4g Mbit/s) on %.4f MHz; transmitter's carrier %+.0f Hz, symbols %+.0f ppm"
              % (name, R / 1e6, R * bits / 1e6, F_C / 1e6, r["cfo"], r["sro"]))
        print("DAC waveform: rms %.1f codes, PAPR %.1f dB, %.2f%% of samples clipped"
              % (np.std(r["wave"]), r["papr"], 100 * r["clipped"]))
        last = slice(-200, None)
        print("timing loop:  symbol rate offset found %+.0f ppm (mean of the last 200 symbols)"
              % np.mean((r["sps"] / r["period"][last] - 1) * 1e6))
        print("carrier:      x^4 line says %+.0f Hz, then the loop finds %+.0f Hz more"
              % (r["coarse"], np.mean(r["w"][last] * R / (2 * np.pi))))
        print("unique words at symbols %s, turned by %s x %d deg; fine gain %.3f"
              % (list(r["starts"]), list(r["rot"]), 360 // symmetry(M), r["gain"]))
        radii, meas, cnt = rings(r["z"], M)
        print("rings |z|: expected %s" % " ".join("%.3f" % x for x in radii))
        print("           measured %s" % " ".join("%.3f" % x for x in meas))
        print("%d bit errors in %d bits after the first %d symbols; MER %.1f dB"
              % (r["errs"], r["nbits"], args.skip, r["mer"]))
        if args.out:
            np.savez(args.out, **{k: v for k, v in r.items() if isinstance(v, (np.ndarray, int, float))})
        if not args.no_plot:
            plot(r, M, "%s, %s" % (name, "simulated" if args.sim else " ".join(args.ports) or "one board"),
                 args.skip)
