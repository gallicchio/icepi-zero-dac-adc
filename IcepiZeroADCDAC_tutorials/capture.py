#!/usr/bin/env python3
"""Tutorial 3, the PC side: ask capture.v for 16384 ADC samples and plot them.

    python3 capture.py            # 25 MS/s
    python3 capture.py -d 4       # 25 MS/s / 2^4 = 1.5625 MS/s
    python3 capture.py -d 4 -o scope.csv --no-plot
"""
import argparse
import time

import numpy as np
import serial                        # pip install pyserial

N = 16384
FS_MAX = 25e6                        # the ADC runs at 50 MHz / 2


def capture(port, d):
    """Returns (time in seconds, ADC codes 0..255)."""
    with serial.Serial(port, 1_000_000, timeout=2) as ser:
        time.sleep(0.05)                 # let the line settle after opening,
        ser.reset_input_buffer()         # and throw away anything stale
        ser.write(b"%x" % d)             # D as one hex digit: b"0" .. b"f"
        raw = ser.read(N)
    if len(raw) != N:
        raise RuntimeError(f"got {len(raw)} of {N} bytes -- is capture.bit loaded?")
    fs = FS_MAX / 2**d
    return np.arange(N) / fs, np.frombuffer(raw, dtype=np.uint8)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-d", type=int, default=0, help="keep 1 sample in 2^d (0..15)")
    ap.add_argument("--port", default="/dev/ttyUSB0")
    ap.add_argument("-o", "--out", help="save time,code to this CSV file")
    ap.add_argument("--no-plot", action="store_true")
    args = ap.parse_args()

    t0 = time.time()
    t, code = capture(args.port, args.d)
    print(f"{N} samples at {FS_MAX / 2**args.d / 1e6:g} MS/s in {time.time() - t0:.2f} s; "
          f"codes {code.min()}..{code.max()}, mean {code.mean():.1f}")
    if args.out:
        np.savetxt(args.out, np.column_stack([t, code]), delimiter=",",
                   header="time_s,adc_code", fmt=["%.9g", "%d"])
    if not args.no_plot:
        import matplotlib.pyplot as plt
        plt.plot(t * 1e6, code, ".-", markersize=3, linewidth=0.5)
        plt.xlabel("time (µs)")
        plt.ylabel("ADC code (0..255)")
        plt.grid(True)
        plt.show()
