#!/usr/bin/env python3
"""The AMOD-P board's passive tiles, measured: a lock-in swept in frequency is a network analyzer.

    make load-lockin2                  # ECP5-2ADC-2DAC: lockin2.bit
    python3 amodp.py p0                # the through: a barrel joining the two cables, the calibration
    python3 amodp.py p1                # a tile: DAC 1 -> the tile's IN, its OUT -> ADC A; divided by p0

The same file sits in the Icepi Zero tutorial (with lockin_half.bit there); the board decides which lock-in it uses.
Each sweep is 121 frequencies from 1 kHz to 12 MHz, log spaced, two 42 ms averages each.  The lock-in gives the ADC's
complex amplitude against the DAC's own oscillator, so the phase is absolute up to a fixed delay that p0 measures and
the division removes, along with both cables, the DAC's and the ADC's response and their different volts per code.
Saved in ../../dev/data/amodp/: <board>_<tile>.npz (f, z at the ADC, and h = z / z of p0) and <board>_<tile>.png.
"""
import argparse
import glob
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "../../dev/data/amodp"))
FREQS = np.geomspace(1e3, 12e6, 121)
TILES = {"p0": "through (a barrel): the calibration", "p1": "pi pad, -20 dB", "p2": "RC low-pass, 159 kHz",
         "p3": "RC high-pass, 159 kHz", "p4": "series RLC, 100 uH 220 pF", "p5": "LC low-pass, 9 MHz",
         "p6": "LC low-pass, 100 kHz", "p7": "band-pass, 4.7-7.5 MHz", "p8": "quartz crystal, 4 MHz",
         "p9": "ceramic resonator, 455 kHz", "p10": "clipper, 1N4148 +-0.6 V", "p11": "delay line, 400 ns",
         "p12": "LEDs", "p13": "AM loopstick, 0.5-1.7 MHz"}


class Ecp5:
    name, label = "ecp5", "ECP5-2ADC-2DAC board A: DAC 1 -> tile -> ADC A (50 ohm)"

    def open(self):                          # after any load: a port opened before it may be stale
        sys.path.insert(0, HERE)
        import lockin2
        import serial
        self.li = lockin2
        self.ser = serial.Serial(lockin2.find_port(), 1_000_000, timeout=0.2)
        time.sleep(0.1)
        self.ser.reset_input_buffer()

    def load(self):
        subprocess.run(["make", "-C", HERE, "load-lockin2"], capture_output=True)
        time.sleep(1)

    def measure(self, f):
        fa, za, zb = self.li.measure(self.ser, f, averages=2)
        return fa, za


class Icepi:
    name, label = "icepi", "Icepi Zero DK0GFLAW: DAC OUT -> tile -> ADC IN (high impedance), +-1.95 V"
    SERIAL = "DK0GFLAW"

    def open(self):                          # the FT231X programs the FPGA too: open the port after loading
        sys.path.insert(0, HERE)
        import lockin
        port = glob.glob("/dev/serial/by-id/usb-FTDI_FT231X_USB_UART_%s-if00-port0" % self.SERIAL)
        self.li = lockin.LockIn(port[0] if port else None)

    def load(self):
        subprocess.run(["openFPGALoader", "-b", "icepi-zero", "--usb-serial-num", self.SERIAL,
                        os.path.join(HERE, "lockin_half.bit")], capture_output=True)
        time.sleep(1)

    def measure(self, f):
        return self.li.measure(f, 2)


def board():
    return Ecp5() if os.path.exists(os.path.join(HERE, "lockin2.sv")) else Icepi()


def sweep(b):
    fs, zs = [], []
    for f in FREQS:
        for attempt in range(2):
            try:
                fa, z = b.measure(f)
                break
            except (RuntimeError, ValueError, OSError) as e:
                if attempt:
                    raise
                print("%s: reloading the lock-in" % e, flush=True)
                b.load(); b.open()
        fs.append(fa); zs.append(z)
    return np.array(fs), np.array(zs)


def summary(f, h, tile):
    db = 20 * np.log10(np.abs(h))
    ph = np.degrees(np.unwrap(np.angle(h)))
    out = []
    for fq in (1e4, 1e5, 1e6, 1e7):
        i = np.argmin(np.abs(f - fq))
        out.append("%s %+.1f dB %+.0f deg" % (("%g kHz" % (fq / 1e3)) if fq < 1e6 else ("%g MHz" % (fq / 1e6)), db[i], ph[i]))
    i = np.argmax(db)
    s = "; ".join(out) + "; max %+.1f dB at %.3g Hz" % (db[i], f[i])
    below = np.flatnonzero(db < db[i] - 3)
    lo, hi = below[below < i], below[below > i]
    if len(hi):
        s += "; -3 dB above it at %.3g Hz" % f[hi[0]]
    if len(lo):
        s += "; -3 dB below it at %.3g Hz" % f[lo[-1]]
    return s


def plot(path, f, h, tile, label, raw=False):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(9, 6.5), sharex=True)
    a1.semilogx(f, 20 * np.log10(np.abs(h)), "o-", ms=2.5, lw=1)
    a1.set_ylabel("gain (dB)" + (", from its value at 1 kHz" if raw else ", over p0's"))
    a1.grid(alpha=0.3, which="both")
    a2.semilogx(f, np.degrees(np.unwrap(np.angle(h))), "o-", ms=2.5, lw=1)
    a2.set_ylabel("phase (degrees)"); a2.set_xlabel("frequency (Hz)"); a2.grid(alpha=0.3, which="both")
    a1.set_title("AMOD-P %s, %s\n%s, %s" % (tile, TILES.get(tile, ""), label, time.strftime("%Y-%m-%d %H:%M")), fontsize=10)
    fig.tight_layout(); fig.savefig(path, dpi=100); plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tile", help="p0 (the through) .. p13")
    ap.add_argument("--load", action="store_true", help="load the lock-in's bitstream first")
    a = ap.parse_args()
    os.makedirs(DATA, exist_ok=True)
    b = board()
    if a.load:
        b.load()
    b.open()
    t0 = time.time()
    f, z = sweep(b)
    base = os.path.join(DATA, "%s_%s" % (b.name, a.tile))
    p0 = os.path.join(DATA, "%s_p0.npz" % b.name)
    if a.tile == "p0":
        h = z / z[0]
        np.savez(base + ".npz", f=f, z=z, h=h, tile=a.tile, label=b.label, t=time.strftime("%Y-%m-%d %H:%M:%S"))
        plot(base + ".png", f, h, a.tile, b.label, raw=True)
        hi = f > 1e6
        slope = np.polyfit(f[hi], np.unwrap(np.angle(z[hi])), 1)[0]
        print("%s p0: %.0f s; |z| at 1 kHz %.4g; %s; the chain's delay (phase slope above 1 MHz) %.1f ns"
              % (b.name, time.time() - t0, abs(z[0]), summary(f, h, a.tile), -slope / (2 * np.pi) * 1e9))
    else:
        d0 = np.load(p0)
        h = z / d0["z"]
        np.savez(base + ".npz", f=f, z=z, h=h, tile=a.tile, label=b.label, t=time.strftime("%Y-%m-%d %H:%M:%S"))
        plot(base + ".png", f, h, a.tile, b.label)
        print("%s %s: %.0f s; %s" % (b.name, a.tile, time.time() - t0, summary(f, h, a.tile)))


if __name__ == "__main__":
    main()
