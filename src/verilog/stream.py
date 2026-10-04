#!/usr/bin/env python3
"""The laptop side of adc_stream.sv: read 0.1 s of samples and plot them.

    python3 stream.py                 # finds the Icepi Zero's serial port by itself
    python3 stream.py -n 50000        # a whole second
    python3 stream.py --port /dev/ttyUSB1   # or name the port yourself
    python3 stream.py -n 500000 --play   # 10 s, then play it through the laptop's speaker
    python3 stream.py -n 500000 --play --bits 3     # ...as if the ADC had 3 bits
    python3 stream.py -n 500000 --play --keep 10    # ...as if it took 5,000 samples a second
    python3 stream.py -n 500000 --play --reverse    # ...backwards
"""
import argparse
import shutil
import subprocess
import wave

import numpy as np
import serial                         # pip install pyserial
from serial.tools import list_ports

FS = 50_000                           # samples per second: adc_stream.sv sends one every 20 us


def find_port():
    """The first FTDI FT231X serial port (USB ID 0403:6015): the Icepi Zero's."""
    for p in list_ports.comports():
        if (p.vid, p.pid) == (0x0403, 0x6015):
            return p.device
    raise SystemExit("No Icepi Zero found. Is it plugged in? (Or give --port.)")


def requantize(code, bits):
    """What an ADC with fewer bits would have recorded: only the top `bits` bits of each
    sample, put back in the middle of its step."""
    step = 2 ** (8 - bits)
    return (code // step) * step + step / 2


def save_wav(code, path="stream.wav", fs=FS):
    """Save the samples (taken at fs) as a sound file: 16-bit, 48 kHz, as loud as possible."""
    x = code - code.mean()                       # remove the ADC's mid-scale offset
    x = x / max(1, np.abs(x).max())              # as loud as it can be without clipping
    # Sound cards want 44.1 or 48 kHz, not 50 kHz: interpolate onto a 48 kHz grid.
    t48 = np.arange(int(len(x) * 48_000 / fs)) / 48_000
    x48 = np.interp(t48, np.arange(len(x)) / fs, x)
    with wave.open(path, "wb") as w:             # 16-bit mono WAV
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(48_000)
        w.writeframes((x48 * 32000).astype("<i2").tobytes())
    print(f"wrote {path}")
    return x48


def play(code, path="stream.wav", fs=FS):
    """Play the samples through the laptop's speaker (and save them as a sound file)."""
    x48 = save_wav(code, path, fs)
    try:
        import sounddevice                       # pip install sounddevice, if you like
        print(f"Playing {path} through the laptop's speaker with sounddevice...")
        sounddevice.play(x48, 48_000, blocking=True)
        return
    except ImportError:
        pass
    for player in ["afplay", "paplay", "aplay"]:  # macOS, then Linux
        if shutil.which(player):
            print(f"Playing {path} through the laptop's speaker with {player}...")
            subprocess.run([player, path])
            return
    print(f"no audio player found: open {path} yourself")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", help="serial port (default: find it)")
    ap.add_argument("-n", type=int, default=5000, help="number of samples (default 5000)")
    ap.add_argument("--play", action="store_true",
                    help="play the samples through the laptop's speaker (and save stream.wav)")
    ap.add_argument("--bits", type=int, default=8, help="--play: keep only this many bits (1..8)")
    ap.add_argument("--keep", type=int, default=1, help="--play: keep only every KEEP-th sample")
    ap.add_argument("--reverse", action="store_true", help="--play: play it backwards")
    args = ap.parse_args()

    # read() gives up when the timeout runs out, so allow the n / FS seconds the samples take
    with serial.Serial(args.port or find_port(), 1_000_000, timeout=args.n / FS + 2) as ser:
        ser.reset_input_buffer()      # throw away whatever arrived before we were ready
        # ######################################################################
        # ##  KEY LINE: every byte that arrives is one ADC sample, 0..255.
        # ######################################################################
        raw = ser.read(args.n)

    code = np.frombuffer(raw, dtype=np.uint8)
    volts = (code - 126.7) / 25.35    # the ADC's calibration, from the hardware table
    t_ms = np.arange(len(code)) / FS * 1e3
    print(f"{len(code)} samples; codes {code.min()}..{code.max()}, "
          f"{volts.min():.2f} V to {volts.max():.2f} V")
    if args.play:
        played = requantize(code.astype(float), args.bits)
        # Every KEEP-th sample: 50,000 / KEEP a second.  No filter first, so anything
        # above the new Nyquist frequency folds back: aliasing, as in 1.06.
        played = played[::args.keep]
        if args.reverse:
            played = played[::-1]
        play(played, fs=FS / args.keep)

    import matplotlib.pyplot as plt
    plt.plot(t_ms, volts, ".-", markersize=3, linewidth=0.5)
    plt.xlabel("time (ms)")
    plt.ylabel("ADC input (V)")
    plt.grid(True)
    plt.show()
