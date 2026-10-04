"""Instructor's measurement: modem.sv's error rate against SNR, on one board looped back (JLC3).

    python3 fsk_ber.py BITSTREAM_DIR [OUT.npz]

For each build of twoboard/modem_noise.sv (NOISE, AMP, LOGWIN), named by NOISE_AMP_LOGWIN:
  mm_*.bit  a steady MARK tone plus the noise, and capture.sv: 24 records of the ADC give the
            SNR per sample, and the receiver's decisions done offline on those samples
  mn_*.bit  the modem itself: 100 000 random bytes at 115 200 baud through the PC's UART,
            aligned with what was sent, and the wrong bits counted
Results go to data/OUT.npz.  The measuring design, mn_measure.v, is modem_noise with
uart_rx tied high, plus the tutorial's capture.sv on the ADC; it is kept here, next to this.
"""
import difflib
import os
import sys
import threading
import time

import numpy as np
import serial

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import boards

S = sys.argv[1]                                 # folder of mm_*.bit and mn_*.bit
OUT = sys.argv[2] if len(sys.argv) > 2 else "tb_fsk_ber.npz"
P = boards.port("JLC3")
WM, WS = 2 * np.pi / 4, 2 * np.pi / 8          # MARK and SPACE, radians per ADC sample


def sliding(y, n):
    c = np.cumsum(np.concatenate([[0], y]))
    return c[n:] - c[:-n]


def analyse(records, win):
    """SNR per sample (tone fit), and the fraction of windows where SPACE beats MARK."""
    n = np.arange(records.shape[1])
    M = np.column_stack([np.cos(WM * n), np.sin(WM * n), np.ones(len(n))])
    snrs, errs, tot = [], 0, 0
    for codes in records.astype(float):
        co = np.linalg.lstsq(M, codes, rcond=None)[0]
        res = codes - M @ co
        snrs.append(np.hypot(co[0], co[1]) ** 2 / 2 / res.var())
        x = codes - 128
        em = np.abs(sliding(x * np.exp(-1j * WM * n), win)) ** 2
        es = np.abs(sliding(x * np.exp(-1j * WS * n), win)) ** 2
        errs += np.sum(es > em)
        tot += len(em)
    return np.mean(snrs), errs, tot


def link(nbytes=100000, baud=115200):
    s = serial.Serial(P, baud, timeout=0.5)
    time.sleep(0.05)
    s.reset_input_buffer()
    data, got = os.urandom(nbytes), bytearray()
    deadline = time.time() + nbytes * 10 / baud + 1.0

    def rd():
        # until the line is quiet for 0.5 s -- or the deadline: in heavy noise, idle MARK
        # makes false start bits, and garbage bytes keep coming for ever
        while time.time() < deadline:
            c = s.read(65536)
            if not c:
                break
            got.extend(c)
    t = threading.Thread(target=rd)
    t.start()
    s.write(data)
    t.join()
    s.close()
    got = bytes(got)
    # align what came back with what was sent: a corrupted start bit loses or adds bytes
    bits = 0
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, data, got, autojunk=False).get_opcodes():
        if op == "replace":
            k = min(i2 - i1, j2 - j1)
            bits += sum(bin(a ^ b).count("1") for a, b in zip(data[i1:i1 + k], got[j1:j1 + k]))
            bits += 8 * abs((i2 - i1) - (j2 - j1))
        elif op == "delete" or (op == "insert" and i1 < len(data)):   # not garbage after the end
            bits += 8 * max(i2 - i1, j2 - j1)
    return bits, len(got) - len(data), len(data) * 8


SWEEPS = {"w16": (100, 4, (0, 43, 61, 70, 78, 86, 95, 104, 113, 139)),
          "w128": (25, 7, (0, 40, 49, 55, 61, 69, 77, 87, 97))}
out = {}
for name, (amp, logwin, levels) in SWEEPS.items():
    rows = []
    for m in levels:
        tag = "%d_%d_%d" % (m, amp, logwin)
        boards.load("JLC3", "%s/mm_%s.bit" % (S, tag))
        time.sleep(0.3)
        records = np.array([boards.capture("JLC3")[1] for _ in range(24)])
        snr, derr, dtot = analyse(records, 1 << logwin)
        boards.load("JLC3", "%s/mn_%s.bit" % (S, tag))
        time.sleep(0.3)
        bits, extra, nb = link()
        rows.append((m, snr, derr, dtot, bits, extra, nb))
        print("%s NOISE %3d: SNR/sample %5.1f dB; offline decisions wrong %d of %d (%.2e); "
              "link bit errors %d of %d (BER %.2e), bytes %+d" %
              (name, m, 10 * np.log10(snr), derr, dtot, derr / dtot, bits, nb, bits / nb, extra), flush=True)
    out[name] = np.array(rows)
np.savez(os.path.join(HERE, "..", "..", "data", OUT),
         columns="noise snr_linear decisions_wrong decisions bit_errors bytes_extra bits", **out)
