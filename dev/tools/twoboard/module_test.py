"""Characterise the three DAC -> cable -> ADC paths with loopback.sv's patterns.

JLC3 loops to itself; JLC1 and JLC2 are cross-connected, so each one's recording is
the OTHER board's pattern, starting at an arbitrary point (re-aligned here).
"""
import os, sys, time
import numpy as np
import serial
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import boards
T = os.path.join(HERE, "..", "..")
PATHS = {"JLC3->JLC3": ("JLC3", "JLC3"), "JLC1->JLC2": ("JLC1", "JLC2"), "JLC2->JLC1": ("JLC2", "JLC1")}

def send_all(mode, names):
    """Send one loopback command to several boards at once, then collect each one's record."""
    ports = {n: serial.Serial(boards.port(n), 1_000_000, timeout=3) for n in names}
    time.sleep(0.05)
    for s in ports.values(): s.reset_input_buffer()
    for s in ports.values(): s.write(mode.encode())
    # read all ports at the same time: a port nobody reads loses data beyond ~4 kB
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(len(ports)) as ex:
        raw = dict(zip(ports, ex.map(lambda s: s.read(16384), ports.values())))
    out = {n: np.frombuffer(r, np.uint8).astype(int) for n, r in raw.items()}
    assert all(len(v) == 16384 for v in out.values()), {n: len(v) for n, v in out.items()}
    for s in ports.values(): s.close()
    return out

def align_staircase(c):
    """Rotate a record of the 64-sample staircase so the step from 255 to 0 is at index 0."""
    i = int(np.argmin(np.diff(c))) + 1          # the big drop
    return np.roll(c, -i)

if __name__ == "__main__":
    for n in ("JLC1", "JLC2", "JLC3"):
        boards.load(n, os.path.join(T, "loopback.bit"))
    rec = {m: send_all(m, ["JLC1", "JLC2", "JLC3"]) for m in "rsp"}
    np.savez_compressed(os.path.join(T, "data", "tb_module_test.npz"), **{"%s_%s" % (m, n): v.astype(np.uint8) for m, d in rec.items() for n, v in d.items()})
    k = np.arange(256)
    for path, (src, dst) in PATHS.items():
        c = rec["r"][dst]
        c = align_staircase(c) if src != dst else c
        steps = c.reshape(256, 64)[:, 16:].mean(axis=1)
        p = np.polyfit(k, steps, 1); inl = steps - np.polyval(p, k)
        dnl = np.diff(steps) / p[0] - 1
        print("%s: ADC = %.4f x DAC + %.2f; INL %.2f codes rms, worst %+.2f at DAC %d; DNL worst %+.2f at %d->%d; codes seen %d..%d" %
              (path, p[0], p[1], inl.std(), inl[np.argmax(abs(inl))], np.argmax(abs(inl)), dnl[np.argmax(abs(dnl))], np.argmax(abs(dnl)), np.argmax(abs(dnl)) + 1, c.min(), c.max()))
