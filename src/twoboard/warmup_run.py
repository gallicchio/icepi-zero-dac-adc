#!/usr/bin/env python3
"""Warm one board with its own logic while another board's lock-in follows its crystal.

    python3 warmup_run.py HEATER_PORT LOCKIN_PORT --on 600 --off 1500 --end 2700 -o warm.npz

HEATER board: warmup.bit (1 MHz sine, heater, thermometer).  LOCKIN board: lockin.bit,
set to 1 MHz.  The lock-in's phase drifts at f_heater - f_lockin, so its slope is the
heater board's crystal frequency relative to the lock-in board's.
"""
import argparse
import threading
import time

import numpy as np
import serial


def s32(v):
    return v - (1 << 32) if v & (1 << 31) else v


ap = argparse.ArgumentParser()
ap.add_argument("heater")
ap.add_argument("lockin")
ap.add_argument("--on", type=float, default=600, help="heater on at this time (s)")
ap.add_argument("--off", type=float, default=1500, help="heater off at this time (s)")
ap.add_argument("--end", type=float, default=2700, help="stop recording (s)")
ap.add_argument("-o", "--out", default="warm.npz")
a = ap.parse_args()

TW = int(round(1e6 / 50e6 * 2**32))                 # 1 MHz
li = serial.Serial(a.lockin, 1_000_000, timeout=1)
hs = serial.Serial(a.heater, 1_000_000, timeout=1)
time.sleep(0.05)
li.reset_input_buffer()
hs.reset_input_buffer()
li.write(b"%08x\n" % TW)
hs.write(b"C")                                      # start with the heater off

L, H = [], []                                       # lock-in results; heater reports
t0 = time.time()
stop = False


def read_lockin():
    while not stop:
        p = li.readline().split()
        if len(p) != 3:
            continue
        try:
            t, x, y = (int(v, 16) for v in p)
        except ValueError:
            continue
        if t == TW:
            L.append((time.time() - t0, s32(x) / 65536, s32(y) / 65536))


def read_heater():
    while not stop:
        p = hs.readline().split()               # "TT h": DTR code (hex), heater on/off
        if len(p) != 2:
            continue
        try:
            H.append((time.time() - t0, int(p[0], 16), int(p[1])))
        except ValueError:
            pass


threads = [threading.Thread(target=read_lockin), threading.Thread(target=read_heater)]
for t in threads:
    t.start()
state = "cold"
while time.time() - t0 < a.end:
    t = time.time() - t0
    if state == "cold" and t > a.on:
        hs.write(b"H")
        state = "hot"
        print("%.0f s heater on" % t, flush=True)
    if state == "hot" and t > a.off:
        hs.write(b"C")
        state = "cooling"
        print("%.0f s heater off" % t, flush=True)
    time.sleep(0.5)
    if int(t) % 60 == 0 and L and H:                # a progress line once a minute
        print("%5.0f s  %d lock-in points, DTR code %d (%s)" %
              (t, len(L), H[-1][1] & 63, "on" if H[-1][2] else "off"), flush=True)
        time.sleep(0.6)
stop = True
for t in threads:
    t.join()
hs.write(b"C")
np.savez(a.out, lockin=np.array(L), heater=np.array(H), on=a.on, off=a.off)
