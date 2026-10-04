#!/usr/bin/env python3
"""Trading speed for bits: the 8-bit DAC made to act as a 1-, 2- or 4-bit one in four
ways, and how many bits a low-pass filter gets back.

    python3 sigma_delta.py --sim                  # 1-bit, four ways: ENOB against OSR (channel.py)
    python3 sigma_delta.py /dev/ttyUSB0           # one board looped back (awgcap.bit loaded)
    python3 sigma_delta.py --m2k /dev/ttyUSB0     # the DAC pin on an ADALM2000 scope, 100 MS/s
    python3 sigma_delta.py --sim --bits 4 --amp 100 --cycles 3
    python3 sigma_delta.py --sim --table          # 1, 2, 4, 8 bits x four methods x five OSRs
    python3 sigma_delta.py --sim --digital        # the stream itself, before any converter
    python3 sigma_delta.py --sim -o sd.npz

    import sigma_delta as sd
    u = sd.sine(cycles=3, amp=64)                 # 8192 samples at 25 MS/s, in signal units
    y = sd.requantize(u, bits=1, method="order2") # a 1-bit stream: +-127.5 (DAC codes 255 / 0)
    wave = sd.hold2(y)                            # 16384 DAC samples at 50 MS/s, for awgcap
    r = sd.analyze(rec - rec.mean(), 25e6, sd.F_LOOP * 3, [1, 4, 16, 64, 256], amp=64,
                   gain=sd.ADC_GAIN)                # ENOB per OSR from an ADC record

A sine of a few kHz is re-quantized for the DAC four ways:
  plain    round to the nearest of the 2^N levels (N = 1: DAC codes 0 and 255);
  dither   add TPDF noise (two uniform dice, +-1 step) first, then round;
  order1   first-order delta-sigma, error feedback: v = u - e[n-1], y = Q(v), e = y - v,
           so y = u + (1 - z^-1) e: the error is pushed up in frequency;
  order2   second-order: v = u - 2 e[n-1] + e[n-2], y = u + (1 - z^-1)^2 e.
Signal units: s = DAC code - 127.5, so full scale is +-127.5 and an N-bit converter's
levels are k x 255 / (2^N - 1) - 127.5 (1, 17, 85 or 255 codes apart).

THE RATE.  The modulator runs at 25 MS/s and every output is held for two DAC samples
(hold2), so the DAC's stream changes at 25 MS/s and the shaped noise lives in
0..12.5 MHz.  That is deliberate: the ADC samples at 25 MS/s, and anything the DAC
put between 12.5 and 25 MHz would fold straight back into the band being measured,
with the loudest shaped noise landing on the quietest part.  A modulator at the DAC's
full 50 MS/s would need an analog filter in front of the ADC, which this module does
not have.  (At 100 MS/s the M2k scope sees everything, folded or not.)

THE LOOP.  awgcap.sv plays the 327.68 us loop forever, so the modulator's state at
the end of the loop must be its state at the start, or every wrap is a glitch (a
step of up to a whole level, once a loop: at OSR 256 that alone would cap a 1-bit
stream near 9 bits).  periodic_state() finds a start state in which the loop ends
exactly as it began: for the first order any e[-1] with sum(y - u) = 0 over the
loop, which half of all starts give; for the second order one more linear step.

THE MEASUREMENT.  Low-pass to fs/(2 OSR) with a windowed sinc (kaiser, 64 x OSR taps,
circular over the periodic record), keep every OSR-th sample, fit a sine, and call the
residual noise plus distortion: SINAD referred to a full-scale sine, and
ENOB = (SINAD - 1.76) / 6.02.  An ideal N-bit converter with white error gives
ENOB = log2(2^N - 1): 7.99 for 8 bits and 0 for 1 bit (its two levels are a whole
full scale apart; the textbook's 6.02 N + 1.76 with N = 1 credits it with a step half
that size).  The textbook slopes: white error (plain or dithered) + 0.5 bit per octave
of OSR (TPDF dither costs 0.79 bit at the start); first order + 1.5 bit per octave,
less 0.86; second order + 2.5, less 2.14.

THE INSTRUMENT.  The record is made by an 8-bit ADC (its rounding plus 0.1 code of
noise, 0.31 code rms, white if the signal keeps it busy) or by the M2k's 12-bit scope
(12 mV per LSB in its +-25 V range, 0.4 DAC code).  After the same decimation those
floors are ENOB ceilings of their own, printed beside the results so that the limit
the student sees is named.
"""
import argparse
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "comms"))        # channel
sys.path.insert(0, os.path.join(HERE, "..", "twoboard"))     # awgcap
sys.path.insert(0, os.path.join(HERE, "..", "..", "dev", "tools"))   # m2k

N_DAC = 16384                    # DAC samples per loop (awgcap)
N = N_DAC // 2                   # modulator samples per loop: 8192 at 25 MS/s
FS_DAC, FS = 50e6, 25e6          # the DAC's clock, and the modulator's / ADC's rate
F_LOOP = FS_DAC / N_DAC          # 3051.76 Hz: one cycle per loop
V_PER_CODE = 0.0307              # the DAC pin: 30.7 mV per code (3.07 V at 100 codes)
OSRS = [1, 4, 16, 64, 256]
METHODS = ["plain", "dither", "order1", "order2"]
BITS = [1, 2, 4, 8]
ADC_GAIN, ADC_NOISE = 0.776, 0.1     # channel.py: ADC codes per DAC code, codes rms
FS_RMS = 127.5 / math.sqrt(2)        # a full-scale sine's rms, in DAC codes


# ---- the signal, and the four ways to make it fit N bits -------------------------------
def sine(cycles=3, amp=64.0, n=N):
    """A sine with a whole number of cycles per loop, in signal units (codes - 127.5)."""
    return amp * np.sin(2 * np.pi * cycles * np.arange(n) / n)


def step_of(bits):
    """The distance between an N-bit converter's levels, in DAC codes."""
    return 255.0 / (2**bits - 1)


def quantize(u, bits):
    """Round to the nearest of the 2^N levels (plain)."""
    step = step_of(bits)
    k = np.clip(np.floor((np.asarray(u, float) + 127.5) / step + 0.5), 0, 2**bits - 1)
    return k * step - 127.5


def dithered(u, bits, rng=None):
    """TPDF dither: two uniform dice of +-half a step, added before rounding.  The
    rounding error is then independent of the signal (white, at the price of its
    own 2 x step^2 / 12), so averaging buys bits.  A 1-bit quantizer is overloaded by
    it (the dice reach a whole step), which bends its average: a limit, not a bug."""
    rng = np.random.default_rng(rng)
    step = step_of(bits)
    d = (rng.random(len(u)) + rng.random(len(u)) - 1.0) * step
    return quantize(u + d, bits)


def modulate(u, bits, order, e1=0.0, e2=0.0):
    """Error-feedback delta-sigma, first or second order, from the state (e[-1], e[-2]).
    Returns the output levels and the final state (e[n-1], e[n-2])."""
    step = step_of(bits)
    kmax = 2**bits - 1
    h1, h2 = (1.0, 0.0) if order == 1 else (2.0, -1.0)
    y = [0.0] * len(u)
    floor = math.floor
    for i, un in enumerate(np.asarray(u, float).tolist()):
        # ##########################################################################
        # ##  KEY LINE: feed the last error(s) back before rounding, so that the
        # ##  rounding error of this sample cancels the last one's at low frequency:
        # ##  y = u + (1 - z^-1)^order e.
        # ##########################################################################
        v = un - h1 * e1 - h2 * e2
        k = floor((v + 127.5) / step + 0.5)
        k = 0 if k < 0 else (kmax if k > kmax else k)
        q = k * step - 127.5
        e2, e1 = e1, q - v
        y[i] = q
    return np.array(y), (e1, e2)


def periodic_state(u, bits, order, tries=200, seed=0):
    """A state to start the loop in so that the loop ends in it, by trying random ones.
    First order: e[end] - e[start] = sum(y - u), which is a whole number of steps and
    zero for about half of all starts: any of those is exactly periodic.
    Second order: with g = e[n] - e[n-1], g[end] - g[start] = sum(y - u) again, and
    e[end] - e[start] = N g[-1] + sum((N - k)(y - u)[k]), linear in g[-1] with slope
    N for as long as no sample flips; so from a start with sum(y - u) = 0 take the one
    step in g[-1] that zeroes it and check that nothing flipped.  Returns (e1, e2,
    leftover); leftover is 0 when exact, else the smallest e mismatch found (its
    glitch at the wrap is first-order shaped, so weak in band)."""
    step = step_of(bits)
    rng = np.random.default_rng(seed)
    s_u = u.sum()
    best = None
    for _ in range(tries):
        e1 = rng.uniform(-0.8 * step, 0.8 * step)
        g = rng.uniform(-step, step) if order == 2 else 0.0
        y, (f1, f2) = modulate(u, bits, order, e1, e1 - g)
        if abs(y.sum() - s_u) > 0.5 * step:
            continue
        if order == 1:
            return e1, e1, 0.0
        g0 = g - (f1 - e1) / len(u)                # the same cell, where e[end] = e[start]
        y, (f1, f2) = modulate(u, bits, order, e1, e1 - g0)
        left = abs(f1 - e1) + abs(f2 - (e1 - g0))
        if abs(y.sum() - s_u) < 0.5 * step and left < 1e-9 * step:
            return e1, e1 - g0, 0.0
        if best is None or left < best[2]:
            best = (e1, e1 - g0, left)
    assert best is not None, "no periodic start state found"
    return best


def requantize(u, bits, method, rng=None):
    """One of the four: 'plain', 'dither', 'order1', 'order2'.  Levels in signal units."""
    if method == "plain":
        return quantize(u, bits)
    if method == "dither":
        return dithered(u, bits, rng)
    order = {"order1": 1, "order2": 2}[method]
    e1, e2, _ = periodic_state(u, bits, order)
    return modulate(u, bits, order, e1, e2)[0]


def hold2(y):
    """Each 25 MS/s level held for two DAC samples: the 16384-code waveform for awgcap."""
    return np.repeat(np.asarray(y) + 127.5, 2)


# ---- the receiver: low-pass, decimate, fit, count the bits -----------------------------
def lowpass(x, osr, fs=FS, periodic=True, taps_per_osr=64, beta=14.0):
    """A windowed-sinc low-pass to fs / (2 OSR): the ideal filter's impulse response
    cut to 64 x OSR + 1 taps by a Kaiser window (130 dB of stopband, a transition
    +-13 % of the cutoff).  Circular over a periodic record; otherwise the ends that
    the filter cannot fill are dropped."""
    if osr == 1:
        return np.asarray(x, float)
    taps = taps_per_osr * osr + 1
    if not periodic:                                       # keep at least half the record
        taps = min(taps, 2 * (len(x) // 4) + 1)
    n = np.arange(taps) - (taps - 1) / 2
    h = np.sinc(n / osr) / osr * np.kaiser(taps, beta)
    h /= h.sum()
    x = np.asarray(x, float)
    if periodic:
        L = len(x)
        hw = np.zeros(L)
        for i in range(taps):                                 # wrap the kernel, centred at 0
            hw[(i - (taps - 1) // 2) % L] += h[i]
        return np.fft.irfft(np.fft.rfft(x) * np.fft.rfft(hw), L)
    L = len(x) + taps - 1
    y = np.fft.irfft(np.fft.rfft(x, L) * np.fft.rfft(h, L), L)
    return y[taps - 1:len(x)]


def decimate(x, osr, fs=FS, periodic=True):
    """Low-pass, then keep every OSR-th sample."""
    return lowpass(x, osr, fs, periodic)[::osr]


def fit_sine(x, f_cyc, refine=False):
    """Least squares a cos + b sin + c at f_cyc cycles per sample; with refine, two
    Gauss-Newton steps on the frequency too (for a record on another clock).
    Returns amplitude, offset, the residual rms, and the frequency used."""
    x = np.asarray(x, float)
    n = np.arange(len(x))
    for _ in range(3 if refine else 1):
        w = 2 * np.pi * f_cyc * n
        cols = [np.cos(w), np.sin(w), np.ones(len(x))]
        if refine:
            a, b, c = np.linalg.lstsq(np.column_stack(cols), x, rcond=None)[0]
            cols.append(2 * np.pi * n * (-a * np.sin(w) + b * np.cos(w)))    # d/df
        coef = np.linalg.lstsq(np.column_stack(cols), x, rcond=None)[0]
        if refine:
            f_cyc += coef[3]
    a, b, c = coef[:3]
    resid = x - (a * np.cos(2 * np.pi * f_cyc * n) + b * np.sin(2 * np.pi * f_cyc * n) + c)
    return math.hypot(a, b), c, float(np.sqrt(np.mean(resid**2))), f_cyc


def enob(resid_rms_codes):
    """SINAD (dB, against a full-scale sine) and ENOB from a residual in DAC codes."""
    sinad = 20 * np.log10(FS_RMS / max(resid_rms_codes, 1e-12))
    return sinad, (sinad - 1.76) / 6.02


def analyze(x, fs, f0, osrs, amp, gain=1.0, periodic=True, refine=False):
    """x: a record of the sine, mean removed, in units of `gain` x DAC codes (the
    ADC reads 0.776 of a DAC code; the scope is scaled to codes already).  For each
    OSR: decimate, fit, refer the residual to DAC codes.  `ratio` is the fitted
    amplitude over the one sent: 1.00 for a faithful converter, 2.5 for a comparator
    (a square wave's fundamental is 4 / pi of its height).  A list of dicts."""
    out = []
    for osr in osrs:
        d = decimate(x, osr, fs, periodic)
        A, c, resid, f = fit_sine(d, f0 * osr / fs, refine)
        sinad, bits = enob(resid / gain)
        out.append(dict(osr=osr, enob=bits, sinad=sinad, amp=A / gain, ratio=A / gain / amp,
                        resid=resid / gain, n=len(d), f=f * fs / osr))
    return out


# ---- the textbook, and the instruments' own floors --------------------------------------
def theory(bits, method, osr):
    """ENOB an ideal modulator would give: the in-band part of a white error of
    step^2 / 12 after the noise transfer function, through a brick-wall at fs / (2 OSR).
    plain: only if the error were white (it is not: it is the signal's harmonics)."""
    base = np.log2(2**bits - 1)
    lo = np.log2(osr)
    if method == "plain":
        return base + 0.5 * lo
    if method == "dither":
        return base + 0.5 * lo - 0.5 * np.log2(3)             # the dice add 2 x step^2 / 12
    if method == "order1":
        return base + 1.5 * lo - 0.5 * np.log2(np.pi**2 / 3)
    return base + 2.5 * lo - 0.5 * np.log2(np.pi**4 / 5)


def floor_enob(noise_codes_rms, osr, fs_record=FS):
    """The ENOB ceiling an instrument imposes: its white noise (DAC codes rms over
    0..fs_record / 2) after the band is cut to FS / (2 OSR)."""
    inband = noise_codes_rms * np.sqrt(FS / fs_record / osr)
    return enob(inband)[1]


ADC_FLOOR = math.sqrt(1 / 12 + ADC_NOISE**2) / ADC_GAIN       # 0.39 DAC codes rms, white


# ---- getting the record: the model, the board, or the scope ----------------------------
class Link:
    """play(wave) then record() -> (x, fs, periodic): a record in units of `gain` x DAC
    codes, mean removed, at its sample rate.  floor() is the instrument's own noise in
    DAC codes rms over its whole band; `source` the caption.  Four kinds: the model
    (--sim), the model of a scope (--sim --m2k), the board looped back (PORT), or the
    DAC pin on an ADALM2000 scope while the board plays (--m2k PORT)."""

    def __init__(self, args):
        self.sim, self.m2k, self.seed = args.sim, args.m2k, args.seed
        self.n_scope = args.m2k_samples
        self.rng = np.random.default_rng(args.seed)
        self.gain = 1.0 if args.m2k else ADC_GAIN
        if args.sim and not args.m2k:
            self.source = "simulated (channel.py), the 8-bit ADC as the instrument"
        elif args.sim:
            self.source = "simulated scope (12 bits at 100 MS/s, 1 LSB of noise)"
        elif not args.m2k:
            self.source = "measured, one board looped back, the 8-bit ADC as the instrument"
        else:
            self.source = "measured, the DAC pin on an ADALM2000 scope at 100 MS/s"
        if not args.sim:
            import awgcap
            self.awgcap, self.port = awgcap, args.port
        if args.m2k and not args.sim:
            import m2k                                 # dev/tools/m2k.py (libm2k)
            self.scope = m2k.M2k()
            self.scope.set_range(0, high=False)        # +-25 V: the DAC pin swings +-3.9 V
        self.lsb = 50.0 / 4096 / V_PER_CODE            # the scope's 12 bits: 0.40 DAC codes

    def play(self, wave):
        if self.sim:
            self.wave = wave
        else:
            self.awgcap.upload(self.port, wave)

    def record(self):
        if self.sim and not self.m2k:
            import channel
            r = channel.channel(self.wave, rng=self.rng).astype(float)
            return r - r.mean(), FS, True
        if self.sim:                                   # the pin as the model's analog() has it
            import channel
            Y, f = channel.analog(self.wave)
            y = np.fft.irfft(Y, N_DAC * channel.UP)[::channel.UP // 2]       # 100 MS/s
            start = self.rng.integers(len(y))
            v = np.tile(y, self.n_scope // len(y) + 2)[start:start + self.n_scope]
            v = np.round((v + self.lsb * self.rng.standard_normal(len(v))) / self.lsb) * self.lsb
            return v - v.mean(), 1e8, False
        if not self.m2k:
            r = self.awgcap.record(self.port).astype(float)
            return r - r.mean(), FS, True
        t, v = self.scope.ch1(1e8, self.n_scope)
        v = v / V_PER_CODE
        return v - v.mean(), 1e8, False

    def floor(self):
        if not self.m2k:
            return ADC_FLOOR
        if self.sim:
            return self.lsb * math.sqrt(1 / 12 + 1)
        self.play(np.full(N_DAC, 128))                 # the DAC quiet: what the scope adds
        return float(np.std(self.record()[0]))


def prepare(x, fs, periodic):
    """A scope record at 100 MS/s is brought to the modulator's 25 MS/s first
    (low-pass to 12.5 MHz, keep every 4th), so that every OSR means the same band."""
    if fs > FS:
        r = int(round(fs / FS))
        return decimate(x, r, fs, periodic), FS
    return x, fs


def report_line(m, res):
    return "%-7s" % m + "".join("  OSR %3d: %5.2f" % (r["osr"], r["enob"]) for r in res) \
        + "   amplitude %.2fx of sent" % res[0]["ratio"]


def run(link, bits, methods, cycles, amp, osrs=OSRS, seed=1, quiet=False):
    """Make, play, record and analyze each method.  link = None analyzes the stream
    itself (no converter in the way: what the modulator achieves).  Returns
    {method: dict(u, y, x, fs, periodic, res)}."""
    u = sine(cycles, amp)
    f0 = cycles * F_LOOP
    out = {}
    for m in methods:
        y = requantize(u, bits, m, rng=seed)
        if link is None:
            x, fs, periodic, gain = np.tile(y - y.mean(), 2), FS, True, 1.0
        else:
            link.play(hold2(y))
            x, fs, periodic = link.record()
            gain = link.gain
        x25, _ = prepare(x, fs, periodic)
        res = analyze(x25, FS, f0, osrs, amp, gain, periodic, refine=not periodic)
        out[m] = dict(u=u, y=y, x=x, fs=fs, periodic=periodic, res=res)
        if not quiet:
            print(report_line(m, res))
    return out


def print_table(rows, osrs, floor_codes, fs_record, caption):
    """rows: [(bits, method, [enob per osr])]."""
    print("ENOB, measured (textbook) against OSR -- band edge 12.5 MHz / OSR; %s" % caption)
    print("bits  method " + "".join("%14s" % ("OSR %d" % o) for o in osrs))
    for bits, m, e in rows:
        cells = "".join("%6.2f (%5.2f)" % (v, theory(bits, m, o)) for v, o in zip(e, osrs))
        print("%4d  %-7s%s" % (bits, m, cells))
    print("the instrument's own ceiling (%.2f DAC codes rms, white):  "
          % floor_codes + "  ".join("%5.2f" % floor_enob(floor_codes, o, fs_record) for o in osrs))
    print("  (white only if the stream keeps its rounding busy.  A stream of a few fixed")
    print("   levels meets the same rounding errors every time: a nonlinearity, which no")
    print("   averaging removes.  Two levels are the exception: any two errors are only a")
    print("   gain and an offset, which is why 1-bit converters are linear by construction.)")
    print("textbook: white error  log2(2^N - 1) + 0.5 log2 OSR  (dither: - 0.79; plain: only if")
    print("          its error were white, which a sine's rounding error is not)")
    print("          1st order    log2(2^N - 1) + 1.5 log2 OSR - 0.86   (pi^2 / 3)")
    print("          2nd order    log2(2^N - 1) + 2.5 log2 OSR - 2.14   (pi^4 / 5)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("port", nargs="?", help="the board's serial port (awgcap.bit loaded)")
    ap.add_argument("--sim", action="store_true", help="channel.py's model instead of a board")
    ap.add_argument("--m2k", action="store_true", help="record the DAC pin with an ADALM2000 scope")
    ap.add_argument("--m2k-samples", type=int, default=2**19, help="scope samples at 100 MS/s (default 2^19: 5.2 ms)")
    ap.add_argument("--bits", type=int, default=1, choices=BITS, help="the converter to imitate (default 1)")
    ap.add_argument("--amp", type=float, default=64.0, help="sine amplitude in DAC codes (default 64 = half scale)")
    ap.add_argument("--cycles", type=int, default=3, help="cycles per 327.68 us loop (default 3: 9.155 kHz)")
    ap.add_argument("--method", choices=METHODS, help="just one of the four")
    ap.add_argument("--osr", type=int, help="just one OSR")
    ap.add_argument("--table", action="store_true", help="every bit depth, method and OSR")
    ap.add_argument("--digital", action="store_true", help="the stream itself, no converter")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("-o", "--out", help="save the records and results (.npz)")
    args = ap.parse_args()
    if not (args.sim or args.port or args.digital):
        ap.error("give the board's port, or --sim, or --digital")
    osrs = [args.osr] if args.osr else OSRS
    methods = [args.method] if args.method else METHODS
    bits_list = BITS if args.table else [args.bits]
    link = None if args.digital else Link(args)
    caption = "the stream itself (no converter)" if link is None else link.source

    print("sine: %d cycles per loop = %.3f kHz, %.0f codes amplitude; modulator at 25 MS/s, held x2"
          % (args.cycles, args.cycles * F_LOOP / 1e3, args.amp))
    rows, saved = [], {}
    for bits in bits_list:
        print("--- %d bit%s (levels %.0f codes apart)" % (bits, "s" if bits > 1 else "", step_of(bits)))
        out = run(link, bits, methods, args.cycles, args.amp, osrs, args.seed)
        for m in methods:
            rows.append((bits, m, [r["enob"] for r in out[m]["res"]]))
            saved["%d_%s_x" % (bits, m)] = out[m]["x"]
            saved["%d_%s_y" % (bits, m)] = out[m]["y"]
            saved["%d_%s_enob" % (bits, m)] = [r["enob"] for r in out[m]["res"]]
        fs_record = out[methods[0]]["fs"]
    fl = 0.0 if link is None else link.floor()
    print()
    print_table(rows, osrs, fl, fs_record, caption)
    if args.out:
        np.savez(args.out, osrs=osrs, bits=bits_list, methods=methods, amp=args.amp, cycles=args.cycles,
                 floor=fl, fs=fs_record, caption=caption, **saved)
        print("saved", args.out)


if __name__ == "__main__":
    main()
