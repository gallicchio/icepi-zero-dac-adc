<!-- nav -->
[← 6.07 OFDM: the triumph of physics over math](6_07_ofdm.md#607-ofdm-the-triumph-of-physics-over-math) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)** &emsp;&emsp;&emsp; [6.09 Error-correcting codes →](6_09_error_correcting_codes.md#609-error-correcting-codes)

# 6.08 Shannon's limit, and how far from it you are

![Left, theory: spectral efficiency in bits per second per hertz against Eb/N0: Shannon's curve, the curves for BPSK, QPSK, 16-QAM and 64-QAM with the best possible code, the uncoded operating points at a bit error rate of one in a hundred thousand, the 7.8 dB gap uncoded QPSK leaves at 2 bits per second per hertz, DVB-S2's coded modes, and the −1.59 dB limit. Right, the cable as 6.07 measured it: Shannon's capacity against random noise alone and against QAM-64's error vector magnitude, the rates OFDM and QPSK actually carried, and what QPSK's own 2.1 MHz could carry at its own MER](img/comms_capacity.png)

In 1948 Claude Shannon proved that a channel of bandwidth *B* and
[signal-to-noise ratio](https://en.wikipedia.org/wiki/Signal-to-noise_ratio) *S*/*N*, with Gaussian noise, can carry

  *C* = *B* log<sub>2</sub>(1 + *S*/*N*) bits per second

and not one more, *and* that below that rate there exist codes with as
few errors as you like. Every page in this chapter has been circling that
sentence. This one asks the question it invites: how far from *C* are the
things we built? The answer has two halves, and "[QPSK](https://en.wikipedia.org/wiki/Phase-shift_keying#Quadrature_phase-shift_keying_(QPSK)) against Shannon"
means both.

## The theorem, in one paragraph

Here is the proof a physicist can keep. A code word of *n* symbols is a
point in *n* dimensions. Noise of power *N* moves it to somewhere in a ball
of radius √(*nN*) around it, and the received signal, with power *S* + *N*,
lives inside a ball of radius √(*n*(*S* + *N*)). The number of small balls that
fit in the big one without overlapping is the ratio of their volumes,
((*S* + *N*)/*N*)<sup>*n*/2</sup>, so that many code words can be told apart: (*n*/2)
log<sub>2</sub>(1 + *S*/*N*) bits in *n* symbols. And 2*B* symbols a second fit in a
bandwidth *B* ([1.06](1_06_fast_capture.md#106-fast-captures)'s [sampling theorem](https://en.wikipedia.org/wiki/Nyquist%E2%80%93Shannon_sampling_theorem)). That's *C*. It is a volume
argument, and the "as few errors as you like" part is that in high
dimensions almost all of a ball's volume is near its surface, so the noise
balls stay apart. What the theorem does *not* say: which code (that took
forty-five years, [6.09](6_09_error_correcting_codes.md#609-error-correcting-codes)); how long the code word may be (as long as you like,
with the delay to match); that the noise is anything but Gaussian (a dropout
isn't); or that anything at all helps above *C*.

## Energy per bit, and the end of the road at −1.59 dB

Write the signal power as *S* = η *E*<sub>b</sub> *B* for η bits per second per
hertz, and the noise as *N* = *N*<sub>0</sub> *B*, and the limit becomes

  η = log<sub>2</sub>(1 + η *E*<sub>b</sub>/*N*<sub>0</sub>),  i.e.  *E*<sub>b</sub>/*N*<sub>0</sub> ≥ (2<sup>η</sup> − 1)/η.

As η → 0 this tends to ln 2 = −1.59 dB: with unlimited bandwidth, each
bit still needs 0.69 times the noise density in energy. Bandwidth is free
in the limit; energy is not. Deep-space links live in that corner. The
left panel of the figure is this equation, and everything else on it is
measured against it:

<details>
<summary>The whole file: <code>capacity.py</code></summary>

<!-- file: src/comms/capacity.py -->
```python
#!/usr/bin/env python3
"""Shannon's limit, and how far from it 6.02's QPSK and 6.07's OFDM are.

    python3 capacity.py                 # the table: Shannon against uncoded modulations
    python3 capacity.py --snr 30        # what a 30 dB channel can carry, per hertz
    python3 capacity.py --plot          # draw the curves (fig_capacity.py does it better)

No board: everything here is theory, plus the numbers 6.07 measured on the cable.

Shannon (1948): a channel of bandwidth B hertz and signal-to-noise ratio S/N can carry

    C = B log2(1 + S/N)   bits per second

with as few errors as you like, and not one bit more.  Per hertz: C/B = log2(1 + S/N).

The fair axis for comparing modulations is Eb/N0, the energy per bit over the noise
density (6.02).  At a spectral efficiency eta = C/B bits per second per hertz the
signal power is S = eta Eb, and the noise power in the band is N = N0 B, so
S/N = eta Eb/N0, and the limit becomes

    eta = log2(1 + eta Eb/N0),   i.e.   Eb/N0 = (2^eta - 1) / eta

and as eta -> 0 (all the bandwidth you like), Eb/N0 -> ln 2 = -1.59 dB.  Below that
nothing can be sent reliably at any rate, however wide the band.

A constellation of M fixed points can't follow log2(1 + S/N) for ever: it saturates
at log2(M) bits per symbol.  For M equally likely points x_k in complex Gaussian noise
n (E|n|^2 = N0) the mutual information is (Ungerboeck 1982)

    I = log2 M - (1/M) sum_i E_n[ log2 sum_k exp(-(|x_i - x_k + n|^2 - |n|^2) / N0) ]

computed here by Gauss-Hermite quadrature over the noise.  Below about 1 bit per
symbol short of log2 M each constellation hugs Shannon's curve: the points don't
cost you anything, the CODE is what you're missing.
"""
import argparse
import math

import numpy as np

# ---- what 6.07 measured on the 101.5 cm cable (one board looped back) --------------
CABLE = dict(
    ofdm_band=(0.29e6, 11.23e6),     # subcarriers 3..115 of 25 MS/s / 256
    ofdm_B=113 * 25e6 / 256,         # 113 subcarriers x 97.66 kHz = 11.04 MHz
    evm=0.031,                       # QAM-64's rms EVM: everything counted (SNR 30 dB)
    qam16_rate=37.2e6, qam64_rate=55.9e6, qam256_rate=74.5e6,   # bit/s while sending
    qam256_ber=2.2e-3,               # ... and QAM-256 wasn't error-free
    sounding_snr_db=40.0,            # against random noise only, every 3 kHz bin
    sounding_C=169e6,                # ... summed over 3 kHz - 12.4 MHz
    qpsk_rate=3.125e6,               # 6.02: 1.5625 Msymbol/s x 2 bits
    qpsk_band=(5.2e6, 7.3e6),        # 1.35 x 1.5625 MHz: the roll-off costs 35%
    qpsk_mer_db=38.3,                # 6.02's measured MER: the cable as QPSK sees it
)


# ---- Shannon ----------------------------------------------------------------------
def capacity(snr_db):
    """Bits per second per hertz at this signal-to-noise ratio."""
    return np.log2(1 + 10**(np.asarray(snr_db, float) / 10))


def shannon_ebn0(eta):
    """The least Eb/N0 (dB) at which eta bit/s/Hz is possible at all."""
    eta = np.asarray(eta, float)
    # ##########################################################################
    # ##  KEY LINE: S/N = eta Eb/N0, so eta = log2(1 + eta Eb/N0).  Solve for
    # ##  Eb/N0.  At eta -> 0 this is ln 2 = -1.59 dB, the end of the road.
    # ##########################################################################
    return 10 * np.log10((2**eta - 1) / eta)


# ---- constellations ---------------------------------------------------------------
def points(M):
    """BPSK, QPSK, 16-QAM, 64-QAM: M points with average energy 1 (as 6.03's qam_map)."""
    if M == 2:
        return np.array([1.0, -1.0], complex)
    m = int(round(math.sqrt(M)))
    g = np.arange(m) * 2 - (m - 1)
    x = (g[:, None] + 1j * g[None, :]).ravel()
    return x / np.sqrt(np.mean(np.abs(x)**2))


def constrained_capacity(M, esn0_db, nodes=32):
    """Mutual information (bits per symbol) of M equally likely points in complex
    Gaussian noise, at symbol SNR Es/N0 (dB): Gauss-Hermite with nodes^2 noise points."""
    x = points(M)
    N0 = 1 / 10**(esn0_db / 10)                       # Es = 1
    t, w = np.polynomial.hermite.hermgauss(nodes)     # weight e^(-t^2)
    n = np.sqrt(N0) * (t[:, None] + 1j * t[None, :]).ravel()      # noise samples
    wn = (w[:, None] * w[None, :]).ravel() / np.pi                # ... and weights
    d = x[:, None] - x[None, :]                       # x_i - x_k
    # ##########################################################################
    # ##  KEY LINE: for each sent point i and each noise sample, how much more
    # ##  likely are the OTHER points than the sent one?  Sum, log, average.
    # ##########################################################################
    a = -(np.abs(d[:, None, :] + n[None, :, None])**2 - np.abs(n[None, :, None])**2) / N0
    amax = a.max(axis=2, keepdims=True)               # log-sum-exp, without overflow
    lse = (amax[..., 0] + np.log(np.sum(np.exp(a - amax), axis=2))) / math.log(2)
    return math.log2(M) - np.mean(lse @ wn)


def constrained_curve(M, esn0_db):
    """(Eb/N0 in dB, bits per symbol) along the constrained capacity of M points:
    at I bits per symbol, Eb = Es / I."""
    I = np.array([constrained_capacity(M, s) for s in esn0_db])
    return esn0_db - 10 * np.log10(I), I


# ---- uncoded modulation -----------------------------------------------------------
def Q(x):
    return 0.5 * math.erfc(x / math.sqrt(2))


def ber_uncoded(M, ebn0_db):
    """Bit error rate of Gray-coded BPSK, QPSK or square M-QAM, with no code
    (6.07's ber_curve.py, written per bit)."""
    x = 10**(ebn0_db / 10)
    if M == 2:
        return Q(math.sqrt(2 * x))
    k = math.log2(M)
    return 4 / k * (1 - 1 / math.sqrt(M)) * Q(math.sqrt(3 * k * x / (M - 1)))


def ebn0_for_ber(M, ber=1e-5):
    """The Eb/N0 (dB) at which uncoded M-ary modulation reaches this BER (bisection)."""
    lo, hi = -2.0, 40.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if ber_uncoded(M, mid) > ber else (lo, mid)
    return (lo + hi) / 2


NAMES = {2: "BPSK", 4: "QPSK", 16: "16-QAM", 64: "64-QAM"}


def table(ber=1e-5):
    """Rows (M, bits per symbol, Shannon's Eb/N0, uncoded Eb/N0 at `ber`, the gap)."""
    rows = []
    for M in (2, 4, 16, 64):
        eta = math.log2(M)
        sh, un = float(shannon_ebn0(eta)), ebn0_for_ber(M, ber)
        rows.append((M, eta, sh, un, un - sh))
    return rows


def cable():
    """6.07's cable, in bits per second: what Shannon allows and what was carried."""
    c = CABLE
    B = c["ofdm_B"]
    snr_evm = 1 / c["evm"]**2
    C_evm = B * math.log2(1 + snr_evm)                # the page's 110 Mbit/s
    C_noise = B * math.log2(1 + 10**(c["sounding_snr_db"] / 10))
    Bq = c["qpsk_band"][1] - c["qpsk_band"][0]
    C_qpsk_band = Bq * math.log2(1 + 10**(c["qpsk_mer_db"] / 10))
    return dict(B=B, snr_evm_db=10 * math.log10(snr_evm), C_evm=C_evm, C_noise=C_noise,
                Bq=Bq, C_qpsk_band=C_qpsk_band,
                frac_qam64=c["qam64_rate"] / C_evm, frac_qam16=c["qam16_rate"] / C_evm,
                frac_qpsk_cable=c["qpsk_rate"] / C_evm, frac_qpsk_band=c["qpsk_rate"] / C_qpsk_band)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snr", type=float, help="print what this S/N (dB) can carry per hertz")
    ap.add_argument("--ber", type=float, default=1e-5, help="the BER that counts as 'working' (1e-5)")
    ap.add_argument("--plot", action="store_true")
    args = ap.parse_args()

    if args.snr is not None:
        print("S/N = %.1f dB: Shannon allows %.2f bit/s/Hz; the constellations manage" % (args.snr, capacity(args.snr)))
        for M in (2, 4, 16, 64):
            print("   %-7s %.2f of %d bits per symbol" % (NAMES[M], constrained_capacity(M, args.snr), math.log2(M)))

    print("Shannon: Eb/N0 >= (2^eta - 1)/eta at eta bit/s/Hz; eta -> 0 gives ln 2 = %.2f dB"
          % (10 * math.log10(math.log(2))))
    print("%-7s %5s  %14s  %21s  %6s" % ("", "eta", "Shannon Eb/N0", "uncoded, BER %.0e" % args.ber, "gap"))
    for M, eta, sh, un, gap in table(args.ber):
        print("%-7s %5.0f  %11.2f dB  %18.2f dB  %4.1f dB" % (NAMES[M], eta, sh, un, gap))

    c = cable()
    print("\n6.07's cable, %.2f MHz used for OFDM:" % (c["B"] / 1e6))
    print("   SNR %.1f dB from QAM-64's EVM (everything counted):  C = %.0f Mbit/s" % (c["snr_evm_db"], c["C_evm"] / 1e6))
    print("   SNR %.0f dB against random noise only (sounding):   C = %.0f Mbit/s" % (CABLE["sounding_snr_db"], c["C_noise"] / 1e6))
    print("   OFDM QAM-64 carried %.1f Mbit/s with no errors: %.0f%% of C" % (CABLE["qam64_rate"] / 1e6, 100 * c["frac_qam64"]))
    print("   OFDM QAM-16 carried %.1f Mbit/s:                %.0f%% of C" % (CABLE["qam16_rate"] / 1e6, 100 * c["frac_qam16"]))
    print("   QPSK (6.02) carried %.3f Mbit/s:               %.1f%% of C" % (CABLE["qpsk_rate"] / 1e6, 100 * c["frac_qpsk_cable"]))
    print("   ... and %.0f%% of the %.0f Mbit/s its own %.1f MHz could carry at its MER of %.1f dB"
          % (100 * c["frac_qpsk_band"], c["C_qpsk_band"] / 1e6, c["Bq"] / 1e6, CABLE["qpsk_mer_db"]))

    if args.plot:
        import matplotlib.pyplot as plt
        eta = np.linspace(0.02, 8, 400)
        plt.plot(shannon_ebn0(eta), eta, "k", label="Shannon: log2(1 + S/N)")
        for M in (2, 4, 16, 64):
            eb, I = constrained_curve(M, np.linspace(-10, 30, 81))
            plt.plot(eb, I, label="%s points only" % NAMES[M])
        for M, e, sh, un, gap in table(args.ber):
            plt.plot(un, e, "o", color="k")
        plt.axvline(10 * np.log10(np.log(2)), ls="--", color="0.5")
        plt.xlim(-3, 25); plt.ylim(0, 8); plt.grid(True)
        plt.xlabel("Eb/N0 (dB)"); plt.ylabel("bit/s/Hz"); plt.legend(); plt.show()
```

</details>

```console
$ python3 capacity.py                   # no board: theory, and 6.07's numbers
Shannon: Eb/N0 >= (2^eta - 1)/eta at eta bit/s/Hz; eta -> 0 gives ln 2 = -1.59 dB
          eta   Shannon Eb/N0     uncoded, BER 1e-05     gap
BPSK        1         0.00 dB                9.59 dB   9.6 dB
QPSK        2         1.76 dB                9.59 dB   7.8 dB
16-QAM      4         5.74 dB               13.43 dB   7.7 dB
64-QAM      6        10.21 dB               17.79 dB   7.6 dB

6.07's cable, 11.04 MHz used for OFDM:
   SNR 30.2 dB from QAM-64's EVM (everything counted):  C = 111 Mbit/s
   SNR 40 dB against random noise only (sounding):   C = 147 Mbit/s
   OFDM QAM-64 carried 55.9 Mbit/s with no errors: 51% of C
   OFDM QAM-16 carried 37.2 Mbit/s:                34% of C
   QPSK (6.02) carried 3.125 Mbit/s:               2.8% of C
   ... and 12% of the 27 Mbit/s its own 2.1 MHz could carry at its MER of 38.3 dB
```

## The points are not the problem

At 2 bits per second per hertz Shannon asks for *E*<sub>b</sub>/*N*<sub>0</sub> = 1.76 dB.
Uncoded QPSK at one error in 10<sup>5</sup> needs 9.59 dB. The gap is 7.8 dB: a
factor of six in transmitter power, or in antenna area, or in range
squared. That is "QPSK against Shannon", the first meaning, and the natural
guess is that the four points are to blame. They aren't. Fix the input to
four points and ask how many bits per symbol the best possible code could
still carry (the *constrained capacity*, computed in `capacity.py` by
integrating over the noise): at *E*<sub>s</sub>/*N*<sub>0</sub> = 5 dB QPSK's four points carry 1.72
bits of their 2, where Shannon's unconstrained curve gives 2.06 bits, barely higher; 64-QAM
at 20 dB carries 5.80 of 6. The coloured curves hug the black one until
about a bit short of their maximum and only then flatten. So QPSK with a
good code runs at 1.5 bits per second per hertz within a fraction of a
decibel of the best anything can do. The 7.8 dB is entirely the absence of a
code: "uncoded" means every symbol must stand alone against the noise, and
Shannon's whole point is that it needn't.

There are two ways toward the curve, and the figure shows both. A **code**
moves you *left* at fixed η: the diamonds are DVB-S2's modes (its standard's
table), QPSK with a rate-½ LDPC code at 1.1 dB from Shannon, 8PSK at 2.3 dB.
**More points** move you *up* at fixed *E*<sub>b</sub>/*N*<sub>0</sub>: 64-QAM at 17.8 dB carries 6
bits where QPSK carries 2 ([6.03](6_03_qam.md#603-qam-more-bits-per-symbol)). [6.07](6_07_ofdm.md#607-ofdm-the-triumph-of-physics-over-math) did the second with no code and
reached half of capacity; [6.09](6_09_error_correcting_codes.md#609-error-correcting-codes)'s codes do the first.

## The cable

The second meaning is in the right panel. [6.07](6_07_ofdm.md#607-ofdm-the-triumph-of-physics-over-math) sounded the cable: 40 dB
against random noise alone, 30 dB counting everything the OFDM signal
suffered (quantization, the converters' distortion, a channel measured from
one noisy pilot), which over its 11.04 MHz is 111 Mbit/s. [QAM-64](https://en.wikipedia.org/wiki/Quadrature_amplitude_modulation) OFDM
carried 55.9 Mbit/s with no errors: half the cable. QPSK, the modem of
[6.02](6_02_psk_and_qpsk.md#602-psk-and-qpsk-finding-the-clock-and-the-carrier), carried 3.1 Mbit/s: 2.8% of the cable. Even inside its own 2.1 MHz, at
its own MER of 38 dB, it used 12% of the 27 Mbit/s Shannon allows there.
Three reasons, in order of size:

1. Two bits per symbol, where 38 dB of SNR would support twelve or
   thirteen (Shannon) or ten (uncoded 1024-QAM).
2. The roll-off of 0.35, which spends 2.1 MHz on 1.56 million symbols a
   second.
3. No code.

The 8 dB coding gap is the *smallest* of the three on this cable, which is
the opinionated point of the page: on a good channel the way toward
Shannon is more points first and a code second; in deep space, where the
SNR is a few dB, it is the other way round, and there the code is
everything.

<details>
<summary><b>Detail:</b> what 8-bit converters do to the SNR you quote</summary>

Three SNRs for one cable: 40 dB from the sounding (random noise only),
30 dB from the OFDM signal's EVM, 38 dB from QPSK's MER. They differ
because an 8-bit DAC's distortion depends on the signal: OFDM's peaks are
three or four times its rms ([6.04](6_04_msk_and_gmsk.md#604-msk-and-gmsk-constant-envelope)), so it either clips or uses fewer codes;
QPSK's are not. And the 38 dB is close to what the converters allow:
[6.02](6_02_psk_and_qpsk.md#602-psk-and-qpsk-finding-the-clock-and-the-carrier)'s
receiver reads 39 dB on the model, where the only noise is the model's
8 bits and 0.1 code, and 38.3 on the cable. With these
converters, "the capacity of the cable" is a number that depends on what
you send down it, and the honest figure gives three.

</details>

**Try this:**

- Bit-loading: from the per-subcarrier SNR in the right panel, give each
  subcarrier the largest constellation its own SNR allows, as DSL does, and
  add up the rate. How close to the 111 Mbit/s does it get?
- Voyager 1: 23 W into a 3.7 m dish, 24 billion kilometres, a 70 m dish at
  the other end with a 20 K receiver, 160 bits a second. Compute its
  *E*<sub>b</sub>/*N*<sub>0</sub> and see why it lives near the −1.59 dB corner, and why its
  modulation is a few points and a very good code ([6.09](6_09_error_correcting_codes.md#609-error-correcting-codes)).
- Put a 20 dB attenuator in the cable and sound it again (`ofdm.py --sound`):
  the capacity falls by about 20 dB × 11 MHz / 3 = 73 Mbit/s. Does it?
- `python3 ecc.py` through the cable, and compare its MER with [6.02](6_02_psk_and_qpsk.md#602-psk-and-qpsk-finding-the-clock-and-the-carrier)'s.
