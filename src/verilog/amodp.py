#!/usr/bin/env python3
"""The AMOD-P board's passive tiles, measured: a lock-in swept in frequency is a network analyzer.

    make load-lockin2                  # ECP5-2ADC-2DAC: lockin2.bit
    python3 amodp.py p0                # the through: a barrel joining the two cables, the calibration
    python3 amodp.py p1                # a tile: DAC 1 -> the tile's IN, its OUT -> ADC A; divided by p0
    python3 amodp.py p4-12             # p4 with both DIP switches on (p4, p4-1, p4-2, p4-12)

The same file sits in the Icepi Zero tutorial (with lockin_half.bit there); the board decides which lock-in it uses.
Each sweep is 121 frequencies from 1 kHz to 12 MHz, log spaced, two 42 ms averages each, plus finer steps where a
tile has a narrow feature (the resonators; the quartz crystal gets a search and then 5 Hz steps).  The lock-in gives
the ADC's complex amplitude against the DAC's own oscillator, so the phase is absolute up to a fixed delay that p0
measures and the division removes, along with both cables, the DAC's and the ADC's response and their different volts
per code.  (p0 is interpolated to the extra frequencies with its delay taken out first.)

The two boards load a tile differently, and the dashed "expected" curve is the handbook's circuit between them:
    ECP5-2ADC-2DAC   the DAC is a 50 ohm source, ADC A (TERM jumper in) a 50 ohm load: what the handbook assumes
    Icepi Zero       the DAC is a 51 ohm source (p1 says so), the ADC about 20.6 k (p2's loss at 1 kHz says so) and
                     18.4 pF with its 10 cm cable (p4's peak at 3.7 MHz says so)
On the Icepi a tile made for 50 ohm can be followed by p1 (tile OUT -> p1 IN, p1 OUT -> ADC IN): p1's IN is 51.6 ohm,
so the tile sees the load it was made for.  A sweep 14 dB or more down everywhere is taken to be through p1, and is
divided by p1's own sweep.
Saved in ../../dev/data/amodp/: <board>_<tile>.npz (f, z at the ADC, h = z / z of p0) and <board>_<tile>.png.
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
         "p3": "RC high-pass, 159 kHz", "p4": "series RLC 100 uH 220 pF, switches off: 1.07 MHz",
         "p4-1": "series RLC, switch 1 on (+47 pF): 0.98 MHz", "p4-2": "series RLC, switch 2 on (+100 pF): 0.89 MHz",
         "p4-12": "series RLC, both switches on (+147 pF): 0.83 MHz", "p5": "LC low-pass, 9 MHz",
         "p6": "LC low-pass, 118 kHz", "p7": "band-pass, 4.7-7.5 MHz", "p8": "quartz crystal, 4 MHz",
         "p9": "ceramic resonator, 455 kHz", "p10": "clipper, 1N4148 +-0.6 V", "p11": "delay line, 400 ns",
         "p12": "LEDs", "p13": "AM loopstick, 0.5-1.7 MHz"}
EXTRA = {"p4": np.linspace(0.4e6, 2.4e6, 81), "p5": np.linspace(4e6, 12e6, 41), "p6": np.linspace(50e3, 300e3, 51),
         "p7": np.linspace(3e6, 10e6, 71), "p9": np.linspace(420e3, 500e3, 401), "p11": np.linspace(0.2e6, 12e6, 119)}
BOARD_LOAD = {"ecp5": (50.0, 50.0, 0.0), "icepi": (51.0, 20.6e3, 18.4e-12)}   # the DAC's source (ohm), the ADC's load
#   (ohm, and the farad across it: the Icepi's 18.4 pF of cable and ADC input is what p4's 100 uH rings with at 3.7 MHz)


# ---- the handbook's circuits, as ABCD matrices (series Z, shunt Y), for the expected curves -----------------------
def _ser(z):
    z = np.asarray(z, complex)
    return np.array([[np.ones_like(z), z], [np.zeros_like(z), np.ones_like(z)]])


def _sh(y):
    y = np.asarray(y, complex)
    return np.array([[np.ones_like(y), np.zeros_like(y)], [y, np.ones_like(y)]])


def _chain(*ms):
    out = ms[0]
    for m in ms[1:]:
        out = np.einsum("ijf,jkf->ikf", out, m)
    return out


def _xtal(w, cm, q, c0, f0=None):
    lm = 1 / ((2 * np.pi * f0) ** 2 * cm)
    zm = 2 * np.pi * f0 * lm / q + 1j * w * lm + 1 / (1j * w * cm)
    z0 = 1 / (1j * w * c0)
    return zm * z0 / (zm + z0)


def abcd(tile, f):
    w = 2 * np.pi * np.asarray(f, float)
    C = lambda c: 1j * w * c                                   # noqa: E731
    L = lambda l: 1j * w * l                                   # noqa: E731
    if tile == "p1":
        return _chain(_sh(1 / 61.9 + 0 * w), _ser(249 + 0 * w), _sh(1 / 61.9 + 0 * w))
    if tile == "p2":
        return _chain(_ser(1000 + 0 * w), _sh(C(1e-9)))
    if tile == "p3":
        return _chain(_ser(1 / C(1e-9)), _sh(1 / 1000 + 0 * w))
    if tile.startswith("p4"):
        c = 220e-12 + 47e-12 * ("1" in tile[2:]) + 100e-12 * ("2" in tile[2:])
        return _ser(10 + L(100e-6) + 1 / C(c))
    if tile == "p5":
        return _chain(_sh(C(220e-12)), _ser(L(1.5e-6)), _sh(C(680e-12)), _ser(L(1.5e-6)), _sh(C(220e-12)))
    if tile == "p6":
        return _chain(_sh(C(20e-9)), _ser(L(150e-6)), _sh(C(20e-9)))
    if tile == "p7":
        s = L(2.7e-6) + 1 / C(270e-12)
        return _chain(_ser(s), _sh(1 / L(330e-9) + C(2.2e-9)), _ser(s))
    if tile == "p8":
        return _ser(_xtal(w, 15e-15, 50e3, 4e-12, 4.0e6))
    if tile == "p9":
        return _ser(_xtal(w, 7e-12, 400, 250e-12, 455e3))
    if tile == "p11":
        return _chain(*[m for _ in range(20) for m in (_ser(L(1e-6)), _sh(C(390e-12)))])
    return None


def expected(tile, f, board, via_p1=False):
    """The tile's gain over the through, from the handbook's values and the board's source and load."""
    m = abcd(tile, f)
    if m is None:
        return None
    rs, r_l, c_l = BOARD_LOAD[board]
    rl = 1 / (1 / r_l + 2j * np.pi * np.asarray(f, float) * c_l)

    def vout(m):                                               # V_load / V_source
        a, b, c, d = m[0, 0], m[0, 1], m[1, 0], m[1, 1]
        return rl / (a * rl + b + rs * (c * rl + d))
    through = rl / (rl + rs)
    if via_p1:
        return vout(_chain(m, abcd("p1", f))) / vout(abcd("p1", f))
    return vout(m) / through


# ---- the two boards ---------------------------------------------------------------------------------------------
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
    name, label = "icepi", "Icepi Zero DK0GFLAW: DAC OUT -> tile -> ADC IN (20.6 k), +-1.95 V"
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


def sweep(b, freqs):
    fs, zs = [], []
    for f in freqs:
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


def crystal_sweep(b, z0_at):
    """The quartz crystal: Q about 17,000 between 50 ohm ports, a 230 Hz wide peak somewhere near 4 MHz (the crystal's
    tolerance and the board's own clock both move it by 100s of Hz).  Search in 50 Hz steps, then 5 Hz steps across
    the series resonance (the peak) and the parallel resonance (the notch a few kHz above it)."""
    f1, z1 = sweep(b, np.arange(3.985e6, 4.015e6, 50.0))
    g = np.abs(z1 / z0_at(f1))
    k = np.argmax(g)
    above = (f1 > f1[k] + 1e3) & (f1 < f1[k] + 15e3)
    kp = np.flatnonzero(above)[np.argmin(g[above])] if above.any() else k
    f2, z2 = sweep(b, f1[k] + np.arange(-300, 301, 5.0))
    f3, z3 = sweep(b, f1[kp] + np.arange(-300, 301, 5.0))
    return np.concatenate([f1, f2, f3]), np.concatenate([z1, z2, z3])


def interp_through(f0, z0):
    """p0 at any frequency: take the chain's delay out (a straight phase line above 1 MHz), interpolate the smooth
    rest in log f, put the delay back."""
    hi = f0 > 1e6
    tau = -np.polyfit(f0[hi], np.unwrap(np.angle(z0[hi])), 1)[0] / (2 * np.pi)
    zc = z0 * np.exp(2j * np.pi * f0 * tau)
    lf, lm, ph = np.log(f0), np.log(np.abs(zc)), np.unwrap(np.angle(zc))

    def at(f):
        f = np.clip(np.asarray(f, float), f0[0], f0[-1])
        return np.exp(np.interp(np.log(f), lf, lm) + 1j * np.interp(np.log(f), lf, ph)) * np.exp(-2j * np.pi * f * tau)
    return at


def summary(f, h):
    o = np.argsort(f); f, h = f[o], h[o]
    db = 20 * np.log10(np.abs(h))
    ph = np.degrees(np.unwrap(np.angle(h)))
    out = []
    for fq in (1e4, 1e5, 1e6, 1e7):
        i = np.argmin(np.abs(f - fq))
        out.append("%s %+.1f dB %+.0f deg" % (("%g kHz" % (fq / 1e3)) if fq < 1e6 else ("%g MHz" % (fq / 1e6)), db[i], ph[i]))
    i = np.argmax(db)
    s = "; ".join(out) + "; max %+.1f dB at %.6g Hz" % (db[i], f[i])
    below = np.flatnonzero(db < db[i] - 3)
    lo, hi = below[below < i], below[below > i]
    if len(hi):
        s += "; -3 dB above it at %.4g Hz" % f[hi[0]]
    if len(lo):
        s += "; -3 dB below it at %.4g Hz" % f[lo[-1]]
    return s


def plot(path, f, h, tile, label, board_name, via_p1=False, raw=False):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    o = np.argsort(f); f, h = f[o], h[o]
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(9, 6.5), sharex=True)
    a1.semilogx(f, 20 * np.log10(np.abs(h)), "o-", ms=2.5, lw=1, label="measured")
    a2.semilogx(f, np.degrees(np.unwrap(np.angle(h))), "o-", ms=2.5, lw=1)
    e = None if raw else expected(tile, f, board_name, via_p1)
    if e is not None:
        a1.semilogx(f, 20 * np.log10(np.abs(e)), "k--", lw=1, label="expected (the handbook's circuit)")
        a2.semilogx(f, np.degrees(np.unwrap(np.angle(e))), "k--", lw=1)
        a1.legend(fontsize=9)
    a1.set_ylabel("gain (dB)" + (", from its value at 1 kHz" if raw else ", over the through"))
    a1.grid(alpha=0.3, which="both")
    a2.set_ylabel("phase (degrees)"); a2.set_xlabel("frequency (Hz)"); a2.grid(alpha=0.3, which="both")
    a1.set_title("AMOD-P %s, %s%s\n%s, %s" % (tile, TILES.get(tile, ""), " (then p1: a 50 ohm load)" if via_p1 else "",
                                             label, time.strftime("%Y-%m-%d %H:%M")), fontsize=10)
    fig.tight_layout(); fig.savefig(path, dpi=100); plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tile", help="p0 (the through) .. p13; p4-1, p4-2, p4-12 for p4's switches")
    ap.add_argument("--load", action="store_true", help="load the lock-in's bitstream first")
    a = ap.parse_args()
    os.makedirs(DATA, exist_ok=True)
    b = board()
    if a.load:
        b.load()
    b.open()
    t0 = time.time()
    base = os.path.join(DATA, "%s_%s" % (b.name, a.tile))
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    if a.tile == "p0":
        f, z = sweep(b, FREQS)
        h = z / z[0]
        np.savez(base + ".npz", f=f, z=z, h=h, tile=a.tile, label=b.label, t=stamp)
        plot(base + ".png", f, h, a.tile, b.label, b.name, raw=True)
        hi = f > 1e6
        slope = np.polyfit(f[hi], np.unwrap(np.angle(z[hi])), 1)[0]
        print("%s p0: %.0f s; |z| at 1 kHz %.4g; %s; the chain's delay (phase slope above 1 MHz) %.1f ns"
              % (b.name, time.time() - t0, abs(z[0]), summary(f, h), -slope / (2 * np.pi) * 1e9))
        return
    d0 = np.load(os.path.join(DATA, "%s_p0.npz" % b.name))
    z0_at = interp_through(d0["f"], d0["z"])
    if a.tile == "p8":
        f, z = crystal_sweep(b, z0_at)
        f2, z2 = sweep(b, FREQS)
        f, z = np.concatenate([f2, f]), np.concatenate([z2, z])
    else:
        extra = EXTRA.get(a.tile.split("-")[0], np.array([]))
        f, z = sweep(b, np.sort(np.concatenate([FREQS, extra])))
    h = z / z0_at(f)
    via_p1 = b.name == "icepi" and a.tile not in ("p1", "p2", "p3") and np.abs(h).max() < 10 ** (-14 / 20)
    h_raw = h
    if via_p1:
        d1 = np.load(os.path.join(DATA, "%s_p1.npz" % b.name))
        h = h / interp_through(d1["f"], d1["z"])(f) * z0_at(f)       # / (p1 over the through)
    np.savez(base + ".npz", f=f, z=z, h=h, h_before_p1=h_raw, via_p1=via_p1, tile=a.tile, label=b.label, t=stamp)
    plot(base + ".png", f, h, a.tile, b.label, b.name, via_p1)
    print("%s %s%s: %.0f s; %s" % (b.name, a.tile, " (through p1, divided by it)" if via_p1 else "", time.time() - t0,
                                  summary(f, h)))


if __name__ == "__main__":
    main()
