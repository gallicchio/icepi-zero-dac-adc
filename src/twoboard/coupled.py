#!/usr/bin/env python3
"""Two coupled oscillators: each board's lockin.sv is an oscillator (its DDS) and a phase
meter (its lock-in sees the OTHER board's sine).  Every 42 ms the laptop reads both phases
and sets each frequency to

    f_i = f0 + detune_i + K_i * sin(phi_i - c/2)        (Hz)

where phi_i is the phase of the other board's signal relative to board i's own, and
c = phi_A + phi_B is the round-trip phase (cable and converter delays, both ways).
c does not depend on the oscillators' phases at all, so it can be measured all along;
subtracting half of it from each side makes the coupling symmetric, as in Adler's
equation (without it, the delays would scale the coupling by cos(c/2)).
K_A = 0, K_B > 0 is a phase-locked loop (B follows A).  K_A = K_B > 0 is mutual
coupling (Kuramoto / Adler): the two lock when |natural detuning| < K_A + K_B.

    python3 coupled.py PORT_A PORT_B --KA 0.5 --KB 0.5 --seconds 60 [--detune 0.3] -o out.npz
"""
import argparse
import threading
import time

import numpy as np
import serial

F_CLK = 50e6


def tw(f):
    return int(round(f / F_CLK * 2**32)) & 0xFFFFFFFF


def s32(v):
    return v - (1 << 32) if v & (1 << 31) else v


class Board:
    def __init__(self, port):
        self.s = serial.Serial(port, 1_000_000, timeout=1)
        time.sleep(0.05)
        self.s.reset_input_buffer()
        self.tw = None

    def set(self, f):
        self.tw = tw(f)
        self.s.write(b"%08x\n" % self.tw)

    def result(self):
        """The next complete average taken with the current tuning word."""
        while True:
            p = self.s.readline().split()
            if len(p) != 3:
                continue
            try:
                t, x, y = (int(v, 16) for v in p)
            except ValueError:
                continue
            if t == self.tw:
                return complex(s32(x), s32(y)) / 65536


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("port_a"); ap.add_argument("port_b")
    ap.add_argument("--f0", type=float, default=1e6)
    ap.add_argument("--KA", type=float, default=0.0)
    ap.add_argument("--KB", type=float, default=0.5)
    ap.add_argument("--detune", type=float, default=0.0, help="added to B's frequency, Hz")
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("-o", "--out", default="coupled.npz")
    a = ap.parse_args()
    A, B = Board(a.port_a), Board(a.port_b)
    fa, fb = a.f0, a.f0 + a.detune
    A.set(fa); B.set(fb)
    rows = []; t0 = time.time(); csum = 1
    while time.time() - t0 < a.seconds:
        res = {}
        th = [threading.Thread(target=lambda n, b: res.__setitem__(n, b.result()), args=(n, b)) for n, b in (("A", A), ("B", B))]
        for t in th: t.start()
        for t in th: t.join()
        pa, pb = np.angle(res["A"]), np.angle(res["B"])
        csum = 0.9 * csum + 0.1 * np.exp(1j * (pa + pb)) if rows else np.exp(1j * (pa + pb))
        half = np.angle(csum) / 2
        fa = a.f0 + a.KA * np.sin(pa - half)
        fb = a.f0 + a.detune + a.KB * np.sin(pb - half)
        A.set(fa); B.set(fb)
        rows.append((time.time() - t0, pa, pb, abs(res["A"]), abs(res["B"]), fa, fb))
    np.savez(a.out, rows=np.array(rows), KA=a.KA, KB=a.KB, detune=a.detune, f0=a.f0)
    r = np.array(rows)
    print("%d updates in %.1f s; final half: phi_A %.1f +- %.1f deg, phi_B %.1f +- %.1f deg; f_B - f_A %.4f Hz" %
          (len(r), r[-1, 0], np.degrees(np.mean(r[len(r)//2:, 1])), np.degrees(np.std(np.unwrap(r[len(r)//2:, 1]))),
           np.degrees(np.mean(r[len(r)//2:, 2])), np.degrees(np.std(np.unwrap(r[len(r)//2:, 2]))), np.mean(r[len(r)//2:, 6] - r[len(r)//2:, 5])))
