#!/usr/bin/env python3
"""Eye diagrams: square and root-raised-cosine pulses through the cable, faster and faster.

    python3 eye.py                      # one board looped back (finds its port)
    python3 eye.py PORT_A PORT_B        # board A plays, board B records
    python3 eye.py --sim                # no board: channel.py's model
    python3 eye.py --sim --corner 5e6   # ... with a 5 MHz low-pass in the cable
    python3 eye.py --noise 0.5          # add noise at the transmitter (rms, relative
                                        #   to the signal), to see the matched filter work
    python3 eye.py -o eye.npz --no-plot

The board runs awgcap.sv (5.01).  Each waveform is BPSK at BASEBAND, with no carrier:
the DAC's voltage is +1 or -1 (times 100 codes, about mid-scale) for each bit, the
bits from GPS's G1 register (1.07).  Two pulse shapes:

  square   the obvious one: hold the level for the whole symbol
  rrc      root-raised cosine, roll-off 0.35, as psk.py sends

and for each, the eye diagram of what the ADC records, raw and after the matched
filter (for square pulses, the matched filter averages over one symbol: "integrate
and dump"; for rrc, it is the same rrc again).

Equivalent-time sampling: each loop holds an ODD number of symbols (255, 511, ...,
4095), so the ADC's 8192 samples per loop land at 8192 different places within a
symbol, and folding them at the symbol period draws the whole eye, the trick of a
sampling oscilloscope (1.07).  Even at 12.5 Mbaud, two samples per symbol, the eye
is drawn with 8192 points.
"""
import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import channel                                      # noqa: E402
from psk import g1, rrc, find_port                 # noqa: E402

N, L = 16384, 8192                  # DAC samples per loop; ADC samples per loop
FS_DAC, FS_ADC = 50e6, 25e6
RATES = (255, 511, 1023, 2047, 4095)    # symbols per loop: 0.78 ... 12.5 Mbaud
AMP = 100


def square(a, shift=0.0):
    """Square pulses at the DAC: levels a[0..n-1], each held for 16384/n DAC samples,
    starting `shift` DAC samples into the loop (any fraction), over and over."""
    n = len(a)
    T = N / n                                               # DAC samples per symbol
    cum = np.concatenate([[0], np.cumsum(a)]) * T           # level integrated up to each edge
    def integral(x):                                        # of the levels, from `shift` to x
        loops, x = np.divmod(x - shift, N)
        k = np.minimum(np.floor(x / T).astype(int), n - 1)
        return loops * cum[-1] + cum[k] + a[k] * (x - k * T)
    u = np.arange(N, dtype=float)
    # ##########################################################################
    # ##  KEY LINE: each DAC sample takes the average of the levels over its
    # ##  20 ns, so an edge that falls between two DAC samples gets an
    # ##  in-between value, in the right proportion.
    # ##########################################################################
    return integral(u + 1) - integral(u)


def waveform(nsym, pulse, noise=0.0, rng=None):
    """One loop of baseband BPSK: 16384 DAC codes."""
    a = 1 - 2 * g1(nsym)                            # bits 0, 1 -> +1, -1
    if pulse == "square":
        s = square(a)
    else:
        u = np.arange(N)
        t = u * nsym / N                                        # in symbols
        k0 = np.floor(t).astype(int)
        s = np.zeros(N)
        for j in range(-8, 9):
            k = k0 + j
            s += a[k % nsym] * rrc(t - k)
    s = s / np.abs(s).max()
    if noise:
        s = s + noise * np.std(s) * np.random.default_rng(rng).standard_normal(N)
    return 128 + AMP * s / max(1.0, np.abs(s).max())


def matched(x, nsym, pulse):
    """The matched filter for one loop of samples.  The loop repeats, so filter in the
    frequency domain: multiply the spectrum by the pulse's own spectrum (it is real
    and even, so that is also its complex conjugate)."""
    R = nsym / L                                    # symbols per sample
    f = np.fft.fftfreq(L)                           # cycles per sample
    if pulse == "square":
        # ######################################################################
        # ##  KEY LINE: a square pulse's spectrum is sinc(f / symbol rate), so
        # ##  this is "average over one symbol" (integrate and dump), done for
        # ##  every possible sampling instant at once.
        # ######################################################################
        H = np.sinc(f / R)
    else:
        m = np.arange(-L // 2, L // 2)
        h = rrc(m * R) * (np.abs(m * R) <= 8)
        H = np.real(np.fft.fft(np.fft.ifftshift(h)))
    return np.real(np.fft.ifft(np.fft.fft(x) * H / H[0]))


def fold(x, nsym):
    """Equivalent time: the place within its symbol of every sample, in symbols, for
    one loop of samples, shifted so that the eye's opening is centred on 0."""
    n = np.arange(L)
    # ##########################################################################
    # ##  KEY LINE: sample n is (n x nsym / 8192) symbols after the loop start,
    # ##  and nsym is odd, so these fractions are all different: 8192 places in
    # ##  one symbol.
    # ##########################################################################
    ph = (n * nsym / L) % 1.0
    c = np.arange(128) / 128
    op = np.array([opening((ph - ci + 0.5) % 1.0 - 0.5, x) for ci in c])
    # the middle of the longest stretch of (nearly) the widest opening
    good = np.concatenate([op, op]) >= op.max() - 0.02
    best, run, start = 0, 0, 0
    for i, g in enumerate(good):
        run = run + 1 if g else 0
        if run > best and run <= 128:
            best, start = run, i - run + 1
    centre = c[(start + best // 2) % 128]
    return (ph - centre + 0.5) % 1.0 - 0.5


def opening(ph, x, width=0.02):
    """How open the eye is at its centre: (lowest +1 - highest -1) / (mean +1 - mean -1).
    1 = wide open; 0 or less = shut."""
    c = np.abs(ph) < width
    up, dn = x[c & (x > 0)], x[c & (x < 0)]
    if len(up) == 0 or len(dn) == 0:
        return -1.0
    return (up.min() - dn.max()) / (up.mean() - dn.mean())


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ports", nargs="*", help="one port: looped back; two: A plays, B records")
    ap.add_argument("--sim", action="store_true", help="use channel.py's model, not a board")
    ap.add_argument("--corner", type=float, default=40e6, help="--sim: the cable's low-pass, Hz")
    ap.add_argument("--noise", type=float, default=0.0, help="noise at the transmitter, rms relative to the signal")
    ap.add_argument("--rates", default=",".join(map(str, RATES)), help="symbols per loop (odd)")
    ap.add_argument("-o", "--out", help="save the results (.npz)")
    ap.add_argument("--no-plot", action="store_true")
    args = ap.parse_args()
    rates = [int(x) for x in args.rates.split(",")]
    if args.sim:
        rng = np.random.default_rng(1)
        play_record = lambda w: channel.channel(w, corner=args.corner, rng=rng)
    else:
        sys.path.insert(0, os.path.join(HERE, "..", "twoboard"))
        import awgcap
        ports = args.ports or [find_port()]
        def play_record(w):
            awgcap.upload(ports[0], w)
            return awgcap.record(ports[-1])
    out = {}
    print("eye opening (1 = wide open, 0 or less = shut)")
    print("  Mbaud    square raw  square matched    rrc raw  rrc matched")
    for nsym in rates:
        row = []
        for pulse in ("square", "rrc"):
            rec = play_record(waveform(nsym, pulse, args.noise, rng=nsym))
            x = rec[:L] - rec.mean()                        # one loop
            x = x / np.median(np.abs(x))
            for name, y in (("raw", x), ("matched", matched(x, nsym, pulse))):
                y = y / np.median(np.abs(y))
                ph = fold(y, nsym)
                out["%s_%s_%d" % (pulse, name, nsym)] = np.array([ph, y])
                row.append(opening(ph, y))
        print("%7.3f   %10.2f  %14.2f  %9.2f  %11.2f" % ((nsym * FS_DAC / N / 1e6,) + tuple(row)))
    if args.out:
        np.savez(args.out, rates=rates, **out)
    if not args.no_plot:
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(len(rates), 4, figsize=(12, 2.2 * len(rates)), sharex=True, sharey=True)
        ax = np.atleast_2d(ax)
        for i, nsym in enumerate(rates):
            for j, key in enumerate(("square_raw", "square_matched", "rrc_raw", "rrc_matched")):
                ph, y = out["%s_%d" % (key, nsym)]
                for shift in (-1, 0, 1):                     # draw two symbol periods
                    ax[i, j].plot(ph + shift, y, ".", markersize=0.6, color="C%d" % (j // 2))
                ax[i, j].set_xlim(-1, 1); ax[i, j].set_ylim(-2, 2); ax[i, j].grid(True)
                if i == 0:
                    ax[i, j].set_title(key.replace("_", ", "))
            ax[i, 0].set_ylabel("%.2f Mbaud" % (nsym * FS_DAC / N / 1e6))
        for a in ax[-1]:
            a.set_xlabel("time (symbols)")
        fig.tight_layout()
        plt.show()


if __name__ == "__main__":
    main()
