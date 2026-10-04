#!/usr/bin/env python3
"""Count the QPSK modem's bit errors, on one board whose DAC OUT is cabled to its ADC IN
(qpsk_modem.bit loaded), or between two boards.

    python3 qpsk_modem_test.py PORT [--bytes 20000]
    python3 qpsk_modem_test.py PORT_A PORT_B      # A's DAC to B's ADC: A sends, B receives

Sends random bytes through the modem and lines up what comes back with what was sent, as
modem_ber.py (5.06) does: difflib finds the matching runs, so a lost or invented byte
costs 8 bits and doesn't spoil the count of everything after it.  The modem's own frames
carry a byte at most every 5.12 us (195 kB/s), so at 1 Mbaud (100 kB/s) nothing queues.

The port must be at 1,000,000 baud: that is what qpsk_modem.sv's serial ports run at.  (At
115,200 the design's 1 Mbaud receiver samples the slow line like a digitizer, 8 samples a
byte, and the far transmitter replays them with a stop bit cut into every 10 us: most
bytes survive, 6 % of the bits don't.  --baud anything else is refused.)
"""
import argparse
import difflib
import os
import threading
import time

import serial

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("ports", nargs="+", help="one port: looped back; two: A sends, B receives")
ap.add_argument("--bytes", type=int, default=20000)
ap.add_argument("--baud", type=int, default=1_000_000, help="must be 1000000 (see above)")
a = ap.parse_args()
if a.baud != 1_000_000:
    raise SystemExit("qpsk_modem.sv's serial ports run at 1,000,000 baud, and only that works (see the docstring)")

tx = serial.Serial(a.ports[0], a.baud, timeout=0.5)
rx = tx if len(a.ports) == 1 else serial.Serial(a.ports[1], a.baud, timeout=0.5)
time.sleep(0.1)
rx.reset_input_buffer()
sent, got = os.urandom(a.bytes), bytearray()
deadline = time.time() + a.bytes * 10 / a.baud + 2


def reader():
    """Read until the line goes quiet for 0.5 s (or the deadline).  Reading while writing
    matters: Linux keeps only about 4 kB for a port that nobody is reading."""
    while time.time() < deadline:
        chunk = rx.read(65536)
        if not chunk:
            break
        got.extend(chunk)


t0 = time.time()
t = threading.Thread(target=reader)
t.start()
tx.write(sent)
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
print("%d bytes sent at %d baud, %d received; %d bit errors in %d bits: BER %.1e"
      % (len(sent), a.baud, len(got), bits, 8 * len(sent), bits / (8 * len(sent))))
