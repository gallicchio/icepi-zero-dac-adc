#!/usr/bin/env python3
"""Log lockin.sv results from several boards at once.

    python3 lockin_log.py OUT.npz SECONDS F_HZ PORT_A PORT_B [...]

Sets every board to F_HZ, then records each board's results for SECONDS.  A board
sends one line, "TW X Y", every 2^20 samples: 41.94 ms of ITS OWN clock.  Saved per
board, as board0, board1, ...: rows of (laptop arrival time, X, Y), X and Y in lock-in
units.  So result k was taken at k * 2^20 / 25 MHz of that board's time (as long as
no line is lost), and the laptop times give the same thing against the laptop's clock.
"""
import sys
import threading
import time

import numpy as np
import serial


def tw_of(f, fclk=50e6):
    return int(round(f / fclk * 2**32)) & 0xFFFFFFFF


def s32(v):
    return v - (1 << 32) if v & (1 << 31) else v


def logger(port, tw, secs, out):
    s = serial.Serial(port, 1_000_000, timeout=1)
    time.sleep(0.05)
    s.reset_input_buffer()
    s.write(b"%08x\n" % tw)
    rows = []
    t0 = time.time()
    while time.time() - t0 < secs:
        p = s.readline().split()
        if len(p) != 3:
            continue
        try:
            t, x, y = (int(v, 16) for v in p)
        except ValueError:
            continue
        if t == tw:                          # skip anything from before the change
            rows.append((time.time(), s32(x) / 65536, s32(y) / 65536))
    s.close()
    out[port] = np.array(rows)


if __name__ == "__main__":
    out_path, secs, f = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    ports = sys.argv[4:]
    out = {}
    # one thread per board, so that no port's input buffer overflows
    threads = [threading.Thread(target=logger, args=(p, tw_of(f), secs, out)) for p in ports]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    np.savez(out_path, f=f, tw=tw_of(f), ports=ports,
             **{"board%d" % i: out[p] for i, p in enumerate(ports)})
    for p in ports:
        print(p, len(out[p]), "results")
