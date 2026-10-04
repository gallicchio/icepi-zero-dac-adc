#!/usr/bin/env python3
"""The laptop side of ddc.sv (6.11): tones out of the DAC, and I/Q frames in from the DDC.

    python3 ddc.py --tone 6.78e6              # a continuous 6.78 MHz tone (finds the port)
    python3 ddc.py /dev/ttyUSB0 --tone 6.78e6 --amp 50
    python3 ddc.py --monitor                  # NCO at 6.78 MHz: print |z|, dB and the
                                              #   frequency offset once a second (Ctrl-C stops)
    python3 ddc.py --monitor --rx 6.7800e6 --decim 13
    python3 ddc.py --queue 0,1,0,1 --symbol 8388608     # 4 symbols of 167.77 ms: tones
                                              #   6.78 MHz + idx x 5.96 Hz
    python3 ddc.py --queue 0,1,2,3 --symbol 50000000 --monitor   # 1 s symbols, watched:
                                              #   the offset should step 0, 6, 12, 18 Hz
    python3 ddc.py --off                      # silence
    python3 ddc.py --selftest                 # the frame parser against made-up bytes

    import ddc
    ser = ddc.open_port()                     # or open_port("/dev/ttyUSB0")
    ddc.set_tone(ser, 0, 6.78e6); ddc.set_tone(ser, 1, 6.78e6 + ddc.F_BIN)
    ddc.set_amp(ser, 100); ddc.set_symbol(ser, 2**23)
    ddc.queue(ser, [0, 1, 1, 0, None])        # None = a silent symbol
    ddc.set_rx(ser, 6.78e6); ddc.set_decim(ser, 13); ddc.stream(ser, True)
    z = ddc.read_iq(ser, 3052)                # one second of complex samples, in ADC codes

Every frame from the board is 7 bytes: 0xA5, then I and Q as 24-bit signed big-endian,
I = sum(x cos) >>> (d - 9) over 2^d ADC samples.  A tone of A codes at the NCO frequency
gives |I + jQ| = A x 2^d x 127/2 / 2^(d-9) = A x 32512, so read_iq divides by 32512 and
returns ADC codes.  The tone's offset from the NCO is the slope of the phase: a tone
above the NCO turns the I/Q counterclockwise (checked in ddc_tb.sv with +df=1000).
"""
import argparse
import struct
import sys
import time

import numpy as np

FS_DAC, FS_ADC = 50e6, 25e6
F_BIN = FS_ADC / 2**22          # 5.96 Hz: one FT8-style tone spacing (symbol = 2^22 ADC samples)
SYMBOL = 2**23                  # the FT8-style symbol in 50 MHz clocks: 167.77 ms
HDR = 0xA5
FRAME = 7
SCALE = 2**9 * 127 / 2          # 32512 I/Q units per ADC code of tone amplitude
SILENT = 0xFF                   # the FIFO entry for a silent symbol


# ---- the port -----------------------------------------------------------------------
def find_port():
    """The first FTDI FT231X serial port (USB ID 0403:6015): the Icepi Zero's."""
    from serial.tools import list_ports
    for p in list_ports.comports():
        if (p.vid, p.pid) == (0x0403, 0x6015):
            return p.device
    raise SystemExit("No Icepi Zero found. Is it plugged in? (Or give its port.)")


def open_port(port=None, baud=1_000_000):
    import serial                                   # pip install pyserial
    ser = serial.Serial(port or find_port(), baud, timeout=1)
    time.sleep(0.02)
    ser.reset_input_buffer()                        # the FT231X's junk byte on opening
    return ser


# ---- the commands (see the header of ddc.sv) ---------------------------------------
def dac_word(f_hz):
    return int(round(f_hz / FS_DAC * 2**32)) & 0xFFFFFFFF


def adc_word(f_hz):
    return int(round(f_hz / FS_ADC * 2**32)) & 0xFFFFFFFF


def set_tone(ser, idx, f_hz):
    """Tone table entry idx (0..7) = f_hz, as the DAC's tuning word."""
    ser.write(b"W" + bytes([idx & 7]) + struct.pack(">I", dac_word(f_hz)))


def set_amp(ser, amp):
    """The transmitted amplitude in DAC codes, 0..127 (0 = silent)."""
    ser.write(b"A" + bytes([max(0, min(127, int(amp)))]))


def set_symbol(ser, clocks):
    """The symbol length in 50 MHz clocks (2^23 = 167.77 ms)."""
    ser.write(b"T" + struct.pack(">I", int(clocks) & 0xFFFFFFFF))


def queue(ser, indices):
    """Append tone indices (0..7, or None / 0xFF for silence) to the board's 256-entry
    FIFO; it plays one per symbol, starting at once if it was idle."""
    idx = bytes([SILENT if i is None else (i & 0xFF) for i in indices])
    for k in range(0, len(idx), 255):               # 'M' takes at most 255 at a time
        chunk = idx[k:k + 255]
        ser.write(b"M" + bytes([len(chunk)]) + chunk)


def tone(ser, idx_or_none):
    """A continuous tone from table entry idx (for tuning antennas); None turns it off."""
    ser.write(b"C" + bytes([SILENT if idx_or_none is None else idx_or_none & 7]))


def set_rx(ser, f_hz):
    """The receiver's NCO frequency (restarts the boxcar)."""
    ser.write(b"R" + struct.pack(">I", adc_word(f_hz)))


def set_decim(ser, d):
    """One I/Q sample per 2^d ADC samples, d = 10..16 (restarts the boxcar).
    d = 13 is 3051.76 samples a second; d = 10 is more than the UART carries."""
    assert 10 <= d <= 16
    ser.write(b"D" + bytes([d]))


def stream(ser, on):
    ser.write(b"S" + bytes([1 if on else 0]))


def iq_rate(d=13):
    """I/Q samples per second at decimation d."""
    return FS_ADC / 2**d


# ---- the frames back ----------------------------------------------------------------
def parse_frames(buf):
    """Pull every complete frame out of `buf` (bytes).  Returns (z, rest): z the complex
    I + jQ values (raw units, not yet scaled), rest the unparsed tail to prepend to the
    next read.  Resyncs on the 0xA5 header: a header is only believed if the frame after
    it also starts with 0xA5 (or the buffer ends there), so a data byte that happens to
    be 0xA5 does not throw the alignment off."""
    buf = bytes(buf)
    out = []
    i = 0
    n = len(buf)
    while i + FRAME <= n:
        if buf[i] != HDR or (i + FRAME < n and buf[i + FRAME] != HDR):
            i += 1
            continue
        I = int.from_bytes(buf[i + 1:i + 4], "big", signed=True)
        Q = int.from_bytes(buf[i + 4:i + 7], "big", signed=True)
        out.append(complex(I, Q))
        i += FRAME
    # the tail: from the last byte that could still start a frame
    j = buf.find(bytes([HDR]), i)
    rest = buf[j:] if j >= 0 else b""
    return np.array(out, dtype=complex), rest


def read_iq(ser, n, d=13):
    """n I/Q samples from the stream (streaming must be on), scaled to ADC codes: a tone
    of A codes at the NCO frequency gives |z| = A.  (The scale does not depend on d; it
    is here for the record, and to size the read.)"""
    want = int(n)
    got = []
    total = 0
    rest = b""
    deadline = time.time() + want / iq_rate(d) + 2.0
    while total < want:
        chunk = ser.read(max(FRAME, (want - total) * FRAME + FRAME))
        if not chunk:
            if time.time() > deadline:
                raise RuntimeError("only %d of %d frames: is ddc.bit loaded and streaming on?"
                                   % (total, want))
            continue
        z, rest = parse_frames(rest + chunk)
        if len(z):
            got.append(z)
            total += len(z)
    z = np.concatenate(got)[:want]
    return z / SCALE


def summarize(z, d=13):
    """|z| in codes and dB (re 1 code), and the tone's offset from the NCO, from the
    average phase step between consecutive samples."""
    mag = np.abs(z).mean()
    db = 20 * np.log10(max(mag, 1e-9))
    step = np.angle(np.sum(z[1:] * np.conj(z[:-1])))     # radians per I/Q sample
    f_off = step / (2 * np.pi) * iq_rate(d)
    return mag, db, f_off


# ---- a test of the parser, with bytes made up here ---------------------------------
def make_frame(I, Q):
    return bytes([HDR]) + struct.pack(">i", I)[1:] + struct.pack(">i", Q)[1:]


def selftest():
    vals = [(650240, 0), (-78919, -647022), (-5921371, -0x800000),   # -5921371 is bytes A5 A5 A5
            (1, -1), (0x7FFFFF, 0)]
    frames = b"".join(make_frame(I, Q) for I, Q in vals)
    # junk before, a frame whose data contains 0xA5, and a cut-off frame at the end
    buf = b"\x12\xa5\x00" + frames + frames[:4]
    z, rest = parse_frames(buf)
    assert len(z) == len(vals), (len(z), z)
    for (I, Q), v in zip(vals, z):
        assert v == complex(I, Q), (I, Q, v)
    assert rest == frames[:4], rest
    # the tail joins the next read: the rest of the cut-off frame, then another
    z2, rest2 = parse_frames(rest + frames[4:FRAME] + make_frame(5, 6))
    assert list(z2) == [complex(*vals[0]), complex(5, 6)] and rest2 == b"", (z2, rest2)
    # the scale and the offset estimate: a 20-code tone 3 Hz above the NCO at d = 13
    t = np.arange(3052) / iq_rate(13)
    z = 20 * np.exp(2j * np.pi * 3.0 * t) * SCALE
    buf = b"".join(make_frame(int(round(v.real)), int(round(v.imag))) for v in z)
    zz, _ = parse_frames(buf)
    mag, db, f_off = summarize(zz / SCALE, 13)
    assert abs(mag - 20) < 0.01 and abs(f_off - 3.0) < 0.01, (mag, f_off)
    print("selftest: %d frames parsed, tail kept, scale %.3f codes, offset %.3f Hz: OK"
          % (len(vals), mag, f_off))


# ---- the command line -----------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("port", nargs="?", help="serial port (default: the first Icepi Zero)")
    ap.add_argument("--tone", type=float, metavar="HZ", help="a continuous tone at HZ")
    ap.add_argument("--amp", type=int, default=100, help="DAC codes, 0..127 (default 100)")
    ap.add_argument("--queue", metavar="IDX,IDX,...", help="play these tone indices (0..7, x = silence), "
                    "one a symbol, from a table of 8 tones --carrier + idx x 5.96 Hz")
    ap.add_argument("--carrier", type=float, default=6.78e6, metavar="HZ", help="tone 0 (default 6.78e6)")
    ap.add_argument("--symbol", type=int, default=SYMBOL, help="symbol length in clocks (default 2^23)")
    ap.add_argument("--monitor", action="store_true", help="stream I/Q and print |z|, dB, offset")
    ap.add_argument("--rx", type=float, default=6.78e6, metavar="HZ", help="the NCO (default 6.78e6)")
    ap.add_argument("--decim", type=int, default=13, help="log2 decimation, 10..16 (default 13)")
    ap.add_argument("--off", action="store_true", help="silence, streaming off")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    if not (args.tone or args.queue or args.monitor or args.off):
        ap.error("say what to do: --tone, --queue, --monitor or --off")

    ser = open_port(args.port)
    if args.off:
        tone(ser, None)
        set_amp(ser, 0)
        stream(ser, False)
        print("off")
    if args.tone:
        set_tone(ser, 0, args.tone)
        set_amp(ser, args.amp)
        tone(ser, 0)
        print("continuous tone at %.6f MHz, %d codes (word 0x%08x)" % (args.tone / 1e6, args.amp, dac_word(args.tone)))
    if args.queue:
        idx = [None if s.strip().lower() in ("x", "-", "ff") else int(s) for s in args.queue.split(",")]
        for k in range(8):                              # the FT8-style tones, 5.96 Hz apart
            set_tone(ser, k, args.carrier + k * F_BIN)
        set_amp(ser, args.amp)
        set_symbol(ser, args.symbol)
        queue(ser, idx)
        print("tones %.6f MHz + idx x %.4f Hz; queued %d symbols of %.3f ms: %s"
              % (args.carrier / 1e6, F_BIN, len(idx), args.symbol / 50e3, idx))
    if args.monitor:
        d = args.decim
        set_rx(ser, args.rx)
        set_decim(ser, d)
        stream(ser, True)
        ser.reset_input_buffer()
        n = int(round(iq_rate(d)))
        print("NCO %.6f MHz (word 0x%08x), d = %d: %.2f I/Q samples a second, %d a line"
              % (args.rx / 1e6, adc_word(args.rx), d, iq_rate(d), n))
        try:
            while True:
                z = read_iq(ser, n, d)
                mag, db, f_off = summarize(z, d)
                print("|z| = %8.3f codes  %6.1f dB   phase %7.1f deg   offset %+9.3f Hz"
                      % (mag, db, np.degrees(np.angle(z[-1])), f_off))
        except KeyboardInterrupt:
            pass
        stream(ser, False)
    ser.close()


if __name__ == "__main__":
    main()
