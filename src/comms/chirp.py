#!/usr/bin/env python3
"""Chirps, Zadoff-Chu sequences and GPS codes, compressed: ranging, and radar on a cable.

    python3 chirp.py                    # one board looped back (finds its port)
    python3 chirp.py PORT_A PORT_B      # board A plays, board B records
    python3 chirp.py --sim              # no board: channel.py's model
    python3 chirp.py --snr -20          # noise at the transmitter, 20 dB above the signal
                                        #   (power in a band B wide; the noise is white
                                        #   over the ADC's whole 0-12.5 MHz)
    python3 chirp.py --cfo 1            # the transmitter's carrier 1 step (3052 Hz) high:
                                        #   what a Doppler shift does to each waveform
    python3 chirp.py --bw 10e6          # the chirp and the pulse sweep 10 MHz (the codes
                                        #   keep their chip rate: it's set by their length)
    python3 chirp.py --sim --stub 30    # radar: a T at the DAC with a 30 m open stub
                                        #   (the model has no T; with a board, fit one)
    python3 chirp.py --stubs            # print stub lengths for 1, 2, 5, 10 range cells
    python3 chirp.py -o chirp.npz --no-plot

The board runs awgcap.sv (5.01): a 16384-sample waveform at 50 MS/s, over and over
(one loop T = 327.68 us), recorded at 25 MS/s.  Five waveforms, each one loop long,
each a complex envelope on the 6.25 MHz carrier (I on cos, Q on -sin, as psk.py):

  pulse   one square pulse 1/B long, then nothing: the simplest radar
  chirp   a linear sweep of B over the whole loop: BT = 1023 (--bw changes B)
  zc      a Zadoff-Chu sequence, 1021 chips held at 3.116 Mchip/s, root u = 1:
              x[n] = exp(-j pi u n (n + 1) / N)        (N odd, u coprime with N)
          u = 1 is a chirp sampled once per chip: its phase is a parabola, so its
          frequency, the phase's slope, ramps -(n + 1/2) / N cycles per chip, one
          sweep of the chip rate per sequence (chirp.py --sim prints the check)
  m       GPS's G1 register (1.07): an m-sequence, 1023 chips of +-1 at 3.122 Mchip/s
  gold    GPS's C/A code for satellite 1 (6.06): G1 xor G2, the same chip rate

The receiver mixes down (1, -j, -1, j, as the lock-in), then correlates one loop with
the waveform it sent at every lag at once (FFTs, as 6.06's acquisition): the MATCHED
FILTER.  A long waveform collapses into a peak as narrow as 1/B: PULSE COMPRESSION.
The peak's position is the cable's delay, to a fraction of a sample; its shape is
the waveform's autocorrelation; what's left beside it are the sidelobes.

Doppler: a transmitter whose carrier is df high looks, to the correlator, like a
different waveform.  The code decorrelates (its peak falls as sinc(df T), gone at
df = 1/T = 3052 Hz); the chirp's peak just slides, by df T / B (one chip per step
here): the DELAY-DOPPLER COUPLING, a bug for a radar, a feature for LoRa (lora.py).
"""
import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import channel                                      # noqa: E402
from psk import g1, find_port                      # noqa: E402
from cdma import ca_code                           # noqa: E402
from eye import square                             # noqa: E402

N, L = 16384, 8192                  # DAC samples per loop; ADC samples per loop
FS_DAC, FS_ADC = 50e6, 25e6
F_LOOP = FS_DAC / N                 # 3051.76 Hz: one cycle per loop
T = N / FS_DAC                      # one loop, 327.68 us
F_C = 6.25e6
CHIPS = 1023                        # GPS's code: one period per loop, 3.122 Mchip/s
N_ZC = 1021                         # prime, so every pair of roots behaves alike
B0 = CHIPS * F_LOOP                 # the codes' chip rate, and the default sweep
AMP = 100                           # DAC codes from mid-scale
V_CABLE = 0.695 * 299792458.0       # RG-316's velocity factor; RG-58 is 0.66
KINDS = ("pulse", "chirp", "zc", "m", "gold")


# ---- the waveforms: complex envelopes, 16384 points on the DAC's grid -------------
def zc(n, u=1):
    """Zadoff-Chu sequence, length n (odd), root u (coprime with n): n unit-size
    complex numbers whose cyclic autocorrelation is exactly zero at every lag but 0."""
    k = np.arange(n)
    # ##########################################################################
    # ##  KEY LINE: a quadratic phase.  Its slope, u k / n cycles per chip, is a
    # ##  frequency that ramps linearly: a chirp, sampled.  u = 2 ramps twice as
    # ##  fast (two sweeps), u = 7 seven times: a mess to the eye, but each root
    # ##  still correlates with every other at only 1 / sqrt(n).
    # ##########################################################################
    return np.exp(-1j * np.pi * u * k * (k + 1) / n)


def held(seq):
    """A sequence of (complex) chips, each held for one chip time, filling the loop."""
    seq = np.asarray(seq, complex)
    return square(seq.real) + 1j * square(seq.imag)


def envelope(kind, bw=B0, u=1, width=1.0):
    """One loop's complex envelope for each waveform.  Peak size 1.  `width`: the
    pulse's length in units of 1/B (a long pulse has energy; a short one, resolution)."""
    t = np.arange(N) / FS_DAC
    if kind == "pulse":
        return (t < width / bw).astype(complex)
    if kind == "chirp":
        # ######################################################################
        # ##  KEY LINE: the linear chirp.  Frequency -B/2 + B t / T, so phase
        # ##  2 pi (-B t / 2 + B t^2 / 2T): a parabola in time.
        # ######################################################################
        return np.exp(2j * np.pi * (-bw * t / 2 + bw * t**2 / (2 * T)))
    if kind == "zc":
        return held(zc(N_ZC, u))
    if kind == "m":
        return held(1.0 - 2 * g1(CHIPS))
    if kind == "gold":
        return held(1.0 - 2 * ca_code(1))
    raise ValueError(kind)


def chip_rate(kind, bw=B0):
    """The bandwidth each waveform fills, Hz."""
    return {"zc": N_ZC * F_LOOP, "m": B0, "gold": B0}.get(kind, bw)


def transmit(env, snr=None, cfo_bins=0, rng=None, bw=B0, power=None):
    """DAC codes for one loop: the envelope on the carrier, with white noise over
    the ADC's band at `snr` dB (signal power over noise power in a band bw wide).
    `power`: the signal power the SNR refers to; by default this waveform's mean
    power.  A radar's pulse is judged by its PEAK power: give 0.5 (a unit envelope)."""
    u = np.arange(N)
    fc = F_C + cfo_bins * F_LOOP
    s = np.real(env * np.exp(2j * np.pi * fc * u / FS_DAC))
    if snr is not None:
        p = np.mean(s**2) if power is None else power
        s = s + white_noise(p / (bw * 10**(snr / 10)), rng)
    return 128 + AMP * s / np.abs(s).max()


def white_noise(n0, rng=None):
    """One loop of white Gaussian noise, n0 (power per hertz, one-sided) from just
    above 0 to 12.5 MHz: what a receiver's front end adds, made at the transmitter.
    Periodic in the loop, like everything the DAC plays."""
    k = np.arange(N // 2 + 1)
    band = (k > 0) & (k * F_LOOP <= FS_ADC / 2)
    X = np.zeros(N // 2 + 1, complex)
    X[band] = np.random.default_rng(rng).standard_normal((band.sum(), 2)) @ [1, 1j]
    x = np.fft.irfft(X, N)
    return x * np.sqrt(n0 * band.sum() * F_LOOP) / x.std()


# ---- the receiver -----------------------------------------------------------------
def mixdown(rec):
    """Both loops of a record, mixed down to complex baseband and averaged: 8192
    samples at 25 MS/s.  Mixing a real signal makes a second copy at -2 x 6.25 MHz,
    the IMAGE, which lands at the band's far edge (+-12.5 MHz); a brick-wall low-pass
    at +-6.25 MHz, half-way, removes it exactly (the point of a carrier at fs / 4)."""
    r = np.asarray(rec, float) - np.mean(rec)
    z = 2 * r * np.exp(-2j * np.pi * F_C * np.arange(len(r)) / FS_ADC)
    z = (z[:L] + z[L:2 * L]) / 2 if len(z) >= 2 * L else z[:L]
    f = np.fft.fftfreq(L, 1 / FS_ADC)
    return np.fft.ifft(np.fft.fft(z) * (np.abs(f) < FS_ADC / 4))


def reference(env):
    """The envelope as the receiver sees it: through the same +-6.25 MHz band, at the
    ADC's rate (every second DAC sample)."""
    return bandlimit(env, FS_ADC / 2)[::2]


def compress(z, ref, window=None):
    """Correlate one loop z with the reference at every lag at once.  Returns the
    complex correlation against lag in samples (lag k at index k, cyclic), scaled
    so that a copy of the reference of amplitude A gives A at its lag (the ADC
    sees 0.776 x 100 = 77.6 codes for a unit envelope at 100 DAC codes)."""
    w = ref if window is None else ref * window
    # ##########################################################################
    # ##  KEY LINE: the matched filter, for every delay at once.  Multiply the
    # ##  spectra, conjugating the reference's, and transform back: a long
    # ##  waveform collapses into one peak as narrow as 1 / bandwidth.
    # ##########################################################################
    return np.fft.ifft(np.fft.fft(z) * np.conj(np.fft.fft(w))) / np.vdot(w, ref).real


def delay_of(r, up=16):
    """Where the peak of |r| is, to a fraction of a sample: upsample the correlation
    (zero-pad its spectrum) by `up`, then put a parabola through the three points
    around the highest.  Returns (delay in samples, the peak's complex value)."""
    R = np.fft.fftshift(np.fft.fft(r))
    fine = np.fft.ifft(np.fft.ifftshift(np.concatenate(
        [np.zeros((up - 1) * L // 2), R, np.zeros((up - 1) * L // 2)]))) * up
    p = np.abs(fine)**2
    k = int(np.argmax(p))
    a, b, c = p[k - 1], p[k], p[(k + 1) % len(p)]
    frac = 0.5 * (a - c) / (a - 2 * b + c)
    d = (k + frac) / up
    return (d + L / 2) % L - L / 2, fine[k]


def width_3db(r, up=16):
    """The main lobe's full width at -3 dB (power), in samples."""
    R = np.fft.fftshift(np.fft.fft(r))
    fine = np.abs(np.fft.ifft(np.fft.ifftshift(np.concatenate(
        [np.zeros((up - 1) * L // 2), R, np.zeros((up - 1) * L // 2)])))) * up
    k = int(np.argmax(fine)); half = fine[k] / np.sqrt(2)
    fine = np.roll(fine, len(fine) // 2 - k)                 # peak in the middle
    k = len(fine) // 2
    lo = k
    while fine[lo - 1] > half:
        lo -= 1
    hi = k
    while fine[hi + 1] > half:
        hi += 1
    return (hi - lo + (fine[lo] - half) / (fine[lo] - fine[lo - 1])
            + (fine[hi] - half) / (fine[hi] - fine[hi + 1])) / up


def sidelobes(r, bw):
    """The highest |r| (dB) outside the main lobe (|lag| > 1 / B, the first null of
    a chirp's sinc and the foot of a code's triangle)."""
    lag = (np.arange(L) + L / 2) % L - L / 2
    k = int(np.argmax(np.abs(r)))
    out = np.abs((lag - lag[k] + L / 2) % L - L / 2) > 1.02 * FS_ADC / bw
    return 20 * np.log10(np.abs(r[out]).max() / np.abs(r[k]))


def papr(env):
    """Peak-to-average power ratio of an envelope, dB."""
    p = np.abs(env)**2
    return 10 * np.log10(p.max() / p.mean())


def bandlimit(env, bw):
    """The envelope through a brick-wall filter |f| <= bw / 2: what a channel exactly
    bw wide would pass."""
    f = np.fft.fftfreq(len(env), 1 / FS_DAC)
    return np.fft.ifft(np.fft.fft(env) * (np.abs(f) <= bw / 2))


def rms_bandwidth(ref):
    """The rms width of the reference's spectrum about its centroid, Hz: the number
    in the Cramer-Rao bound,  sigma_tau = 1 / (2 pi B_rms sqrt(2 E / N0))."""
    S = np.abs(np.fft.fft(ref))**2
    f = np.fft.fftfreq(L, 1 / FS_ADC)
    f0 = np.sum(f * S) / S.sum()
    return np.sqrt(np.sum((f - f0)**2 * S) / S.sum())


def crb(bw_rms, snr_db, bw):
    """The Cramer-Rao bound on a delay estimate, seconds, for noise white at
    N0 = signal power / (bw 10^(snr/10)) and one loop's integration: E/N0 = snr B T."""
    e_n0 = 10**(snr_db / 10) * bw * T
    return 1 / (2 * np.pi * bw_rms * np.sqrt(2 * e_n0))


def doppler_cut(z, ref, dfs):
    """The ambiguity function along the Doppler axis: shift the record by each df
    (multiply by e^(j 2 pi df t), what a mixer would do) and correlate.  Returns the
    peak's height (relative to df = 0) and its delay (samples) at each df."""
    n = np.arange(L)
    h, d = [], []
    for df in dfs:
        r = compress(z * np.exp(2j * np.pi * df * n / FS_ADC), ref)
        delay, pk = delay_of(r)
        h.append(abs(pk)); d.append(delay)
    h = np.array(h)
    return h / h[np.argmin(np.abs(dfs))], np.array(d)


# ---- radar on a cable -------------------------------------------------------------
def stub_echo(env, length, gamma=0.67, v=V_CABLE, bounces=3):
    """What a T at the DAC with an open stub does to an envelope (for --sim; a real
    T does it to the real signal): the direct signal, plus an echo delayed by the
    round trip 2 L / v with size `gamma`, plus the echo's echoes, each another
    round trip later and -1/3 the size (the T's junction, 25 ohms, reflects -1/3)."""
    f = np.fft.fftfreq(N, 1 / FS_DAC)
    E = np.fft.fft(env)
    out = np.array(E)
    for k in range(1, bounces + 1):
        out += gamma * (-1 / 3)**(k - 1) * E * np.exp(-2j * np.pi * f * k * 2 * length / v)
    return np.fft.ifft(out)


def cell(bw, v=V_CABLE):
    """One range cell: a round trip of 1 / B, so a stub v / (2 B) long."""
    return v / (2 * bw)


# ---- the board, or the model ------------------------------------------------------
def make_link(args):
    """play(wave), record(): the board(s), or channel.py."""
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


def run(kind, play, record, bw=B0, snr=None, cfo_bins=0, stub=None, rng=None, u=1,
        width=1.0, power=None):
    """Play one waveform, record it, compress it.  Returns a dict."""
    env = envelope(kind, bw, u, width)
    if stub:
        env = stub_echo(env, stub)
    b = chip_rate(kind, bw)
    play(transmit(env, snr, cfo_bins, rng, b, power))
    rec = record()
    z = mixdown(rec)
    ref = reference(envelope(kind, bw, u, width))
    r = compress(z, ref)
    delay, pk = delay_of(r)
    return dict(kind=kind, bw=b, env=env, rec=rec, z=z, ref=ref, r=r, delay=delay,
                peak=pk, width=width_3db(r), sidelobe=sidelobes(r, b))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ports", nargs="*", help="one port: looped back; two: A plays, B records")
    ap.add_argument("--sim", action="store_true", help="use channel.py's model, not a board")
    ap.add_argument("--snr", type=float, help="noise at the transmitter: signal/noise in dB, in a band B wide")
    ap.add_argument("--cfo", type=int, default=0, help="transmitter's carrier offset, steps of 3051.76 Hz")
    ap.add_argument("--bw", type=float, default=B0, help="the chirp's and the pulse's bandwidth, Hz")
    ap.add_argument("--stub", type=float, help="--sim: an open stub this many metres long on a T")
    ap.add_argument("--stubs", action="store_true", help="print stub lengths per range cell and exit")
    ap.add_argument("--kinds", default=",".join(KINDS), help="which waveforms")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("-o", "--out", help="save the results (.npz)")
    ap.add_argument("--no-plot", action="store_true")
    args = ap.parse_args()

    if args.stubs:
        print("one range cell = a round trip of 1/B = a stub v/2B long (v = 0.695 c, RG-316):")
        print("   B (MHz)   cell (m)   1, 2, 5, 10 cells (m)       RG-58 (0.66 c): 1 cell")
        for bw in (2e6, B0, 10e6, 12e6):
            c = cell(bw)
            print("  %6.2f   %8.1f   %s   %8.1f" % (bw / 1e6, c, "  ".join("%6.1f" % (k * c) for k in (1, 2, 5, 10)),
                                                    cell(bw, 0.66 * 299792458)))
        return

    # A chirp is a waveform whose phase is a parabola: check Zadoff-Chu's.
    d2 = np.diff(np.angle(zc(N_ZC, 1)), 2)
    d2 = (d2 + np.pi) % (2 * np.pi) - np.pi
    print("zc(%d, 1): the phase's second difference is %.6f rad at every chip (spread %.0e):"
          " -2 pi / %d, a parabola, so its frequency ramps: a chirp sampled once per chip"
          % (N_ZC, d2.mean(), d2.std(), N_ZC))

    play, record = make_link(args)
    kinds = args.kinds.split(",")
    print("B = %.3f MHz (%s), T = %.2f us, BT = %.0f;  SNR %s, carrier %+.0f Hz%s"
          % (args.bw / 1e6, "chirp and pulse" if args.bw != B0 else "all", T * 1e6, args.bw * T,
             "none added" if args.snr is None else "%.0f dB" % args.snr, args.cfo * F_LOOP,
             "; stub %.1f m: echo %.1f ns = %.2f samples = %.1f cells" %
             (args.stub, 2 * args.stub / V_CABLE * 1e9, 2 * args.stub / V_CABLE * FS_ADC,
              2 * args.stub / V_CABLE * args.bw) if args.stub else ""))
    print("          -3 dB width   sidelobe   B_rms    PAPR (dB)       delay   Doppler at 1 step: peak, slide")
    print("          ns   x(1/B)        dB     MHz   ideal  in B      samples")
    out = {}
    for kind in kinds:
        x = run(kind, play, record, args.bw, args.snr, args.cfo, args.stub, rng=args.seed)
        env = envelope(kind, args.bw)
        h, d = doppler_cut(x["z"], x["ref"], np.array([0.0, F_LOOP]))
        print("%-6s %7.1f  %5.2f   %7.1f   %6.2f   %5.1f  %5.1f   %8.3f    %5.2f  %s"
              % (kind, x["width"] / FS_ADC * 1e9, x["width"] / FS_ADC * x["bw"], x["sidelobe"],
                 rms_bandwidth(x["ref"]) / 1e6, papr(env), papr(bandlimit(env, x["bw"])),
                 x["delay"], h[1], "%+6.2f" % (d[1] - d[0]) if h[1] > 0.5 else "  lost"))
        out[kind] = x
    if args.out:
        np.savez(args.out, **{"%s_%s" % (k, f): v[f] for k, v in out.items()
                              for f in ("rec", "r", "delay", "bw")}, kinds=kinds)
    if not args.no_plot:
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
        lag = ((np.arange(L) + L / 2) % L - L / 2) / FS_ADC * 1e6
        o = np.argsort(lag)
        for kind, x in out.items():
            db = 20 * np.log10(np.abs(x["r"]) / np.abs(x["peak"]) + 1e-6)
            ax[0].plot(lag[o], db[o], lw=0.7, label=kind)
            ax[1].plot(lag[o], db[o], lw=1, label="%s: %.2f samples" % (kind, x["delay"]))
        ax[0].set_xlim(-T / 2 * 1e6, T / 2 * 1e6); ax[1].set_xlim(-2, 4)
        for a in ax:
            a.set_xlabel("delay (us)"); a.set_ylabel("matched-filter output (dB)")
            a.set_ylim(-70, 5); a.grid(True); a.legend()
        ax[0].set_title("the whole loop"); ax[1].set_title("around the peak")
        fig.tight_layout(); plt.show()


if __name__ == "__main__":
    main()
