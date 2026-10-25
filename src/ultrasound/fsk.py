#!/usr/bin/env python3
"""4.06: a frequency-shift-keying modem through the air, on ddc.sv (6.12).

    python3 fsk.py "HELLO THROUGH THE AIR"          # 509 baud (the default)
    python3 fsk.py "HELLO" --baud 1000              # the nearest rate it can do: 1017
    python3 fsk.py --ber --baud 509 --frames 20     # random bits: count the errors

ddc.bit must be loaded (in src/twoboard: make load-ddc).  Its transmitter has a table
of 8 tones and a FIFO of tone indices, played one per symbol and switched without a
phase jump; this modem uses two of the tones, a 0 at fc - df/2 and a 1 at fc + df/2,
with df equal to the baud rate.  Its receiver is a digital down-converter at fc that
streams I/Q, 12,207 samples a second (d = 11), so a symbol is a whole number M of
I/Q samples and the baud rate is 12207/M: 1017 (M = 12), 509 (24), 254 (48), ...

The receiver here is non-coherent, as FT8's (6.12) is with eight tones: correlate
each symbol's I/Q with each tone, compare the energies, keep the bigger.  It finds
where the symbols start from a 13-symbol Barker sync word at the front of every
frame.  A frame is at most 255 symbols (one FIFO load): the sync word and 242 bits.
"""
import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "twoboard"))
import ddc                                      # noqa: E402  (6.12's laptop side)

FC = 40300.0                                    # Hz: the pair's peak (sweep.py)
D = 11                                          # ddc.sv decimation: 2^11 ADC samples per I/Q
FS_IQ = ddc.FS_ADC / 2**D                       # 12,207.03 I/Q samples a second
CLOCKS_PER_IQ = 2 ** (D + 1)                    # 4096 clocks of 50 MHz
BARKER = np.array([1, 1, 1, 1, 1, 0, 0, 1, 1, 0, 1, 0, 1])
MAX_SYMBOLS = 255


def text_bits(text):
    return np.unpackbits(np.frombuffer(text.encode("ascii"), np.uint8))


def bits_text(bits):
    b = np.packbits(np.asarray(bits[:len(bits) // 8 * 8], np.uint8))
    return "".join(chr(c) if 32 <= c < 127 else "?" for c in b)


class Modem:
    def __init__(self, port=None, M=24, fc=FC, amp=127):
        self.M = M
        self.fc = fc
        self.baud = FS_IQ / M
        self.df = self.baud                     # the closest orthogonal spacing
        self.ser = ddc.open_port(port)
        ddc.set_tone(self.ser, 0, fc - self.df / 2)
        ddc.set_tone(self.ser, 1, fc + self.df / 2)
        ddc.set_amp(self.ser, amp)
        ddc.set_symbol(self.ser, M * CLOCKS_PER_IQ)
        ddc.tone(self.ser, None)                # no continuous tone: the FIFO plays
        ddc.set_rx(self.ser, fc)
        ddc.set_decim(self.ser, D)

    def send_and_listen(self, bits):
        """Queue the sync word and `bits`; return the I/Q stream (ADC codes) that heard them."""
        symbols = np.concatenate([BARKER, bits]).astype(int)
        assert len(symbols) <= MAX_SYMBOLS
        ddc.stream(self.ser, True)
        time.sleep(0.03)
        self.ser.reset_input_buffer()
        pre = int(0.02 * FS_IQ)                 # 20 ms of silence first, to see the start
        z0 = ddc.read_iq(self.ser, pre, D)
        ddc.queue(self.ser, list(symbols))
        n = (len(symbols) + 6) * self.M + int(0.05 * FS_IQ)   # and 50 ms for USB latency
        z1 = ddc.read_iq(self.ser, n, D)
        ddc.stream(self.ser, False)
        return np.concatenate([z0, z1])


def energies(z, M):
    """For every possible symbol start n: the energy at tone 0 and tone 1 over the M
    I/Q samples from n.  (A moving correlation: z times each tone's conjugate, summed
    over a window of M.)  The tones are at -df/2 and +df/2 from the NCO, df = 1/T."""
    df = FS_IQ / M
    t = np.arange(len(z)) / FS_IQ
    win = np.ones(M)
    e = []
    for f in (-df / 2, +df / 2):
        # ######################################################################
        # ##  KEY LINE: correlate with the tone (undo its rotation, then add up
        # ##  a symbol's worth); the energy is the magnitude squared.
        # ######################################################################
        c = np.convolve(z * np.exp(-2j * np.pi * f * t), win, "valid")
        e.append(abs(c) ** 2)
    return np.array(e)                          # shape (2, len(z) - M + 1)


def receive(z, M, nbits):
    """Find the frame (Barker correlation) and decide nbits bits after it.  Returns
    the bits, the soft values (E1 - E0) / (E1 + E0), and where the frame starts."""
    e = energies(z, M)
    soft = (e[1] - e[0]) / (e[1] + e[0] + 1e-12)
    # Look for the sync word only where the sound starts.  13 random bits match it
    # once in 8192 tries, and a frame of random data offers over a thousand.
    total = e[0] + e[1]
    onset = int(np.argmax(total > 0.25 * np.percentile(total, 90)))
    # Correlate the energy difference, not soft: in the silence before the frame
    # soft is +-1 at random.
    diff = e[1] - e[0]
    pattern = 2.0 * BARKER - 1
    best, start = -np.inf, 0
    for n in range(max(0, onset - M), onset + 3 * M):
        s = np.dot(diff[n:n + len(BARKER) * M:M], pattern)
        if s > best:
            best, start = s, n
    idx = start + M * (len(BARKER) + np.arange(nbits))
    v = soft[idx]
    return (v > 0).astype(int), v, start


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("text", nargs="?", help="the message (ASCII, up to 30 characters)")
    ap.add_argument("--port")
    ap.add_argument("--baud", type=float, default=509, help="rounded to 12207/M")
    ap.add_argument("--fc", type=float, default=FC)
    ap.add_argument("--amp", type=int, default=127, help="DAC codes, 0..127")
    ap.add_argument("--ber", action="store_true", help="random bits; count the errors")
    ap.add_argument("--frames", type=int, default=10)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    M = max(1, int(round(FS_IQ / a.baud)))
    m = Modem(a.port, M, a.fc, a.amp)
    print(f"{m.baud:.1f} baud: tones {a.fc - m.df / 2:.1f} and {a.fc + m.df / 2:.1f} Hz, "
          f"{M} I/Q samples a symbol")
    if a.ber:
        rng = np.random.default_rng(a.seed)
        errors = total = 0
        for k in range(a.frames):
            bits = rng.integers(0, 2, MAX_SYMBOLS - len(BARKER))
            z = m.send_and_listen(bits)
            got, soft, start = receive(z, M, len(bits))
            e = int(np.sum(got != bits))
            errors += e
            total += len(bits)
            print(f"frame {k + 1:3d}: {e:3d} errors in {len(bits)} bits; "
                  f"smallest |soft| {np.min(abs(soft)):.2f}")
        print(f"BER {errors}/{total} = {errors / total:.2e}")
    else:
        text = a.text or "HELLO THROUGH THE AIR"
        bits = text_bits(text)
        z = m.send_and_listen(bits)
        got, soft, start = receive(z, M, len(bits))
        print("sent:     ", text)
        print("received: ", bits_text(got))
        print(f"{np.sum(got != bits)} bit errors in {len(bits)}")


if __name__ == "__main__":
    main()
