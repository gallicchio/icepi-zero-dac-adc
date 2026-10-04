"""Instructor's simulation of the FSK link of 10.6, to see where its errors come from.

    python3 fsk_sim.py [nbytes]

Random bytes, back to back at 115 200 baud, as phase-continuous MARK/SPACE tones at
25 MS/s, plus Gaussian noise; modem.sv's receiver (W-sample sliding sums, the stronger tone
wins); then two ways of reading bits from its output:
  ideal  each bit decided once, with the window centred in the bit (perfect timing)
  UART   a 16x-oversampling UART: start bit = a 1 -> 0 edge still 0 half a bit later, each
         bit sampled once, timed from that edge; a framing error delivers 0x00
and the jitter of the start edge, as it appears at the receiver's output.
"""
import difflib
import sys

import numpy as np

FS, BAUD = 25e6, 115200
SPB = FS / BAUD                                    # 217 samples per bit
rng = np.random.default_rng(1)


def count_bits(sent, got):
    bits = 0
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, sent, got, autojunk=False).get_opcodes():
        if op == "replace":
            n = min(i2 - i1, j2 - j1)
            bits += sum(bin(x ^ y).count("1") for x, y in zip(sent[i1:i1 + n], got[j1:j1 + n]))
            bits += 8 * abs((i2 - i1) - (j2 - j1))
        elif op == "delete" or (op == "insert" and i1 < len(sent)):
            bits += 8 * max(i2 - i1, j2 - j1)
    return bits


def link(snr, W, nbytes, A=20.0):
    sent = rng.integers(0, 256, nbytes, dtype=np.uint8).tobytes()
    line = [1] * 20
    for b in sent:
        line += [0] + [(b >> i) & 1 for i in range(8)] + [1]
    line = np.array(line + [1] * 20)
    n = np.arange(int(len(line) * SPB))
    level = line[(n / SPB).astype(int)]
    x = A * np.cos(2 * np.pi * np.cumsum(np.where(level == 1, 0.25, 0.125)))
    x += rng.normal(0, A / np.sqrt(2 * snr), len(n))

    def window(y):
        c = np.cumsum(np.concatenate([[0], y]))
        return c[W:] - c[:-W]
    em = np.abs(window(x * np.exp(-1j * np.pi / 2 * n))) ** 2
    es = np.abs(window(x * np.exp(-1j * np.pi / 4 * n))) ** 2
    d = np.concatenate([np.ones(W - 1, int), (em >= es).astype(int)])   # d[i]: window ending at i

    k = np.arange(len(line))
    centre = ((k + 0.5) * SPB + W / 2).astype(int)
    ok = centre < len(d)
    ideal = np.mean(d[centre[ok]] != line[k[ok]])

    edges = np.where((line[1:] == 0) & (line[:-1] == 1))[0] + 1
    late = []
    for e in edges[:3000]:
        s0 = int(e * SPB)
        z = np.where((d[s0:s0 + 2 * W + 20][1:] == 0) & (d[s0:s0 + 2 * W + 20][:-1] == 1))[0]
        if len(z):
            late.append(z[0] + 1 - (e * SPB - s0))
    late = np.array(late)

    tick = (np.arange(int(len(d) / SPB * 16)) * SPB / 16).astype(int)
    L = d[tick[tick < len(d)]]
    got, j = bytearray(), 1
    while j < len(L) - 160:
        if L[j] == 0 and L[j - 1] == 1 and L[j + 8] == 0:
            b = sum(int(L[j + 8 + 16 * (i + 1)]) << i for i in range(8))
            got.append(b if L[j + 8 + 16 * 9] else 0)
            j += 8 + 16 * 9                        # look for the next start from mid-stop
        else:
            j += 1
    return ideal, count_bits(sent, bytes(got)) / (8 * nbytes), np.median(late), late.std()


if __name__ == "__main__":
    nbytes = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    for W, snrs in ((16, (3.8, 2.9, 2.0, 1.1, 0.4)), (128, (-4.5, -5.5, -6.4, -7.5, -8.4))):
        for s in snrs:
            snr = 10 ** (s / 10)
            ideal, uart, delay, jitter = link(snr, W, nbytes)
            print("W %3d  SNR %5.1f dB:  theory %.2e  ideal timing %.2e  UART %.2e;  start edge %.0f "
                  "samples late, jitter %.1f rms (margin %.0f)" %
                  (W, s, 0.5 * np.exp(-W * snr / 4), ideal, uart, delay, jitter, (SPB - W) / 2), flush=True)
