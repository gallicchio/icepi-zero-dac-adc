#!/usr/bin/env python3
"""The laptop side of am_radio.sv: listen to the FPGA's AM radio.

    python3 am_radio.py                     # 10 s at 1.000 MHz, then play it: with a cable
                                            #   from the DAC to the ADC, Ode to Joy
    python3 am_radio.py --source tone --plot   # the 1 kHz test tone; plot it and its spectrum
    python3 am_radio.py --rx 1.01e6         # tune 10 kHz away: the station all but vanishes
    python3 am_radio.py --tx 7.2e6 --rx 7.2e6  # move both: 0.1 to 20 MHz
    python3 am_radio.py --source off --rx 1.07e6 --seconds 30
                                            # transmitter off, an antenna on the ADC: a station?
    python3 am_radio.py -o ode.wav --no-play

The FPGA sends its AM detector's output, the envelope, 25,000 times a second, each
sample as two bytes: 0 + its low 7 bits, then 1 + its high 7 bits (see am_radio.sv).
A carrier of amplitude A ADC codes at the receive frequency gives an envelope of
473.1 A, divided by 2^g (the gain command; by default this script picks g itself).
"""
import argparse
import time

import numpy as np

import stream                        # stream.py: save_wav() and play()

F_CLK = 50e6                         # both DDSs: f = TW x 50 MHz / 2^32
FS = 25_000                          # envelope samples per second: 25 MS/s / 1000
ENV_PER_CODE = 473.1                 # envelope for a carrier of 1 ADC code (am_radio.sv's header)
ADC_CODES_PER_VOLT = 25.35           # measured: code = 126.7 + 25.35 * V
FULL = 16383                         # the biggest 14-bit sample; bigger ones are sent as this
SOURCES = {"off": 0, "carrier": 1, "melody": 2, "tone": 3}


def find_port():
    """The first FTDI FT231X serial port (USB ID 0403:6015): the Icepi Zero's."""
    from serial.tools import list_ports
    for p in list_ports.comports():
        if (p.vid, p.pid) == (0x0403, 0x6015):
            return p.device
    raise SystemExit("No Icepi Zero found. Is it plugged in? (Or give --port.)")


def tuning_word(f):
    return int(round(f / F_CLK * 2**32)) & 0xFFFFFFFF


def decode(raw):
    """Bytes from am_radio.sv -> envelope samples, 0..16383.

    A sample is a byte with its top bit 0 (the low 7 bits) followed by one with its
    top bit 1 (the high 7 bits).  So wherever the reading starts -- even halfway
    through a sample -- the pairs find themselves, and a lost byte costs one sample."""
    b = np.frombuffer(raw, dtype=np.uint8).astype(np.int64)
    # ##########################################################################
    # ##  KEY LINES: find each "low byte, then high byte" pair, and join them.
    # ##########################################################################
    starts = np.nonzero((b[:-1] < 128) & (b[1:] >= 128))[0]
    return (b[starts] & 0x7F) | ((b[starts + 1] & 0x7F) << 7)


def command(ser, letter, value):
    """Send one command line, e.g. command(ser, "r", 0x051eb852) sends "r51eb852\\n"."""
    ser.write(b"%s%x\n" % (letter.encode(), value))


def read_envelope(ser, seconds):
    """Read `seconds` of envelope samples."""
    n = 2 * int(seconds * FS) + 2               # bytes: 2 per sample, and a spare pair
    ser.timeout = seconds + 2
    raw = ser.read(n)
    if len(raw) < n:
        raise RuntimeError(f"got {len(raw)} of {n} bytes -- is am_radio.bit loaded?")
    env = decode(raw)
    lost = len(raw) // 2 - 1 - len(env)
    if lost > 0:
        print(f"  ({lost} samples lost on the way: the laptop didn't keep up?)")
    return env[:int(seconds * FS)]


def settle(ser):
    """After a command: give the FPGA time to act on it and its filters time to
    fill (5 ms), then throw away whatever was already on its way."""
    time.sleep(0.05)
    ser.reset_input_buffer()
    read_envelope(ser, 0.02)


def auto_gain(ser):
    """The smallest g for which the loudest of 0.3 s of envelope / 2^g stays below
    8192, half of the 14 bits: room for louder moments.  If g = 0 overflows,
    look again at g = 4, then 8 (2^18 / 2^8 can't overflow)."""
    for g in (0, 4, 8):
        command(ser, "g", g)
        settle(ser)
        peak = int(read_envelope(ser, 0.3).max())
        if peak < FULL:
            break
    return max(0, ((peak << g) // 8192).bit_length())


def listen(ser, rx=1e6, tx=1e6, source="melody", gain=None, seconds=10.0):
    """Tune, transmit, set the gain, listen.  Returns (the envelope in the FPGA's
    units before the shift, i.e. the samples x 2^g; the 14-bit samples; g)."""
    # ##########################################################################
    # ##  KEY LINES: the commands: transmit and receive frequencies, what to
    # ##  transmit, and the gain; then "m" again, so the melody starts from
    # ##  the top as we start listening.
    # ##########################################################################
    command(ser, "t", tuning_word(tx))
    command(ser, "r", tuning_word(rx))
    command(ser, "m", SOURCES[source])
    g = auto_gain(ser) if gain is None else gain
    command(ser, "g", g)
    command(ser, "m", SOURCES[source])
    settle(ser)
    samples = read_envelope(ser, seconds)
    return samples.astype(float) * 2**g, samples, g


def describe(env, samples, g):
    codes = env / ENV_PER_CODE                   # carrier amplitude, ADC codes
    clipped = np.mean(samples >= FULL)
    audio = codes - codes.mean()
    spec = np.abs(np.fft.rfft(audio * np.hanning(len(audio))))
    f = np.fft.rfftfreq(len(audio), 1 / FS)
    k = int(np.argmax(spec[1:])) + 1
    print(f"{len(samples)} samples ({len(samples) / FS:.2f} s), g = {g}: carrier amplitude "
          f"{codes.mean():.2f} ADC codes = {codes.mean() / ADC_CODES_PER_VOLT:.3f} V at the ADC")
    if codes.mean() > 0:
        print(f"  the sound: {audio.std() / codes.mean() * 100:.1f}% rms of the carrier, "
              f"loudest frequency {f[k]:.1f} Hz" + (f"; {clipped * 100:.2f}% of samples clipped "
                                                    f"at 16383: use a bigger --gain" if clipped else ""))


def plot(env, g, title):
    import matplotlib.pyplot as plt
    volts = env / ENV_PER_CODE / ADC_CODES_PER_VOLT
    t_ms = np.arange(len(env)) / FS * 1e3
    fig, (a, b) = plt.subplots(2, 1, figsize=(9, 7))
    a.plot(t_ms, volts, ".-", markersize=2, linewidth=0.5)
    a.set_xlabel("time (ms)")
    a.set_ylabel("envelope: carrier amplitude at the ADC (V)")
    a.set_title(title, fontsize=10)
    a.grid(True)
    audio = env - env.mean()
    w = np.hanning(len(audio))
    # amplitude spectrum, scaled so a sine of amplitude a volts reads 20 log10(a) dB re 1 V
    spec = np.abs(np.fft.rfft(audio * w)) * 2 / w.sum() / ENV_PER_CODE / ADC_CODES_PER_VOLT
    f = np.fft.rfftfreq(len(audio), 1 / FS)
    b.plot(f / 1e3, 20 * np.log10(np.maximum(spec, 1e-9)), linewidth=0.7)
    b.set_xlabel("audio frequency (kHz)")
    b.set_ylabel("dB re 1 V (envelope minus its average)")
    b.set_xlim(0, FS / 2e3)
    b.grid(True)
    plt.tight_layout()
    plt.show()


def main(argv=None, ser=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", help="serial port (default: find the Icepi Zero)")
    ap.add_argument("--rx", type=float, default=1e6, help="receive frequency, Hz (default 1e6)")
    ap.add_argument("--tx", type=float, default=1e6, help="transmit frequency, Hz (default 1e6)")
    ap.add_argument("--source", choices=SOURCES, default="melody", help="what to transmit")
    ap.add_argument("--seconds", type=float, default=10.0, help="how long to listen (default 10)")
    ap.add_argument("--gain", type=int, choices=range(16), metavar="G",
                    help="output = envelope / 2^G, 0..15 (default: pick it automatically)")
    ap.add_argument("-o", "--out", default="am_radio.wav", help="sound file (default am_radio.wav)")
    ap.add_argument("--no-play", action="store_true", help="just save the sound file")
    ap.add_argument("--plot", action="store_true", help="plot the envelope and its spectrum")
    args = ap.parse_args(argv)
    for f in (args.rx, args.tx):
        if not 0 <= f < F_CLK / 2:
            raise SystemExit("frequencies must be 0 to 25 MHz (0.1 to 20 MHz is sensible)")

    print(f"transmitting {args.source} at {tuning_word(args.tx) * F_CLK / 2**32 / 1e6:.6f} MHz, "
          f"receiving at {tuning_word(args.rx) * F_CLK / 2**32 / 1e6:.6f} MHz")
    if ser is None:
        import serial                    # pip install pyserial
        ser = serial.Serial(args.port or find_port(), 1_000_000, timeout=2)
    with ser:
        time.sleep(0.05)                 # let the line settle after opening
        ser.reset_input_buffer()
        env, samples, g = listen(ser, args.rx, args.tx, args.source, args.gain, args.seconds)
    describe(env, samples, g)
    # The sound, in ADC codes of carrier amplitude.  stream.py makes it as loud as it
    # can, unless its swings are under 1 code: then it plays quieter, in proportion.
    if args.no_play:
        stream.save_wav(env / ENV_PER_CODE, args.out, fs=FS)
    else:
        stream.play(env / ENV_PER_CODE, args.out, fs=FS)
    if args.plot:
        plot(env, g, f"received at {args.rx / 1e6:g} MHz, g = {g} ({args.source} "
                     f"transmitted at {args.tx / 1e6:g} MHz)")
    return env, samples, g


if __name__ == "__main__":
    main()
