#!/usr/bin/env python3
"""QPSK through an echo, and three equalizers that undo it: LMS, a DFE, and divide-by-H(f).

    python3 equalize.py --sim --echo 1:0.67     # an echo one symbol late, 2/3 the size
    python3 equalize.py --sim --stub 25         # a 25 m open stub on a T: echo.py's bounces and loss
    python3 equalize.py PORT --stub 25          # the real cable, plus the simulated stub
    python3 equalize.py PORT                    # the real cable alone (or with a real T and stub)
    python3 equalize.py --sim --echo 1:0.67 --ebn0 10    # noise at the receiver: Eb/N0 = 10 dB
    python3 equalize.py --sim --echo 1:0.67 --ber 0:12   # bit error rate against Eb/N0
    python3 equalize.py --sim --echo 1:0.67 --taps 21 --mu 0.1 --nlms
    python3 equalize.py --sim --echo 1:0.67 --spacing 1  # one tap per symbol instead of two
    python3 equalize.py --sim --echo 1:0.67 -o eq.npz --no-plot

The board runs awgcap.sv (5.01) and plays psk.py's QPSK: 512 symbols per loop (a 32-symbol
unique word, then 480 of data) at 1.5625 Msymbol/s on 6.25 MHz, 16 ADC samples a symbol.

THE CHANNEL is the record (the ADC's, or channel.py's model) plus echo.py's echo, plus
white noise added at the RECEIVER (--ebn0), after the echo, where a radio's front end
adds it.  So a notch in the channel does not notch the noise, and undoing the notch
costs something: that is the whole subject.

FOUR RECEIVERS, all on the same record
  loops  6.02's receiver, untouched: matched filter, Gardner loop, Costas loop, slice.
  lms    the matched filter; then the unique word, correlated at every sample, gives the
         symbol timing and the carrier phase in one go (a burst modem's way: no loops);
         then an FIR filter with `taps` complex taps, 2 per symbol (--spacing 2, "T/2-
         spaced") or 1 (--spacing 1, "symbol-spaced"), whose taps LEARN by the LMS rule:
             y_k = sum_i w_i x_{k-i}           the filter
             e_k = d_k - y_k                   how wrong it was
             w_i <- w_i + mu e_k x*_{k-i}      nudge every tap towards less error
         d_k is the symbol that was sent while training (the first --train records are
         a training sequence the receiver knows in full, as a modem's handshake sends),
         and every frame's unique word; in between it is the receiver's own decision
         (decision-directed).  mu is in units of 1/(taps x input power); --nlms divides
         by the actual |x|^2 of each input vector instead (normalized LMS).
  dfe    the same, plus --fb taps fed with the past DECISIONS: a decided symbol is clean,
         so subtracting the echo it causes adds no noise (until a decision is wrong, and
         the error propagates).
  fd     divide by H(f).  The channel is sounded once with sound.py's multitone, and the
         record's spectrum is divided by H(f) bin by bin (zero forcing, ZF), or multiplied
         by (1/H) x S/(S + N), which backs off where the signal is weak (MMSE).  The result
         goes to 6.02's receiver, untouched.

The matched filter is the best receiver for one pulse in white noise.  After an echo the
signal isn't one pulse any more, and the equalizer is what fixes that.
"""
import argparse
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import channel                                      # noqa: E402
import echo                                         # noqa: E402
import psk                                          # noqa: E402
import sound                                        # noqa: E402
from psk import N, FS_ADC, F_LOOP, F_C, NSYM, NUW, find_port       # noqa: E402

L = 8192                            # ADC samples per loop
M = 4                               # QPSK
EDGE = 7 * 16                       # samples at each end of the matched filter's output to skip


# ---- the channel ------------------------------------------------------------------
def add_noise(rec, ebn0_db, nsym=NSYM, rng=None):
    """White noise at the receiver, in fc +- the symbol rate, for Eb/N0 = ebn0_db, with
    Eb the energy per bit AS RECEIVED (from the record's own power, echoes and all)."""
    rng = np.random.default_rng(rng)
    rec = np.asarray(rec, float)
    R = nsym * F_LOOP
    s = rec - rec.mean()
    Eb = np.mean(s**2) / R / math.log2(M)
    N0 = Eb / 10**(ebn0_db / 10)
    f = np.fft.rfftfreq(len(rec), 1 / FS_ADC)
    band = np.abs(f - F_C) <= R
    var = N0 * band.sum() * (FS_ADC / len(rec))           # noise power = N0 x bandwidth
    X = np.zeros(len(f), complex)
    X[band] = rng.standard_normal(band.sum()) + 1j * rng.standard_normal(band.sum())
    x = np.fft.irfft(X, len(rec))
    return rec + x * np.sqrt(var) / x.std()


def make_link(args):
    """play(wave) and record() for the board(s) or the model, with the echo (--echo or
    --stub) added to every record.  Returns them and a description for the plots."""
    if args.sim:
        rng = np.random.default_rng(args.seed)
        st = {}
        def play(wave):
            st["wave"] = wave
        def record():
            return channel.channel(st["wave"], rng=rng)
        desc = "simulated"
    else:
        sys.path.insert(0, os.path.join(HERE, "..", "twoboard"))
        import awgcap
        ports = args.ports or [find_port()]
        play = lambda wave: awgcap.upload(ports[0], wave)
        record = lambda: awgcap.record(ports[-1])
        desc = "measured"
    rec0 = record
    if args.stub:
        record = lambda: echo.add_stub(rec0(), args.stub, vf=args.vf, loss=args.loss)
        desc += ", %g m stub" % args.stub
    elif args.echo:
        D, a, b = args.echo
        tau = D / (args.nsym * F_LOOP)
        record = lambda: echo.add_echo(rec0(), tau, a, b)
        desc += ", echo %g symbol%s late, size %g" % (D, "" if D == 1 else "s", a)
    return play, record, desc


def sound_channel(play, record, records=4):
    """H(f) on the loop's bins, by sound.py's multitone, through whatever record() does."""
    wave, x = sound.probe_multitone()
    play(wave)
    rec = np.mean([record() for _ in range(records)], axis=0)
    return sound.by_divide(rec, x)


# ---- receiver 1: 6.02's loops ----------------------------------------------------------
def loops(rec, q, nsym=NSYM):
    """psk.py's receiver (any symbols per loop).  Returns its dict: errs, nbits, mer, ..."""
    sps = FS_ADC * N / psk.FS_DAC / nsym
    y = psk.matched(rec, nsym)
    zs, times, ted, period = psk.timing_loop(y, sps)
    zs = zs / np.sqrt(np.mean(np.abs(zs)**2))
    zc, phi, w, ec = psk.costas(zs, M)
    r = dict(y=y, sps=sps, times=times, zc=zc, phi=phi)
    r.update(psk.score(zc, M, nsym, q))
    return r


# ---- receivers 2 and 3: sync on the unique word, then LMS, with or without feedback ----
def sync(y, q, sps):
    """Where the frame starts (a sample of y) and the carrier phase there: correlate the
    matched filter's output with the unique word at every sample offset.  (6.02 did
    this once per symbol, after the loops; here it replaces them.)"""
    uw = psk.point(q[:NUW], M)
    step = int(round(sps))
    K = len(y) - NUW * step
    c = np.zeros(K, complex)
    for i in range(NUW):
        c += np.conj(uw[i]) * y[i * step:i * step + K]
    c /= NUW
    t0 = EDGE + int(np.argmax(np.abs(c[EDGE:EDGE + L])))     # the first whole frame
    return t0, np.angle(c[t0]), c


def lms(u, j0, ks, known, w, mu, sps, fb=0, nlms=False, power=1.0):
    """The LMS equalizer, run over symbols ks.  u: the input, `sps` samples per symbol,
    symbol k's centre at u[j0 + sps k].  known[k]: the symbol sent, or None (decide).
    w: the taps, feedforward (centred on the symbol) then `fb` feedback ones; updated in
    place.  Returns the outputs y_k, the errors e_k, the decisions, and the taps' history."""
    taps = len(w) - fb
    half = taps // 2
    up = np.concatenate([np.zeros(half), u, np.zeros(half)])      # so the edges are safe
    past = np.zeros(fb, complex)                                   # the last fb decisions
    ys, es, ds, W = [], [], [], []
    for k in ks:
        j = j0 + sps * k + half
        x = up[j + half - np.arange(taps)]                         # newest sample first
        if fb:
            x = np.concatenate([x, past])
        # ######################################################################
        # ##  KEY LINES: the filter, the error, the update.  A DFE is the same
        # ##  thing with the past decisions appended to the input vector.
        # ######################################################################
        y = w @ x
        d = known[k] if known[k] is not None else psk.point(psk.decide(y, M), M)
        e = d - y
        g = mu / (1e-9 + np.vdot(x, x).real) if nlms else mu / (len(x) * power)
        w += g * e * np.conj(x)
        if fb:
            past = np.concatenate([[d], past[:-1]])
        ys.append(y); es.append(e); ds.append(d); W.append(w.copy())
    return np.array(ys), np.array(es), np.array(ds), np.array(W)


def wiener(u, j0, ks, sent, taps, sps):
    """The least-squares taps for the same input: the answer the LMS creeps towards.  One
    matrix solve instead of thousands of nudges, but it needs the whole record at once."""
    half = taps // 2
    up = np.concatenate([np.zeros(half), u, np.zeros(half)])
    X = np.array([up[j0 + sps * k + 2 * half - np.arange(taps)] for k in ks])
    # ##########################################################################
    # ##  KEY LINE: minimize sum |d - X w|^2 over w: a least-squares solve.
    # ##########################################################################
    return np.linalg.lstsq(X, sent, rcond=None)[0]


def equalized(y, w, step):
    """The whole matched-filter output put through the (feedforward) taps, spaced `step`
    samples: the equalized signal at every sample, for an eye diagram."""
    taps = len(w)
    half = taps // 2
    out = np.zeros(len(y), complex)
    for i, wi in enumerate(w):
        out += wi * np.roll(y, -(half - i) * step)
    return out


# ---- receiver 4: divide by H(f) ----------------------------------------------------------
def fd_equalize(rec, H, mmse=True, nsym=NSYM, smooth=64, hlen=256):
    """The record's spectrum divided by the sounded H(f): zero forcing, or MMSE.  The
    signal repeats every loop, so it has power only on the record's EVEN bins; the odd
    bins hold noise alone, and that measures S and N for the MMSE's S/(S + N)."""
    rec = np.asarray(rec, float)
    m = rec.mean()
    Rf = np.fft.rfft(rec - m)
    f = np.fft.rfftfreq(len(rec), 1 / FS_ADC)
    fH = np.fft.rfftfreq(L, 1 / FS_ADC)
    # The sounded H(f) carries the converters' rounding noise, 1-2% per bin, and 1/H
    # would stamp that onto the signal.  But the channel's h[n] is short (sound.py),
    # so keep only its first `hlen` samples: H(f) smoothed, the noise averaged away.
    h = np.fft.irfft(np.nan_to_num(H), L)
    h[hlen:] = 0
    H = np.fft.rfft(h, L)
    Hi = np.interp(f, fH, H.real) + 1j * np.interp(f, fH, H.imag)
    R = nsym * F_LOOP
    inband = np.abs(f - F_C) <= R                              # the matched filter's band
    W = np.zeros(len(f), complex)
    # ##########################################################################
    # ##  KEY LINE: zero forcing is one complex divide per bin.
    # ##########################################################################
    W[inband] = 1 / Hi[inband]
    if mmse:
        k = np.ones(smooth) / smooth
        P = np.abs(Rf)**2
        Ps = np.convolve(P[0::2], k, mode="same")              # even bins: signal + noise
        Pn = np.convolve(P[1::2], k, mode="same")              # odd bins: noise
        Pn = np.append(Pn, Pn[-1])                              # (one fewer odd bin than even)
        wiener = np.clip(1 - Pn / Ps, 0, 1)
        # ######################################################################
        # ##  KEY LINE: MMSE = zero forcing times S / (S + N): where the channel
        # ##  has buried the signal in noise, don't try to dig it out.
        # ######################################################################
        W *= np.repeat(wiener, 2)[:len(W)]
    return m + np.fft.irfft(Rf * W, len(rec)), W


# ---- putting it together ------------------------------------------------------------------
def score(z, sent, is_uw):
    """Bit errors, bits and MER (dB) of the symbols z against the ones sent, data only."""
    d = ~is_uw
    errs = int(np.sum(psk.q_to_bits(psk.decide(z[d], M), M) != psk.q_to_bits(psk.decide(sent[d], M), M)))
    return dict(errs=errs, nbits=2 * int(d.sum()), mer=-10 * np.log10(np.mean(np.abs(z[d] - sent[d])**2)))


def slicer(rec, q, nsym=NSYM, spacing=2):
    """Matched filter, unique-word sync, and the symbols at every symbol instant, with
    `spacing` samples per symbol in between (u, j0): the equalizers' input."""
    sps_in = FS_ADC * N / psk.FS_DAC / nsym                    # 16
    step = int(round(sps_in / spacing))                        # samples between taps
    y = psk.matched(rec, nsym)
    t0, phi, c = sync(y, q, sps_in)
    u = y[t0 % step::step] * np.exp(-1j * phi)
    j0 = t0 // step
    ks = np.arange(int(np.ceil((EDGE - t0) / sps_in)), (len(y) - EDGE - t0) // int(sps_in))
    sent = psk.point(q[ks % nsym], M)
    is_uw = (ks % nsym) < NUW
    return dict(y=y, t0=t0, phi=phi, u=u, j0=j0, step=step, ks=ks, sent=sent, is_uw=is_uw,
                x=u[j0 + spacing * ks])


def receive_all(rec, q, args, state, H=None, count=True):
    """Run every receiver on one record.  `state` keeps the equalizers' taps between
    records; `count` says whether this record's errors are to be counted (not while
    training).  Returns a dict of results."""
    nsym = args.nsym
    out = {}
    # 1. the loops
    r = loops(rec, q, nsym)
    out["loops"] = dict(errs=r["errs"], nbits=r["nbits"], mer=r["mer"], r=r)
    # 2, 3. sync, then LMS and DFE
    s = slicer(rec, q, nsym, args.spacing)
    out["sync"] = s
    out["none"] = score(s["x"], s["sent"], s["is_uw"])
    out["none"]["x"] = s["x"]
    training = not count or args.train_all
    known = {k: (z if (training or uw) else None) for k, z, uw in zip(s["ks"], s["sent"], s["is_uw"])}
    power = np.mean(np.abs(s["u"])**2)
    for name, fb in (("lms", 0), ("dfe", args.fb)):
        if name not in state:
            state[name] = np.zeros(args.taps + fb, complex)
            state[name][args.taps // 2] = 1.0                    # start as "do nothing"
        ys, es, ds, W = lms(s["u"], s["j0"], s["ks"], known, state[name], args.mu, args.spacing,
                            fb, args.nlms, power)
        out[name] = score(ys, s["sent"], s["is_uw"])
        out[name].update(y=ys, e=es, W=W, ks=s["ks"])
    # 4. divide by H(f), then the same sync and slicer (and, for the record, 6.02's loops)
    if H is not None:
        for name, mmse in (("fd_zf", False), ("fd_mmse", True)):
            req, W = fd_equalize(rec, H, mmse, nsym)
            s2 = slicer(req, q, nsym, args.spacing)
            out[name] = score(s2["x"], s2["sent"], s2["is_uw"])
            out[name].update(W=W, rec=req, x=s2["x"])
        r = loops(req, q, nsym)
        out["fd_mmse_loops"] = dict(errs=r["errs"], nbits=r["nbits"], mer=r["mer"])
    return out


RECEIVERS = ("loops", "none", "lms", "dfe", "fd_zf", "fd_mmse", "fd_mmse_loops")
LABELS = {"loops": "6.02's loops, no equalizer", "none": "unique-word sync, no equalizer",
          "lms": "LMS", "dfe": "DFE", "fd_zf": "divide by H(f), zero forcing",
          "fd_mmse": "divide by H(f), MMSE", "fd_mmse_loops": "divide by H(f), MMSE, then 6.02's loops"}


def run(args, play, record, q, H, ebn0=None, rng=None, records=None, state=None, min_errs=0):
    """`records` records (the first `train` of them as training), every receiver; with
    min_errs, keep going (up to args.max_records) until the LMS has that many errors.
    Returns (totals per receiver, the last record's results, the equalizers' state)."""
    records = records or args.records
    state = {} if state is None else state
    tot = {k: [0, 0, []] for k in RECEIVERS}
    hist = {"W_lms": [], "e_lms": [], "e_dfe": []}                # the whole run, record by record
    last = None
    i = 0
    while i < records or (min_errs and tot["lms"][0] < min_errs and i < args.max_records):
        rec = record()
        if ebn0 is not None:
            rec = add_noise(rec, ebn0, args.nsym, rng)
        last = receive_all(rec, q, args, state, H, count=i >= args.train)
        if i >= args.train:
            for k in RECEIVERS:
                if k in last:
                    tot[k][0] += last[k]["errs"]; tot[k][1] += last[k]["nbits"]; tot[k][2].append(last[k]["mer"])
        hist["W_lms"].append(last["lms"]["W"]); hist["e_lms"].append(last["lms"]["e"]); hist["e_dfe"].append(last["dfe"]["e"])
        i += 1
    state["hist"] = {k: np.concatenate(v) for k, v in hist.items()}
    return tot, last, state


def plot(res, tot, desc, args):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 3, figsize=(13, 8))
    ks = res["lms"]["ks"]
    W = res["lms"]["W"]
    half = args.taps // 2
    for i in range(max(0, half - 2 * args.spacing), min(args.taps, half + 8 * args.spacing + 1)):
        ax[0, 0].plot(ks, W[:, i].real, lw=0.8, label="tap %+d" % (i - half) if i in (half, half + args.spacing) else None)
    ax[0, 0].set_xlabel("symbol"); ax[0, 0].set_ylabel("Re(tap)"); ax[0, 0].legend(fontsize=8)
    ax[0, 0].set_title("LMS taps (last record)")
    for name in ("lms", "dfe"):
        e2 = np.abs(res[name]["e"])**2
        ax[0, 1].plot(ks, 10 * np.log10(np.convolve(e2, np.ones(32) / 32, mode="same") + 1e-9), lw=0.8, label=name)
    ax[0, 1].set_xlabel("symbol"); ax[0, 1].set_ylabel("error power (dB)"); ax[0, 1].legend()
    ax[0, 1].set_title("|e|^2, averaged over 32 symbols")
    f = np.fft.rfftfreq(2 * L, 1 / FS_ADC) / 1e6
    for name in ("fd_zf", "fd_mmse"):
        if name in res:
            ax[0, 2].plot(f, np.abs(res[name]["W"]), lw=0.8, label=name)
    ax[0, 2].set_xlim(4.5, 8); ax[0, 2].set_xlabel("frequency (MHz)"); ax[0, 2].set_ylabel("|W(f)|")
    ax[0, 2].set_title("the frequency-domain equalizers"); ax[0, 2].legend()
    pts = (("none", res["none"]["x"]), ("lms", res["lms"]["y"]), ("dfe", res["dfe"]["y"]))
    for a, (name, z) in zip(ax[1], pts):
        a.plot(z.real, z.imag, ".", ms=2)
        a.set_aspect("equal"); a.set_xlim(-2, 2); a.set_ylim(-2, 2)
        a.set_title("%s: %d errors in %d bits, MER %.1f dB" % (name, tot[name][0], tot[name][1], np.mean(tot[name][2])), fontsize=9)
    fig.suptitle("QPSK, %s" % desc); fig.tight_layout(); plt.show()


def parse_echo(s):
    p = [float(x) for x in s.split(":")]
    return (p + [0.0])[:3] if len(p) >= 2 else (p[0], 0.67, 0.0)


def defaults(D, spacing=2, taps=None, fb=None, mu=0.3, nlms=False, train=2, records=6,
             max_records=24, nsym=NSYM, train_all=False):
    """The equalizers' settings for an echo D symbols late, as the command line would
    set them: taps spanning 8 echo delays each side (the inverse of an echo is a series
    that dies away as a^k), and feedback taps spanning 3 (the echoes themselves)."""
    import types
    taps = taps or 2 * spacing * max(4, int(math.ceil(8 * D))) + 1
    fb = fb or max(2, int(math.ceil(3 * D)))
    return types.SimpleNamespace(spacing=spacing, taps=taps, fb=fb, mu=mu, nlms=nlms, train=train,
                                 records=records, max_records=max_records, nsym=nsym, train_all=train_all)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ports", nargs="*", help="one port: looped back; two: A plays, B records")
    ap.add_argument("--sim", action="store_true", help="use channel.py's model, not a board")
    ap.add_argument("--echo", type=parse_echo, help="DELAY:SIZE[:RATIO]: an echo DELAY symbols late, SIZE times the direct signal (RATIO: each further echo over the last)")
    ap.add_argument("--stub", type=float, default=0.0, help="a simulated open stub of this many metres on a T (echo.py)")
    ap.add_argument("--vf", type=float, default=echo.VF, help="--stub: velocity factor")
    ap.add_argument("--loss", type=float, default=echo.LOSS, help="--stub: dB per metre at 10 MHz")
    ap.add_argument("--ebn0", type=float, help="noise at the receiver: Eb/N0 in dB")
    ap.add_argument("--ber", help="bit error rate at Eb/N0 = LO:HI dB (1 dB steps)")
    ap.add_argument("--records", type=int, default=6, help="records per run (--ber: at least this many per point)")
    ap.add_argument("--max-records", type=int, default=24, help="--ber: at most this many per point (it stops at 100 LMS errors)")
    ap.add_argument("--train", type=int, default=2, help="of which the first this many are a training sequence")
    ap.add_argument("--train-all", action="store_true", help="never decision-directed: always told the symbols")
    ap.add_argument("--taps", type=int, help="feedforward taps (default: from the echo's delay)")
    ap.add_argument("--fb", type=int, help="the DFE's feedback taps (default: from the echo's delay)")
    ap.add_argument("--spacing", type=int, default=2, choices=(1, 2), help="taps per symbol")
    ap.add_argument("--mu", type=float, default=0.3, help="LMS step, in units of 1/(taps x power)")
    ap.add_argument("--nlms", action="store_true", help="normalized LMS")
    ap.add_argument("--nsym", type=int, default=NSYM, help="symbols per loop (2048: 6.25 Msymbol/s)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("-o", "--out", help="save the results (.npz)")
    ap.add_argument("--no-plot", action="store_true")
    args = ap.parse_args()
    D = args.echo[0] if args.echo else (2 * args.stub / (args.vf * echo.C)) * args.nsym * F_LOOP if args.stub else 0.5
    d = defaults(D, args.spacing, args.taps, args.fb)
    args.taps, args.fb = d.taps, d.fb
    play, record, desc = make_link(args)
    R = args.nsym * F_LOOP
    print("QPSK at %.4g Msymbol/s, %s; echo %.2f symbols late (%.0f ns); equalizer: %d taps, %d per symbol, "
          "%d feedback, mu %g%s, %d training records" % (R / 1e6, desc, D, D / R * 1e9, args.taps, args.spacing,
                                                         args.fb, args.mu, " (NLMS)" if args.nlms else "", args.train))
    H = sound_channel(play, record)
    q, _ = psk.make_frame(M, args.nsym)
    play(psk.transmit(q, M))
    rng = np.random.default_rng(args.seed + 1)
    if args.ber:
        lo, hi = (float(x) for x in args.ber.split(":"))
        rows = []
        shown = RECEIVERS[:-1]
        print("Eb/N0 (dB), then bit errors / bits for: " + ", ".join(shown) + "  (theory)")
        for eb in np.arange(lo, hi + 0.01, 1.0):
            tot, _, _ = run(args, play, record, q, H, eb, rng, min_errs=100)
            rows.append([eb] + [tot[k][0] / max(1, tot[k][1]) for k in shown])
            print("%5.1f  " % eb + "  ".join("%5d/%-6d" % (tot[k][0], tot[k][1]) for k in shown)
                  + "  (%.1e)" % psk.ber_theory(eb), flush=True)
        if args.out:
            np.savez(args.out, rows=np.array(rows), receivers=shown, desc=desc)
    else:
        tot, res, state = run(args, play, record, q, H, args.ebn0, rng)
        print("sync: frame starts at sample %d, phase %.0f deg" % (res["sync"]["t0"], np.degrees(res["sync"]["phi"])))
        for k in RECEIVERS:
            print("  %-32s %5d errors in %6d bits, MER %5.1f dB" % (LABELS[k] + ":", tot[k][0], tot[k][1], np.mean(tot[k][2])))
        if args.out:
            np.savez(args.out, desc=desc, **{k + "_" + f: v for k in RECEIVERS for f in ("errs", "nbits")
                                           for v in [tot[k][0 if f == "errs" else 1]]},
                     W_lms=res["lms"]["W"], e_lms=res["lms"]["e"], y_lms=res["lms"]["y"], x_none=res["none"]["x"],
                     ks=res["lms"]["ks"], W_zf=res["fd_zf"]["W"], W_mmse=res["fd_mmse"]["W"])
        if not args.no_plot:
            plot(res, tot, desc, args)
