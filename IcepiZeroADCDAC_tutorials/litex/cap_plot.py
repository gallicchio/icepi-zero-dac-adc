#!/usr/bin/env python3
"""Part 6, the PC side: ask the firmware for a capture and plot it.

    python3 cap_plot.py                 # 25 MS/s, free-running
    python3 cap_plot.py -d 2 -t 128     # 6.25 MS/s, triggered at mid-scale
    python3 cap_plot.py -o scope.csv --no-plot

The firmware must be running (its prompt is "adda>"), and no terminal program
may have the port open.
"""
import argparse
import re
import time

import numpy as np
import serial

N = 16384


def cap(port, d=0, level=None):
    """Returns (time in s, ADC codes) from the firmware's cap + dump commands."""
    with serial.Serial(port, 115200, timeout=0.2) as ser:
        ser.write(b"\r")
        time.sleep(0.2)
        ser.reset_input_buffer()
        ser.write(b"cap %d%s\r" % (d, b"" if level is None else b" %d" % level))
        reply = b""
        while b"adda> " not in reply:
            chunk = ser.read(256)
            if not chunk and b"cap" in reply and time.time() > deadline:
                raise RuntimeError("no reply: is the firmware running?")
            if not reply:
                deadline = time.time() + 25
            reply += chunk
        print(reply.decode(errors="replace").replace("\r", "").splitlines()[1])
        ser.write(b"dump\r")
        text = b""
        while text.count(b"\n") < N // 64 + 1:
            chunk = ser.read(4096)
            if not chunk:
                break
            text += chunk
    text = text.replace(b"\r", b"")          # LiteX's console ends lines with \n\r
    hexdigits = b"".join(re.findall(rb"^[0-9a-f]{128}$", text, re.M))
    codes = np.frombuffer(bytes.fromhex(hexdigits.decode()), dtype=np.uint8)
    if len(codes) != N:
        raise RuntimeError(f"got {len(codes)} of {N} samples")
    return np.arange(N) / (25e6 / 2**d), codes


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default="/dev/ttyUSB0")
    ap.add_argument("-d", type=int, default=0, help="keep 1 sample in 2^d")
    ap.add_argument("-t", "--trigger", type=int, help="trigger level, 0..255")
    ap.add_argument("-o", "--out", help="save time,code as CSV")
    ap.add_argument("--no-plot", action="store_true")
    args = ap.parse_args()

    t, code = cap(args.port, args.d, args.trigger)
    if args.out:
        np.savetxt(args.out, np.column_stack([t, code]), delimiter=",",
                   header="time_s,adc_code", fmt=["%.9g", "%d"])
    if not args.no_plot:
        import matplotlib.pyplot as plt
        plt.plot(t * 1e6, (code - 126.7) / 25.35, ".-", markersize=3, linewidth=0.5)
        plt.xlabel("time (µs)")
        plt.ylabel("ADC input (V)")
        plt.grid(True)
        plt.show()
