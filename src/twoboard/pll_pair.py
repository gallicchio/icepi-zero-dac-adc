#!/usr/bin/env python3
"""Discipline one board's oscillator to another's, in hardware.

    python3 pll_pair.py PORT_A PORT_B --open 20 --closed 40 -o pll_pair.npz

A runs lockin.sv at 1 MHz: it plays A's sine and measures whatever comes back.
B runs pll.sv with its DAC playing its own oscillator (command L), locked to A's sine.
With B's loop open, A sees B's free-running crystal: a beat.  Closed, B sends A's
own frequency back, and the beat stops.
"""
import argparse
import threading
import time

import numpy as np
import serial


def tw(f):
    return int(round(f / 50e6 * 2**32))


def s32(v):
    return v - (1 << 32) if v & (1 << 31) else v


ap = argparse.ArgumentParser()
ap.add_argument("port_a")
ap.add_argument("port_b")
ap.add_argument("--open", type=float, default=20, help="seconds with B's loop open")
ap.add_argument("--closed", type=float, default=40, help="then seconds with it closed")
ap.add_argument("-o", "--out", default="pll_pair.npz")
a = ap.parse_args()

A = serial.Serial(a.port_a, 1_000_000, timeout=1)
B = serial.Serial(a.port_b, 1_000_000, timeout=1)
time.sleep(0.05)
A.reset_input_buffer()
B.reset_input_buffer()
TW = tw(1e6)
A.write(b"%08x\n" % TW)                            # A: lock-in at 1 MHz
for c in ("O", "F%08x\n" % TW, "L"):               # B: loop open, centre 1 MHz, play the oscillator
    B.write(c.encode())
    time.sleep(0.02)

LA, LB = [], []
t0 = time.time()
stop = False


def read_a():                                      # A's lock-in: B's sine, as A sees it
    while not stop:
        p = A.readline().split()
        if len(p) != 3:
            continue
        try:
            t, x, y = (int(v, 16) for v in p)
        except ValueError:
            continue
        if t == TW:
            LA.append((time.time() - t0, s32(x), s32(y)))


def read_b():                                      # B's PLL: its correction, I and Q
    while not stop:
        p = B.readline().split()
        if len(p) != 3:
            continue
        try:
            LB.append((time.time() - t0, (int(p[0], 16) - TW) * 50e6 / 2**32,
                       s32(int(p[1], 16)), s32(int(p[2], 16))))
        except ValueError:
            pass


threads = [threading.Thread(target=read_a), threading.Thread(target=read_b)]
for t in threads:
    t.start()
time.sleep(a.open)
B.write(b"C")                                      # close B's loop
t_close = time.time() - t0
time.sleep(a.closed)
stop = True
for t in threads:
    t.join()

LA, LB = np.array(LA), np.array(LB)
np.savez(a.out, A=LA, B=LB, t_close=t_close)
phase = np.unwrap(np.angle(LA[:, 1] + 1j * LA[:, 2])) / (2 * np.pi)      # turns
for name, sel in (("open", LA[:, 0] < t_close - 1), ("closed (last 20 s)", LA[:, 0] > LA[-1, 0] - 20)):
    p = np.polyfit(LA[sel, 0], phase[sel], 1)
    rest = (phase[sel] - np.polyval(p, LA[sel, 0])) * 360
    print("%-20s A sees B's sine turning at %+.5f Hz; phase scatter %.3f deg rms" % (name, p[0], rest.std()))
locked = LB[:, 0] > LB[-1, 0] - 20
print("B's correction when locked: %+.4f Hz (= A's crystal minus B's, at 1 MHz)" % LB[locked, 1].mean())
