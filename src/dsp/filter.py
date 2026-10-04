#!/usr/bin/env python3
"""The laptop side of filter.sv (7.03): design a filter with scipy, quantize it to the
board's 16-bit Q2.13 integers, load it over the serial port, and measure it.

Designs (one of):
    --lowpass FC [--taps N]     a windowed-sinc FIR (scipy.signal.firwin), N <= 16, default 15
    --highpass FC [--taps N]    likewise (N must be odd)
    --bandpass F1 F2 [--taps N]
    --moving N                  an N-sample moving average, N <= 16
    --edge                      [-1, 2, -1]: the second difference
    --rc FC                     the one-pole: an RC low-pass at FC (one pole at exp(-2 pi FC / fs))
    --butter ORDER FC [--high]  a Butterworth IIR, order <= 4 (scipy.signal.butter)
    --b 1,2,1 --a 1,-0.5        raw coefficients: b_0.. (16 at most), a_0.. (5 at most; divided by a_0)

Then, any of:
    (nothing)                   print the coefficient table and the predicted response, load it,
                                and leave the filter running on the ADC
    --m2k                       the M2k bench (W1 -> ADC IN, DAC OUT -> scope 1): a sine at each
                                of 40 frequencies, 100 kHz to 12 MHz; |H| is the DAC's amplitude
                                with the filter over its amplitude with 'O' 1 (the input played
                                straight through, same delay), each from a sine fit; with --ch2
                                (W1 also on scope 2+) the phase as well
    --m2k --impulse             the impulse response on the M2k's scope: the board's own one-
                                sample impulse (src 1), through the filter, out of the DAC
    --measure impulse|step|noise   ONE BOARD LOOPED BACK (DAC OUT -> ADC IN): a built-in stimulus
                                goes through the filter, out of the DAC, through the cable and
                                into the ADC, so the capture IS the response (untested until the
                                cable is back; written against channel.py's cable model)
    --src N --out N --tone F    the stimulus (0 ADC, 1 impulse, 2 step, 3 noise, 4 tone), what the
                                DAC plays (0 output, 1 input), and the tone's frequency, by hand
    --capture                   16384 ADC samples at 25 MS/s, as capture.py
    --design-only               no board: the table and the prediction only
    --selftest                  the Python model of filter.sv against filter_tb.sv's numbers
    -o NAME.npz                 save what was measured;  --no-plot
    PORT, or --port PORT        the serial port (default: find the Icepi Zero)

    python3 filter.py /dev/ttyUSB0 --lowpass 2e6 --m2k -o ../../dev/data/dsp_lowpass.npz
    python3 filter.py --moving 16 --m2k --impulse -o ../../dev/data/dsp_impulse.npz
    python3 filter.py --rc 1e6 --measure step        # with the loopback cable

The board's arithmetic (filter.sv): y[n] = (sum b_k x[n-k] - sum a_k y[n-k]) / 8192 with the
coefficients as integers, y kept with 8 bits below the ADC's lsb and saturating at +-512, and
the DAC playing y rounded and clipped to -128..127, plus 128.  simulate() below is that,
bit for bit; it is what the testbench checked, and what the predictions here are made with.
"""
import argparse
import os
import struct
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "dev", "tools"))      # m2k.py (the instructor's bench)

FS = 25e6                       # the ADC's rate: the filter runs once per sample
SCALE = 8192                    # Q2.13: the coefficient x 8192 is the integer the board holds
NB, NA = 16, 4                  # b_0..b_15, a_1..a_4
N = 16384                       # the capture's length
IMPULSE, STEP, NOISE = 64, 64, 32   # the built-in stimuli, in ADC codes
SEED = 0x2545F491               # the noise generator's seed at each capture
CABLE_GAIN = 0.776              # ADC codes per DAC code through the loopback cable (1.07)
DAC_V = 0.0307                  # volts per DAC code (0.00)
SRC_NAMES = ["ADC", "impulse", "step", "noise", "tone"]


# ---- the port -----------------------------------------------------------------------
def find_port():
    """The first FTDI FT231X serial port (USB ID 0403:6015): the Icepi Zero's."""
    from serial.tools import list_ports
    for p in list_ports.comports():
        if (p.vid, p.pid) == (0x0403, 0x6015):
            return p.device
    raise SystemExit("No Icepi Zero found. Is it plugged in? (Or give --port.)")


def open_port(port=None, baud=1_000_000):
    import serial                                   # pip install pyserial
    ser = serial.Serial(port or find_port(), baud, timeout=3)
    time.sleep(0.02)
    ser.reset_input_buffer()                        # the FT231X's junk byte on opening
    return ser


class Board:
    """filter.sv's commands (see the header of filter.sv)."""

    def __init__(self, port=None):
        self.ser = open_port(port)

    def coef(self, which, k, v):
        self.ser.write(which + bytes([k]) + struct.pack(">h", int(v)))

    def upload(self, bq, aq):
        """All 16 b's and 4 a's, as 16-bit integers (the unused ones 0)."""
        for k in range(NB):
            self.coef(b"B", k, bq[k] if k < len(bq) else 0)
        for k in range(1, NA + 1):
            self.coef(b"A", k, aq[k] if k < len(aq) else 0)

    def set_src(self, s):
        self.ser.write(b"S" + bytes([int(s)]))

    def set_out(self, o):
        self.ser.write(b"O" + bytes([int(o)]))

    def set_tone(self, f_hz):
        self.ser.write(b"F" + struct.pack(">I", int(round(f_hz / FS * 2**32)) & 0xFFFFFFFF))

    def capture(self):
        """16384 ADC codes (0..255), recorded from the stimulus period's start."""
        self.ser.reset_input_buffer()
        self.ser.write(b"C")
        raw = self.ser.read(N)
        if len(raw) != N:
            raise RuntimeError("got %d of %d bytes -- is filter.bit loaded?" % (len(raw), N))
        return np.frombuffer(raw, dtype=np.uint8).astype(int)


# ---- the designs --------------------------------------------------------------------
def design(args):
    """(b, a, name) as floats, a[0] = 1, from the command line."""
    from scipy import signal
    n = args.taps
    if args.lowpass is not None:
        return signal.firwin(n, args.lowpass, fs=FS), [1.0], "low-pass %s, %d taps" % (hz(args.lowpass), n)
    if args.highpass is not None:
        n = min(n, NB - 1) | 1                      # a high-pass needs an odd number of taps
        return signal.firwin(n, args.highpass, pass_zero=False, fs=FS), [1.0], "high-pass %s, %d taps" % (hz(args.highpass), n)
    if args.bandpass is not None:
        f1, f2 = args.bandpass
        return signal.firwin(n, [f1, f2], pass_zero=False, fs=FS), [1.0], "band-pass %s-%s, %d taps" % (hz(f1), hz(f2), n)
    if args.moving is not None:
        return np.ones(args.moving) / args.moving, [1.0], "%d-sample moving average" % args.moving
    if args.edge:
        return np.array([-1.0, 2.0, -1.0]), [1.0], "edge detector [-1 2 -1]"
    if args.rc is not None:
        p = np.exp(-2 * np.pi * args.rc / FS)       # the pole: an RC's impulse response, sampled
        return np.array([1 - p]), np.array([1.0, -p]), "one-pole RC at %s" % hz(args.rc)
    if args.butter is not None:
        order, fc = int(args.butter[0]), args.butter[1]
        b, a = signal.butter(order, fc, btype="high" if args.high else "low", fs=FS)
        return b, a, "Butterworth %s-pass, order %d, %s" % ("high" if args.high else "low", order, hz(fc))
    if args.b is not None:
        b = np.array([float(v) for v in args.b.split(",")])
        a = np.array([float(v) for v in args.a.split(",")]) if args.a else np.array([1.0])
        return b / a[0], a / a[0], "b = %s, a = %s" % (args.b, args.a or "1")
    return np.array([1.0]), [1.0], "a wire (b_0 = 1)"


def hz(f):
    return "%g MHz" % (f / 1e6) if f >= 1e6 else "%g kHz" % (f / 1e3)


def quantize(c):
    """Coefficients -> the board's integers (x 8192, rounded, clipped to 16 bits)."""
    q = np.round(np.asarray(c, float) * SCALE).astype(int)
    return np.clip(q, -32768, 32767)


def poles(aq):
    """The quantized denominator's roots: |pole| < 1 is stable."""
    a = np.concatenate([[SCALE], np.asarray(aq[1:], float)]) / SCALE
    return np.roots(a) if len(a) > 1 else np.array([])


def response(bq, aq, f):
    """The quantized filter's H(f), complex, from scipy.signal.freqz."""
    from scipy import signal
    a = np.concatenate([[SCALE], np.asarray(aq[1:], float)]) / SCALE
    _, H = signal.freqz(np.asarray(bq, float) / SCALE, a, worN=np.atleast_1d(f), fs=FS)
    return H


def table(b, a, bq, aq, name):
    """Print the coefficients, their integers, and the predicted response."""
    print("design: %s" % name)
    print("  k        b_k    int     hex   |      a_k    int     hex")
    for k in range(max(len(b), len(a))):
        left = "%2d  %9.5f  %6d  0x%04x" % (k, b[k], bq[k], bq[k] & 0xFFFF) if k < len(b) else " " * 31
        right = "%9.5f  %6d  0x%04x" % (a[k], aq[k], aq[k] & 0xFFFF) if 1 <= k < len(a) else ""
        print("%s   | %s" % (left, right))
    big = [c for c in np.concatenate([b, a[1:]]) if abs(c) >= 4]
    if big:
        print("  WARNING: |coefficient| >= 4 does not fit Q2.13; clipped to +-3.9999: %s" % big)
    p = poles(aq)
    if len(p):
        r = np.abs(p).max()
        print("  poles after quantization: |p| max = %.5f %s" % (r, "UNSTABLE" if r >= 1 else "(stable)"))
        if r >= 1:
            print("  WARNING: the quantized denominator is unstable; lower the order or raise the cutoff")
    from scipy import signal
    fs_ = [0.25e6, 0.5e6, 1e6, 2e6, 3e6, 4e6, 5e6, 6e6, 8e6, 10e6, 12e6]
    _, Hd = signal.freqz(b, a, worN=fs_, fs=FS)
    Hq = response(bq, aq, fs_)
    print("  predicted |H|, dB:  " + "  ".join("%6s" % hz(f).replace(" MHz", "M").replace(" kHz", "k") for f in fs_))
    print("    as designed:      " + "  ".join("%6.1f" % db(v) for v in Hd))
    print("    as quantized:     " + "  ".join("%6.1f" % db(v) for v in Hq))


def db(v):
    return 20 * np.log10(np.abs(v) + 1e-12)


# ---- the model of filter.sv, bit for bit ---------------------------------------------
def simulate(bq, aq, x):
    """What the DAC plays (y, -128..127) for ADC-code input x (ints), aligned with x; the
    hardware shows it 3 samples later.  Integer arithmetic exactly as filter.sv's."""
    bq = np.asarray(bq, np.int64)
    aq = [int(v) for v in np.asarray(aq)[:NA + 1]] + [0] * (NA + 1 - len(aq))
    x = np.asarray(x, np.int64)
    F = np.convolve(x, bq)[:len(x)] << 8            # the feed-forward sums, in Q.21
    y = np.empty(len(x), np.int64)
    w = [0] * (NA + 1)                               # w[k] = y[n-k] in Q10.8
    for n in range(len(x)):
        acc = int(F[n]) - sum(aq[k] * w[k] for k in range(1, NA + 1))
        s = max(-131072, min(131071, acc >> 13))     # saturate to 18 bits
        w = [0, s] + w[1:NA]
        y[n] = max(-128, min(127, (s + 128) >> 8))   # rounded, clipped, as the DAC shows it
    return y


def noise_sequence(n, seed=SEED):
    """The board's noise stimulus from a capture's start: a 32-bit xorshift, the four bytes
    of each state added, -510, >> 4: -32..31, nearly Gaussian, 9 codes rms."""
    r, out = seed, np.empty(n, int)
    for i in range(n):
        s = (r & 0xFF) + ((r >> 8) & 0xFF) + ((r >> 16) & 0xFF) + ((r >> 24) & 0xFF) - 510
        out[i] = s >> 4
        r ^= (r << 13) & 0xFFFFFFFF
        r ^= r >> 17
        r ^= (r << 5) & 0xFFFFFFFF
    return out


def stimulus(src, n=N):
    """The built-in stimulus as the filter sees it from a capture's start."""
    k = np.arange(n)
    if src == 1:
        return np.where(k % 2**14 == 0, IMPULSE, 0)
    if src == 2:
        return np.where((k // 2**14) % 2 == 0, STEP, -STEP)     # +64 first: the capture starts at the rising edge
    if src == 3:
        return noise_sequence(n)
    raise ValueError("src 1, 2 or 3")


def selftest():
    """simulate() against the numbers filter_tb.sv printed for filter.sv."""
    taps = np.array([3, -5, 7, 11, -2]) * 128
    x = np.zeros(20, int); x[5] = IMPULSE
    y = simulate(taps, [SCALE], x)
    ok1 = list(y[5:10]) == [3, -5, 7, 11, -2] and not y[:5].any() and not y[10:].any()
    print("impulse through [3 -5 7 11 -2] x 128:", list(y[5:10]), "ok" if ok1 else "FAIL")
    x = np.concatenate([np.full(16384, -64), np.full(60, 64)])
    y = simulate([819], [SCALE, -7373], x)[16384:]
    want = {0: -51, 1: -40, 2: -29, 3: -20, 4: -12, 5: -4, 6: 3, 7: 9, 12: 31, 20: 50, 28: 58, 36: 61, 44: 63, 52: 64}
    ok2 = all(y[k] == v for k, v in want.items())
    print("step through the one-pole a1 = -0.9, b0 = 0.1:", list(y[:8]), "...", "ok" if ok2 else "FAIL")
    y = simulate([32767], [SCALE], np.array([64, -64]))
    ok3 = list(y) == [127, -128]
    print("b0 = 3.9999, +-64: ", list(y), "ok (saturates)" if ok3 else "FAIL")
    nz = noise_sequence(1000)
    ok4 = nz.min() >= -32 and nz.max() <= 31 and 8 < nz.std() < 10.5
    print("noise: %d..%d, %.1f codes rms" % (nz.min(), nz.max(), nz.std()), "ok" if ok4 else "FAIL")
    print("PASS" if ok1 and ok2 and ok3 and ok4 else "FAIL")
    return ok1 and ok2 and ok3 and ok4


# ---- the M2k bench: W1 -> ADC IN, DAC OUT -> scope 1 ---------------------------------
class Scope:
    """The ADALM2000 through dev/tools/m2k.py: a sine on W1, captures on channel 1 (and 2)."""

    def __init__(self):
        import m2k
        self.m2k = m2k
        self.m = m2k.M2k()
        self.m.ctx.setTimeout(3000)                 # ms: a capture that never triggers raises

    def sine(self, f, amp):
        """A sine of amplitude amp (V) on W1; returns the frequency actually made."""
        fa = self.m.w1_sine(f, amp)
        time.sleep(0.15)                            # the AWG restarts
        return fa

    def grab(self, n=N, rate=1e8, high=True, trigger=None, pre=0):
        """n samples of channel 1 (and 2) at `rate`; high = the +-2.5 V range.
        trigger = (level in V, rising) on channel 1, with `pre` samples before it."""
        import libm2k
        m, ain, trig = self.m, self.m.ain, self.m.trig
        m.set_range(0, high)
        m.set_range(1, high)
        ain.setSampleRate(rate)
        ain.setOversamplingRatio(1)
        if trigger is None:
            trig.setAnalogMode(0, libm2k.ALWAYS)
        else:
            level, rising = trigger
            trig.setAnalogSource(0)
            trig.setAnalogMode(0, libm2k.ANALOG)
            trig.setAnalogCondition(0, libm2k.RISING_EDGE_ANALOG if rising else libm2k.FALLING_EDGE_ANALOG)
            trig.setAnalogLevel(0, float(level))
            trig.setAnalogDelay(-int(pre))
        trig.setAnalogStreamingFlag(False)
        ain.stopAcquisition()
        data = np.array(ain.getSamples(n))
        return np.arange(n) / rate, data[0], data[1]

    def fit(self, t, v, f):
        return self.m2k.fit_sine(t, v, f)           # f, A, phi, offset, rms

    def close(self):
        self.m.close()


def sweep(board, scope, bq, aq, freqs, amp=1.0, ch2=False, verbose=True):
    """|H| (and the phase, with ch2) at each frequency: the DAC's sine with the filter over
    the DAC's sine with the input played straight through."""
    out = dict(f=[], A_in=[], A_out=[], H=[], phase=[], rms_in=[], rms_out=[])
    if verbose:
        print("  %9s  %8s  %8s  %8s  %8s  %7s" % ("MHz", "in (V)", "out (V)", "|H| dB", "predict", "phase"))
    for f in freqs:
        fa = scope.sine(f, amp)
        Hp = response(bq, aq, fa)[0]
        board.set_out(1)
        time.sleep(0.02)
        t, v1, v2 = scope.grab(high=True)
        _, A_in, ph_in, _, rms_in = scope.fit(t, v1, fa)
        ph_ref_in = scope.fit(t, v2, fa)[2] if ch2 else 0.0
        board.set_out(0)
        time.sleep(0.02)
        high = A_in * abs(Hp) * 1.4 < 2.4           # the +-2.5 V range unless the output is big
        t, v1, v2 = scope.grab(high=high)
        _, A_out, ph_out, _, rms_out = scope.fit(t, v1, fa)
        if high and A_out > 2.3:                    # clipped after all: the +-25 V range
            t, v1, v2 = scope.grab(high=False)
            _, A_out, ph_out, _, rms_out = scope.fit(t, v1, fa)
        ph_ref_out = scope.fit(t, v2, fa)[2] if ch2 else 0.0
        H = A_out / A_in
        phase = ((ph_out - ph_ref_out) - (ph_in - ph_ref_in) + np.pi) % (2 * np.pi) - np.pi if ch2 else np.nan
        for k, v in zip(out, (fa, A_in, A_out, H, phase, rms_in, rms_out)):
            out[k].append(v)
        if verbose:
            print("  %9.4f  %8.4f  %8.4f  %8.2f  %8.2f  %7s" % (fa / 1e6, A_in, A_out, db(H), db(Hp),
                                                              "" if ch2 is False else "%+.1f" % np.degrees(phase)))
    board.set_out(0)
    return {k: np.array(v) for k, v in out.items()}


def impulse_trace(board, scope, bq, aq, n=1500, pre=100, rate=1e8):
    """The filter's impulse response as the scope sees it: src 1 (one sample of +64 every
    2^14 samples) through the filter to the DAC; triggered on its first big sample."""
    h = simulate(bq, aq, stimulus(1, 256))          # the DAC codes the impulse should give
    k = int(np.argmax(np.abs(h) >= 0.5 * np.abs(h).max()))
    level, rising = 0.5 * h[k] * DAC_V, h[k] > 0
    board.set_src(1)
    board.set_out(0)
    time.sleep(0.02)
    t, v, _ = scope.grab(n, rate, high=np.abs(h).max() * DAC_V < 2.2, trigger=(level, rising), pre=pre)
    board.set_src(0)
    return t, v, h


# ---- one board looped back: DAC OUT -> ADC IN -----------------------------------------
def loopback(board, kind, bq, aq, ntaps=64):
    """The impulse response from a capture of the stimulus `kind` (impulse, step or noise)
    through the filter, the DAC, the cable and the ADC.  Returns (h, f, H, record, delay).
    UNTESTED on hardware (written against the cable model of 1.07: 0.776 codes per code,
    about 6 samples of delay)."""
    src = ["", "impulse", "step", "noise"].index(kind)
    board.set_src(src)
    board.set_out(0)
    time.sleep(0.01)
    rec = board.capture() - 128.0
    board.set_src(0)
    u = stimulus(src).astype(float)
    if kind == "impulse":
        x = rec - np.median(rec)                    # the cable's DC offset
        h_full = x / (IMPULSE * CABLE_GAIN)
    elif kind == "step":
        h_full = np.diff(rec, prepend=rec[0]) / (2 * STEP * CABLE_GAIN)
    else:                                           # least squares: rec[n] = sum_k h[k] u[n-d-k]
        c = np.fft.irfft(np.fft.rfft(rec - rec.mean()) * np.conj(np.fft.rfft(u - u.mean())))
        d = int(np.argmax(c[:64]))
        rows = np.arange(200, N)
        X = np.stack([u[rows - d - k] for k in range(ntaps)], axis=1)
        h, *_ = np.linalg.lstsq(X, rec[rows] - rec.mean(), rcond=None)
        h_full = np.zeros(N)
        h_full[d:d + ntaps] = h / CABLE_GAIN
    hp = simulate(bq, aq, stimulus(1, 256)) / IMPULSE          # the prediction, per unit impulse
    c = np.correlate(h_full[:512], hp, "full")                 # where the response starts
    d = int(np.argmax(c)) - len(hp) + 1
    h = h_full[max(d, 0):max(d, 0) + ntaps]
    f = np.fft.rfftfreq(N, 1 / FS)
    H = np.fft.rfft(np.roll(h_full, -max(d, 0)))
    return h, f, H, rec, d


# ---- main -----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("port_arg", nargs="?", metavar="PORT", help="serial port (default: find the Icepi Zero)")
    g = ap.add_argument_group("design")
    g.add_argument("--lowpass", type=float, metavar="FC")
    g.add_argument("--highpass", type=float, metavar="FC")
    g.add_argument("--bandpass", type=float, nargs=2, metavar=("F1", "F2"))
    g.add_argument("--taps", type=int, default=15)
    g.add_argument("--moving", type=int, metavar="N")
    g.add_argument("--edge", action="store_true")
    g.add_argument("--rc", type=float, metavar="FC")
    g.add_argument("--butter", type=float, nargs=2, metavar=("ORDER", "FC"))
    g.add_argument("--high", action="store_true", help="--butter: a high-pass")
    g.add_argument("--b", help="raw b's, comma-separated")
    g.add_argument("--a", help="raw a's, comma-separated (a_0 first)")
    g = ap.add_argument_group("measure")
    g.add_argument("--m2k", action="store_true")
    g.add_argument("--impulse", action="store_true", help="--m2k: the impulse response on the scope")
    g.add_argument("--ch2", action="store_true", help="--m2k: W1 is also on scope 2: measure the phase")
    g.add_argument("--amp", type=float, default=1.0, help="--m2k: W1's amplitude, V (default 1)")
    g.add_argument("--points", type=int, default=40)
    g.add_argument("--fmin", type=float, default=100e3)
    g.add_argument("--fmax", type=float, default=12e6)
    g.add_argument("--measure", choices=["impulse", "step", "noise"], help="looped back: see above")
    g.add_argument("--src", type=int)
    g.add_argument("--out", type=int)
    g.add_argument("--tone", type=float)
    g.add_argument("--capture", action="store_true")
    g.add_argument("--design-only", action="store_true")
    g.add_argument("--selftest", action="store_true")
    g.add_argument("--port")
    g.add_argument("-o", "--save", metavar="NAME.npz")
    g.add_argument("--no-plot", action="store_true")
    args = ap.parse_args()
    args.port = args.port or args.port_arg
    if args.selftest:
        sys.exit(0 if selftest() else 1)

    b, a, name = design(args)
    if len(b) > NB or len(a) > NA + 1:
        sys.exit("too many taps: %d b's (max %d), %d a's (max %d)" % (len(b), NB, len(a), NA + 1))
    bq, aq = quantize(b), quantize(a)
    table(b, a, bq, aq, name)
    saved = dict(name=name, b=bq, a=aq, bf=b, af=a, fs=FS)
    if args.design_only:
        if args.save:
            np.savez(args.save, **saved)
        return

    board = Board(args.port)
    board.upload(bq, aq)
    print("loaded")
    if args.src is not None:
        board.set_src(args.src)
    if args.out is not None:
        board.set_out(args.out)
    if args.tone is not None:
        board.set_tone(args.tone)

    if args.capture:
        rec = board.capture()
        print("%d samples at 25 MS/s; codes %d..%d, mean %.1f" % (N, rec.min(), rec.max(), rec.mean()))
        saved.update(rec=rec, source="ADC capture")

    if args.m2k:
        scope = Scope()
        try:
            if args.impulse:
                t, v, h = impulse_trace(board, scope, bq, aq)
                print("impulse: the scope saw %.3f to %.3f V; predicted peak %.3f V" % (v.min(), v.max(), np.abs(h).max() * DAC_V))
                saved.update(t=t, v=v, h_codes=h, source="measured, M2k scope on DAC OUT, the board's impulse")
            else:
                freqs = np.geomspace(args.fmin, args.fmax, args.points)
                r = sweep(board, scope, bq, aq, freqs, args.amp, args.ch2)
                Hp = response(bq, aq, r["f"])
                err = db(r["H"]) - db(Hp)
                sel = db(Hp) > -40
                print("measured - predicted |H|: %.2f dB rms where the prediction is above -40 dB" % np.sqrt(np.mean(err[sel]**2)))
                saved.update(r, H_pred=Hp, amp=args.amp, source="measured, M2k: W1 -> ADC IN, DAC OUT -> scope 1" + (" and 2" if args.ch2 else ""))
        finally:
            scope.close()

    if args.measure:
        h, f, H, rec, d = loopback(board, args.measure, bq, aq)
        hp = simulate(bq, aq, stimulus(1, 256)) / IMPULSE
        print("loopback %s: the response begins %d samples into the capture; measured taps / predicted:" % (args.measure, d))
        for k in range(min(8, len(h))):
            print("  h[%d] = %+.4f  (%+.4f)" % (k, h[k], hp[k]))
        saved.update(h=h, h_pred=hp[:len(h)], f_lb=f, H_lb=H, rec=rec, delay=d,
                     source="measured, one board looped back, %s" % args.measure)

    if args.save:
        np.savez(args.save, **saved)
        print("saved", args.save)
    if args.no_plot or not ({"f", "t", "h", "rec"} & set(saved)):
        return
    import matplotlib.pyplot as plt
    if "f" in saved:
        fig, ax = plt.subplots(2 if args.ch2 else 1, 1, figsize=(8, 6), squeeze=False)
        ff = np.geomspace(args.fmin, args.fmax, 400)
        ax[0, 0].semilogx(ff / 1e6, db(response(bq, aq, ff)), color="C1", label="predicted (quantized)")
        ax[0, 0].semilogx(saved["f"] / 1e6, db(saved["H"]), "o", color="C0", ms=4, label="measured")
        ax[0, 0].set_ylabel("|H| (dB)"); ax[0, 0].set_ylim(-70, 15); ax[0, 0].grid(True, which="both")
        ax[0, 0].legend(); ax[0, 0].set_title(name)
        if args.ch2:
            ax[1, 0].semilogx(ff / 1e6, np.degrees(np.angle(response(bq, aq, ff))), color="C1")
            ax[1, 0].semilogx(saved["f"] / 1e6, np.degrees(saved["phase"]), "o", color="C0", ms=4)
            ax[1, 0].set_ylabel("phase (deg)"); ax[1, 0].grid(True, which="both")
        ax[-1, 0].set_xlabel("frequency (MHz)")
    elif "t" in saved:
        plt.plot(saved["t"] * 1e6, saved["v"], color="C0", lw=1)
        plt.xlabel("time (µs)"); plt.ylabel("DAC OUT (V)"); plt.grid(True)
        plt.title("impulse response: %s" % name)
    elif "h" in saved:
        plt.stem(saved["h"], linefmt="C0-", markerfmt="C0o", basefmt=" ", label="measured")
        plt.plot(saved["h_pred"], "C1x", label="predicted")
        plt.xlabel("sample"); plt.ylabel("impulse response"); plt.legend(); plt.grid(True)
    else:
        plt.plot(np.arange(N) / FS * 1e6, saved["rec"], lw=0.5)
        plt.xlabel("time (µs)"); plt.ylabel("ADC code"); plt.grid(True)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
