#!/usr/bin/env python3
"""1.09, on the laptop: the spectrum of what the ADC sees.  Takes many 16384-sample
records, multiplies each by a window, FFTs it, and averages the power.

    python3 spectrum.py                   # capture.sv (1.06): 25 MS/s, 16 records
    python3 spectrum.py -d 4              # capture.sv at 25 MS/s / 2^4
    python3 spectrum.py --loopback s      # loopback.sv (1.07): its square wave, through the cable
    python3 spectrum.py -n 64 --window rect -o spec.npz --no-plot
"""
import argparse

import numpy as np
import serial                         # pip install pyserial

N = 16384
FS_MAX = 25e6
CODES_PER_VOLT = 25.35


def find_port():
    """The first FTDI FT231X serial port (USB ID 0403:6015): the Icepi Zero's."""
    from serial.tools import list_ports
    for p in list_ports.comports():
        if (p.vid, p.pid) == (0x0403, 0x6015):
            return p.device
    raise SystemExit("No Icepi Zero found. Is it plugged in? (Or give --port.)")


def records(port, command, n):
    """n records of N samples each, in volts.  capture.sv and loopback.sv both answer one
    command byte with N raw bytes."""
    out = []
    with serial.Serial(port, 1_000_000, timeout=2) as ser:
        ser.reset_input_buffer()
        for _ in range(n):
            ser.write(command)
            raw = ser.read(N)
            if len(raw) != N:
                raise RuntimeError(f"got {len(raw)} of {N} bytes -- is capture.bit or loopback.bit loaded?")
            out.append(np.frombuffer(raw, dtype=np.uint8) / CODES_PER_VOLT)
    return np.array(out)


def spectrum(x, fs, window="hann"):
    """Average amplitude spectrum of the rows of x, in volts: a sine of amplitude A that
    sits on a bin reads A.  Returns (frequencies in Hz, amplitudes in V)."""
    w = np.hanning(x.shape[1]) if window == "hann" else np.ones(x.shape[1])
    x = x - x.mean(axis=1, keepdims=True)
    # ##########################################################################
    # ##  KEY LINES: window each record, FFT it, and average the POWER of the
    # ##  records (averaging the complex values would cancel the noise and the
    # ##  signal alike unless every record started at the same phase).
    # ##########################################################################
    X = np.fft.rfft(x * w, axis=1) / (w.sum() / 2)
    power = np.mean(np.abs(X) ** 2, axis=0)
    return np.fft.rfftfreq(x.shape[1], 1 / fs), np.sqrt(power)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-d", type=int, default=0, help="capture.sv: keep 1 sample in 2^d (0..15)")
    ap.add_argument("--loopback", choices=["s", "r", "p"], help="use loopback.sv's pattern instead")
    ap.add_argument("-n", type=int, default=16, help="number of records to average (default 16)")
    ap.add_argument("--window", choices=["hann", "rect"], default="hann")
    ap.add_argument("--port", help="serial port (default: find the Icepi Zero)")
    ap.add_argument("-o", "--out", help="save frequency (Hz) and amplitude (V) to this .npz")
    ap.add_argument("--no-plot", action="store_true")
    args = ap.parse_args()

    command = args.loopback.encode() if args.loopback else b"%x" % args.d
    fs = FS_MAX if args.loopback else FS_MAX / 2**args.d
    x = records(args.port or find_port(), command, args.n)
    f, amp = spectrum(x, fs, args.window)
    db = 20 * np.log10(amp + 1e-9)
    print(f"{args.n} records of {N} samples at {fs / 1e6:g} MS/s: bins {fs / N:.1f} Hz apart")
    peaks = [i for i in range(1, len(amp) - 1) if amp[i - 1] < amp[i] >= amp[i + 1]]
    for i in sorted(peaks, key=lambda i: -amp[i])[:5]:      # the five biggest peaks
        print(f"  {f[i] / 1e6:10.6f} MHz  {amp[i] * 1e3:9.2f} mV  ({db[i]:6.1f} dBV)")
    if args.out:
        np.savez(args.out, f=f, amp=amp)
    if not args.no_plot:
        import matplotlib.pyplot as plt
        plt.plot(f / 1e6, db, linewidth=0.7)
        plt.xlabel("frequency (MHz)")
        plt.ylabel("amplitude (dB re 1 V)")
        plt.grid(True)
        plt.show()
