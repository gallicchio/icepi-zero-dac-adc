#!/usr/bin/env python3
"""4.06: the ultrasonic pair's frequency response, measured with lockin.sv (1.08).

    python3 sweep.py 37e3 43e3                  # 20 Hz steps; plots amplitude and phase
    python3 sweep.py 30e3 64e3 --step 10 -o pair.npz    # and save it
    python3 sweep.py --watch 40.3e3 --seconds 60        # one frequency against time
    python3 sweep.py --impulse pair.npz         # the impulse response from a saved sweep

lockin.bit must be loaded.  Each point is two 42 ms averages, of which only the
second is kept: the transducers ring for a millisecond or so after the frequency
changes, and the first average would still hear the last frequency.

The impulse response is the inverse Fourier transform of the sweep.  Only positive
frequencies were measured, so the transform gives the *analytic* impulse response,
whose magnitude is the envelope of h(t): when the sound arrives, and how long it rings.
"""
import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "verilog"))
import lockin                                   # noqa: E402  (1.08's laptop side)


def sweep(li, freqs, quiet=False):
    """Complex response (volts at the ADC) at each frequency, settled."""
    z = np.zeros(len(freqs), complex)
    for i, f in enumerate(freqs):
        li.measure(f)                           # let the transducers settle...
        f_used, z[i] = li.measure(f)            # ...then keep this one
        freqs[i] = f_used
        if not quiet and i % 25 == 0:
            print(f"{f_used:10.1f} Hz  {abs(z[i]) * 1e3:9.3f} mV  {np.degrees(np.angle(z[i])):8.1f} deg")
    return freqs, z


def impulse(f, z, fs_out=None):
    """The analytic impulse response from a sweep on a uniform grid of step df: a
    Hann window over the band (to keep the sidelobes down), then an inverse FFT.
    Returns t (s) and h (complex; |h| is the envelope)."""
    df = f[1] - f[0]
    n = int(2 ** np.ceil(np.log2(4 * len(f))))     # zero-padded: a smooth envelope
    w = np.hanning(len(f))
    spec = np.zeros(n, complex)
    k0 = int(round(f[0] / df))
    spec[:len(f)] = z * w
    h = np.fft.ifft(spec) * n
    t = np.arange(n) / (n * df)
    # the grid started at f[0], not 0: shift it back up, which only turns the phase
    h = h * np.exp(2j * np.pi * k0 * df * t)
    return t, h / w.sum()


def group_delay(f, z):
    return -np.gradient(np.unwrap(np.angle(z)), 2 * np.pi * f)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("band", nargs="*", type=float, help="FMIN FMAX in Hz")
    ap.add_argument("--step", type=float, default=20.0, help="Hz between points")
    ap.add_argument("-o", "--out", help="save f, z (complex volts) and the time as .npz")
    ap.add_argument("--watch", type=float, help="measure this one frequency over and over")
    ap.add_argument("--seconds", type=float, default=30.0, help="how long to --watch")
    ap.add_argument("--impulse", help="plot the impulse response of a saved sweep")
    ap.add_argument("--port")
    ap.add_argument("--no-plot", action="store_true")
    a = ap.parse_args()

    if a.impulse:
        d = np.load(a.impulse)
        t, h = impulse(d["f"], d["z"])
        k = np.argmax(abs(h))
        print(f"envelope peaks at {t[k] * 1e6:.0f} us")
        if not a.no_plot:
            import matplotlib.pyplot as plt
            plt.plot(t * 1e3, abs(h))
            plt.xlim(0, 5); plt.xlabel("time (ms)"); plt.ylabel("|h(t)|")
            plt.show()
        sys.exit()

    li = lockin.LockIn(a.port)
    if a.watch:
        rows = []
        t0 = time.time()
        while time.time() - t0 < a.seconds:
            f, z = li.measure(a.watch)
            rows.append((time.time() - t0, z))
            print(f"{rows[-1][0]:7.2f} s  {abs(z) * 1e3:9.3f} mV  {np.degrees(np.angle(z)):8.2f} deg")
        t = np.array([r[0] for r in rows]); z = np.array([r[1] for r in rows])
        if a.out:
            np.savez(a.out, t=t, z=z, f=a.watch)
        sys.exit()

    if len(a.band) != 2:
        ap.error("give FMIN FMAX, or --watch F, or --impulse FILE")
    freqs = np.arange(a.band[0], a.band[1] + a.step / 2, a.step)
    t_start = time.time()
    f, z = sweep(li, freqs)
    print(f"{len(f)} points in {time.time() - t_start:.0f} s")
    k = np.argmax(abs(z))
    print(f"peak {abs(z[k]) * 1e3:.1f} mV at {f[k]:.0f} Hz; "
          f"group delay there {group_delay(f, z)[k] * 1e6:.0f} us")
    if a.out:
        np.savez(a.out, f=f, z=z, when=time.strftime("%Y-%m-%d %H:%M"))
    if not a.no_plot:
        import matplotlib.pyplot as plt
        fig, (p, q) = plt.subplots(2, 1, sharex=True)
        p.plot(f / 1e3, 20 * np.log10(abs(z))); p.set_ylabel("dB re 1 V")
        q.plot(f / 1e3, group_delay(f, z) * 1e6); q.set_ylabel("group delay (us)")
        q.set_xlabel("frequency (kHz)")
        plt.show()
