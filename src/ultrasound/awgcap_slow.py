#!/usr/bin/env python3
"""The laptop side of awgcap_slow.sv: play a waveform at 195 kS/s, record at 97.7 kS/s.

    import awgcap_slow as awg
    ser = awg.open_port()                  # finds the Icepi Zero (or open_port("/dev/ttyUSB0"))
    awg.upload(ser, wave)                  # 16384 DAC codes 0..255: one 83.89 ms loop, forever
    x = awg.record(ser)                    # 16384 mean ADC codes (floats), 167.77 ms, from a loop's start
    t_dac, t_adc = awg.times()             # the instants they belong to, in seconds

    python3 awgcap_slow.py --burst 40300 --ms 2    # a 2 ms tone burst, recorded and plotted

The record's value n is the mean of the ADC over [2n, 2n + 2) DAC sample periods, so
it belongs to the instant (2n + 1) / FS_DAC: half a record period after its start.
"""
import argparse
import time

import numpy as np

N = 16384
K = 8                                   # one DAC sample every 2^K clocks
FS_DAC = 50e6 / 2**K                    # 195,312.5 S/s
FS_ADC = FS_DAC / 2                     # 97,656.25 S/s: one record value per two DAC samples
LOOP = N / FS_DAC                       # 83.89 ms


def find_port():
    """The first FTDI FT231X serial port (USB ID 0403:6015): the Icepi Zero's."""
    from serial.tools import list_ports
    for p in list_ports.comports():
        if (p.vid, p.pid) == (0x0403, 0x6015) and p.product in (None, "FT231X USB UART"):
            return p.device
    raise SystemExit("No Icepi Zero found. Is it plugged in? (Or give --port.)")


def open_port(port=None, k=K):
    import serial                       # pip install pyserial
    ser = serial.Serial(port or find_port(), 1_000_000, timeout=2)
    time.sleep(0.02)
    ser.reset_input_buffer()            # the FT231X's junk byte on opening
    ser.write(b"K" + bytes([k]))
    return ser


def upload(ser, wave):
    w = np.clip(np.round(np.asarray(wave)), 0, 255).astype(np.uint8)
    assert len(w) == N
    ser.write(b"W" + w.tobytes())
    ser.flush()
    time.sleep(0.02)


def record(ser):
    ser.reset_input_buffer()
    ser.write(b"C")
    raw = ser.read(2 * N)
    if len(raw) != 2 * N:
        raise RuntimeError("got %d of %d bytes -- is awgcap_slow.bit loaded?" % (len(raw), 2 * N))
    return np.frombuffer(raw, ">u2").astype(float) / 256


def times():
    """When each DAC sample starts, and the middle of each record value, in seconds."""
    return np.arange(N) / FS_DAC, (2 * np.arange(N) + 1) / FS_DAC


def tone_burst(f, ms, amp=127, start_ms=1.0):
    """A burst of f Hz, ms long, starting start_ms into the loop; silence elsewhere."""
    t, _ = times()
    on = (t >= start_ms * 1e-3) & (t < (start_ms + ms) * 1e-3)
    return 128 + amp * np.sin(2 * np.pi * f * (t - start_ms * 1e-3)) * on


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port")
    ap.add_argument("--burst", type=float, default=40300.0, help="tone frequency, Hz")
    ap.add_argument("--ms", type=float, default=2.0, help="burst length, ms")
    ap.add_argument("--amp", type=float, default=127, help="DAC codes, 0..127")
    a = ap.parse_args()
    ser = open_port(a.port)
    wave = tone_burst(a.burst, a.ms, a.amp)
    upload(ser, wave)
    time.sleep(2 * LOOP)                # let the old waveform's sound die away
    x = record(ser)
    t_dac, t_adc = times()
    import matplotlib.pyplot as plt
    fig, (p, q) = plt.subplots(2, 1, sharex=True)
    p.plot(t_dac * 1e3, wave); p.set_ylabel("DAC code")
    q.plot(t_adc * 1e3, x); q.set_ylabel("mean ADC code"); q.set_xlabel("time (ms)")
    q.set_xlim(0, 10)
    plt.show()
