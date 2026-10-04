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
