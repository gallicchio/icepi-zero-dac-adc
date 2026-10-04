#!/usr/bin/env python3
"""Instructor's check of the ADC/DAC under the SD-card Linux, on several boards at once.

    python3 adda_check.py SERIAL [SERIAL ...]

Logs in to each board's console, sets every DAC playing 1 MHz, then reads each lock-in
(as 8.6's sweep.sh does, for one point), takes one capture (dump.sh), and reports the
range of ADC codes.  A board looped back to itself reads its own
sine; two cross-connected boards each read the other's (the same 1 MHz, give or take a
crystal's ppm, which a 42 ms lock-in hardly notices); a board without a module reads ~0.
"""
import os
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from linux_shell import Shell

shells = {s: Shell("/dev/serial/by-id/usb-FTDI_FT231X_USB_UART_%s-if00-port0" % s, boot_timeout=30)
          for s in sys.argv[1:]}
res = {}
A = "/sys/bus/platform/devices/f0002000.adda"


def parallel(fn):
    threads = [threading.Thread(target=fn, args=(s, sh)) for s, sh in shells.items()]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def play(s, sh):                     # every DAC on first, so that each partner is playing
    sh.run("cd /root; echo 1000000 > %s/funcgen/frequency" % A)


def measure(s, sh):
    x, y = (float(v) for v in sh.run("cat %s/lockin/result" % A).split()[:2])
    volts = 2 * (x * x + y * y) ** 0.5 / 127 / 25.35          # sweep.sh's conversion
    codes = []
    for ln in sh.run("./dump.sh", 120).split():
        if len(ln) == 128:
            codes += [int(ln[i:i + 2], 16) for i in range(0, 128, 2)]
    res[s] = (volts, len(codes), min(codes) if codes else None, max(codes) if codes else None)


parallel(play)
parallel(measure)
for s in sys.argv[1:]:
    volts, n, lo, hi = res[s]
    print("%s: 1 MHz at the ADC: %.3f V   capture: %d samples, codes %s..%s" % (s, volts, n, lo, hi))
