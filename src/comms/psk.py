#!/usr/bin/env python3
"""BPSK and QPSK through the cable, received with a Gardner timing loop and a Costas loop.

    python3 psk.py                      # QPSK, one board looped back (finds its port)
    python3 psk.py PORT_A PORT_B        # board A plays, board B records
    python3 psk.py --sim                # no board: the channel model of channel.py
    python3 psk.py --sim --ppm 0.76     #   ... pretending to be two boards
    python3 psk.py --bpsk               # BPSK instead (one bit per symbol)
    python3 psk.py --cfo 3000 --sro 2000    # give the loops work to do: the transmitter's
                                        #   carrier 3 kHz high, its symbols 2000 ppm fast
    python3 psk.py --ebn0 6             # add noise at the transmitter: Eb/N0 = 6 dB
    python3 psk.py --ber 0:10           # bit error rate against Eb/N0, 0 to 10 dB
    python3 psk.py --diff               # differential coding instead of the unique word
    python3 psk.py -o psk.npz --no-plot

The board runs awgcap.sv (5.01): it plays a 16384-sample waveform at 50 MS/s, over
and over (one loop = 327.68 us), and records 16384 samples at 25 MS/s (two loops).

TRANSMITTER (here, in Python; the board just plays the result)
  bits    GPS's G1 register (1.07), a pseudo-random sequence that repeats every 1023 bits
  symbols Gray-coded: BPSK +1 or -1; QPSK one of four points at 45, 135, 225, 315 deg
  frame   one frame per loop: a 32-symbol unique word, then 480 symbols of data
  pulses  root-raised-cosine, roll-off 0.35, 512 symbols per loop = 1.5625 Msymbol/s
  carrier 6.25 MHz: a quarter of the ADC's 25 MS/s, and exactly 2048 cycles per loop

Everything is a whole number of cycles per loop, or the waveform would jump at the
loop's seam.  So --cfo moves the carrier in steps of 1/327.68 us = 3051.76 Hz, and
--sro adds or removes whole symbols per loop (1 in 512 = 1953 ppm).

Why these numbers: 6.25 MHz sits in the middle of the ADC's 0-12.5 MHz, far from the
converters' offsets near 0 and the DAC's images near 12.5 MHz, and at a quarter of
25 MS/s mixing down is multiplying by 1, -j, -1, j.  16 samples per symbol make
smooth eyes and leave the timing loop room to work; the signal is 1.35 x 1.5625 =
2.1 MHz wide (5.2-7.3 MHz).  Roll-off 0.35 is what DVB-S, digital satellite TV, uses.

RECEIVER (in Python, on the record)
  1. mix down with cos and -sin at 6.25 MHz, as the lock-in (1.08) does
  2. matched filter: the same root-raised-cosine
  3. Gardner timing loop: where, between samples, is the middle of each symbol?
  4. Costas loop: which way is up?  It turns the constellation to square it up
  5. the unique word fixes the 90-degree (QPSK) or 180-degree (BPSK) ambiguity
     that's left (or, with --diff, the data are in the CHANGES of phase), and
     shows where each frame starts; then count the bit errors

Both loops are second order (they learn a frequency as well as a phase), with noise
bandwidths of 0.01 (timing) and 0.02 (carrier) times the symbol rate, 16 and 31 kHz.
They settle in about 300 symbols; the first 400 aren't counted.  Wider loops lock
faster but jitter more; narrower ones are quieter but slow, and lose lock more easily
when the transmitter's carrier is off.
"""
import argparse
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import channel                                              # noqa: E402

N = 16384                       # DAC samples per loop
FS_DAC, FS_ADC = 50e6, 25e6
F_LOOP = FS_DAC / N             # 3051.76 Hz: anything periodic in the loop is a multiple
F_C = 6.25e6                    # carrier: FS_ADC / 4, 2048 cycles per loop
NSYM = 512                      # symbols per loop: 1.5625 Msymbol/s, 16 ADC samples each
ALPHA = 0.35                    # root-raised-cosine roll-off (excess bandwidth)
NUW = 32                        # unique-word symbols at the start of each frame
UW_START = 319                  # ... taken from G2 starting here: its shifted copies
                                #   match it by at most 18% (BPSK and QPSK)
SPAN = 6                        # pulses are cut off this many symbols each side
AMP = 100                       # the waveform's peaks, DAC codes from mid-scale


# ---- bits -------------------------------------------------------------------------
def lfsr(taps, n, out_stage=10, start=0):
    """A 10-stage shift register, as loopback.sv's: each step shifts left, feeding the
    XOR of the `taps` stages into stage 1, and outputs stage 10.  Starts all ones.
    Returns n bits (0/1), starting `start` steps in."""
    reg = [1] * 10                                   # reg[0] is stage 1
    seq = []
    for _ in range(1023):
        seq.append(reg[out_stage - 1])
        fb = 0
        for t in taps:
            fb ^= reg[t - 1]
        reg = [fb] + reg[:9]
    return np.resize(np.roll(np.array(seq), -start), n)


def g1(n, start=0):
    """GPS's G1: x^10 + x^3 + 1."""
    return lfsr((3, 10), n, start=start)


def g2(n, start=0):
    """GPS's G2: x^10 + x^9 + x^8 + x^6 + x^3 + x^2 + 1."""
    return lfsr((2, 3, 6, 8, 9, 10), n, start=start)


# ---- symbols ----------------------------------------------------------------------
# A symbol is a whole number q of turns of 360/M degrees: BPSK (M = 2) sends
# e^(j pi q), QPSK (M = 4) e^(j (pi/4 + q pi/2)).  Gray code: bit pairs 00 01 11 10
# go to q = 0 1 2 3, so neighbouring points differ in only one bit.
GRAY = {2: [0, 1], 4: [0, 1, 3, 2]}           # q -> the bits it carries, as a number


def point(q, M):
    """The constellation point for symbol number q (a complex number of size 1)."""
    q = np.asarray(q)
    return np.exp(1j * np.pi * q) if M == 2 else np.exp(1j * (np.pi / 4 + np.pi / 2 * q))


def bits_to_q(bits, M):
    """Bits (0/1, 1 or 2 per symbol) -> symbol numbers q."""
    b = int(math.log2(M))
    v = bits.reshape(-1, b) @ (1 << np.arange(b)[::-1])          # bits -> number
    # ##########################################################################
    # ##  KEY LINE: Gray code.  Bits 00 01 11 10 -> q = 0 1 2 3: a small error
    # ##  (to a neighbouring point) costs only one bit.
    # ##########################################################################
    return np.argsort(GRAY[M])[v]


def q_to_bits(q, M):
    """Symbol numbers q -> the bits they carry."""
    b = int(math.log2(M))
    v = np.array(GRAY[M])[np.asarray(q) % M]
    return ((v[:, None] >> np.arange(b)[::-1]) & 1).ravel()


def decide(z, M):
    """The nearest constellation point to each z: returns q."""
    if M == 2:
        return (z.real < 0).astype(int)
    return np.round((np.angle(z) - np.pi / 4) / (np.pi / 2)).astype(int) % 4


def make_frame(M, nsym=NSYM, start=0, diff=False):
    """One loop's symbols.  Returns (q of every symbol, the data bits)."""
    b = int(math.log2(M))
    uw = bits_to_q(g2(NUW * b, start=UW_START), M)   # the unique word: from G2
    data = g1((nsym - NUW) * b, start=start)         # the data: G1, a PRBS-10
    dq = bits_to_q(data, M)
    if diff:
        # ######################################################################
        # ##  KEY LINE: differential coding.  The data say how far to TURN from
        # ##  the previous symbol, not where to point.
        # ######################################################################
        dq = (uw[-1] + np.cumsum(dq)) % M
    return np.concatenate([uw, dq]), data


# ---- pulses -----------------------------------------------------------------------
def rrc(t, alpha=ALPHA):
    """Root-raised-cosine pulse; t in symbol periods.  Not normalized."""
    t = np.asarray(t, float)
    out = np.empty_like(t)
    a = alpha
    zero = np.isclose(t, 0)
    edge = np.isclose(np.abs(t), 1 / (4 * a))
    ok = ~(zero | edge)
    tt = t[ok]
    out[ok] = (np.sin(np.pi * tt * (1 - a)) + 4 * a * tt * np.cos(np.pi * tt * (1 + a))) / \
              (np.pi * tt * (1 - (4 * a * tt)**2))
    out[zero] = 1 - a + 4 * a / np.pi
    out[edge] = a / np.sqrt(2) * ((1 + 2 / np.pi) * np.sin(np.pi / (4 * a)) +
                                  (1 - 2 / np.pi) * np.cos(np.pi / (4 * a)))
    return out


def rc(t, alpha=ALPHA):
    """Raised-cosine pulse (= rrc convolved with itself), 1 at t = 0; t in symbols."""
    t = np.asarray(t, float)
    den = 1 - (2 * alpha * t)**2
    safe = np.where(np.isclose(den, 0), 1, den)
    return np.where(np.isclose(den, 0), np.pi / 4 * np.sinc(1 / (2 * alpha)),
                    np.sinc(t) * np.cos(np.pi * alpha * t) / safe)


# ---- transmitter ------------------------------------------------------------------
def transmit(q, M, cfo_bins=0, ebn0=None, rng=None):
    """The DAC waveform (16384 codes) for one loop of symbols q, on the carrier, with
    optional noise.  Symbols per loop = len(q), any whole number."""
    nsym = len(q)
    a = point(q, M)
    u = np.arange(N)                                  # DAC sample number
    t = u * nsym / N                                  # ... in symbol periods
    k0 = np.floor(t).astype(int)
    env = np.zeros(N, complex)                        # the complex envelope I + jQ
    for j in range(-SPAN - 2, SPAN + 3):
        k = k0 + j
        # ######################################################################
        # ##  KEY LINE: pulse shaping.  Each symbol is a root-raised-cosine
        # ##  pulse centred on its own time k; the waveform is their sum.
        # ######################################################################
        env += a[k % nsym] * rrc(t - k)
    fc = F_C + cfo_bins * F_LOOP
    # ##########################################################################
    # ##  KEY LINE: onto the carrier.  I rides on cos, Q on -sin, so that the
    # ##  lock-in's  < s e^(-jwt) >  gives back I + jQ.
    # ##########################################################################
    s = np.real(env * np.exp(2j * np.pi * fc * u / FS_DAC))
    if ebn0 is not None:
        s = s + noise_for(s, ebn0, M, nsym, fc, rng)
    return 128 + AMP * s / np.abs(s).max()


def noise_for(s, ebn0_db, M, nsym, fc, rng):
    """White Gaussian noise for Eb/N0 = ebn0_db, in a band fc +- the symbol rate
    (wider than the signal, 1.35x the symbol rate in all, so the matched filter
    sees it as white).  Periodic in the loop, like everything the DAC plays."""
    rng = np.random.default_rng(rng)
    R = nsym * F_LOOP                                 # symbols per second
    Eb = np.mean(s**2) / R / math.log2(M)             # signal power x time per bit
    N0 = Eb / 10**(ebn0_db / 10)                      # one-sided noise density
    k = np.arange(N // 2 + 1)
    band = np.abs(k * F_LOOP - fc) <= R
    var = N0 * band.sum() * F_LOOP                    # noise power = N0 x bandwidth
    X = np.zeros(N // 2 + 1, complex)
    X[band] = rng.standard_normal(band.sum()) + 1j * rng.standard_normal(band.sum())
    x = np.fft.irfft(X, N)
    return x * np.sqrt(var) / x.std()


# ---- receiver ---------------------------------------------------------------------
def loop_gains(bnt, kd, zeta=1 / np.sqrt(2)):
    """Proportional and integral gains of a second-order loop with noise bandwidth
    bnt (in units of the update rate, here once per symbol) and damping zeta, when
    its detector gives kd per unit of error (Rice, Digital Communications, App. C)."""
    th = bnt / (zeta + 1 / (4 * zeta))
    d = 1 + 2 * zeta * th + th**2
    return 4 * zeta * th / d / kd, 4 * th**2 / d / kd


def gardner_gain(sps, alpha=ALPHA):
    """Slope of the Gardner detector's average output against timing error (per
    sample), for unit-power symbols and raised-cosine pulses: its "S-curve" at 0."""
    j = np.arange(-20, 21)
    def S(tau):                                       # tau in samples
        x = tau / sps
        return np.sum(rc(j - 0.5 + x, alpha) * (rc(j + x, alpha) - rc(j - 1 + x, alpha)))
    return (S(0.01) - S(-0.01)) / 0.02


def interp(y, t):
    """y at fractional sample t: cubic through the 4 nearest samples (a Farrow
    interpolator, as an FPGA would do it)."""
    i = int(t)
    mu = t - i
    ym1, y0, y1, y2 = y[i - 1], y[i], y[i + 1], y[i + 2]
    c1 = -ym1 / 3 - y0 / 2 + y1 - y2 / 6
    c2 = ym1 / 2 - y0 + y1 / 2
    c3 = -ym1 / 6 + y0 / 2 - y1 / 2 + y2 / 6
    return ((c3 * mu + c2) * mu + c1) * mu + y0


def matched(rec, nsym=NSYM):
    """Steps 1 and 2: mix down, matched-filter.  Returns the complex baseband signal at
    25 MS/s, scaled so that the symbols come out about 1 in size."""
    sps = FS_ADC * N / FS_DAC / nsym                 # samples per symbol (16.0)
    r = rec - np.mean(rec)
    n = np.arange(len(r))
    # ##########################################################################
    # ##  KEY LINE: the lock-in again: multiply by cos and -sin, i.e. by
    # ##  e^(-jwt).  At 6.25 MHz = 25 MS/s / 4 that's just 1, -j, -1, j, ...
    # ##########################################################################
    z = 2 * r * np.exp(-2j * np.pi * F_C * n / FS_ADC)
    m = np.arange(-int(SPAN * sps), int(SPAN * sps) + 1)
    h = rrc(m / sps)
    # ##########################################################################
    # ##  KEY LINE: the matched filter: the same pulse shape again.  It throws
    # ##  away the 12.5 MHz (2 x carrier) part of the mixing, and all noise
    # ##  outside the signal's band, and makes the pulses raised cosines.
    # ##########################################################################
    y = np.convolve(z, h, mode="same")
    return y * np.sqrt(1 - ALPHA / 4) / np.sqrt(np.mean(np.abs(y)**2))


def timing_loop(y, sps, bnt=0.01, t0=None):
    """Step 3: Gardner's timing loop.  Returns the symbols (one complex number each),
    the time of each (in samples), and the loop's error and period, symbol by symbol."""
    kd = gardner_gain(sps)
    k1, k2 = loop_gains(bnt, kd)
    t = sps if t0 is None else t0                    # a guess for the first symbol
    t_prev = t - sps
    y_prev = interp(y, t_prev)
    integ = 0.0
    out, times, errs, periods = [], [], [], []
    while t + 3 < len(y):
        y_now = interp(y, t)
        y_mid = interp(y, (t_prev + t) / 2)          # half-way between this symbol and the last
        # ######################################################################
        # ##  KEY LINE: Gardner's timing error.  Half-way between two different
        # ##  symbols the signal should be crossing zero.  If it has already
        # ##  crossed (in the direction it was going), we are sampling late: e > 0.
        # ######################################################################
        e = np.real(np.conj(y_mid) * (y_now - y_prev))
        # ######################################################################
        # ##  KEY LINES: the loop filter.  A little of e moves this one symbol;
        # ##  e summed up (integ) learns the transmitter's symbol period.
        # ######################################################################
        integ += k2 * e
        step = sps - (k1 * e + integ)
        out.append(y_now); times.append(t); errs.append(e); periods.append(sps - integ)
        t_prev, y_prev = t, y_now
        t += step
    return np.array(out), np.array(times), np.array(errs), np.array(periods)


def costas(z, M, bnt=0.02):
    """Step 4: the Costas loop, once per symbol.  Returns the turned symbols, and the
    loop's phase (rad), frequency (rad per symbol) and error, symbol by symbol."""
    k1, k2 = loop_gains(bnt, 1.0)                    # detector: sin(error) ~ error
    phi = w = 0.0
    out, phis, ws, errs = [], [], [], []
    for zk in z:
        zr = zk * np.exp(-1j * phi)                  # turn back by our phase estimate
        d = point(decide(zr, M), M)                  # the nearest constellation point
        # ######################################################################
        # ##  KEY LINE: the phase detector.  Im(z d*) = |z| sin(angle from z to
        # ##  the nearest point): how far the symbol is turned from where it
        # ##  belongs.  (For BPSK this is Q * sign(I), almost the I*Q of the
        # ##  original Costas loop.)
        # ######################################################################
        e = np.imag(zr * np.conj(d))
        # ######################################################################
        # ##  KEY LINES: the loop filter.  w integrates e: it learns the carrier's
        # ##  frequency offset (radians per symbol).  phi integrates w + k1 e.
        # ######################################################################
        w += k2 * e
        out.append(zr); phis.append(phi); ws.append(w); errs.append(e)
        phi += w + k1 * e
    return np.array(out), np.array(phis), np.array(ws), np.array(errs)


def score(zc, M, nsym, q_tx, diff=False, skip=400):
    """Step 5: find each frame's unique word, undo the constellation's leftover turn,
    and count bit errors in one loop's worth of symbols after `skip` (the loops' time
    to settle).  Returns a dict."""
    uw = point(q_tx[:NUW], M)
    K = len(zc)
    c = np.array([np.vdot(uw, zc[k:k + NUW]) / NUW for k in range(K - NUW)])   # sum z uw*
    # Frames repeat every nsym symbols: the biggest peak marks one of them; let each
    # other frame's own peak move by a symbol or two (in case the timing slipped).
    p0 = int(np.argmax(np.abs(c[skip // 2:]))) + skip // 2
    starts, seen = [], []
    for p in range(p0 - nsym, K, nsym):
        if 2 <= p < len(c) - 2:                        # a unique word inside the record
            p = p - 2 + int(np.argmax(np.abs(c[p - 2:p + 3])))
            seen.append(len(starts))
        starts.append(p)
    starts = np.array(starts)
    # ##########################################################################
    # ##  KEY LINE: the phase ambiguity.  The Costas loop squares the
    # ##  constellation up but can't know which way is up: it may be off by a
    # ##  multiple of 90 deg (QPSK) or 180 deg (BPSK).  The unique word's
    # ##  correlation points the way: round its angle to a multiple of 360/M.
    # ##########################################################################
    rot = np.round(np.angle(c[starts[seen]]) / (2 * np.pi / M)).astype(int)
    # a frame whose unique word fell outside the record borrows its neighbour's
    rot = rot[np.clip(np.searchsorted(seen, np.arange(len(starts))), 0, len(seen) - 1)]
    q_rx = decide(zc, M)
    bits_per = int(math.log2(M))
    errs = nbits = 0
    sq_err = []
    for k in range(skip, min(skip + nsym, K)):
        f = np.searchsorted(starts, k, side="right") - 1      # the frame this symbol is in
        if f < 0:
            continue
        i = k - starts[f]                                     # position in the frame
        if i < NUW + (1 if diff else 0) or i >= nsym:
            continue
        if diff:
            dq = (q_rx[k] - q_rx[k - 1]) % M                  # how far it turned
            want = (q_tx[i] - q_tx[i - 1]) % M
        else:
            dq = (q_rx[k] - rot[f]) % M
            want = q_tx[i]
        errs += int(np.sum(q_to_bits([dq], M) != q_to_bits([want], M)))
        nbits += bits_per
        sq_err.append(abs(zc[k] * np.exp(-2j * np.pi * rot[f] / M) - point(q_tx[i], M))**2)
    mer = -10 * np.log10(np.mean(sq_err)) if sq_err else float("nan")
    return dict(errs=errs, nbits=nbits, mer=mer, starts=starts, rot=rot, uwcorr=c)


def receive(rec, M, nsym_tx=NSYM, q_tx=None, diff=False, bnt_timing=0.01,
            bnt_carrier=0.02, skip=400):
    """The whole receiver.  nsym_tx and q_tx are only for counting errors: the loops
    assume the nominal 512 symbols per loop and the nominal carrier."""
    sps = FS_ADC * N / FS_DAC / NSYM
    y = matched(rec)
    zs, times, ted, period = timing_loop(y, sps, bnt_timing)
    zs = zs / np.sqrt(np.mean(np.abs(zs)**2))         # symbols: rms 1
    zc, phi, w, ec = costas(zs, M, bnt_carrier)
    out = dict(y=y, sps=sps, times=times, ted=ted, period=period, zs=zs, zc=zc,
               phi=phi, w=w, ec=ec, naive=y[np.arange(int(sps), len(y) - 1, sps).astype(int)])
    if q_tx is not None:
        out.update(score(zc, M, nsym_tx, q_tx, diff, skip))
    return out


def eye(r, M, skip=400, nsym=600, res=8):
    """Eye-diagram traces from the matched filter's output: two symbol periods
    around each symbol time the timing loop found, turned by the Costas loop's
    phase and the unique word's.  Returns (time in symbols, traces)."""
    y, sps, times = r["y"], r["sps"], r["times"]
    rot = np.exp(-2j * np.pi * (r["rot"][-1] if "rot" in r else 0) / M)
    tau = np.arange(-res * sps, res * sps + 1) / res          # samples, -1..+1 symbol
    tr = []
    for k in range(skip, min(skip + nsym, len(times))):
        tt = times[k] + tau
        if tt[0] < 2 or tt[-1] > len(y) - 3:
            continue
        tr.append(channel.cubic(y, tt) * np.exp(-1j * r["phi"][k]) * rot)
    return tau / sps, np.array(tr)


# ---- the board, or the model ------------------------------------------------------
def find_port():
    """The first FTDI FT231X serial port (USB ID 0403:6015): the Icepi Zero's."""
    from serial.tools import list_ports
    for p in list_ports.comports():
        if (p.vid, p.pid) == (0x0403, 0x6015):
            return p.device
    raise SystemExit("No Icepi Zero found. Is it plugged in? (Or give its port, or --sim.)")


def make_link(args):
    """Returns play(wave) and record() for the board(s), or for the model."""
    if args.sim:
        rng = np.random.default_rng(args.seed)
        st = {"wave": None, "start": rng.uniform(0, N)}
        def play(wave):
            st["wave"] = wave
        def record():
            if args.ppm:                              # two boards
                return channel.channel(st["wave"], start=st["start"], ppm=args.ppm, rng=rng)
            return channel.channel(st["wave"], rng=rng)
        return play, record
    sys.path.insert(0, os.path.join(HERE, "..", "twoboard"))
    import awgcap
    ports = args.ports or [find_port()]
    tx, rx = ports[0], ports[-1]
    return (lambda wave: awgcap.upload(tx, wave)), (lambda: awgcap.record(rx))


def ber_theory(ebn0_db, diff=False):
    """Coherent BPSK, or Gray-coded QPSK, per bit: Q(sqrt(2 Eb/N0)).  Differential
    encoding with a coherent receiver gives exactly 2p(1 - p): one wrong symbol spoils
    two differences."""
    p = 0.5 * math.erfc(math.sqrt(10**(ebn0_db / 10)))
    return 2 * p * (1 - p) if diff else p


def run_once(args, M, play, record, start=0, ebn0=None, rng=None):
    """Make a frame, play it, record it, receive it.  args: sro, cfo, diff, bnt_timing,
    bnt_carrier, skip (as the command line's)."""
    nsym_tx = NSYM + int(round(args.sro * 1e-6 * NSYM))
    q, data = make_frame(M, nsym_tx, start=start, diff=args.diff)
    cfo_bins = int(round(args.cfo / F_LOOP))
    play(transmit(q, M, cfo_bins, ebn0=ebn0, rng=rng))
    rec = record()
    r = receive(rec, M, nsym_tx, q, args.diff, args.bnt_timing, args.bnt_carrier, args.skip)
    r.update(rec=rec, q_tx=q, nsym_tx=nsym_tx, cfo=cfo_bins * F_LOOP,
             sro=(nsym_tx / NSYM - 1) * 1e6, M=M)
    return r


def plot(r, M, title, skip=400):
    """Constellations before and after, the eye, and the two loops at work."""
    import matplotlib.pyplot as plt
    R = NSYM * F_LOOP
    k = np.arange(len(r["zc"]))
    us = k / R * 1e6                                         # time, microseconds
    fig, ax = plt.subplots(2, 3, figsize=(13, 7.5))
    a = ax[0, 0]
    zn = r["naive"] / np.sqrt(np.mean(np.abs(r["naive"])**2))
    a.plot(zn.real, zn.imag, ".", markersize=2)
    a.set_title("before the loops: one sample every 16")
    a = ax[0, 1]
    good = k >= skip
    zr = r["zc"] * np.exp(-2j * np.pi * (r["rot"][-1] if "rot" in r else 0) / M)
    a.plot(zr[~good].real, zr[~good].imag, ".", color="0.75", markersize=2, label="settling")
    a.plot(zr[good].real, zr[good].imag, ".", markersize=2, label="after %d symbols" % skip)
    a.set_title("after the loops: %d errors in %d bits" % (r.get("errs", 0), r.get("nbits", 0)))
    a.legend(loc="upper right", fontsize=8)
    for a in ax[0, :2]:
        a.set_aspect("equal"); a.set_xlim(-1.8, 1.8); a.set_ylim(-1.8, 1.8)
        a.set_xlabel("I"); a.set_ylabel("Q"); a.grid(True)
    a = ax[0, 2]
    tau, tr = eye(r, M, skip)
    for x in tr[:300]:
        a.plot(tau, x.real, color="C0", lw=0.3, alpha=0.4)
    a.set_xlabel("time from the symbol's centre (symbols)"); a.set_ylabel("I (after both loops)")
    a.set_title("eye diagram, I"); a.grid(True)
    a = ax[1, 0]
    a.plot(us, r["times"] - r["sps"] * k, ".", markersize=1.5)
    a.set_xlabel("time (us)"); a.set_ylabel("sampling time - k x 16 (samples)")
    a.set_title("timing loop: where it samples symbol k")
    a2 = a.twinx()
    a2.plot(us, (r["sps"] / r["period"] - 1) * 1e6, color="C1", lw=1)
    a2.set_ylabel("symbol rate offset it found (ppm)", color="C1")
    a.grid(True)
    a = ax[1, 1]
    a.plot(us, np.degrees(r["phi"]), lw=1)
    a.set_xlabel("time (us)"); a.set_ylabel("phase correction (deg)")
    a.set_title("Costas loop"); a.grid(True)
    a2 = a.twinx()
    a2.plot(us, r["w"] * R / (2 * np.pi) / 1e3, color="C1", lw=1)
    a2.set_ylabel("carrier offset it found (kHz)", color="C1")
    a = ax[1, 2]
    a.plot(us, r["ted"], ".", markersize=1.5, label="Gardner (timing)")
    a.plot(us, r["ec"], ".", markersize=1.5, label="Costas (phase)")
    a.set_xlabel("time (us)"); a.set_ylabel("error signal"); a.legend(fontsize=8)
    a.set_title("what the loops' detectors say"); a.grid(True)
    fig.suptitle(title)
    fig.tight_layout()
    plt.show()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ports", nargs="*", help="one port: looped back; two: A plays, B records")
    ap.add_argument("--sim", action="store_true", help="use channel.py's model, not a board")
    ap.add_argument("--ppm", type=float, default=0.0, help="--sim: pretend to be two boards, A this many ppm fast")
    ap.add_argument("--bpsk", action="store_true", help="BPSK (default QPSK)")
    ap.add_argument("--cfo", type=float, default=0.0, help="transmitter's carrier offset, Hz (rounded to 3051.76 Hz steps)")
    ap.add_argument("--sro", type=float, default=0.0, help="transmitter's symbol-rate offset, ppm (rounded to 1953 ppm steps)")
    ap.add_argument("--ebn0", type=float, help="add noise at the transmitter: Eb/N0 in dB")
    ap.add_argument("--ber", help="measure BER at Eb/N0 = LO:HI dB (1 dB steps)")
    ap.add_argument("--records", type=int, default=40, help="--ber: at most this many uploads per point")
    ap.add_argument("--diff", action="store_true", help="differential coding")
    ap.add_argument("--bnt-timing", type=float, default=0.01, help="timing loop bandwidth x symbol time")
    ap.add_argument("--bnt-carrier", type=float, default=0.02, help="Costas loop bandwidth x symbol time")
    ap.add_argument("--skip", type=int, default=400, help="symbols to let the loops settle")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("-o", "--out", help="save the results (.npz)")
    ap.add_argument("--no-plot", action="store_true")
    args = ap.parse_args()
    M = 2 if args.bpsk else 4
    name = "BPSK" if M == 2 else "QPSK"
    play, record = make_link(args)
    R = NSYM * F_LOOP

    if args.ber:
        lo, hi = (float(x) for x in args.ber.split(":"))
        rng = np.random.default_rng(args.seed)
        rows = []
        print("%s%s, %.4g Msymbol/s: Eb/N0 (dB), bit errors, bits, BER, theory, MER (dB)"
              % (name, " (differential)" if args.diff else "", R / 1e6))
        for eb in np.arange(lo, hi + 0.01, 1.0):
            e = nb = 0; mers = []
            for i in range(args.records):
                # a fresh noise waveform and fresh data for every upload: within one
                # upload the noise repeats every loop, so count one loop's worth
                r = run_once(args, M, play, record, start=int(rng.integers(0, 1023)), ebn0=eb, rng=rng)
                e += r["errs"]; nb += r["nbits"]; mers.append(r["mer"])
                if e >= 200 and i >= 2:
                    break
            th = ber_theory(eb, args.diff)
            rows.append((eb, e, nb, e / nb, th, np.mean(mers)))
            print("%5.1f %6d %8d  %.2e  %.2e  %5.1f" % rows[-1], flush=True)
        if args.out:
            np.savez(args.out, rows=np.array(rows), M=M, diff=args.diff)
        if not args.no_plot:
            import matplotlib.pyplot as plt
            rows = np.array(rows)
            ebs = np.linspace(lo, hi, 100)
            plt.semilogy(ebs, [ber_theory(x, args.diff) for x in ebs], label="theory")
            ok = rows[:, 1] > 0
            plt.semilogy(rows[ok, 0], rows[ok, 3], "o", label="measured")
            plt.xlabel("Eb/N0 (dB)"); plt.ylabel("bit error rate"); plt.grid(True, which="both")
            plt.legend(); plt.title("%s through the cable" % name); plt.show()
    else:
        r = run_once(args, M, play, record, ebn0=args.ebn0, rng=args.seed)
        print("%s at %.4g Msymbol/s (%.4g Mbit/s) on %.4f MHz; transmitter's carrier %+.0f Hz, symbols %+.0f ppm"
              % (name, R / 1e6, R * math.log2(M) / 1e6, F_C / 1e6, r["cfo"], r["sro"]))
        last = slice(-200, None)
        print("timing loop:  symbol rate offset found %+.0f ppm (mean of the last 200 symbols)"
              % np.mean((r["sps"] / r["period"][last] - 1) * 1e6))
        print("Costas loop:  carrier offset found %+.0f Hz" % np.mean(r["w"][last] * R / (2 * np.pi)))
        print("unique words at symbols %s, turned by %s x %d deg"
              % (list(r["starts"]), list(r["rot"]), 360 // M))
        print("%d bit errors in %d bits after the first %d symbols; MER %.1f dB"
              % (r["errs"], r["nbits"], args.skip, r["mer"]))
        if args.out:
            tau, tr = eye(r, M, args.skip)
            np.savez(args.out, **{k: v for k, v in r.items() if isinstance(v, (np.ndarray, int, float))},
                     eye_t=tau, eye=tr[:300])
        if not args.no_plot:
            plot(r, M, "%s, %s" % (name, "simulated" if args.sim else " ".join(args.ports) or "one board"),
                 args.skip)
