#!/usr/bin/env python3
"""Analyse a lockin_log.py file: the phase of the other board's signal against this
board's own time, its slope (the beat between the two crystals), and what is left.

    python3 beat.py beat.npz
"""
import sys

import numpy as np

z = np.load(sys.argv[1])
f = float(z["f"])
T = 2**20 / 25e6 * int(z["every"]) if "every" in z.files else 2**20 / 25e6
#   one row, in this board's time: every result, or every `every`-th one
for name in [k for k in z.files if k.startswith("board")]:
    d = z[name]
    xy = d[:, 1] + 1j * d[:, 2]
    phase = np.unwrap(np.angle(xy))           # radians, of the other board's sine
    t = np.arange(len(phase)) * T
    slope, _ = np.polyfit(t, phase, 1)
    beat = slope / (2 * np.pi)                # Hz: f_other - f_this, in this board's units
    rest = phase - np.polyval(np.polyfit(t, phase, 1), t)
    volts = abs(xy) * 2 / 127 / 25.35         # 1.08's conversion to volts at the ADC
    print("%s: %d points over %.0f s; beat %+.6f Hz = %+.4f ppm of %.0f Hz; amplitude %.3f V; "
          "phase residual %.2f deg rms" % (name, len(t), t[-1], beat, beat / f * 1e6, f,
                                          volts.mean(), np.degrees(rest.std())))
