#!/usr/bin/env python3
"""Drive pll.sv: set it up, close the loop, and print what it reports.

    python3 pll_test.py PORT --test-offset 100        # one board looped back: lock to a test tone 100 Hz off
    python3 pll_test.py PORT --seconds 60 -o pll.npz  # follow whatever arrives (another board)
"""
import argparse
import time

import numpy as np
import serial


def tw(f):
    return int(round(f / 50e6 * 2**32))


def s32(v):
    return v - (1 << 32) if v & (1 << 31) else v


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("port")
    ap.add_argument("--f0", type=float, default=1e6, help="centre frequency (Hz)")
    ap.add_argument("--test-offset", type=float, help="play a test tone this far from f0, and lock to it")
    ap.add_argument("--seconds", type=float, default=3)
    ap.add_argument("-o", "--out")
    a = ap.parse_args()

    s = serial.Serial(a.port, 1_000_000, timeout=1)
    time.sleep(0.05)
    commands = ["O", "F%08x\n" % tw(a.f0)]               # open the loop, set the centre
    if a.test_offset is not None:
        commands += ["T%08x\n" % tw(a.f0 + a.test_offset), "X"]   # the DAC plays a test tone
    else:
        commands += ["L"]                                  # the DAC plays the oscillator
    commands += ["C"]                                      # close the loop
    for c in commands:
        s.write(c.encode())
        time.sleep(0.02)

    s.reset_input_buffer()
    s.readline()                                           # drop a partial line
    rows = []
    t0 = time.time()
    while time.time() - t0 < a.seconds:
        p = s.readline().split()
        if len(p) != 3:
            continue
        t, i, q = int(p[0], 16), s32(int(p[1], 16)), s32(int(p[2], 16))
        rows.append((time.time() - t0, (t - tw(a.f0)) * 50e6 / 2**32, i, q))
        print("%6.2f s  oscillator %+10.4f Hz from f0   I %9d  Q %8d  phase error %+7.3f deg" %
              (rows[-1][0], rows[-1][1], i, q, np.degrees(np.arctan2(q, i))), flush=True)
    if a.out:
        np.savez(a.out, rows=np.array(rows), f0=a.f0)
