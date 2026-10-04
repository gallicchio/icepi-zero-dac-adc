"""Instructor's measurement for modem_sync.v (on the looped-back board, JLC3).

    python3 fsk_sync_ber.py BITSTREAM [BITSTREAM ...]

Each bitstream is loaded in turn; then 400 bytes of 0x55 (alternating bits, so that the
bit clock can find the bits) and 100 000 random bytes go out in one write, back to back.
The preamble is cut off what comes back, and the rest counted as fsk_ber.py does.
"""
import difflib
import os
import sys
import threading
import time

import serial

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import boards

P = boards.port("JLC3")


def count_bits(sent, got):
    bits = 0
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, sent, got, autojunk=False).get_opcodes():
        if op == "replace":
            k = min(i2 - i1, j2 - j1)
            bits += sum(bin(a ^ b).count("1") for a, b in zip(sent[i1:i1 + k], got[j1:j1 + k]))
            bits += 8 * abs((i2 - i1) - (j2 - j1))
        elif op == "delete" or (op == "insert" and i1 < len(sent)):
            bits += 8 * max(i2 - i1, j2 - j1)
    return bits


def link(nbytes=100000, npre=400, baud=115200):
    s = serial.Serial(P, baud, timeout=0.5)
    time.sleep(0.05)
    s.reset_input_buffer()
    pre, data, got = b"\x55" * npre, os.urandom(nbytes), bytearray()
    deadline = time.time() + (nbytes + npre) * 10 / baud + 1.0

    def rd():
        while time.time() < deadline:
            c = s.read(65536)
            if not c:
                break
            got.extend(c)
    t = threading.Thread(target=rd)
    t.start()
    s.write(pre + data)
    t.join()
    s.close()
    got = bytes(got)
    # where does the payload start?  the longest match with its first 64 bytes
    m = difflib.SequenceMatcher(None, data[:64], got[:npre + 2000], autojunk=False).find_longest_match(0, 64, 0, min(len(got), npre + 2000))
    start = max(0, m.b - m.a)
    return count_bits(data, got[start:start + nbytes + 50]), len(got) - start - nbytes, nbytes * 8, m.size


if __name__ == "__main__":
    for bit in sys.argv[1:]:
        boards.load("JLC3", bit)
        time.sleep(0.5)
        bits, extra, nb, anchor = link()
        print("%s: %d bit errors of %d (BER %.2e), bytes %+d, payload found by a %d-byte match" %
              (os.path.basename(bit), bits, nb, bits / nb, extra, anchor), flush=True)
