#!/usr/bin/env python3
"""Measure the board's 50 MHz oscillator against the PC's (NTP-disciplined) clock.

Load tick.bit first, then:   python3 measure_osc.py [seconds] [port]   (default 720, /dev/ttyUSB0)

Each byte from tick.v marks 2^22 oscillator cycles.  A straight-line fit of
arrival time against cycle count gives the frequency; USB's ~1 ms jitter
averages out over minutes.  The PC clock's own error (a few tenths of a ppm
under NTP) is not included in the printed uncertainty.
"""
import sys
import time

import numpy as np
import serial

secs = float(sys.argv[1]) if len(sys.argv) > 1 else 720
port = sys.argv[2] if len(sys.argv) > 2 else "/dev/ttyUSB0"
ser = serial.Serial(port, 1000000, timeout=1)
try:
    ser.set_low_latency_mode(True)
except Exception as e:
    print("low-latency mode not available:", e)
ser.reset_input_buffer()
t0 = time.monotonic()
rows, last, n = [], None, 0
while time.monotonic() - t0 < secs:
    b = ser.read(1)
    if not b:
        continue
    t = time.monotonic()
    if last is not None:
        n += (b[0] - last) % 256        # counts any byte lost on the way
    last = b[0]
    rows.append((n, t))
k, t = np.array(rows).T
t -= t[0]
p = np.polyfit(k, t, 1)
r = t - np.polyval(p, k)
f = 2**22 / p[0]
se = r.std() / np.sqrt(((k - k.mean())**2).sum()) / p[0]
print("%d ticks over %.1f s, residual rms %.2f ms" % (len(k), t[-1], 1e3 * r.std()))
print("f = %.3f Hz  (%+.2f ppm, +/- %.2f ppm statistical)" % (f, (f / 50e6 - 1) * 1e6, se * 1e6))
