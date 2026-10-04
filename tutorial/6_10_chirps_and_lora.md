<!-- nav -->
[← 6.09 Error-correcting codes](6_09_error_correcting_codes.md#609-error-correcting-codes) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)** &emsp;&emsp;&emsp; [6.11 The modem in the FPGA →](6_11_the_modem_in_the_fpga.md#611-the-modem-in-the-fpga)

# 6.10 Chirps, Zadoff–Chu and LoRa: ranging, and radar on a cable

![Five waveforms of the same bandwidth through the cable: ten chips of each; their recorded spectra; each one's matched-filter output over a whole loop with its sidelobe level; the peaks close up, with a Hamming-windowed chirp dashed; what a frequency offset does to each (the codes' peaks collapse at 1/T, the chirps' slide); and all five with noise 15 dB above the signal, where the long waveforms show the cable's delay and the single pulse shows nothing](img/comms_compression.png)

A radar, a GPS receiver and a LoRa radio all do one thing: send a long
waveform the receiver knows, and correlate what comes back with it at every
delay. That correlation is the matched filter of
[6.01](6_01_eye_diagrams.md#601-eye-diagrams-and-pulse-shaping), and the
whole of [6.06](6_06_spread_spectrum.md#606-spread-spectrum-the-gps-way)'s
acquisition was it. This page asks what the waveform should *be*. GPS chose
a binary code in 1973 because a code is one pin and an XOR. Radar chose the
[chirp](https://en.wikipedia.org/wiki/Chirp) in 1960 because a chirp is what a swept oscillator does. LTE, 5G and
the author's drone chose Zadoff–Chu sequences, which turn out to be chirps
in disguise. Once your transmitter is a DAC rather than a pin, the choice is
open, and the page measures it. Everything here is laptop Python driving
`awgcap.sv` over the [UART](https://en.wikipedia.org/wiki/Universal_asynchronous_receiver-transmitter), exactly as
[6.02](6_02_psk_and_qpsk.md#602-psk-and-qpsk-finding-the-clock-and-the-carrier)
did; nothing new goes into the FPGA.

## Five waveforms, one receiver

`chirp.py` plays five waveforms of the same bandwidth *B* = 3.12 MHz on the
6.25 MHz carrier, each one loop (*T* = 327.68 µs) long, and correlates the
record with what it sent at every lag:

- **pulse**: one square pulse 1/*B* = 320 ns long, then silence. The simplest
  radar, and the control.
- **chirp**: a linear sweep of *B* over the whole loop. *BT* = 1023.
- **zc**: a Zadoff–Chu sequence of *N* = 1021 chips, root *u* = 1, each chip
  held for 1/*B*.
- **m**: GPS's G1 register from
  [1.07](1_07_closing_the_loop.md#107-closing-the-loop-the-dac-talks-to-the-adc),
  1023 chips of ±1 at *B* chips per second.
- **gold**: GPS's [C/A code](https://en.wikipedia.org/wiki/GPS_signals#Coarse/Acquisition_code) for satellite 1 from
  [6.06](6_06_spread_spectrum.md#606-spread-spectrum-the-gps-way), the same
  chip rate.

<details>
<summary>The whole file: <code>chirp.py</code></summary>

<!-- file: src/comms/chirp.py -->
```python
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
```

</details>

<!-- CHIRP_HW -->
```console
$ cd src/comms
$ python3 chirp.py --no-plot                  # one board looped back
zc(1021, 1): the phase's second difference is -0.006154 rad at every chip (spread 3e-13): -2 pi / 1021, a parabola, so its frequency ramps: a chirp sampled once per chip
B = 3.122 MHz (all), T = 327.68 us, BT = 1023;  SNR none added, carrier +0 Hz
          -3 dB width   sidelobe   B_rms    PAPR (dB)       delay   Doppler at 1 step: peak, slide
          ns   x(1/B)        dB     MHz   ideal  in B      samples
pulse    211.6   0.66     -33.0     1.37    29.8   30.0      5.445     1.00   -0.00
chirp    284.0   0.89     -13.2     0.90     0.0    5.0      5.465     1.00   -8.01
zc       206.6   0.64     -35.8     1.43     0.1    1.3      5.445     1.00   +8.02
m        206.2   0.64     -40.7     1.43     0.1    6.8      5.456     0.04    lost
gold     206.2   0.64     -23.1     1.43     0.1    7.0      5.455     0.08    lost
```

Read the columns left to right and you have the page. The **width** of the
peak is about 1/*B* for all five, whatever their length. The **sidelobes**
are what is left beside the peak: the chirp's −13 dB is its famous flaw, the
[m-sequence](https://en.wikipedia.org/wiki/Maximum_length_sequence)'s −41 dB and Zadoff–Chu's −36 dB are what their exact algebra
(−60 dB and −∞) survives as through real converters, and the Gold code's −23
dB is the price of belonging to a family. ***B*<sub>rms</sub>** is the spectrum's
rms width, which sets how well the peak can be timed. **PAPR** is the
peak-to-average power ratio, raw and after a filter *B* wide: what the
amplifier sees. The **delay** is the cable's, to a hundredth of a sample,
and every waveform finds the same 5.45 samples, 218 ns. (The step of
[1.07](1_07_closing_the_loop.md#107-closing-the-loop-the-dac-talks-to-the-adc)
crossed half-way 6 samples after the DAC moved, and `channel.py`, tuned
to that step, puts the matched-filter peak at 6.0: the real chain delays
6.25 MHz by half a sample less than it delays a step's edge, which the
model's two-pole filter does not know.) The last
two columns are **Doppler**: what one step of carrier offset does to the
peak's height and position, and that column splits the five into two kinds.

## Pulse compression

Why a long waveform at all? The matched filter's output for a delayed copy
of *s*(*t*) is the waveform's own autocorrelation *R*(τ), centred on the
delay, and two facts about *R* carry everything:

1. **Its width is 1/*B*.** *R*(τ) is the Fourier transform of the power
   spectrum (Wiener–Khinchin), and a spectrum *B* wide transforms to a peak
   1/*B* narrow. The length *T* does not enter. For a one-way delay the
   resolution is 1/*B*; a radar measures a round trip, so its range cells
   are *c*/2*B*.
2. **Its height is the energy** *E* = *PT*, and the noise after the filter
   is *N*<sub>0</sub>, so the output SNR is 2*E*/*N*<sub>0</sub>
   ([6.01](6_01_eye_diagrams.md#601-eye-diagrams-and-pulse-shaping)). The
   bandwidth does not enter.

Resolution comes from bandwidth and sensitivity from energy, and the two are
separate knobs. A single pulse 1/*B* long has the resolution but only 1/*B*
seconds' worth of energy; make it longer for energy and it loses resolution.
*Pulse compression* is any waveform that is long *and* wide, so that the
filter squeezes *T* seconds of energy into a peak 1/*B* wide. The gain over
the short pulse is *BT*, the time–bandwidth product: 1023 here, 30 dB. The
bottom row of the figure is the demonstration. With noise 15 dB above the
signal's peak power in a band *B* wide, the chirp, Zadoff–Chu and both codes
show the cable's delay as a peak 16 dB above the floor's rms (2*E*/*N*<sub>0</sub>
= 2 × 1023 × 0.03 ≈ 60, 18 dB, less the converters' share) and 7 dB above
its highest spike; the pulse, with *E*/*N*<sub>0</sub> = 0.03, shows nothing:

<!-- CHIRP_HW_SNR -->
```console
$ python3 chirp.py --no-plot --snr -20
...
          -3 dB width   sidelobe   B_rms    PAPR (dB)       delay   Doppler at 1 step: peak, slide
          ns   x(1/B)        dB     MHz   ideal  in B      samples
pulse    270.3   0.84      -0.2     1.37    29.8   30.0      5.186     1.00   -0.00
chirp    297.5   0.93      -2.6     0.90     0.0    5.0      5.146     0.99   -8.15
zc       265.2   0.83      -3.2     1.43     0.1    1.3      4.810     1.00   +8.02
m        254.4   0.79      -0.6     1.43     0.1    6.8      6.217     0.94  -382.82
gold     292.6   0.91      -3.0     1.43     0.1    7.0      5.784     0.77  +3334.96
```

At −20 dB the "sidelobe" column has become the noise floor's height
relative to the peak: a few dB, so the long waveforms are still finding the
cable (within a sample of 5.5), while the pulse's −0.2 dB means its peak is
a coin toss against the noise (the figure's run lost it entirely). Twenty decibels under the noise with a 30 dB
gain leaves 10 dB, and 10 dB is what you see.

## Zadoff–Chu: the chirp, sampled

![Zadoff–Chu sequences of length 1021 for roots 1, 2 and 7: the real part of the first seventy chips, the instantaneous frequency sweeping once, twice and seven times per sequence, the recorded spectrum against a sinc, the recorded autocorrelations, the recorded cross-correlations between roots at a flat 1 over root N, and the worst cross-correlation of every pair compared with GPS's 32 Gold codes](img/comms_zc.png)

A Zadoff–Chu sequence of odd length *N* and root *u* (coprime with *N*) is

  *x*[*n*] = exp(−*jπ u n*(*n* + 1)/*N*),  *n* = 0 … *N* − 1.

The phase is a parabola in *n*. A parabola's slope is a line, so the
frequency, the phase's slope, ramps linearly: root *u* = 1 is a chirp
sampled once per chip, sweeping the whole chip rate once per sequence and
wrapping at ±½ cycle per chip as anything sampled must. The first line of
`chirp.py`'s output is the check: the phase's second difference is
−2π/1021 at every chip, to thirteen digits. Root 2 sweeps twice per
sequence and root 7 seven times, by which point it looks like noise (the
top row of the figure). Three things are *exactly* true of it, and a
physicist should be suspicious of each until shown:

- **|*x*[*n*]| = 1.** Every chip has the same magnitude, so a DAC uses all
  its codes all the time and an amplifier can run saturated. The PAPR
  column: 0.1 dB raw, 1.3 dB after a filter *B* wide (band-limiting a held,
  sampled chirp gives back the smooth chirp). The ±1 codes are 7 dB after
  the same filter, because their transitions pass through zero.
- **Its *N*-point DFT is flat.** A ZC sequence is its own Fourier transform
  up to a chirp: the spectrum has the same magnitude in every bin.
- **Its cyclic autocorrelation is zero at every lag but zero.** Not small:
  zero. The m-sequence's is −1/*N* (−60 dB), the Gold code's three-valued
  (−24 dB).

And one thing that is *not* true, though the author's GRCon talk said it: two
roots are not orthogonal. With *N* prime, any two roots cross-correlate at
exactly 1/√*N* in magnitude at *every* lag: −30.1 dB for all 1019 pairs
against root 1 in the figure's last panel, where GPS's 32 Gold codes have
496 pairs all at −23.9 dB (65/1023). A constant 1/√*N* is the best that
*any* family of constant-amplitude sequences can do at every lag at once
(the average [cross-correlation](https://en.wikipedia.org/wiki/Cross-correlation) power is 1/*N* for anything, by Parseval), so
ZC's edge over Gold is the worst case, 6 dB, not orthogonality. LTE uses ZC
for all three properties: the random-access preamble (*N* = 839), the
primary synchronization signal (*N* = 63) and the uplink reference
signals; 5G kept the first and the third.

<details>
<summary><b>Detail:</b> why <i>n</i>(<i>n</i> + 1), and why odd <i>N</i></summary>

A plain sampled chirp exp(−*jπ u n*<sup>2</sup>/*N*) repeats only every 2*N* chips when
*N* is odd: *x*[*n* + *N*] = *x*[*n*] exp(−*jπ u*(2*nN* + *N*<sup>2</sup>)/*N*) =
*x*[*n*] exp(−*jπ uN*) = −*x*[*n*] for odd *u*. The extra *n* in *n*(*n* + 1) is a
frequency shift of half a cycle per sequence, and it cancels that sign, so
the sequence is periodic in *N* and the *cyclic* autocorrelation is the one
that is exactly zero. For even *N* the form is exp(−*jπ u n*<sup>2</sup>/*N*) and the
same algebra works. `chirp.py` plays the sequence looped, so cyclic is what
the board sees. Chu's 1972 paper is two pages, and the zero-autocorrelation
proof is a Gauss sum.

</details>

## Sidelobes, spectra, and the amplifier

The chirp's recorded spectrum is flat from 4.69 to 7.81 MHz with sharp
edges; the codes' and ZC's are the flat sequence spectrum times a [sinc](https://en.wikipedia.org/wiki/Sinc_function)
from the held chips, with nulls at 6.25 ± 3.12*k* MHz and tails out to the
edge of the ADC's band (the figure's top-right panel; the ZC figure's
spectrum panel draws the sinc over it). Those tails are where the exact
algebra dies. On paper ZC's sidelobes are −∞ and the m-sequence's −60 dB;
recorded, −36 and −41 dB, and the floor does not move when you switch the
ADC's noise off in the model. It is the chips' sinc tails above 12.5 MHz
[aliasing](https://en.wikipedia.org/wiki/Aliasing) back into the band through an ADC that has no anti-alias filter
([1.06](1_06_fast_capture.md#106-fast-captures)), and the AD9280 has none
either. The chirp has no tails and no such floor. A sequence's algebra is
only as good as your chip shaping and your filters, which is the second
lesson of the page.

The chirp's own flaw is the sinc: a −13.2 dB first sidelobe (theory −13.3),
which would hide a small target one range cell from a big one. Radar
people kill it with a window on the *receiver's* reference, not the
transmitted signal, which stays constant-envelope (a "mismatched filter").
`fig_compression.py` tries a Hamming window (one argument to
`chirp.compress`), the dashed line in the figure's peak panel: sidelobes at −42.6 dB, a main lobe 1.30/*B* wide instead of 0.89/*B*,
and a 1.34 dB loss in SNR, which is exactly the Hamming window's processing
loss from [1.06](1_06_fast_capture.md#106-fast-captures)'s spectra. Nothing
is free: the window trades sidelobes for width and sensitivity.

## Doppler: a bug, and a feature

A transmitter whose carrier is Δ*f* high is, to the correlator, sending a
different waveform. The figure's middle row shows what that does, and
`--cfo 1` does it on the board (one step is 3052 Hz, one cycle per loop):

<!-- CHIRP_HW_CFO -->
```console
$ python3 chirp.py --no-plot --cfo 1
...
B = 3.122 MHz (all), T = 327.68 us, BT = 1023;  SNR none added, carrier +3052 Hz
          -3 dB width   sidelobe   B_rms    PAPR (dB)       delay   Doppler at 1 step: peak, slide
          ns   x(1/B)        dB     MHz   ideal  in B      samples
pulse    211.0   0.66     -33.0     1.37    29.8   30.0      5.447     1.00   -0.00
chirp    284.2   0.89     -13.2     0.90     0.0    5.0     -2.542     1.00   -8.01
zc       206.7   0.64     -35.9     1.43     0.1    1.3     13.468     1.00   +8.02
m        757.7   2.37      -0.2     1.43     0.1    6.8   -2867.612     0.97  -707.55
gold     207.8   0.65      -0.2     1.43     0.1    7.0   3135.961     0.88  +257.14
```

For a **code**, a frequency offset is a slow rotation of the chips through
the correlation, and the peak falls as |sinc(Δ*f T*)|: gone at Δ*f* = 1/*T*
= 3052 Hz. The m-sequence and the Gold code have no peak left (their
"delay" is a noise spike). That is why a GPS receiver searches Doppler in
steps of about 1/*T* for every satellite, the two-dimensional search of
learnSDR's [lesson 23](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson23.md),
and why acquisition is the slow part of a cold start.

For a **chirp**, a frequency shift is a time shift. The chirp's frequency
ramps at *B*/*T*, so a signal Δ*f* high looks like the same chirp arrived
Δ*f T*/*B* early: the peak keeps its full height and slides, one chip per
step here, −8.01 samples for the up-chirp and +8.02 for Zadoff–Chu (a
down-chirp: the sign of the exponent). The delay found by the up-chirp is now
−2.5 samples instead of 5.5, and ZC's 13.5. This *delay–Doppler coupling* is a
bug for a radar that wants range (a 300 m/s target at 10 GHz is 20 kHz, 6.5
chips at this *B*/*T*), and it is the feature that lets LoRa run on a 20 ppm
crystal. The cure is the triangle: an up-chirp and a down-chirp slide
opposite ways, so their mean is the delay and half their difference is the
Doppler. LoRa's preamble (up) and start-of-frame delimiter (down) are
exactly this, and FMCW radars sweep up and down for the same reason. The
figure's fine Doppler curves are a frequency shift applied to the record in
software, which is what a mixer would do; the board itself only moves in
steps of 3052 Hz.

## Ranging, and how well

![Ranging through the cable: the scatter of the delay estimate against SNR for the chirp, Zadoff–Chu and the m-sequence with the Cramér–Rao bound for each, the delay each finds with error bars, and the phase scatter of a plain tone against the chirp's compressed peak as more loops are averaged](img/comms_ranging.png)

How well can the peak be timed? Not better than the *Cramér–Rao bound*, which
for a known waveform in white noise is

  σ<sub>τ</sub> = 1 / (2π *B*<sub>rms</sub> √(2*E*/*N*<sub>0</sub>)),
  *B*<sub>rms</sub><sup>2</sup> = ∫(*f* − *f*<sub>0</sub>)<sup>2</sup> |*S*(*f*)|<sup>2</sup> d*f* / ∫|*S*(*f*)|<sup>2</sup> d*f*,

with *E*/*N*<sub>0</sub> = SNR × *BT*. Two things in it. The SNR enters as a
square root, as any averaging does. And the bandwidth enters as the *rms*
width of the spectrum, not its edges: it is the spectrum's second moment
that times a peak, because the Fisher information is ∑|*s*′|<sup>2</sup>, and Parseval
turns a derivative into a factor of *f*<sup>2</sup>. A flat spectrum *B* wide has
*B*<sub>rms</sub> = *B*/√12 = 0.90 MHz for the chirp. The square chips, with
their tails, have 1.43 MHz over the ADC's band, so at *equal chip rate* the
codes' bound is 1.6 times tighter: they bought it with spectrum out to
four times *B* that a licensed band would not let you use.

<details>
<summary><b>Detail:</b> where the bound comes from, in one paragraph</summary>

The record is *y*[*n*] = *A s*[*n* − τ] + noise of variance σ<sup>2</sup>. The
log-likelihood is −∑|*y* − *A s*(τ)|<sup>2</sup>/2σ<sup>2</sup>, its second derivative in τ is
−*A*<sup>2</sup>∑|*s*′|<sup>2</sup>/σ<sup>2</sup>, and the Cramér–Rao bound says no unbiased estimator has a
variance smaller than minus one over that: σ<sub>τ</sub><sup>2</sup> = σ<sup>2</sup>/(*A*<sup>2</sup>∑|*s*′|<sup>2</sup>).
Parseval: ∑|*s*′|<sup>2</sup> = (2π)<sup>2</sup> ∑ *f*<sup>2</sup> |*S*(*f*)|<sup>2</sup> = (2π)<sup>2</sup> *E B*<sub>rms</sub><sup>2</sup> for a
spectrum centred at zero (at *f*<sub>0</sub>, after mixing down). Put *E*/*N*<sub>0</sub>
in for *A*<sup>2</sup>*E*/σ<sup>2</sup> and you have the formula. The same argument with the
frequency as the unknown gives the bound on a Doppler estimate with the
*duration*'s rms in place of the bandwidth's: the two are a pair.

</details>

The left panel is the test. The estimator (the correlation upsampled 16
times, a parabola through the three points around the peak) sits on the
bound: the chirp scatters 20 ns at −15 dB against a bound of 22 ns, the
m-sequence 8 ns against 14 (twelve trials a point, so each scatter is
good to ±20%); at 0 dB all three reach 2–4 ns, a twentieth of an ADC sample, from a 40 ns sampling period and a 3 MHz bandwidth.
Below a threshold (the chirp's is about −21 dB, *E*/*N*<sub>0</sub> ≈ 8) some
trials land on a noise peak instead, the estimate jumps by microseconds,
and the bound stops applying: the hollow markers. Every radar and every GPS
receiver has such a threshold, and the search-then-track structure exists
to stay above it.

The right panel settles an argument the author has with himself. A plain
tone at 6.25 MHz and the chirp, at the same power, in the same noise,
integrated over one loop, give the same phase scatter: 3.2° and 3.6° at one
loop, falling as 1/√(loops) to 1.2° and 1.1° at eight, against the
predicted 1/√(2*E*/*N*<sub>0</sub>) = 4.0°.
"Bandwidth cancels in the link budget" is true: each of the chirp's 1023 FFT
bins holds a thousandth of its energy, 30 dB below the tone's one bin, and
the matched filter adds the thousand bins back coherently, which *is* pulse
compression. The tone gives you range modulo a wavelength, 33 m at 6.25 MHz
in this cable (48 m in air); the chirp gives the same phase *and* resolves the ambiguity
to ±1/*B* for free. That is the carrier-phase ranging of
[6.13](6_13_more_ideas.md#613-more-ideas-and-a-radar-chapter), and it is how
RTK GPS gets centimetres from a 300 m code chip.

## Radar on a cable

![Simulated: a 30 metre open stub on a T at the DAC seen by a 10 MHz sweep, where the echo at 288 ns sits 2.9 range cells from the direct path, and by a 2 MHz sweep, where it is 0.6 of a cell and merges; and with noise at the signal's peak power, the chirp, a 1 microsecond pulse and a 100 nanosecond pulse: energy, resolution, or both](img/comms_radar.png)

Put an SMA T on the DAC's output and hang an open-ended cable *L* long from
its third port. The signal that goes up the stub comes back 2*L*/*v* later,
inverted by nothing (an open circuit reflects in phase), and joins the
direct path into the ADC, which is a radar target at range *L* that never
moves. The compressed output shows two peaks, and the range is *v*Δ*t*/2.
With 30 m of RG-316 (*v* = 0.695*c*) the echo is at 288 ns, 7.2 samples: 2.9
cells for a 10 MHz sweep (two clean peaks, the echo at −3 dB, a second
bounce at −13 dB at 576 ns), 0.6 of a cell for a 2 MHz sweep (one blob).
The right panel is the pulse-compression argument once more with the
noise at the signal's peak power: the 100 ns pulse's floor is −2 dB (lost),
the 1 µs pulse's −13 dB (found, but one blob), the chirp's −35 dB (two
peaks). Energy, resolution, or both.

The uncomfortable number is the size of a range cell, *v*/2*B*, which
`chirp.py --stubs` tabulates:

```console
$ python3 chirp.py --stubs                 # no board
one range cell = a round trip of 1/B = a stub v/2B long (v = 0.695 c, RG-316):
   B (MHz)   cell (m)   1, 2, 5, 10 cells (m)       RG-58 (0.66 c): 1 cell
    2.00       52.1     52.1   104.2   260.4   520.9       49.5
    3.12       33.4     33.4    66.7   166.8   333.7       31.7
   10.00       10.4     10.4    20.8    52.1   104.2        9.9
   12.00        8.7      8.7    17.4    43.4    86.8        8.2
```

The 5 m stub of [4.05](4_05_quarter_wave_stub.md#405-a-quarter-wave-stub) is six
tenths of a cell even at the ADC's full 12 MHz, so its echo merges with the
direct path: a 25 MS/s ADC makes a poor radar
for anything on a bench, and that is the honest reason the figure above is
simulated. What would make it real: an SMA T and a 30 m spool of RG-58 with
one SMA end and the other end open (two peaks at 10 MHz, one blob at 2 MHz,
from the same stub); 50 m adds the five-cell case; 100 m would give ten but
the loss will eat it. `fig_radar.py PORT --stub 30` is written and waiting.
The parts are in [6.00](6_00_digital_communications.md#600-digital-communications-hardware-defined-radio)'s
list. The stub echo's amplitude (0.67 of the direct path from the T's 25 Ω
junction, then −⅓ per further bounce) is a model of a T whose source
impedance the author will have to measure.

What a real radar adds is Doppler, and a tabletop version is in reach: [4.06](4_06_speed_of_sound.md#406-the-speed-of-sound-at-40-khz)'s
40 kHz ultrasonic transducers have a wavelength of 8.6 mm, the same as a
35 GHz radar, and `awgcap.sv` played 64 times slower gives a 21 ms loop, so a
5 kHz chirp around 40 kHz resolves 3.4 cm, a fan blade gives Doppler, and a
hand walked along a rail gives synthetic-aperture imaging. That is MIT's
[coffee-can radar course](https://ocw.mit.edu/courses/res-ll-003-build-a-small-radar-system-capable-of-sensing-range-doppler-and-synthetic-aperture-radar-imaging-january-iap-2011/)
at 2.4 GHz, on a bench for five dollars, and it is the radar chapter in
[6.13](6_13_more_ideas.md#613-more-ideas-and-a-radar-chapter).

## LoRa

![LoRa through the cable at spreading factor 7: the spectrogram of a frame, two up-chirps, two down-chirps and four data symbols that start their sweep at their value; the preamble's and the delimiter's dechirped bins, whose sum gives the carrier offset and difference the timing; the four data symbols dechirped, one spike each; and the bit error rate for spreading factors 7 to 10 against the exact theory with Semtech's quoted sensitivities](img/comms_lora.png)

LoRa is the chirp's delay–Doppler coupling turned into a modulation, and it
is the reason a $3 radio reaches ten kilometres on twenty-five milliwatts. A symbol
is the base up-chirp (a sweep from −*B*/2 to +*B*/2 over *M* = 2<sup>SF</sup>
chips) *cyclically shifted* by its value *s*, which is to say a sweep that
starts somewhere and wraps round: SF bits per symbol, Gray-coded so that a
near miss costs one bit. The receiver is three lines. Mix down and low-pass
to ±*B*/2, keep one sample per chip, multiply by the conjugate of the base
chirp (*dechirp*: a chirp that started *s* chips late becomes a *tone* at
*sB*/*M*, the sweep is gone), and take one *M*-point FFT. The biggest bin is
*s*. One FFT is *M* matched filters in *M* log *M* operations, detected by
magnitude, with no carrier phase to track. `lora.py` runs it at 3.125
million chips a second, 25 times LoRa's 125 kHz, so that a frame fits a
loop:

<details>
<summary>The whole file: <code>lora.py</code></summary>

<!-- file: src/comms/lora.py -->
```python
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
```

</details>

<!-- LORA_HW -->
```console
$ python3 lora.py --no-plot
LoRa at 3.125 Mchip/s: SF 7, 128 chips per symbol, 8 symbols per loop, 171 kbit/s; a bin is 24.4 kHz
preamble's up-chirps at bin +0.01, SFD's down-chirps at bin -0.01
  so the carrier is off by +0.00 bins (+17 Hz; sent +0) and the timing by -0.01 chips (5.90 samples)
sent     5   77  100  127
found    5   77  100  127   (0 symbol errors, 0 bit errors in 28 bits)
$ python3 lora.py --no-plot --cfo 12
LoRa at 3.125 Mchip/s: SF 7, 128 chips per symbol, 8 symbols per loop, 171 kbit/s; a bin is 24.4 kHz
preamble's up-chirps at bin +1.75, SFD's down-chirps at bin +1.25
  so the carrier is off by +1.50 bins (+36721 Hz; sent +36621) and the timing by -0.25 chips (4.00 samples)
sent     5   77  100  127
found    5   77  100  127   (0 symbol errors, 0 bit errors in 28 bits)
$ python3 lora.py --no-plot --sf 10 --snr -16
LoRa at 3.125 Mchip/s: SF 10, 1024 chips per symbol, 1 symbols per loop, 30.5 kbit/s; a bin is 3.1 kHz
SF 10 has no room for a preamble in a loop; the timing comes from an SF 7 frame
sent   484
found  484   (0 symbol errors, 0 bit errors in 10 bits)
```

The second run is the trick that makes LoRa work on a bad crystal. The
carrier is 36.6 kHz high, a bin and a half, so every dechirped bin has
moved by 1.5. An up-chirp's bin moves by ν − τ (carrier offset minus timing
error, in bins and chips) and a down-chirp's by ν + τ: the preamble lands
at 1.75 and the start-of-frame delimiter at 1.25: ν = 1.50 bins and τ =
−0.25 chips, and the data decode cleanly. That is the whole reason for the
down-chirps. A 20 ppm crystal at 868 MHz is 17 kHz, 14% of a 125 kHz
channel, and a [QPSK](https://en.wikipedia.org/wiki/Phase-shift_keying#Quadrature_phase-shift_keying_(QPSK)) receiver would need
[6.02](6_02_psk_and_qpsk.md#602-psk-and-qpsk-finding-the-clock-and-the-carrier)'s
frequency-locked loop and a long preamble to find it; LoRa reads it off two
FFT bins.

The third run is the energy argument. *E*<sub>s</sub>/*N*<sub>0</sub> = SNR × 2<sup>SF</sup>
per symbol, so SF 10 integrates 1024 chips, 30 dB, and decodes a symbol
sixteen decibels *under* the noise. Each extra spreading factor doubles the
symbol (+3 dB of energy) and doubles *M* (−0.3 dB for the bigger
competition), net 2.7 dB per SF for half the rate. The figure's last panel
is the measured [bit error rate](https://en.wikipedia.org/wiki/Bit_error_rate) for SF 7–10 against the exact theory for *M*
orthogonal signals detected non-coherently (Proakis's textbook formula, in
`lora.ser_theory`): the points sit on it, and the SNRs for one symbol error
in a hundred are −9.0, −11.7, −14.4 and −17.2 dB, with SF 11 and 12 (which
do not fit a loop) at −20.0 and −22.7 by theory. Semtech's datasheet quotes
−7.5, −10, −12.5, −15, −17.5 and −20 dB for SF 7–12: 1.5 to 2.7 dB from the
ideal uncoded detector, which is a fair price for a radio that costs three
dollars.

<details>
<summary><b>Detail:</b> why ten kilometres on ten milliwatts</summary>

Five things, and only one of them is clever. (1) The receiver's noise is
*kTB*, and *B* is 125 kHz: −123 dBm, plus about 6 dB of noise figure for a
three-dollar chip: −117 dBm. (2) A symbol integrates 2<sup>SF</sup> chips,
21–36 dB, so it demodulates at −7.5 to −20 dB SNR: −137 dBm at SF 12,
Semtech's quoted sensitivity, and against +14 dBm transmitted that is a
151 dB link budget;
free space at 868 MHz over 10 km costs 111 dB, leaving 40 dB for walls and
trees. (3) Constant envelope, so a fifty-cent amplifier runs saturated.
(4) The chirp tolerates the crystal, above. (5) Nothing beats Shannon
([6.08](6_08_shannons_limit.md#608-shannons-limit-and-how-far-from-it-you-are)):
the price is 290 bits per second at SF 12, and at that rate GPS, which
also integrates its way 30 dB under the noise, sends 50. LoRa is spread
spectrum ([6.06](6_06_spread_spectrum.md#606-spread-spectrum-the-gps-way))
with a chirp instead of a code, and the chirp's only real advantage over the
code is item 4.

</details>

The opinion. The physics is from 1960 (Klauder, Price, Darlington and
Albersheim, "The theory and design of chirp radars", *Bell System Technical
Journal*) plus textbook *M*-ary orthogonal signalling. Semtech's patent
(Seller and Sornin, EP 2449690 / US 9,252,834, bought with Cycleo in 2012)
covers the framing and the sync trick, and the business is the chips. It
is excellent, cheap engineering of public-domain ideas, and since Matt
Knight (2016) and then Robyns and colleagues (2017) reverse-engineered the
rest (gr-lora), it is also the best teaching modulation there is: every part of it is on this page, and a $10 module will
talk to a `lora.py` that runs at 125 kchip/s with a real radio front end.

## Gold codes, or chirps?

The author's claim was that for ranging, once the hardware is a DAC rather
than a digital pin, Zadoff–Chu sequences and chirps beat GPS's binary
codes. The measurements say he is right, with the fine print:

| | binary code (m-sequence, Gold) | chirp | Zadoff–Chu |
| --- | --- | --- | --- |
| peak width, equal chip rate | 0.65/*B* | 0.89/*B* | 0.65/*B* |
| spectrum | sinc tails to ±4*B* | flat, sharp edges | sinc tails to ±4*B* |
| *B*<sub>rms</sub>, so the ranging bound | 1.43 MHz: 1.6× tighter | 0.90 MHz | 1.43 MHz |
| sidelobes, exact | −60 dB (m), −24 dB (Gold) | −13.3 dB (−43 with a Hamming) | zero |
| sidelobes, recorded | −41 dB, −23 dB | −13.2 dB | −36 dB |
| PAPR after a filter *B* wide | 7 dB | 0 dB (5 at the turn-around) | 1.3 dB |
| Doppler | peak dies at 1/*T*; 2-D search | slides by Δ*f T*/*B*; up/down fixes it | the same |
| family of *N* ≈ 1000 | 32 Gold codes at −24 dB | one | 1020 roots at −30 dB, every lag |
| hardware | one pin, an XOR, a 1-bit correlator | a swept oscillator, or a DAC | a DAC with I and Q |

At equal *occupied* bandwidth the chirp and ZC win on every row but one. At
equal *chip rate* the square-chip codes buy a tighter ranging bound with
spectrum they are not entitled to, which GPS gets away with because its
satellites own the band. ZC's "exactly zero" sidelobes are −36 dB in an ADC
with no anti-alias filter, which is still better than everything but the
m-sequence alone, and a sequence's family is where it wins outright. The
codes' remaining argument is the 1973 one: a Gold code is one pin and an
XOR, and a correlator for it is a counter. With a DAC you give nothing up.

**Try this:**

- `--cfo 2`, `--cfo 3`: the chirp's peak slides a chip per step; check
  Δ*f T*/*B* and the sign for ZC. Then find the offset where the up-chirp's
  peak has wrapped round the loop.
- `--kinds zc` and a root of 2 in the code: how does the double chirp's
  peak move under `--cfo 1`? (Twice as fast: the slope is *uB*/*T*.)
- Find the SNR where the delay estimate first jumps off the bound, for each
  waveform, with `fig_ranging.py --trials 30`. Why is the pulse's threshold
  30 dB higher?
- Hann, Blackman and no window against Hamming on the chirp's reference
  (the `window` argument of `chirp.compress`, as `fig_compression.py` uses
  it): sidelobes, width and loss, as in [1.06](1_06_fast_capture.md#106-fast-captures).
- `lora.py --sf 10 --cfo 1`: one step is exactly one bin at SF 10. Then
  shorten the preamble to one chirp in the code and find the SNR where
  sync fails; real LoRa sends eight.
- `fig_lora.py --records 200` fills in SF 10's low-error points.
- With a second board (`chirp.py PORT_A PORT_B`): the one-way delay now
  includes the two clocks' offset, which is
  [5.03](5_03_time_transfer.md#503-what-time-is-it-over-there)'s [time transfer](https://en.wikipedia.org/wiki/Time_transfer) with a
  chirp; and their 0.76 ppm frequency difference is 4.75 Hz at 6.25 MHz, a
  six-hundredth of a Doppler step. `--cfo 1` fakes a crystal 488 ppm off.
- If you have the T and the stub: `fig_radar.py PORT --stub 30`, then
  `--bw 2e6` and `--bw 12e6`. Then a 50 m stub, or the two in series.
