#!/usr/bin/env python3
"""LoRa's chirp spread spectrum, scaled 25 times up to the board: symbols from one FFT.

    python3 lora.py                     # one board looped back (finds its port): an SF7 frame
    python3 lora.py PORT_A PORT_B       # board A plays, board B records
    python3 lora.py --sim               # no board: channel.py's model
    python3 lora.py --sf 9              # spreading factor 7..10 (frames with a preamble: 7, 8)
    python3 lora.py --snr -12           # noise at the transmitter: signal/noise in dB, in a band
                                        #   one chip rate wide (Semtech's definition)
    python3 lora.py --cfo 12            # the transmitter's carrier 12 steps (36.6 kHz) high:
                                        #   every bin moves, and the preamble sorts it out
    python3 lora.py --ber=-24:-4        # symbol and bit error rates against SNR, SF 7 to 10
    python3 lora.py -o lora.npz --no-plot

The board runs awgcap.sv (5.01).  LoRa sends 125 kchip/s; here, 3.125 Mchip/s, so that
a symbol fits a loop:

  chips    3.125 Mchip/s = B: 16 DAC samples, 8 ADC samples per chip, 1024 chips per loop
  symbol   the BASE CHIRP, a sweep from -B/2 to +B/2 over M = 2^SF chips, started at
           chip s and wrapped round: that cyclic shift s, 0 .. M - 1, is the symbol's
           value, SF bits (Gray-coded, so that a near miss costs one bit)
  SF       7, 8, 9, 10: symbols of 128 .. 1024 chips, 8, 4, 2, 1 of them per loop
  frame    (SF 7) two up-chirps, the PREAMBLE; two down-chirps, the start-of-frame
           delimiter (SFD); then four data symbols (SF 8: one, one and two).  Real
           LoRa: 8 preamble, 2 sync word, 2.25 down-chirps, then the payload, at
           125 kHz and SF 7 to 12.  SF 9 and 10 fill a loop with data alone.

RECEIVER (in Python, on the record)
  1. mix down (1, -j, -1, j, as the lock-in), low-pass to +-B/2, and keep one sample
     per chip: 1024 complex numbers per loop
  2. DECHIRP: multiply each symbol by the conjugate of the base chirp.  A chirp that
     started s chips late becomes a TONE at s B / M: the sweep is gone
  3. an M-point FFT: the biggest bin is s.  One FFT is M matched filters at once
  4. sync: a carrier offset of nu bins moves every bin by nu; a timing error of tau
     chips moves an up-chirp's bin by -tau and a down-chirp's by +tau (the delay-
     Doppler coupling of chirp.py).  The preamble lands at nu - tau and the SFD at
     nu + tau: the sum gives nu, the difference tau.  That is the whole reason for
     the down-chirps.

Why it reaches kilometres on milliwatts: see the page.  Briefly, each symbol is a
long constant-envelope pulse (energy, from a cheap saturated amplifier), the FFT is
an ideal non-coherent detector for it, and the chirp forgives a crystal that is
20 ppm off.  Nothing in it beats Shannon; it just wastes very little.
"""
import argparse
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import channel                                      # noqa: E402
from psk import find_port                          # noqa: E402

N, L = 16384, 8192                  # DAC samples per loop; ADC samples per loop
FS_DAC, FS_ADC = 50e6, 25e6
F_LOOP = FS_DAC / N
F_C = 6.25e6
SPC = 8                             # ADC samples per chip
B = FS_ADC / SPC                    # 3.125 Mchip/s
NCHIP = L // SPC                    # 1024 chips per loop
AMP = 100
# Semtech SX1276 datasheet, table 10: the demodulator's SNR (in the signal bandwidth)
SEMTECH = {7: -7.5, 8: -10.0, 9: -12.5, 10: -15.0, 11: -17.5, 12: -20.0}


# ---- symbols ----------------------------------------------------------------------
def base(M, rate=FS_DAC):
    """The base up-chirp for M = 2^SF chips, at `rate` samples per second: frequency
    -B/2 + B t / Ts over the symbol time Ts = M / B, as one complex envelope."""
    t = np.arange(round(M / B * rate)) / rate
    return np.exp(2j * np.pi * (-B * t / 2 + B * t**2 / (2 * M / B)))


def symbol(s, M):
    """Symbol s (0 .. M-1) at the DAC's rate: the base chirp started s chips in."""
    # ##########################################################################
    # ##  KEY LINE: the symbol is WHERE the sweep starts.  Shift the base chirp
    # ##  by s chips and wrap what falls off the end back to the start.
    # ##########################################################################
    return np.roll(base(M), -s * (N // NCHIP))


def gray(s):
    """Symbol value -> the bits it carries, as a number (Gray code: neighbouring
    values differ in one bit)."""
    return s ^ (s >> 1)


def ungray(g):
    s = 0
    while g:
        s ^= g
        g >>= 1
    return s


def frame(sf, data, preamble=2, sfd=2):
    """One loop of symbols: `preamble` up-chirps (value 0), `sfd` down-chirps, then
    the data symbols; the rest of the loop is filled with more data.  Returns the
    envelope and the symbol values that were sent (down-chirps marked -1)."""
    M = 1 << sf
    per_loop = NCHIP // M
    assert preamble + sfd + len(data) <= per_loop, "%d symbols per loop at SF %d" % (per_loop, sf)
    vals = [0] * preamble + [-1] * sfd + list(data)
    vals += list(np.random.default_rng(len(data)).integers(0, M, per_loop - len(vals)))
    env = np.concatenate([np.conj(base(M)) if v < 0 else symbol(v, M) for v in vals])
    return env, np.array(vals)


def transmit(env, snr=None, cfo_bins=0, rng=None):
    """DAC codes: the envelope on the carrier (cfo_bins steps of 3051.76 Hz off), with
    white noise over the ADC's band for signal/noise = snr dB in a band B wide."""
    u = np.arange(N)
    s = np.real(env * np.exp(2j * np.pi * (F_C + cfo_bins * F_LOOP) * u / FS_DAC))
    if snr is not None:
        n0 = np.mean(s**2) / (B * 10**(snr / 10))
        k = np.arange(N // 2 + 1)
        band = (k > 0) & (k * F_LOOP <= FS_ADC / 2)
        X = np.zeros(N // 2 + 1, complex)
        X[band] = np.random.default_rng(rng).standard_normal((band.sum(), 2)) @ [1, 1j]
        x = np.fft.irfft(X, N)
        s = s + x * np.sqrt(n0 * band.sum() * F_LOOP) / x.std()
    return 128 + AMP * s / np.abs(s).max()


# ---- receiver ---------------------------------------------------------------------
def chips(rec, tau=0.0, nu_hz=0.0):
    """Step 1: one loop of the record, mixed down, moved down by nu_hz, low-passed to
    +-B/2, and sampled once per chip starting tau samples in (any fraction).  Returns
    1024 complex numbers."""
    r = np.asarray(rec, float)[:L] - np.mean(rec)
    n = np.arange(L)
    z = 2 * r * np.exp(-2j * np.pi * (F_C + nu_hz) * n / FS_ADC)
    f = np.fft.fftfreq(L, 1 / FS_ADC)
    z = np.fft.ifft(np.fft.fft(z) * (np.abs(f) <= B / 2))
    return channel.cubic(z, tau + SPC * np.arange(NCHIP))


def dechirp(c, M):
    """Steps 2 and 3: for each symbol's M chips, multiply by the conjugate base
    chirp and FFT.  Returns |X| for each symbol, shape (symbols, M)."""
    ref = base(M, B)                                      # one sample per chip
    # ##########################################################################
    # ##  KEY LINE: dechirp.  Received chirp x conjugate chirp = a tone whose
    # ##  frequency is the shift s: the FFT's biggest bin is the symbol.
    # ##########################################################################
    return np.abs(np.fft.fft(c.reshape(-1, M) * np.conj(ref), axis=1))


def peak_bin(X):
    """The biggest bin of each row, to a fraction (a parabola through three points)."""
    k = np.argmax(X, axis=1)
    i = np.arange(len(X))
    a, b, c = X[i, (k - 1) % X.shape[1]], X[i, k], X[i, (k + 1) % X.shape[1]]
    return k + 0.5 * (a - c) / (a - 2 * b + c)


def sync(rec, sf, preamble=2, sfd=2, tau0=0.0):
    """Step 4: from the preamble's up-chirps and the SFD's down-chirps, the carrier
    offset nu (bins) and the timing tau (chips, from tau0 samples)."""
    M = 1 << sf
    c = chips(rec, tau0)
    up = dechirp(c[:preamble * M], M)
    down = np.abs(np.fft.fft(c[preamble * M:(preamble + sfd) * M].reshape(-1, M) * base(M, B), axis=1))
    # add the chirps' |X| first (LoRa sends 8, for noise), then find the one peak
    pu = peak_bin(up.sum(axis=0, keepdims=True))[0]; pd = peak_bin(down.sum(axis=0, keepdims=True))[0]
    pu = (pu + M / 2) % M - M / 2; pd = (pd + M / 2) % M - M / 2    # as signed offsets
    # ##########################################################################
    # ##  KEY LINE: up-chirps land at nu - tau, down-chirps at nu + tau.
    # ##########################################################################
    return (pu + pd) / 2, (pd - pu) / 2, up, down


def receive(rec, sf, tau, nu_bins=0.0, skip=0):
    """Symbols from one loop: tau in ADC samples, nu in bins of B / 2^SF.  Returns
    the symbol values found (after the first `skip` symbols) and the |X| rows."""
    M = 1 << sf
    c = chips(rec, tau, nu_bins * B / M)
    X = dechirp(c, M)[skip:]
    return np.argmax(X, axis=1), X


def ser_theory(M, es_n0_db):
    """Symbol error rate of M orthogonal signals, detected by their size (no phase):
    Pe = 1 - int_0^inf  x e^(-(x^2 + a^2)/2) I0(a x) (1 - e^(-x^2/2))^(M-1) dx,
    a^2 = 2 Es/N0.  (Proakis, Digital Communications, non-coherent M-FSK.)"""
    a = np.sqrt(2 * 10**(es_n0_db / 10))
    x = np.linspace(0, a + 12, 20001)
    z = a * x
    i0e = np.where(z < 600, np.i0(np.minimum(z, 600)) * np.exp(-np.minimum(z, 600)),
                   (1 + 1 / (8 * np.maximum(z, 1))) / np.sqrt(2 * np.pi * np.maximum(z, 1)))
    pdf = x * np.exp(-(x - a)**2 / 2) * i0e
    pc = np.trapz(pdf * np.exp((M - 1) * np.log(np.maximum(1 - np.exp(-x**2 / 2), 1e-300))), x)
    return max(1 - pc, 1e-12)


def bits_wrong(found, sent, sf):
    """Bit errors between two symbol lists, Gray-coded."""
    return sum(bin(gray(int(a)) ^ gray(int(b))).count("1") for a, b in zip(found, sent))


# ---- the board, or the model ------------------------------------------------------
def make_link(args):
    if args.sim:
        rng = np.random.default_rng(args.seed)
        st = {}
        def play(wave):
            st["wave"] = wave
        def record():
            return channel.channel(st["wave"], rng=rng)
        return play, record
    sys.path.insert(0, os.path.join(HERE, "..", "twoboard"))
    import awgcap
    ports = args.ports or [find_port()]
    return (lambda w: awgcap.upload(ports[0], w)), (lambda: awgcap.record(ports[-1]))


def find_timing(play, record, tau0=6.0):
    """Send a clean SF7 frame and read the loop's delay off its preamble and SFD."""
    env, vals = frame(7, [5, 77, 100, 127])
    play(transmit(env))
    nu, tau, _, _ = sync(record(), 7, tau0=tau0)
    return tau0 + tau * SPC, nu


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ports", nargs="*", help="one port: looped back; two: A plays, B records")
    ap.add_argument("--sim", action="store_true", help="use channel.py's model, not a board")
    ap.add_argument("--sf", type=int, default=7, help="spreading factor, 7..10")
    ap.add_argument("--snr", type=float, help="noise at the transmitter: signal/noise, dB, in B")
    ap.add_argument("--cfo", type=int, default=0, help="transmitter's carrier offset, steps of 3051.76 Hz")
    ap.add_argument("--ber", help="symbol/bit error rate at SNR = LO:HI dB (2 dB steps), SF 7..10")
    ap.add_argument("--records", type=int, default=40, help="--ber: at most this many uploads per point")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("-o", "--out", help="save the results (.npz)")
    ap.add_argument("--no-plot", action="store_true")
    args = ap.parse_args()
    play, record = make_link(args)
    M = 1 << args.sf
    per_loop = NCHIP // M
    print("LoRa at %.4g Mchip/s: SF %d, %d chips per symbol, %d symbols per loop, %.3g kbit/s;"
          " a bin is %.1f kHz" % (B / 1e6, args.sf, M, per_loop, args.sf * per_loop * F_LOOP / 1e3, B / M / 1e3))

    if args.ber:
        lo, hi = (float(x) for x in args.ber.split(":"))
        rng = np.random.default_rng(args.seed)
        tau, _ = find_timing(play, record)
        print("timing from a clean preamble: %.2f samples.  SNR (dB), SF: symbol errors / symbols,"
              " bit errors / bits, SER, theory" % tau)
        rows = []
        for sf in (7, 8, 9, 10):
            M = 1 << sf
            for snr in np.arange(lo, hi + 0.01, 2.0):
                se = ns = be = 0
                for i in range(args.records):
                    sent = rng.integers(0, M, NCHIP // M)
                    env = np.concatenate([symbol(int(s), M) for s in sent])
                    play(transmit(env, snr, rng=rng))
                    found, _ = receive(record(), sf, tau)
                    se += int(np.sum(found != sent)); ns += len(sent)
                    be += bits_wrong(found, sent, sf)
                    if se >= 100 and i >= 4:
                        break
                th = ser_theory(M, snr + 10 * np.log10(M))
                rows.append((snr, sf, se, ns, be, ns * sf, th))
                print("%6.1f  %2d  %5d / %5d  %5d / %6d   %.3f  %.3f" % (snr, sf, se, ns, be, ns * sf, se / ns, th), flush=True)
        if args.out:
            np.savez(args.out, rows=np.array(rows), tau=tau)
        if not args.no_plot:
            import matplotlib.pyplot as plt
            rows = np.array(rows)
            x = np.linspace(lo, hi, 100)
            for sf in (7, 8, 9, 10):
                r = rows[rows[:, 1] == sf]
                p = plt.semilogy(x, [ser_theory(1 << sf, v + 10 * np.log10(1 << sf)) for v in x], label="SF %d" % sf)
                ok = r[:, 2] > 0
                plt.semilogy(r[ok, 0], r[ok, 2] / r[ok, 3], "o", color=p[0].get_color())
                plt.axvline(SEMTECH[sf], color=p[0].get_color(), ls=":", lw=1)
            plt.ylim(1e-4, 1); plt.xlabel("SNR per chip (dB)"); plt.ylabel("symbol error rate")
            plt.grid(True, which="both"); plt.legend(); plt.title("dotted: Semtech's demodulation SNR"); plt.show()
        return

    if args.sf > 8:
        print("SF %d has no room for a preamble in a loop; the timing comes from an SF 7 frame" % args.sf)
        tau, _ = find_timing(play, record)
        data = list(np.random.default_rng(args.seed).integers(0, M, per_loop))
        env = np.concatenate([symbol(int(s), M) for s in data])
        vals = np.array(data); pre = sfd = 0
    else:
        pre, sfd = (2, 2) if args.sf == 7 else (1, 1)       # SF 8: 4 symbols per loop
        data = [5, 77, 100, 127][:per_loop - pre - sfd]
        env, vals = frame(args.sf, data, pre, sfd)
        tau = 6.0
    play(transmit(env, args.snr, args.cfo, rng=args.seed))
    rec = record()
    if pre:
        nu, dtau, up, down = sync(rec, args.sf, pre, sfd, tau0=tau)
        print("preamble's up-chirps at bin %+.2f, SFD's down-chirps at bin %+.2f" % (nu - dtau, nu + dtau))
        print("  so the carrier is off by %+.2f bins (%+.0f Hz; sent %+.0f) and the timing by %+.2f chips"
              " (%.2f samples)" % (nu, nu * B / M, args.cfo * F_LOOP, dtau, tau + dtau * SPC))
        tau += dtau * SPC
    else:
        nu = 0.0
    found, X = receive(rec, args.sf, tau, nu)
    sent = vals[pre + sfd:]
    got = found[pre + sfd:]
    print("sent  %s" % " ".join("%4d" % v for v in sent))
    print("found %s   (%d symbol errors, %d bit errors in %d bits)"
          % (" ".join("%4d" % v for v in got), np.sum(got != sent), bits_wrong(got, sent, args.sf), len(sent) * args.sf))
    if args.out:
        np.savez(args.out, rec=rec, X=X, vals=vals, found=found, tau=tau, nu=nu, sf=args.sf)
    if not args.no_plot:
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(12, 4))
        r = np.asarray(rec, float)[:L] - np.mean(rec)
        z = 2 * r * np.exp(-2j * np.pi * F_C * np.arange(L) / FS_ADC)
        ax[0].specgram(z, NFFT=128, Fs=FS_ADC / 1e6, noverlap=96, cmap="viridis")
        ax[0].set_ylim(-2.5, 2.5); ax[0].set_xlabel("time (us)"); ax[0].set_ylabel("frequency from 6.25 MHz (MHz)")
        ax[0].set_title("one loop, mixed down: the chirps")
        for i, row in enumerate(X):
            ax[1].plot(row / X.max() + i * 1.1, lw=0.8, label="symbol %d: bin %d" % (i, np.argmax(row)))
        ax[1].set_xlabel("FFT bin"); ax[1].set_ylabel("|X|, one trace per symbol"); ax[1].legend(fontsize=7)
        ax[1].set_title("dechirped: a tone per symbol"); ax[1].grid(True)
        fig.tight_layout(); plt.show()


if __name__ == "__main__":
    main()
