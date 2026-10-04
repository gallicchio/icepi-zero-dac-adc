#!/usr/bin/env python3
"""Bit depth grows: the 8-bit ADC made to resolve a sine of a code and a half, and a DC
level to a hundredth of a code, by averaging -- if and only if there is noise to average.

    python3 oversample_adc.py --sim                 # channel.py's model
    python3 oversample_adc.py /dev/ttyUSB0          # one board looped back (awgcap.bit loaded)
    python3 oversample_adc.py --m2k /dev/ttyUSB0    # the ADALM2000's W1 into ADC IN as the source
    python3 oversample_adc.py --sim --amp 1.5 --dither 2.0 --cycles 3
    python3 oversample_adc.py --sim --dc            # a DC level, DAC codes 124..132, with and without
    python3 oversample_adc.py --sim -o oa.npz

    import oversample_adc as oa
    rec = oa.measure(link, amp=1.5, dither=0.0)     # 16384 ADC codes at 25 MS/s (two loops)
    r = oa.analyze(rec, cycles=3, osrs=[1, 4, 16, 64, 256])   # ENOB, fitted amplitude, offset per OSR

The DAC plays 128 + 1.5 sin: a sine that spans four DAC codes and, at 0.776 of a code
per code, about three ADC codes.  Three ways:
  none     the ADC's own noise only (0.1 code rms): what it records is a staircase, and
           averaging a staircase gives a staircase.  The fitted amplitude is wrong, too,
           by whatever the steps happen to do: the bias 2.05's lock-in saw at small
           signals;
  dither   `dither` codes rms of white noise added to the DAC waveform (as channel.py
           and the Chapter 6 scripts add noise at the transmitter): now each ADC sample
           is wrong by a random amount, the rounding error is white, and averaging 2^k
           samples buys k/2 bits: + 0.5 bit per octave of OSR, the slope of plain
           oversampling.  The amplitude and the offset come out right, to a hundredth of
           a code;
  shaped   the same noise put through a first difference (1 - z^-1) at 25 MS/s and held
           for two DAC samples, so that it is as wide at the ADC's input but lives up by
           12.5 MHz: the low-pass removes the noise and keeps the bits it bought.  The
           best of the three.  (Differenced at 50 MS/s it would peak at 25 MHz, which
           the ADC folds straight back to DC: the same rule as sigma_delta.py's.)
HOW MUCH NOISE.  The ADC reads 0.776 of a DAC code, so the ADC's rounding error as a
function of the DAC's (whole) code is a sawtooth that repeats every 1 / (1 - 0.776) =
4.5 codes.  Noise only linearizes what it covers: one code rms leaves 37 % of that
sawtooth (a 5 % amplitude error at 1.5 codes, a 0.08-code ripple in --dc), two codes
leave 2 %.  The default is 2.  A noise-shaped 8-bit stream of the sine itself does
NOT do (it visits three DAC codes, and the ADC's errors on those three never change):
the noise has to spread the ADC's input over many codes, whatever its spectrum.
With the same noise a DC level (--dc) is read to a few thousandths of a code, which is
how 6.12's lock-in read 78.380 codes three decimals deep: its 6.78 MHz tone, 157 codes
peak to peak and incommensurate with the sample clock, swept the ADC's rounding
through every code, and 2^13 samples averaged it down 90 times.  A tone of one code
could not, and read low.

ENOB here is referred to the ADC's full scale (255 codes), so a clean 8-bit record of
anything gives 7.9: the number to watch is how it grows with OSR.
"""
import argparse
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "comms"))        # channel
sys.path.insert(0, os.path.join(HERE, "..", "twoboard"))     # awgcap
import sigma_delta as sd                                     # noqa: E402

N_DAC, FS, F_LOOP, OSRS = sd.N_DAC, sd.FS, sd.F_LOOP, sd.OSRS
N_REC = 16384                   # ADC samples in a record (two loops)
WAYS = ["none", "dither", "shaped"]
ADC_PER_V = 25.35               # ADC codes per volt at its input (0.00)
ADC_ZERO = sd.ADC_GAIN * 128 + 27.5     # 126.83: what the ADC reads of the DAC's mid-scale (0 V)
AWG_RATE, AWG_N, AWG_CYCLES = 75e6, 65536, 8     # the M2k's W1: 8 cycles = 9155.27 Hz, as the DAC's 3


def waveform(amp=1.5, cycles=3, way="none", dither=2.0, rng=None):
    """16384 DAC codes: 128 + amp sin, plain, with white noise, or with blue noise."""
    rng = np.random.default_rng(rng)
    n = np.arange(N_DAC)
    w = 128 + amp * np.sin(2 * np.pi * cycles * n / N_DAC)
    if way == "dither":
        # ##########################################################################
        # ##  KEY LINE: noise, on purpose, so that the ADC's rounding error is
        # ##  different at every sample and averaging can get rid of it.
        # ##########################################################################
        w = w + dither * rng.standard_normal(N_DAC)
    elif way == "shaped":
        d = dither * rng.standard_normal(N_DAC // 2)         # at 25 MS/s, held x2 (as sigma_delta.py):
        w = w + np.repeat((d - np.roll(d, 1)) / np.sqrt(2), 2)   # (1 - z^-1) peaks at 12.5 MHz, not at
    return w                                                 # 25 MHz, which the ADC would fold to DC


def volts_waveform(amp=1.5, way="none", dither=2.0, rng=None):
    """The same sine and noise as volts, for the M2k's W1 into ADC IN: AWG_N samples at
    75 MS/s, cyclic, scaled so that the ADC sees what it would from the DAC."""
    rng = np.random.default_rng(rng)
    n = np.arange(AWG_N)
    v = sd.ADC_GAIN * amp / ADC_PER_V * np.sin(2 * np.pi * AWG_CYCLES * n / AWG_N)
    sigma = sd.ADC_GAIN * dither / ADC_PER_V
    if way == "dither":
        v = v + sigma * rng.standard_normal(AWG_N)
    elif way == "shaped":
        d = sigma * rng.standard_normal(AWG_N // 3 + 1)                  # at 25 MS/s, held x3
        v = v + np.repeat((d - np.roll(d, 1)) / np.sqrt(2), 3)[:AWG_N]
    return v


def measure(link, amp=1.5, cycles=3, way="none", dither=2.0, rng=None):
    if link.m2k:
        link.play_volts(volts_waveform(amp, way, dither, rng))
    else:
        link.play(waveform(amp, cycles, way, dither, rng))
    return link.record()


def analyze(rec, cycles=3, osrs=OSRS, periodic=True):
    """For each OSR: low-pass, decimate, fit the sine.  ENOB against the ADC's full
    scale; the fitted amplitude and offset in ADC codes; the decimated samples.
    A record on another clock (the M2k's) is not periodic: the filter's ends are
    dropped and the fit refines the frequency."""
    x = np.asarray(rec, float)
    out = []
    for osr in osrs:
        d = sd.decimate(x, osr, periodic=periodic)
        A, c, resid, _ = sd.fit_sine(d, cycles * F_LOOP * osr / FS, refine=not periodic)
        sinad, bits = sd.enob(resid)
        out.append(dict(osr=osr, enob=bits, sinad=sinad, amp=A, offset=c, resid=resid, d=d))
    return out


def dc_sweep(link, codes, dither=2.0, rng=None):
    """The ADC's mean reading of each DAC code, with and without noise: a staircase of
    whole codes against a line resolved to thousandths.  (With the M2k, the volts that
    DAC code would make, 30.6 mV a code about 0 V.)"""
    rng = np.random.default_rng(rng)
    rows = []
    for code in codes:
        if link.m2k:
            v0 = (code - 128) * sd.ADC_GAIN / ADC_PER_V
            link.play_volts(np.full(AWG_N, v0))
            plain = np.mean(link.record())
            link.play_volts(v0 + sd.ADC_GAIN * dither / ADC_PER_V * rng.standard_normal(AWG_N))
        else:
            link.play(np.full(N_DAC, float(code)))
            plain = np.mean(link.record())
            link.play(code + dither * rng.standard_normal(N_DAC))
        noisy = link.record()
        rows.append((code, plain, np.mean(noisy), np.std(noisy) / np.sqrt(len(noisy))))
    return rows


class Link:
    """play(wave) or play_volts(v), then record() -> 16384 ADC codes at 25 MS/s.  Three
    kinds: the model (--sim), one board looped back (PORT), or the M2k's W1 driving
    ADC IN with the sine and noise as volts (--m2k PORT): no DAC in the way, so no DAC
    rounding and no beat between two converters' code grids (HOW MUCH NOISE above),
    the cleanest version of this experiment.  --sim --m2k models that: 25.35 codes
    per volt, 0.1 code of noise, rounding."""

    def __init__(self, args):
        self.sim, self.m2k = args.sim, args.m2k
        self.rng = np.random.default_rng(args.seed)
        self.periodic = not args.m2k                   # the M2k's clock is not the board's
        if args.sim and not args.m2k:
            self.source = "simulated (channel.py)"
        elif args.sim:
            self.source = "simulated: an analog sine plus noise into the model's ADC"
        elif not args.m2k:
            self.source = "measured, one board looped back"
        else:
            self.source = "measured, the ADALM2000's W1 driving ADC IN"
        if not args.sim:
            import awgcap
            self.awgcap, self.port = awgcap, args.port
        if args.m2k and not args.sim:
            import m2k                                 # dev/tools/m2k.py (libm2k)
            self.scope = m2k.M2k()

    def play(self, wave):
        """A DAC waveform, 16384 codes at 50 MS/s: the board, or the model."""
        if self.sim:
            self.wave = wave
        else:
            self.awgcap.upload(self.port, wave)

    def play_volts(self, v):
        """An analog waveform from the M2k's W1: AWG_N samples at 75 MS/s, cyclic."""
        if self.sim:
            self.volts = np.asarray(v, float)
        else:
            self.scope._play(0, AWG_RATE, v)
            time.sleep(0.05)

    def record(self):
        if self.sim and not self.m2k:
            import channel
            return channel.channel(self.wave, rng=self.rng).astype(float)
        if self.sim:                                   # the ADC alone, at every 3rd AWG sample
            start = int(self.rng.integers(AWG_N))
            v = np.tile(self.volts, 4)[start:start + 3 * N_REC:3]
            codes = ADC_ZERO + ADC_PER_V * v + sd.ADC_NOISE * self.rng.standard_normal(N_REC)
            return np.clip(np.round(codes), 0, 255)
        return self.awgcap.record(self.port).astype(float)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("port", nargs="?", help="the board's serial port (awgcap.bit loaded)")
    ap.add_argument("--sim", action="store_true", help="channel.py's model instead of a board")
    ap.add_argument("--m2k", action="store_true", help="the ADALM2000's W1 as the source into ADC IN")
    ap.add_argument("--amp", type=float, default=1.5, help="sine amplitude in DAC codes (default 1.5)")
    ap.add_argument("--cycles", type=int, default=3, help="cycles per loop (default 3: 9.155 kHz)")
    ap.add_argument("--dither", type=float, default=2.0, help="noise at the DAC, codes rms (default 2.0)")
    ap.add_argument("--dc", action="store_true", help="a DC sweep instead: DAC codes 124..132")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("-o", "--out", help="save the records and results (.npz)")
    args = ap.parse_args()
    if not (args.sim or args.port):
        ap.error("give the board's port, or --sim")
    link = Link(args)
    expect = sd.ADC_GAIN * args.amp
    print("%s; the DAC plays 128 + %.2f sin at %.3f kHz: about %.2f ADC codes of sine on %.2f"
          % (link.source, args.amp, args.cycles * F_LOOP / 1e3, expect, sd.ADC_GAIN * 128 + 27.5))

    if args.dc:
        codes = list(range(124, 133))
        rows = dc_sweep(link, codes, args.dither, args.seed)
        print("DAC code   ADC mean, no noise   with %.1f codes of noise (+- its standard error)   0.776 x code + 27.5"
              % args.dither)
        for code, plain, noisy, se in rows:
            print("  %3d        %8.3f              %8.3f +- %.3f                             %8.3f"
                  % (code, plain, noisy, se, sd.ADC_GAIN * code + 27.5))
        if args.out:
            np.savez(args.out, dc=np.array(rows), dither=args.dither, source=link.source)
        return

    saved = {}
    print("ENOB against the ADC's full scale, per OSR; then the fitted amplitude and offset at OSR 256")
    print("%-8s" % "way" + "".join("%9s" % ("OSR %d" % o) for o in OSRS) + "     amplitude     offset")
    for way in WAYS:
        rec = measure(link, args.amp, args.cycles, way, args.dither, args.seed)
        res = analyze(rec, args.cycles, periodic=link.periodic)
        last = res[-1]
        print("%-8s" % way + "".join("%9.2f" % r["enob"] for r in res)
              + "     %6.3f      %8.3f" % (last["amp"], last["offset"]))
        saved[way + "_rec"] = rec
        saved[way + "_enob"] = [r["enob"] for r in res]
        saved[way + "_amp"] = [r["amp"] for r in res]
        saved[way + "_offset"] = [r["offset"] for r in res]
    print("expected: amplitude %.3f, offset %.3f (the model's 0.776 x DAC + 27.5); 'none' gets"
          " neither right" % (expect, sd.ADC_GAIN * 128 + 27.5))
    print("theory for white error of %.2f ADC codes rms: %s" % (
        np.sqrt(1 / 12 + 0.1**2 + (sd.ADC_GAIN * args.dither)**2),
        ", ".join("%.2f" % sd.enob(np.sqrt(1 / 12 + 0.1**2 + (sd.ADC_GAIN * args.dither)**2) / np.sqrt(o))[1] for o in OSRS)))
    if args.out:
        np.savez(args.out, osrs=OSRS, amp=args.amp, cycles=args.cycles, dither=args.dither,
                 source=link.source, periodic=link.periodic, **saved)
        print("saved", args.out)


if __name__ == "__main__":
    main()
