#!/usr/bin/env python3
"""Full-duplex test of two boards running modem.sv: each laptop's port sends random bytes to the
other at the same time, and each checks what arrives.

    python3 modem_test.py PORT_A PORT_B [--baud 1000000] [--bytes 20000]
"""
import argparse
import os
import threading
import time

import serial

ap = argparse.ArgumentParser()
ap.add_argument("port_a")
ap.add_argument("port_b")
ap.add_argument("--baud", type=int, default=1_000_000)
ap.add_argument("--bytes", type=int, default=20000)
a = ap.parse_args()

A = serial.Serial(a.port_a, a.baud, timeout=0.5)
B = serial.Serial(a.port_b, a.baud, timeout=0.5)
time.sleep(0.05)
A.reset_input_buffer()
B.reset_input_buffer()
data_a, data_b = os.urandom(a.bytes), os.urandom(a.bytes)
got = {"A": bytearray(), "B": bytearray()}


def reader(name, port):
    """Read until the line goes quiet for 0.5 s.  Reading while writing matters: Linux keeps
    only about 4 kB for a port that nobody is reading."""
    while True:
        chunk = port.read(65536)
        if not chunk:
            break
        got[name].extend(chunk)


readers = [threading.Thread(target=reader, args=("A", A)), threading.Thread(target=reader, args=("B", B))]
for t in readers:
    t.start()
writers = [threading.Thread(target=A.write, args=(data_a,)), threading.Thread(target=B.write, args=(data_b,))]
for t in writers:
    t.start()
for t in writers + readers:
    t.join()

for src, dst, sent in (("A", "B", data_a), ("B", "A", data_b)):
    received = bytes(got[dst])
    wrong = sum(x != y for x, y in zip(sent, received)) + abs(len(sent) - len(received))
    print("%s -> %s at %d baud: %d of %d bytes arrived, %d wrong" %
          (src, dst, a.baud, len(received), len(sent), wrong))
