#!/usr/bin/env python3
"""1.09, the laptop side of fft.sv: a spectrum analyzer, with the FFT in the FPGA.

    python3 fft.py                     # live, 25 MS/s: 0 to 12.5 MHz (close the window to stop)
    python3 fft.py -d 4 -a 6           # 25 MS/s / 2^4 = 1.5625 MS/s: 0 to 781 kHz,
                                       #   each spectrum the average of 2^6 = 64 frames
    python3 fft.py --volts             # y axis in dB re 1 V (as spectrum.py), not re full scale
    python3 fft.py --once -o spec.npz  # one spectrum: plot it and save it

The FPGA sends P[k], k = 0..511: the average over 2^A frames of |X[k]|^2, at
the frequency k * fs / 1024 (see fft.sv).  A sine of amplitude 128 codes (full
scale, about 5 V) exactly at one of those frequencies gives P[k] = 2^30, so

    dB re full scale = 10 log10(P / 2^30).

A sine between two of the frequencies reads up to 1.4 dB low (that's the Hann
window), and an ideal 8-bit ADC's rounding noise reads -75 dB in every k.
"""
import argparse
import time

import numpy as np
import serial                        # pip install pyserial

N = 1024                             # samples per frame in fft.sv
FS_MAX = 25e6                        # the ADC runs at 50 MHz / 2
FULL_SCALE = 2**30                   # P[k] for a sine of amplitude 128 codes at frequency k
ADC_CODES_PER_VOLT = 25.35           # measured: code = 126.7 + 25.35 * V
FLOOR_8BIT = 32                      # P[k] of an ideal 8-bit ADC's rounding noise (1/12 code^2)


def find_port():
    """The first FTDI FT231X serial port (USB ID 0403:6015): the Icepi Zero's."""
    from serial.tools import list_ports
    for p in list_ports.comports():
        if (p.vid, p.pid) == (0x0403, 0x6015):
            return p.device
    raise SystemExit("No Icepi Zero found. Is it plugged in? (Or give --port.)")


def seconds_per_spectrum(d, a):
    """How long the FPGA takes: 2^a frames of (record 1024 samples, FFT, add up
    the powers: 10 * 512 * 6 + 512 * 4 clocks), then 2048 bytes of 10 bits."""
    frame = N * 2**d / FS_MAX + (10 * 512 * 6 + 512 * 4) / 50e6
    return 2**a * frame + 2048 * 10 / 1e6


def parse(raw):
    """2048 bytes from fft.sv -> P[0..511]: 32-bit numbers, least significant byte first."""
    return np.frombuffer(raw, dtype="<u4").astype(float)


def frequencies(d):
    """The frequency of each P[k], in Hz: k * fs / N."""
    return np.arange(N // 2) * (FS_MAX / 2**d) / N


def db_full_scale(P):
    # ##########################################################################
    # ##  KEY LINE: a full-scale sine (amplitude 128 codes) reads 2^30 = 0 dB.
    # ##  (P = 0 would be minus infinity dB: show it as P = 0.5.)
    # ##########################################################################
    return 10 * np.log10(np.maximum(P, 0.5) / FULL_SCALE)


def db_volts(P):
    """Amplitude in dB re 1 V at the ADC input, as in spectrum.py: a sine of
    amplitude A volts exactly at a frequency k reads 20 log10(A).  Full scale,
    128 codes, is 128 / 25.35 = 5.05 V: +14.1 dB re 1 V."""
    return db_full_scale(P) + 20 * np.log10(128 / ADC_CODES_PER_VOLT)


def spectrum(ser, d, a):
    """Ask the FPGA for one spectrum.  Returns P[0..511]."""
    ser.timeout = seconds_per_spectrum(d, a) + 1
    # ##########################################################################
    # ##  KEY LINES: send the command (two hex digits, D then A), then read
    # ##  back 512 numbers of 4 bytes each.
    # ##########################################################################
    ser.write(b"%x%x" % (d, a))
    raw = ser.read(2048)
    if len(raw) != 2048:
        raise RuntimeError(f"got {len(raw)} of 2048 bytes -- is fft.bit loaded? (Or is it "
                           "still busy with an earlier, longer average? Then wait, or reload it.)")
    return parse(raw)


def freq_unit(f_max):
    for scale, unit in ((1e6, "MHz"), (1e3, "kHz"), (1, "Hz")):
        if f_max >= scale:
            return scale, unit
    return 1, "Hz"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-d", type=int, default=0, help="keep 1 sample in 2^d (0..15): fs = 25 MHz / 2^d")
    ap.add_argument("-a", type=int, default=0, help="average 2^a frames per spectrum (0..15)")
    ap.add_argument("--port", help="serial port (default: find the Icepi Zero)")
    ap.add_argument("--once", action="store_true", help="take one spectrum instead of running live")
    ap.add_argument("-o", "--out", help="save the (last) spectrum to this .npz file")
    ap.add_argument("--volts", action="store_true", help="amplitude in dB re 1 V instead of re full scale")
    ap.add_argument("--no-plot", action="store_true", help="take one spectrum and just print its peak")
    ap.add_argument("--quiet", action="store_true",
                    help="turn off the DAC's test square wave, e.g. when the music player is plugged in")
    args = ap.parse_args()
    if not (0 <= args.d <= 15 and 0 <= args.a <= 15):
        raise SystemExit("-d and -a must be 0..15")

    f = frequencies(args.d)
    scale, unit = freq_unit(f[-1])
    to_db = db_volts if args.volts else db_full_scale
    ylabel = "amplitude (dB re 1 V)" if args.volts else "dB re full-scale sine (dBFS)"
    fs = FS_MAX / 2**args.d
    fs_scale, fs_unit = freq_unit(fs)
    title = f"fs = {fs / fs_scale:g} {fs_unit[:-2]}S/s, {2**args.a} frame{'s' * (args.a > 0)} per spectrum"
    print(f"{title}: 0 to {f[-1] / scale:g} {unit} in steps of {f[1] / scale:.4g} {unit}, "
          f"{seconds_per_spectrum(args.d, args.a):.3g} s per spectrum")

    def describe(P):
        k = int(np.argmax(P[2:])) + 2           # the biggest, not counting DC (k = 0,
                                                #   and k = 1 through the window)
        return f"peak {f[k] / scale:.5g} {unit}, {to_db(P)[k]:.1f} dB"

    P = None
    with serial.Serial(args.port or find_port(), 1_000_000, timeout=2) as ser:
        time.sleep(0.05)                 # let the line settle after opening,
        ser.reset_input_buffer()         # and throw away anything stale
        ser.write(b"q" if args.quiet else b"w")   # the DAC's test signal: off or on
        P = spectrum(ser, args.d, args.a)
        print(describe(P))
        if not args.no_plot:
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots()
            line, = ax.plot(f / scale, to_db(P), ".-", markersize=3, linewidth=0.5)
            ax.axhline(to_db(FLOOR_8BIT), color="gray", linestyle="--", linewidth=0.8,
                       label="ideal 8-bit ADC's rounding noise")
            ax.set_xlabel(f"frequency ({unit})")
            ax.set_ylabel(ylabel)
            ax.set_ylim(to_db(0.5) - 5, to_db(FULL_SCALE) + 5)
            ax.legend(loc="upper right")
            ax.grid(True)
            ax.set_title(f"{title}\n{describe(P)}", fontsize=10)
            if args.once:
                plt.show()
            else:
                plt.ion()
                plt.show()
                count, t0 = 0, time.time()
                try:
                    while plt.fignum_exists(fig.number):
                        P = spectrum(ser, args.d, args.a)
                        line.set_ydata(to_db(P))
                        count += 1
                        ax.set_title(f"{title}\n{describe(P)}, "
                                     f"{count / (time.time() - t0):.1f} spectra/s", fontsize=10)
                        fig.canvas.draw_idle()
                        plt.pause(0.001)
                except KeyboardInterrupt:
                    pass

    if args.out:
        np.savez(args.out, freq_hz=f, power=P, db_full_scale=db_full_scale(P), d=args.d, a=args.a)
        print(f"saved to {args.out}")
