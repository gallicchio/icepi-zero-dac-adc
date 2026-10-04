#!/usr/bin/env python3
"""Count a modem's bit errors, on one board whose DAC is cabled to its own ADC.

    python3 modem_ber.py PORT [--bytes 100000] [--baud 115200]

Sends random bytes through the modem and lines up what comes back with what was sent.
A corrupted start bit makes the laptop's UART lose or invent a byte, so a byte-by-byte
comparison would count everything after it as wrong; difflib finds the matching runs.
"""
import argparse
import difflib
import os
import threading
import time

import serial

ap = argparse.ArgumentParser()
ap.add_argument("port")
ap.add_argument("--bytes", type=int, default=100000)
ap.add_argument("--baud", type=int, default=115200)
a = ap.parse_args()

s = serial.Serial(a.port, a.baud, timeout=0.5)
time.sleep(0.05)
s.reset_input_buffer()
sent, got = os.urandom(a.bytes), bytearray()
deadline = time.time() + a.bytes * 10 / a.baud + 1


def reader():
    # until the line is quiet for 0.5 s, or the deadline: in heavy noise the idle tone
    # makes false start bits, and garbage keeps arriving for ever
    while time.time() < deadline:
        chunk = s.read(65536)
        if not chunk:
            break
        got.extend(chunk)


t = threading.Thread(target=reader)
t.start()
s.write(sent)
t.join()
got = bytes(got)

bits = 0
for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, sent, got, autojunk=False).get_opcodes():
    if op == "replace":                          # bytes that came back different
        n = min(i2 - i1, j2 - j1)
        bits += sum(bin(x ^ y).count("1") for x, y in zip(sent[i1:i1 + n], got[j1:j1 + n]))
        bits += 8 * abs((i2 - i1) - (j2 - j1))
    elif op == "delete" or (op == "insert" and i1 < len(sent)):   # lost, or invented
        bits += 8 * max(i2 - i1, j2 - j1)
print("%d bytes sent, %d received; %d bit errors in %d bits: BER %.2e" %
      (len(sent), len(got), bits, 8 * len(sent), bits / (8 * len(sent))))
