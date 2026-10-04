#!/usr/bin/env python3
"""Error-correcting codes on 6.02's QPSK: Hamming(7,4), and the K = 7 convolutional code
with a Viterbi decoder, hard-decision and soft-decision.

    python3 ecc.py --demo               # no board: each code on a few bits, step by step
    python3 ecc.py --ebn0 4             # one noisy frame per code, one board looped back
    python3 ecc.py --sim --ebn0 4       # no board: channel.py's model
    python3 ecc.py --sim --ber 0:8      # bit error rate against Eb/N0, all the decoders
    python3 ecc.py --sim --burst 40     # a 40-symbol dropout, with and without an interleaver
    python3 ecc.py --sim --ber 0:8 -o ecc.npz

The link is psk.py's: one frame per loop, a 32-symbol unique word and 480 data symbols
of QPSK, 960 bits, through awgcap.sv and the cable, received with the Gardner and
Costas loops.  Here the 960 bits are CODE bits.  Three ways to fill them:

  uncoded   960 information bits, as 6.02 sent them
  Hamming   137 blocks of 7: 4 information bits and 3 parity bits each (548 in all);
            the decoder fixes any ONE wrong bit per block (Hamming, Bell Labs, 1950)
  conv      a rate-1/2 convolutional code, constraint length 7, generators 171 and
            133 (octal): each information bit, with the six before it, makes two code
            bits.  474 information bits and 6 zeros to park the encoder.  Voyager,
            DVB-S, 802.11a/g Wi-Fi, the new GPS civil signals and a great deal else use exactly this code.

Decoding, two ways each.  HARD: round every received bit to 0 or 1 first, then
correct.  SOFT: keep the matched filter's value for each bit, which says how SURE
the bit is, and let the decoder weigh it.  The Viterbi decoder is the same for both:
a distance between what was received and what each path through the code's trellis
would have sent; hard decisions just measure that distance after rounding.

Eb/N0 is per INFORMATION bit.  A rate-r code spends 1/r code bits on each, so at the
same Eb/N0 its code bits each get r times the energy, and r times less than that
would be cheating.  (psk.py's --ebn0 is per channel bit; this file converts.)

One change to 6.02's receiver.  A code lets the link run where the code bits are
only 0-3 dB above the noise, and there 6.02's loops misbehave: the Costas loop
(bandwidth 0.02 x the symbol rate) slips a quarter turn now and then, and the Gardner
loop (0.01) jitters by a tenth of a symbol and occasionally runs away, and either
spoils the rest of the frame.  In --sim at 0 dB per code bit 6.02's loops gave a bit
error rate of 0.15 against theory's 0.079.  The cure is the standard one: ACQUIRE
first, feed-forward, then TRACK with narrow loops.  Oerder and Meyr's estimator finds
the symbol timing from |y|^2 with no loop and no decisions, and one board looped back
has no carrier or clock offset to chase, so the loops only have to hold still: 0.002
(timing) and 0.003 (carrier).  That puts the channel BER on theory (0.082 at 0 dB)
and the carrier phase is acquired feed-forward as well (the 4th-power estimate,
ambiguous by a quarter turn, which the unique word resolves), so the narrow loop
starts on target.  (The first version did not, and its MER depended on where the
phase happened to start: 21 to 47 dB on the model, 21.7 dB on the cable.)
--bnt-timing and --bnt-carrier change them back.

--burst switches the DAC off for N symbols in the middle of the frame: a fade, a
scratch on a CD.  Any code built for scattered errors drowns in a clump of them.
An INTERLEAVER (here, write the bits into 32 rows, send them by columns) scatters
the clump before the decoder sees it.
"""
import argparse
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import channel                                              # noqa: E402
import psk                                                  # noqa: E402
from psk import NSYM, NUW, N, F_LOOP, find_port             # noqa: E402

M = 4                                     # QPSK
NBITS = (NSYM - NUW) * 2                  # 960 code bits per frame
ROWS = 32                                 # the interleaver's rows (960 = 32 x 30)
LOOPS = (0.002, 0.003)                    # loop bandwidths (timing, carrier): see the docstring


# ---- Hamming(7,4) -----------------------------------------------------------------
# Number the 7 bits of a block 1..7.  Bits 1, 2 and 4 are parity bits, the rest data.
# Each row of H is a parity check: the bits whose position has that binary digit set.
# So the syndrome (which checks fail), read as a binary number, IS the position of a
# single wrong bit.  That's the whole trick.
H = np.array([[1, 0, 1, 0, 1, 0, 1],              # positions 1, 3, 5, 7 (digit 1)
              [0, 1, 1, 0, 0, 1, 1],              # positions 2, 3, 6, 7 (digit 2)
              [0, 0, 0, 1, 1, 1, 1]])             # positions 4, 5, 6, 7 (digit 4)
PARITY, DATA = [0, 1, 3], [2, 4, 5, 6]            # positions 1, 2, 4 and 3, 5, 6, 7 (0-based)


def hamming_encode(bits):
    """4 information bits -> 7: set each parity bit so that its check comes out even."""
    c = np.zeros((len(bits) // 4, 7), int)
    c[:, DATA] = bits.reshape(-1, 4)
    for p, row in zip(PARITY, H):
        c[:, p] = (c @ row) % 2                   # the parity of the other bits in the check
    return c.ravel()


def hamming_decode(bits):
    """Hard decisions in, 4 information bits per block out: compute the syndrome and
    flip the bit it points at."""
    r = bits.reshape(-1, 7).copy()
    # ##########################################################################
    # ##  KEY LINE: the syndrome.  Which of the three checks fail?  Read as a
    # ##  binary number, that is the position of the wrong bit (0: none).
    # ##########################################################################
    pos = (r @ H.T) % 2 @ np.array([1, 2, 4])
    bad = pos > 0
    r[bad, pos[bad] - 1] ^= 1
    return r[:, DATA].ravel()


ALL16 = ((np.arange(16)[:, None] >> np.arange(4)[::-1]) & 1)          # every 4-bit message
CODEWORDS = 1 - 2 * hamming_encode(ALL16.ravel()).reshape(16, 7)      # ... as +-1


def hamming_decode_soft(values):
    """Soft values in (+ means 0, - means 1, size means confidence).  Only 16 codewords
    exist: pick the one that agrees best with the values, weighted by confidence."""
    v = values.reshape(-1, 7)
    # ##########################################################################
    # ##  KEY LINE: maximum likelihood.  Correlate with all 16 codewords; the
    # ##  best is the nearest in Euclidean distance.  A doubtful bit counts little.
    # ##########################################################################
    return ALL16[np.argmax(v @ CODEWORDS.T, axis=1)].ravel()


# ---- the convolutional code and its Viterbi decoder -------------------------------
def parity(x, nbits):
    """The parity (XOR of the bits) of each integer in x."""
    return np.bitwise_xor.reduce([(x >> i) & 1 for i in range(nbits)])


class ConvCode:
    """Rate 1/2, constraint length K: each input bit, with the K-1 before it, gives two
    output bits, the parities of the register masked by g[0] and g[1] (octal, as the
    textbooks write them).  The STATE is the last K-1 input bits, newest highest."""

    def __init__(self, K=7, g=(0o171, 0o133)):
        self.K, self.g, self.S = K, g, 2**(K - 1)
        s = np.arange(self.S)[:, None]
        b = np.arange(2)[None, :]
        reg = (b << (K - 1)) | s                                   # the K bits in the register
        self.out = np.stack([parity(reg & gi, K) for gi in g], axis=-1)   # (state, input) -> 2 bits
        self.next = (b << (K - 2)) | (s >> 1)                      # (state, input) -> state
        # For the decoder: each state's two possible predecessors, and the input bit
        # that leads into it (its newest bit).
        mask = 2**(K - 2) - 1
        self.pred = ((np.arange(self.S)[:, None] & mask) << 1) | np.arange(2)[None, :]
        self.input_of = np.arange(self.S) >> (K - 2)
        self.rate = 0.5

    def encode(self, bits):
        """Information bits -> code bits, with K-1 zeros at the end to bring the encoder
        back to state 0 (so the decoder knows where the path ends)."""
        bits = np.concatenate([bits, np.zeros(self.K - 1, int)])
        s, out = 0, []
        for b in bits:
            # ######################################################################
            # ##  KEY LINE: the encoder is a lookup: from this state, this input
            # ##  bit sends these two bits and moves to that state.
            # ######################################################################
            out.append(self.out[s, b])
            s = self.next[s, b]
        return np.array(out).ravel()

    def viterbi(self, values, trace=False):
        """Code-bit values in, as +1 (a 0) / -1 (a 1): rounded to +-1 they are HARD
        decisions, left as the matched filter made them they are SOFT.  Returns the
        information bits (and, with trace, the path metrics and survivors at every step)."""
        r = values.reshape(-1, 2)
        T = len(r)
        o = 1 - 2 * self.out                                       # each branch's two bits, as +-1
        pm = np.full(self.S, np.inf)                               # path metrics: the cost of the
        pm[0] = 0.0                                                #   best path into each state
        surv = np.zeros((T, self.S), int)                          # which predecessor each state kept
        hist = []
        for t in range(T):
            # ######################################################################
            # ##  KEY LINE: the branch metric.  How far is what we received from
            # ##  what each branch (state, input) would have sent?  Squared
            # ##  Euclidean distance; for +-1 inputs that's 4 x the Hamming distance.
            # ######################################################################
            bm = np.sum((r[t] - o)**2, axis=-1)                    # (state, input)
            # ######################################################################
            # ##  KEY LINE: add, compare, select.  Two paths arrive at each new
            # ##  state (from its two predecessors).  Keep the cheaper; the other
            # ##  can never win, whatever comes next.  That's the whole algorithm.
            # ######################################################################
            cand = pm[self.pred] + bm[self.pred, self.input_of[:, None]]
            surv[t] = np.argmin(cand, axis=1)
            pm = cand[np.arange(self.S), surv[t]]
            if trace:
                hist.append(pm.copy())
        # ##########################################################################
        # ##  KEY LINE: trace back.  Start at state 0 (the tail zeros parked the
        # ##  encoder there) and walk the survivors backwards; each state's newest
        # ##  bit is the information bit that led into it.
        # ##########################################################################
        s, bits = 0, np.zeros(T, int)
        for t in range(T - 1, -1, -1):
            bits[t] = self.input_of[s]
            s = self.pred[s, surv[t, s]]
        bits = bits[:T - (self.K - 1)]
        return (bits, np.array(hist), surv) if trace else bits


CONV = ConvCode(7, (0o171, 0o133))


# ---- the three schemes, with one interface ----------------------------------------
class Scheme:
    """name, rate, n_info (information bits per frame), encode(info) -> 960 code bits,
    decoders: {label: f(values) -> information bits}."""

    def __init__(self, name, rate, n_info, encode, decoders):
        self.name, self.rate, self.n_info, self.encode, self.decoders = name, rate, n_info, encode, decoders

    def pad(self, code_bits):
        return np.concatenate([code_bits, np.zeros(NBITS - len(code_bits), int)])


def hard(values):
    return (values < 0).astype(int)


SCHEMES = {
    "uncoded": Scheme("uncoded", 1.0, NBITS, lambda b: b, {"hard": hard}),
    "hamming": Scheme("Hamming(7,4)", 4 / 7, 4 * (NBITS // 7), hamming_encode,
                      {"hard": lambda v: hamming_decode(hard(v[:7 * (NBITS // 7)])),
                       "soft": lambda v: hamming_decode_soft(v[:7 * (NBITS // 7)])}),
    "conv": Scheme("conv K=7 r=1/2", 0.5, NBITS // 2 - 6, CONV.encode,
                   {"hard": lambda v: CONV.viterbi(np.sign(v)), "soft": CONV.viterbi}),
}


# ---- the frame, through psk.py --------------------------------------------------
def interleave(x, rows=ROWS):
    """Write row by row, read column by column: neighbours end up len(x)/rows apart."""
    return x.reshape(rows, -1).T.ravel()


def deinterleave(x, rows=ROWS):
    return x.reshape(-1, rows).T.ravel()


SCRAMBLE = psk.g1(NBITS)                  # a known pseudo-random sequence (1.07's G1)


def frame(code_bits):
    """psk.py's frame with these 960 code bits in its 480 data symbols.  Returns q."""
    uw = psk.bits_to_q(psk.g2(NUW * 2, start=psk.UW_START), M)
    # ##########################################################################
    # ##  KEY LINE: the scrambler.  XOR with a known pseudo-random sequence, so
    # ##  that the code's structure doesn't show in the waveform.  (Without it
    # ##  the Hamming frames, with more runs of equal bits than random data,
    # ##  read 3 dB less MER through psk.py's receiver, which assumes random
    # ##  data.)  Every real link does this; the receiver undoes it by flipping
    # ##  the sign of the soft values where the sequence is 1.
    # ##########################################################################
    return np.concatenate([uw, psk.bits_to_q(code_bits ^ SCRAMBLE, M)])


def soft_bits(z):
    """QPSK symbols -> a soft value per bit: + means 0, - means 1, the size says how
    sure.  With psk's Gray map the first bit of each symbol rides on Q, the second on I."""
    return (np.column_stack([z.imag, z.real]) * math.sqrt(2)).ravel()


def collect(r, skip=400, nsym=NSYM):
    """One frame's 480 data symbols, in order, from a received record.  The frame
    repeats every loop and the loops have settled after `skip` symbols, so take each
    position from whichever repeat falls after that, turned by the unique word's answer."""
    zc, K = r["zc"], len(r["zc"])
    out = np.full(nsym - NUW, np.nan, complex)
    i = np.arange(NUW, nsym)
    for st, rot in zip(r["starts"], r["rot"]):
        k = st + i
        ok = (k >= skip) & (k < K) & np.isnan(out)
        out[i[ok] - NUW] = zc[k[ok]] * np.exp(-2j * np.pi * rot / M)
    out[np.isnan(out)] = 0                                    # never seen: an erasure
    return out


def timing_estimate(y, sps):
    """Where are the symbol centres?  Oerder and Meyr (1988): after the matched filter
    |y|^2 bulges once per symbol, so the PHASE of its component at the symbol rate is
    the timing.  No loop and no decisions, so it works at any SNR, given enough symbols.
    Returns the offset in samples, 0 to sps."""
    n = np.arange(len(y))
    # ##########################################################################
    # ##  KEY LINE: a one-bin Fourier transform of |y|^2 at the symbol rate.
    # ##########################################################################
    X = np.sum(np.abs(y)**2 * np.exp(-2j * np.pi * n / sps))
    return (-sps * np.angle(X) / (2 * np.pi)) % sps


def receive(rec, q, loops=LOOPS, skip=400):
    """6.02's receiver (psk.receive), with the timing acquired feed-forward first so
    that both loops can be narrow: they only have to track."""
    sps = psk.FS_ADC * N / psk.FS_DAC / NSYM
    y = psk.matched(rec)
    t0 = timing_estimate(y, sps) + 2 * sps                     # start the loop on a symbol centre
    zs, times, ted, period = psk.timing_loop(y, sps, loops[0], t0)
    zs = zs / np.sqrt(np.mean(np.abs(zs)**2))
    # ##########################################################################
    # ##  KEY LINE: acquire the carrier phase feed-forward too.  Raising QPSK
    # ##  symbols to the 4th power wipes out the data (the four points land on
    # ##  one), leaving 4 x the carrier phase: a one-shot estimate, ambiguous by
    # ##  a quarter turn, which the unique word resolves as before.  The narrow
    # ##  Costas loop then starts on target instead of 400 symbols away from it.
    # ##########################################################################
    phi0 = np.angle(np.mean(zs[skip:]**M) / psk.point(0, M)**M) / M
    zc, phi, w, ec = psk.costas(zs * np.exp(-1j * phi0), M, loops[1])
    r = dict(y=y, sps=sps, times=times, ted=ted, period=period, zs=zs, zc=zc, phi=phi, w=w, ec=ec)
    r.update(psk.score(zc, M, NSYM, q, False, skip))
    return r


def run_frame(scheme, play, record, ebn0=None, rng=None, burst=0, inter=False, skip=400,
              loops=LOOPS):
    """Information bits -> code bits -> QPSK -> the cable, with noise at Eb/N0 per
    INFORMATION bit -> the receiver (loops = its timing and carrier loop bandwidths)
    -> soft values.  Returns (info, values, r)."""
    rng = np.random.default_rng(rng)
    info = rng.integers(0, 2, scheme.n_info)
    code = scheme.pad(scheme.encode(info))
    q = frame(interleave(code) if inter else code)
    # ##########################################################################
    # ##  KEY LINE: a rate-r code sends 1/r code bits per information bit, so
    # ##  at Eb/N0 per information bit each CODE bit gets r times less energy.
    # ##########################################################################
    eb_code = None if ebn0 is None else ebn0 + 10 * math.log10(scheme.rate)
    wave = psk.transmit(q, M, ebn0=eb_code, rng=rng)
    if burst:                                                 # the DAC goes quiet for `burst` symbols
        a = (NUW + (NSYM - NUW - burst) // 2) * N // NSYM
        wave[a:a + burst * N // NSYM] = 128
    play(wave)
    r = receive(record(), q, loops, skip)
    values = soft_bits(collect(r, skip)) * (1 - 2 * SCRAMBLE)      # unscramble
    return info, deinterleave(values) if inter else values, r


def make_link(args):
    """play(wave) and record(), on the board(s) or on channel.py's model."""
    if args.sim:
        rng = np.random.default_rng(args.seed)
        st = {}
        return (lambda w: st.__setitem__("w", w)), (lambda: channel.channel(st["w"], rng=rng))
    sys.path.insert(0, os.path.join(HERE, "..", "twoboard"))
    import awgcap
    ports = args.ports or [find_port()]
    return (lambda w: awgcap.upload(ports[0], w)), (lambda: awgcap.record(ports[-1]))


def ber_run(play, record, ebn0s, records=300, min_errors=100, seed=1, schemes=SCHEMES, out=None,
            loops=LOOPS):
    """BER against Eb/N0 for every scheme and decoder.  Returns {scheme: {decoder:
    rows of (Eb/N0, errors, bits)}} and {scheme: rows of (Eb/N0, channel errors, bits)}."""
    rng = np.random.default_rng(seed)
    res = {k: {d: [] for d in s.decoders} for k, s in schemes.items()}
    raw = {k: [] for k in schemes}
    for key, s in schemes.items():
        for eb in ebn0s:
            errs = {d: 0 for d in s.decoders}
            nb = ne = nraw = 0
            for i in range(records):
                info, values, r = run_frame(s, play, record, eb, rng, loops=loops)
                for d, dec in s.decoders.items():
                    errs[d] += int(np.sum(dec(values) != info))
                nb += s.n_info
                ne += r["errs"]; nraw += r["nbits"]
                if min(errs.values()) >= min_errors and i >= 2:
                    break
            for d in s.decoders:
                res[key][d].append((eb, errs[d], nb))
            raw[key].append((eb, ne, nraw))
            print("%-16s %4.1f dB  %4d frames  channel BER %.2e  %s" %
                  (s.name, eb, i + 1, ne / nraw,
                   "  ".join("%s %d/%d (%.2e)" % (d, errs[d], nb, errs[d] / nb) for d in s.decoders)), flush=True)
    if out:
        np.savez(out, **{"%s_%s" % (k, d): np.array(v) for k in res for d, v in res[k].items()},
                 **{"raw_%s" % k: np.array(v) for k, v in raw.items()})
    return res, raw


def coding_gain(rows_uncoded, rows, ber=1e-4):
    """dB between the uncoded curve and this one at a given BER, by straight lines
    between the measured points on a log scale.  A point with no errors counts as one
    error (an upper limit on its BER, so the gain is then a lower limit).  nan if the
    curve doesn't cross."""
    def cross(rows):
        rows = np.array(rows, float)
        y = np.log10(np.maximum(rows[:, 1], 1) / rows[:, 2])
        for i in range(len(y) - 1):
            if y[i] >= math.log10(ber) >= y[i + 1]:
                return rows[i, 0] + (y[i] - math.log10(ber)) / (y[i] - y[i + 1]) * (rows[i + 1, 0] - rows[i, 0])
        return float("nan")
    return cross(rows_uncoded) - cross(rows)


# ---- a demonstration on a few bits ------------------------------------------------
def demo():
    rng = np.random.default_rng(3)
    print("Hamming(7,4).  Positions 1..7; parity bits at 1, 2, 4.\n")
    info = np.array([1, 0, 1, 1])
    cw = hamming_encode(info)
    print("  message       %s" % info)
    print("  codeword      %s   (positions 1..7; data at 3, 5, 6, 7)" % cw)
    for pos in (1, 5):
        rx = cw.copy(); rx[pos - 1] ^= 1
        syn = (rx @ H.T) % 2
        print("  flip bit %d -> %s   syndrome %s = %d -> flip bit %d back -> %s"
              % (pos, rx, syn, syn @ [1, 2, 4], syn @ [1, 2, 4], hamming_decode(rx)))
    rx = cw.copy(); rx[0] ^= 1; rx[4] ^= 1
    print("  flip bits 1 and 5 -> %s   syndrome %d: wrong, and confidently so  -> %s"
          % (rx, ((rx @ H.T) % 2) @ [1, 2, 4], hamming_decode(rx)))

    small = ConvCode(3, (0o7, 0o5))
    print("\nA small convolutional code first: K = 3, generators 7 and 5 (octal), 4 states.")
    print("  state = the last two input bits (newest highest); from each, input 0 or 1 sends:")
    for s in range(4):
        print("    state %s: 0 -> %s to %s,  1 -> %s to %s" % (
            np.binary_repr(s, 2), small.out[s, 0], np.binary_repr(small.next[s, 0], 2),
            small.out[s, 1], np.binary_repr(small.next[s, 1], 2)))
    info = np.array([1, 0, 1, 1, 0])
    code = small.encode(info)
    print("  message %s + tail 00 -> code bits %s" % (info, code))
    v = 1.0 - 2 * code
    v[3] = -v[3]; v[8] = -v[8]                                 # two wrong bits, 5 apart
    bits, hist, _ = small.viterbi(v, trace=True)
    print("  flip code bits 4 and 9 (hard decisions %s)" % (v < 0).astype(int))
    print("  path metrics after each pair (states 00 01 10 11; 4 per wrong bit; inf = unreachable):")
    for t, pm in enumerate(hist):
        print("    t=%d  %s" % (t + 1, "  ".join("%4s" % ("inf" if np.isinf(x) else "%g" % x) for x in pm)))
    print("  traced back: %s %s" % (bits, "correct" if np.all(bits == info) else "WRONG"))

    print("\nThe real one: K = 7, generators 171 and 133, %d states." % CONV.S)
    info = rng.integers(0, 2, 40)
    code = CONV.encode(info)
    v = 1.0 - 2 * code
    bad = rng.choice(len(v), 8, replace=False)
    v[bad] = -v[bad]
    print("  40 information bits -> %d code bits; flip 8 of them, at %s" % (len(code), sorted(bad)))
    print("  hard Viterbi: %d information bits wrong" % np.sum(CONV.viterbi(v) != info))
    info = rng.integers(0, 2, 400)
    code = CONV.encode(info)
    v = 1.0 - 2 * code + 0.75 * rng.standard_normal(2 * len(info) + 12)   # noisy soft values
    print("  400 information bits with Gaussian noise of rms 0.75 on the +-1 code bits")
    print("  (Eb/N0 2.5 dB per information bit): %d of %d hard decisions wrong;"
          % (np.sum((v < 0) != code), len(v)))
    print("  hard Viterbi %d information bits wrong, soft Viterbi %d"
          % (np.sum(CONV.viterbi(np.sign(v)) != info), np.sum(CONV.viterbi(v) != info)))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ports", nargs="*", help="one port: looped back; two: A plays, B records")
    ap.add_argument("--sim", action="store_true", help="use channel.py's model, not a board")
    ap.add_argument("--demo", action="store_true", help="no board: the codes on a few bits, printed")
    ap.add_argument("--ebn0", type=float, help="add noise at the transmitter: Eb/N0 per information bit, dB")
    ap.add_argument("--ber", help="measure BER at Eb/N0 = LO:HI dB (1 dB steps)")
    ap.add_argument("--records", type=int, default=300, help="--ber: at most this many frames per point")
    ap.add_argument("--errors", type=int, default=100, help="--ber: stop a point after this many errors")
    ap.add_argument("--burst", type=int, default=0, help="switch the DAC off for this many symbols per frame")
    ap.add_argument("--bnt-timing", type=float, default=LOOPS[0], help="timing loop bandwidth x symbol time")
    ap.add_argument("--bnt-carrier", type=float, default=LOOPS[1], help="Costas loop bandwidth x symbol time")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("-o", "--out", help="save the results (.npz)")
    args = ap.parse_args()
    loops = (args.bnt_timing, args.bnt_carrier)

    if args.demo:
        demo()
        sys.exit()
    play, record = make_link(args)
    R = NSYM * F_LOOP

    if args.ber:
        lo, hi = (float(x) for x in args.ber.split(":"))
        ebs = np.arange(lo, hi + 0.01, 1.0)
        print("QPSK, %.4g Msymbol/s; Eb/N0 per information bit; errors/bits (BER) per decoder" % (R / 1e6))
        res, raw = ber_run(play, record, ebs, args.records, args.errors, args.seed, out=args.out, loops=loops)
        for key in ("hamming", "conv"):
            for d, rows in res[key].items():
                print("coding gain at BER 1e-4, %s %s: %.1f dB" %
                      (SCHEMES[key].name, d, coding_gain(res["uncoded"]["hard"], rows)))
    elif args.burst:
        rng = np.random.default_rng(args.seed)
        print("a %d-symbol dropout (%d code bits) in each 480-symbol frame%s:" %
              (args.burst, 2 * args.burst, "" if args.ebn0 is None else ", Eb/N0 %.1f dB" % args.ebn0))
        for key, s in SCHEMES.items():
            for inter in (False, True):
                info, values, r = run_frame(s, play, record, args.ebn0, rng, burst=args.burst, inter=inter, loops=loops)
                print("  %-16s %-20s raw %3d/%d wrong;  %s" % (
                    s.name, "interleaved" if inter else "straight", r["errs"], r["nbits"],
                    "  ".join("%s: %d of %d information bits wrong" % (d, np.sum(dec(values) != info), s.n_info)
                              for d, dec in s.decoders.items())))
    else:
        rng = np.random.default_rng(args.seed)
        print("QPSK at %.4g Msymbol/s%s; one frame per scheme:" %
              (R / 1e6, "" if args.ebn0 is None else ", Eb/N0 %.1f dB per information bit" % args.ebn0))
        for key, s in SCHEMES.items():
            info, values, r = run_frame(s, play, record, args.ebn0, rng, loops=loops)
            print("  %-16s rate %.3f, %3d information bits; channel: %d of %d code bits wrong (MER %.1f dB);  %s" % (
                s.name, s.rate, s.n_info, r["errs"], r["nbits"], r["mer"],
                "  ".join("%s: %d wrong" % (d, np.sum(dec(values) != info)) for d, dec in s.decoders.items())))
