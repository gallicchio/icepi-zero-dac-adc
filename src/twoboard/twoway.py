#!/usr/bin/env python3
"""Two-way time transfer between two boards running awgcap.sv, cross-connected.

    python3 twoway.py PORT_A PORT_B [--seconds 120] [-o out.npz]

Each board loops its own noise-like waveform (a random-phase multitone, 0.2-10 MHz)
and records the other's.  From each record, the delay of the other board's waveform
relative to THIS board's loop start:

    tau_A = theta + d_BA        tau_B = -theta + d_AB        (mod one loop, 327.68 us)

theta = how far B's loop start is behind A's (the clock offset), d = the one-way
delays.  So tau_A + tau_B = d_AB + d_BA, the round trip, whatever the clocks do, and
(tau_A - tau_B)/2 = theta if the two delays are equal (Einstein's convention).
"""
import argparse
import time

import numpy as np

import awgcap

N, P = awgcap.N, awgcap.N / awgcap.FS_DAC          # one loop: 327.68 us


def multitone(seed, fmin=0.2e6, fmax=10e6):
    """A real waveform, periodic in N samples at 50 MS/s, with flat spectrum fmin..fmax."""
    rng = np.random.default_rng(seed)
    X = np.zeros(N // 2 + 1, complex)
    k = np.arange(len(X)); f = k * awgcap.FS_DAC / N
    band = (f >= fmin) & (f <= fmax)
    X[band] = np.exp(2j * np.pi * rng.random(band.sum()))
    x = np.fft.irfft(X, N)
    return 128 + 100 * x / np.abs(x).max()


def delay(record, wave, fmin=0.3e6, fmax=9.5e6):
    """Delay (s, mod one loop) of `wave` (as played at 50 MS/s) inside `record` (25 MS/s,
    starting at this board's loop start).  The record holds exactly two loops: average them,
    then fit the cross-spectrum's phase against frequency -- coarse lag from the
    correlation peak, fine lag from the slope."""
    r = record.reshape(2, N // 2).mean(0); r = r - r.mean()
    w = wave[::2] - wave.mean()                     # the waveform at 25 MS/s
    R, W = np.fft.rfft(r), np.fft.rfft(w)
    C = R * np.conj(W)
    lag0 = np.argmax(np.fft.irfft(C, N // 2))      # integer samples at 25 MS/s
    f = np.fft.rfftfreq(N // 2, 1 / awgcap.FS_ADC)
    band = (f >= fmin) & (f <= fmax)
    ph = np.unwrap(np.angle(C[band] * np.exp(2j * np.pi * f[band] * lag0 / awgcap.FS_ADC)))
    slope = np.polyfit(f[band], ph, 1)[0]
    return (lag0 / awgcap.FS_ADC - slope / (2 * np.pi)) % P


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("port_a"); ap.add_argument("port_b")
    ap.add_argument("--seconds", type=float, default=120)
    ap.add_argument("-o", "--out", default="twoway.npz")
    a = ap.parse_args()
    wa, wb = multitone(1), multitone(2)
    awgcap.upload(a.port_a, wa); awgcap.upload(a.port_b, wb)
    rows = []; t0 = time.time()
    while time.time() - t0 < a.seconds:
        ra, rb = awgcap.record_many([a.port_a, a.port_b])
        ta, tb = delay(ra, wb), delay(rb, wa)
        rows.append((time.time() - t0, ta, tb))
        print("%7.2f s  tau_A %10.3f ns  tau_B %10.3f ns  sum %9.3f ns" %
              (rows[-1][0], ta * 1e9, tb * 1e9, ((ta + tb) % P) * 1e9), flush=True)
    np.savez(a.out, rows=np.array(rows), wa=wa, wb=wb)
