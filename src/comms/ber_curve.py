#!/usr/bin/env python3
"""Bit error rate against signal-to-noise ratio for OFDM with QAM, by adding known
noise to the transmitted symbols.  Compares with the textbook curve for Gray-coded
square M-QAM.

    python3 ber_curve.py -o ber.npz                 # one board looped back
    python3 ber_curve.py PORT_A PORT_B -o ber.npz   # two boards
"""
import argparse
import numpy as np
from math import erfc, sqrt
import ofdm


def ber_theory(M, snr):
    """Gray-coded square M-QAM in white noise; snr = Es/N0 per symbol (linear)."""
    k = np.log2(M); m = sqrt(M)
    return 4 / k * (1 - 1 / m) * 0.5 * np.array([erfc(sqrt(3 * s / (2 * (M - 1)))) for s in np.atleast_1d(snr)])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("ports", nargs="*")
    ap.add_argument("--sim", action="store_true")
    ap.add_argument("--records", type=int, default=4)
    ap.add_argument("-o", "--out", default="ber.npz")
    a = ap.parse_args()
    play, record = ofdm.make_link(a.ports, a.sim)
    rows = []
    for M in (4, 16, 64):
        for nz in (0.0, 0.05, 0.08, 0.12, 0.18, 0.25, 0.35, 0.5, 0.7):
            wave, pilot, bits, x = ofdm.frame(M, noise=nz)
            play(wave)
            errs = nb = 0; ev = []
            for _ in range(a.records):
                for e, evm, Z in ofdm.demod(record(), M, pilot, bits, x):
                    errs += e; nb += len(bits); ev.append(evm)
            evm = np.sqrt(np.mean(np.array(ev)**2))
            snr = 1 / evm**2                       # measured Es/N0, everything included
            rows.append((M, nz, snr, errs, nb))
            print("QAM-%-3d added noise %.2f: SNR %5.1f dB, BER %.2e (%d/%d), theory at that SNR %.2e" %
                  (M, nz, 10 * np.log10(snr), errs / nb, errs, nb, ber_theory(M, snr)[0]), flush=True)
    np.savez(a.out, rows=np.array(rows))
