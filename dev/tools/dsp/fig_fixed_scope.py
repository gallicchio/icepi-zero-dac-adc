#!/usr/bin/env python3
"""Chapter 7 figures: the fixed filters of fir.sv (dsp_fixed_scope.png, 7.01) and iir.sv
(dsp_iir_scope.png, 7.02) on the oscilloscope.

    python3 fig_fixed_scope.py            # from dev/data/dsp_scope_*.npz (recorded by the M2k)

A 300 kHz, 1 V square wave from the ADALM2000's W1 into ADC IN; DAC OUT on the scope,
with each fixed bitstream loaded in turn: fir_set0 (a 16-sample moving average),
fir_set1 (the 15-tap windowed-sinc low-pass at 2 MHz), fir_set2 (the edge detector
[-1 2 -1]) and iir_k4 (the one-pole y += (x - y)/16).  Measured, M2k.
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from plotstyle import plt, save, C1, C2, C3, INK, INK2, MUTED   # noqa: E402

TOP = os.path.join(HERE, "..", "..", "..")
cases = [("fir_set0", "16-sample moving average (fir_set0): the edges become 640 ns ramps", C1),
         ("fir_set1", "windowed-sinc low-pass, 2 MHz (fir_set1): rounded, with a little ring", C2),
         ("fir_set2", "edge detector [-1 2 -1] (fir_set2): only the edges come out, both signs", C3),
         ("iir_k4", "one-pole y += (x - y)/16 (iir_k4): an RC's exponential, tau = 640 ns", INK2)]


def draw(cases, figsize, name):
    fig, ax = plt.subplots(len(cases), 1, figsize=figsize, sharex=True, squeeze=False)
    ax = ax[:, 0]
    for A, (bit, title, c) in zip(ax, cases):
        d = np.load(os.path.join(TOP, "dev", "data", "dsp_scope_%s.npz" % bit))
        t, v = d["t"] * 1e6, d["v"]
        # centre the window on a rising edge of the square wave's period (3.33 us)
        per = 1e6 / float(d["f"])
        i0 = int(np.argmax(np.diff(v[: int(2 * per * 100)]))) if bit != "fir_set2" else int(np.argmax(v[: int(2 * per * 100)]))
        A.plot(t - t[i0], v, color=c, lw=1.0)
        A.set_xlim(-1.0, 2 * per - 1.0)
        A.set_ylabel("DAC OUT (V)")
        A.set_title(title, loc="left", fontweight="bold", fontsize=10)
        A.axhline(0, color=MUTED, lw=0.5)
    ax[-1].set_xlabel("time (µs): a 300 kHz, 1 V square wave into ADC IN")
    fig.suptitle("measured, M2k: W1 -> ADC IN, DAC OUT -> scope 1; each filter a bitstream of its own", x=0.99,
                 ha="right", fontsize=8, color=MUTED)
    save(fig, os.path.join(TOP, "tutorial", "img", name))
    print("wrote tutorial/img/" + name)


draw(cases[:3], (11, 7.6), "dsp_fixed_scope.png")       # 7.01: the three FIRs
draw(cases[3:], (11, 3.0), "dsp_iir_scope.png")         # 7.02: the one-pole
