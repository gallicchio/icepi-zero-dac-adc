#!/usr/bin/env python3
"""The laptop side of sigma_delta.sv (7.05): pick the sine, the mode and the decimation,
and watch what the CIC recovers from the 1-bit stream, live.

    python3 sigma_delta_live.py --tone 1000 --amp 64 --mode 2      # a 1 kHz sine, 1-bit 2nd order
    python3 sigma_delta_live.py --monitor                          # d = 10: print the recovered
                                                                   #   amplitude and noise once a second
    python3 sigma_delta_live.py --monitor --plot                   # ... and draw the last two cycles
    python3 sigma_delta_live.py --mode 0 --amp 1.5 --monitor       # 8-bit plain at a code and a half: steps
    python3 sigma_delta_live.py --mode 3 --amp 1.5 --monitor       # noise-shaped: a sine
    python3 sigma_delta_live.py --off
    python3 sigma_delta_live.py --selftest

    import sigma_delta_live as live
    ser = live.open_port()
    live.set_tone(ser, 1000); live.set_amp(ser, 64); live.set_mode(ser, 2)
    live.set_decim(ser, 10); live.stream(ser, True)
    x = live.read_samples(ser, 24414, 10)        # one second, in ADC codes

Modes: 0 = 8-bit plain, 1 = 1-bit first order, 2 = 1-bit second order, 3 = 8-bit
first-order noise-shaped.  Frames are 4 bytes: 0xA5, then 24 bits signed big-endian,
2^16 per ADC code whatever d is (d = 8..16; the UART keeps up from d = 10).
The CIC is sinc^3: the first sidelobe at 1.5 x the output rate is 40 dB down, so a
little of the shaped noise around multiples of the output rate leaks through; the
monitor's noise figure is after a further windowed-sinc to a quarter of the output
rate, which takes that out.  The amplitude is a lock-in at the frequency sent.
"""
import argparse
import struct
import sys
import time

import numpy as np

FS = 25e6
HDR = 0xA5
FRAME = 4
SCALE = 2**16                   # frame units per ADC code
MODES = {0: "8-bit plain", 1: "1-bit 1st order", 2: "1-bit 2nd order", 3: "8-bit 1st-order shaped"}


def find_port():
    """The first FTDI FT231X serial port (USB ID 0403:6015): the Icepi Zero's."""
    from serial.tools import list_ports
    for p in list_ports.comports():
        if (p.vid, p.pid) == (0x0403, 0x6015):
            return p.device
    raise SystemExit("No Icepi Zero found. Is it plugged in? (Or give its port.)")


def open_port(port=None, baud=1_000_000):
    import serial
    ser = serial.Serial(port or find_port(), baud, timeout=1)
    time.sleep(0.02)
    ser.reset_input_buffer()
    return ser


def word(f_hz):
    return int(round(f_hz / FS * 2**32)) & 0xFFFFFFFF


def set_tone(ser, f_hz):
    ser.write(b"F" + struct.pack(">I", word(f_hz)))


def set_amp(ser, codes):
    """Amplitude in DAC codes, 0..127.99 (sent in 1/256 of a code)."""
    ser.write(b"A" + struct.pack(">H", max(0, min(32767, int(round(codes * 256))))))


def set_mode(ser, mode):
    ser.write(b"M" + bytes([mode & 3]))


def set_decim(ser, d):
    assert 8 <= d <= 16
    ser.write(b"D" + bytes([d]))


def stream(ser, on):
    ser.write(b"S" + bytes([1 if on else 0]))


def rate(d):
    return FS / 2**d


def parse_frames(buf):
    """Every complete frame in buf -> (values, the unparsed tail).  A header is only
    believed if the next frame starts with one too (or the buffer ends), as ddc.py."""
    buf = bytes(buf)
    out, i, n = [], 0, len(buf)
    while i + FRAME <= n:
        if buf[i] != HDR or (i + FRAME < n and buf[i + FRAME] != HDR):
            i += 1
            continue
        out.append(int.from_bytes(buf[i + 1:i + 4], "big", signed=True))
        i += FRAME
    j = buf.find(bytes([HDR]), i)
    return np.array(out, float), (buf[j:] if j >= 0 else b"")


def read_samples(ser, n, d=10):
    """n samples from the stream, in ADC codes."""
    got, total, rest = [], 0, b""
    deadline = time.time() + n / rate(d) + 2.0
    while total < n:
        chunk = ser.read(max(FRAME, (n - total) * FRAME + FRAME))
        if not chunk:
            if time.time() > deadline:
                raise RuntimeError("only %d of %d frames: is sigma_delta.bit loaded and streaming on?" % (total, n))
            continue
        v, rest = parse_frames(rest + chunk)
        if len(v):
            got.append(v)
            total += len(v)
    return np.concatenate(got)[:n] / SCALE


def lowpass(x, cut_frac):
    """A windowed sinc to cut_frac of the sample rate (0.25: a quarter), linear, ends kept."""
    taps = 257
    k = np.arange(taps) - (taps - 1) / 2
    h = np.sinc(2 * cut_frac * k) * 2 * cut_frac * np.kaiser(taps, 10)
    h /= h.sum()
    return np.convolve(x, h, mode="same")


def summarize(x, f_hz, d):
    """Amplitude (a lock-in at f_hz), the mean, and the noise rms after a low-pass to a
    quarter of the output rate with the sine itself subtracted."""
    n = np.arange(len(x))
    w = 2 * np.pi * f_hz / rate(d) * n
    z = 2 * np.mean((x - x.mean()) * np.exp(-1j * w))
    fit = x.mean() + (z * np.exp(1j * w)).real
    resid = lowpass(x - fit, 0.25)[64:-64]
    return abs(z), x.mean(), float(np.sqrt(np.mean(resid**2)))


def selftest():
    vals = [1, -1, 0x7FFFFF, -0x800000, 0xA5A5A5 - 2**24, 4194304]
    frames = b"".join(bytes([HDR]) + struct.pack(">i", v)[1:] for v in vals)
    v, rest = parse_frames(b"\x07\xa5\x01" + frames + frames[:2])
    assert list(v) == vals, v
    assert rest == frames[:2], rest
    v2, rest2 = parse_frames(rest + frames[2:FRAME] + frames[:FRAME])
    assert list(v2) == [vals[0], vals[0]] and rest2 == b"", (v2, rest2)
    t = np.arange(24414) / rate(10)
    x = 126.8 + 64 * np.sin(2 * np.pi * 1000 * t) + 0.01 * np.random.default_rng(1).standard_normal(len(t))
    a, m, r = summarize(x, 1000, 10)
    assert abs(a - 64) < 0.01 and abs(m - 126.8) < 0.01 and r < 0.02, (a, m, r)
    print("selftest: %d frames parsed, tail kept; lock-in %.3f codes, mean %.3f, noise %.4f: OK" % (len(vals), a, m, r))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("port", nargs="?", help="serial port (default: the first Icepi Zero)")
    ap.add_argument("--tone", type=float, metavar="HZ", help="the sine's frequency")
    ap.add_argument("--amp", type=float, metavar="CODES", help="its amplitude in DAC codes (0..127.99)")
    ap.add_argument("--mode", type=int, choices=[0, 1, 2, 3], help="0 plain, 1 1-bit 1st, 2 1-bit 2nd, 3 8-bit shaped")
    ap.add_argument("--decim", type=int, default=10, help="log2 decimation, 8..16 (default 10)")
    ap.add_argument("--monitor", action="store_true", help="stream and print, once a second (Ctrl-C stops)")
    ap.add_argument("--plot", action="store_true", help="--monitor: draw the last two cycles as they come")
    ap.add_argument("--f", type=float, default=1000.0, help="--monitor: the frequency to lock in at (default 1000)")
    ap.add_argument("--off", action="store_true", help="amplitude 0, streaming off")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    if not any(x is not None for x in (args.tone, args.amp, args.mode)) and not (args.monitor or args.off):
        ap.error("say what to do: --tone / --amp / --mode, --monitor, or --off")
    ser = open_port(args.port)
    if args.off:
        set_amp(ser, 0)
        stream(ser, False)
        print("off")
    if args.tone is not None:
        set_tone(ser, args.tone)
        args.f = args.tone
        print("tone %.3f Hz (word 0x%08x)" % (args.tone, word(args.tone)))
    if args.amp is not None:
        set_amp(ser, args.amp)
        print("amplitude %.3f codes" % args.amp)
    if args.mode is not None:
        set_mode(ser, args.mode)
        print("mode %d: %s" % (args.mode, MODES[args.mode]))
    if args.monitor:
        d = args.decim
        set_decim(ser, d)
        stream(ser, True)
        ser.reset_input_buffer()
        n = int(round(rate(d)))
        print("d = %d: %.1f samples a second; lock-in at %.1f Hz" % (d, rate(d), args.f))
        if args.plot:
            import matplotlib.pyplot as plt
            plt.ion()
            fig, ax = plt.subplots(figsize=(8, 4))
            line, = ax.plot([], [], ".-", ms=3)
            ax.set_xlabel("time (ms)"); ax.set_ylabel("ADC codes"); ax.set_title("the CIC's output")
        try:
            while True:
                x = read_samples(ser, n, d)
                a, m, r = summarize(x, args.f, d)
                print("amplitude %8.4f codes   mean %9.4f   noise %.4f codes rms (to %.0f Hz)"
                      % (a, m, r, rate(d) / 4))
                if args.plot:
                    k = int(2 * rate(d) / args.f)
                    t = np.arange(k) / rate(d) * 1e3
                    line.set_data(t, x[:k]); ax.relim(); ax.autoscale_view()
                    fig.canvas.draw(); fig.canvas.flush_events()
        except KeyboardInterrupt:
            pass
        stream(ser, False)
    ser.close()


if __name__ == "__main__":
    main()
