#!/usr/bin/env python3
"""The laptop side of awgcap.sv: load waveforms into boards and record their ADCs.

    import awgcap
    awgcap.upload("/dev/ttyUSB0", wave)        # wave: 16384 numbers 0..255, played at 50 MS/s
    codes = awgcap.record("/dev/ttyUSB0")      # 16384 ADC codes at 25 MS/s
    a, b = awgcap.record_many([port_a, port_b])   # both boards at (nearly) the same moment
"""
import threading
import time

import numpy as np
import serial

N = 16384
FS_DAC, FS_ADC = 50e6, 25e6


def upload(port, wave):
    w = np.clip(np.round(np.asarray(wave)), 0, 255).astype(np.uint8)
    assert len(w) == N
    with serial.Serial(port, 1_000_000, timeout=2) as s:
        s.write(b"W" + w.tobytes())
        s.flush()
    time.sleep(0.05)


def record(port):
    with serial.Serial(port, 1_000_000, timeout=2) as s:
        time.sleep(0.02)
        s.reset_input_buffer()
        s.write(b"C")
        raw = s.read(N)
    if len(raw) != N:
        raise RuntimeError("got %d of %d bytes -- is awgcap.bit loaded?" % (len(raw), N))
    return np.frombuffer(raw, np.uint8).astype(int)


def record_many(ports):
    """Ask several boards to record at once.  Each port is read in its own thread:
    a port nobody is reading loses data after about 4 kB."""
    sers = [serial.Serial(p, 1_000_000, timeout=2) for p in ports]
    time.sleep(0.02)
    for s in sers:
        s.reset_input_buffer()
    out = [None] * len(sers)
    def go(i):
        sers[i].write(b"C")
        out[i] = sers[i].read(N)
    th = [threading.Thread(target=go, args=(i,)) for i in range(len(sers))]
    for t in th: t.start()
    for t in th: t.join()
    for s in sers: s.close()
    if any(len(o) != N for o in out):
        raise RuntimeError("short record: %s" % [len(o) for o in out])
    return [np.frombuffer(o, np.uint8).astype(int) for o in out]
