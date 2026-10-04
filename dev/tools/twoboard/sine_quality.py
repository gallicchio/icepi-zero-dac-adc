"""Instructor's check of each DAC -> ADC path with a sine: amplitude, harmonics, noise.
Every module board runs probe_<f>.bit (the tutorial's sine.sv on the DAC, capture.sv on the ADC).
Board clocks differ, so the analysis uses a 4-parameter sine fit and a Blackman-Harris window.

    python3 sine_quality.py JLC1 JLC2 JLC3      (records each board's ADC 4 times)
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import boards
fs = 25e6
def fit(y, f0):
    t = np.arange(len(y)) / fs; f = f0
    for _ in range(8):
        M = np.column_stack([np.cos(2*np.pi*f*t), np.sin(2*np.pi*f*t), np.ones_like(t)])
        a, b, c = np.linalg.lstsq(M, y, rcond=None)[0]; A = np.hypot(a, b); ph = np.arctan2(-b, a)
        J = np.column_stack([M, -2*np.pi*t*A*np.sin(2*np.pi*f*t + ph)])
        f += np.linalg.lstsq(J, y, rcond=None)[0][3]
    M = np.column_stack([np.cos(2*np.pi*f*t), np.sin(2*np.pi*f*t), np.ones_like(t)])
    p = np.linalg.lstsq(M, y, rcond=None)[0]
    return f, np.hypot(p[0], p[1]), y - M @ p
def harm(y, f):
    w = np.blackman(len(y)); Y = np.abs(np.fft.rfft((y - y.mean()) * w)); fr = np.fft.rfftfreq(len(y), 1/fs)
    pk = lambda g: Y[max(0, np.argmin(abs(fr - abs(((g + fs/2) % fs) - fs/2))) - 3):np.argmin(abs(fr - abs(((g + fs/2) % fs) - fs/2))) + 4].max()
    p1 = pk(f); return [20*np.log10(pk(k*f)/p1) for k in (2, 3, 4, 5)]
if __name__ == "__main__":
    for n in sys.argv[1:]:
        caps = [boards.capture(n)[1].astype(float) for _ in range(4)]
        res = [fit(c, 1.3e6) for c in caps]
        f = np.mean([r[0] for r in res]); A = np.mean([r[1] for r in res])
        h = np.mean([harm(c, r[0]) for c, r in zip(caps, res)], axis=0)
        rr = np.mean([r[2].std() for r in res])
        sinad = 10*np.log10(A**2/2/rr**2)
        print("%s ADC: %.3f Hz, %.2f codes amplitude, harmonics 2-5: %s dBc, residual %.2f codes rms, SINAD %.1f dB" %
              (n, f, A, " ".join("%.1f" % x for x in h), rr, sinad))
