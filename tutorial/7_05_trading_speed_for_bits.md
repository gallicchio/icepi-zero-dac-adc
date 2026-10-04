<!-- nav -->
[← 7.04 The filter as a LiteX peripheral](7_04_the_filter_as_a_litex_peripheral.md#704-the-filter-as-a-litex-peripheral) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)** &emsp;&emsp;&emsp; [7.06 Control at the speed of the cable →](7_06_control.md#706-control-at-the-speed-of-the-cable)

# 7.05 Trading speed for bits

![Measured on the M2k's scope: eight microseconds of a second-order one-bit delta-sigma stream, DAC codes 0 and 255 only, with the sine it encodes; the spectra the instrument records for a plain comparator, dithered rounding, and first- and second-order noise shaping, the shaped noise climbing 20 and 40 decibels a decade; the four streams after a low-pass to 195 kilohertz, where the shaped ones are clean sines; and the effective bits recovered from one bit against the oversampling ratio, measured against the textbook](img/dsp_sigma_delta.png)

You might be disappointed that these are "only" 8-bit converters. Audio
is 16 or 24 bits. But ours are fast, 50 and 25 million samples a second,
where audio needs 48 thousand, and there is a technique for trading speed
for bits. It goes under the names *oversampling*, *noise shaping*, and
*delta-sigma* (ΔΣ) or *sigma-delta* (ΣΔ), depending on whether the people
naming it differenced before they summed or after. At the extreme are
*one-bit* converters that, with an analog low-pass filter, give amazing
audio quality; your phone's audio DAC is one. The
key to these techniques is some analog filtering, digital or analog
feedback, and processing power, which our FPGA has plenty of. This page
does it in both directions, on the hardware we have, and is honest about
where that hardware stops.

## What a bit is worth

Round a signal to *N* bits and the error is uniform between ±half a step:
power Δ<sup>2</sup>/12, whatever the sample rate. A full-scale sine against that
error has a [signal-to-noise ratio](https://en.wikipedia.org/wiki/Signal-to-noise_ratio) of 6.02 dB per bit plus 1.76 dB (the Analog Devices
tutorial [MT-001](https://www.analog.com/media/en/training-seminars/tutorials/MT-001.pdf)
derives it in a page), and turning a measured SNR back through that
formula gives the *effective number of bits*, the ENOB, which is the only
number on this page that matters. An 8-bit converter is 49.9 dB, 7.99
bits; this module's ADC, measured through its own quantization and its
0.1 code of noise, reads about 7.3 at the full 25 MS/s.

Three facts turn that fixed Δ<sup>2</sup>/12 into something you can shrink:

1. **It is only *noise* if something makes it so.** A sine rounded to 8
   bits is a staircase, and a staircase's error is its harmonics, not
   white noise: average it all you like and the harmonics stay. The error
   becomes white, and independent of the signal, when the signal has
   *dither* on it, a little noise of about a step's size. Then averaging
   works.
2. **Oversampling spreads the fixed noise over more bandwidth.** The
   Δ<sup>2</sup>/12 is spread from 0 to *f*<sub>s</sub>/2; keep only the band *B* you
   want with a low-pass filter and you keep 2*B*/*f*<sub>s</sub> = 1/OSR of it:
   half a bit per doubling of the oversampling ratio.
3. **Feedback pushes the noise out of the band.** Subtract last sample's
   rounding error from this sample before rounding, and the error that
   reaches the output is *e*[*n*] − *e*[*n* − 1]: differenced, which is a
   high-pass, |1 − *z*<sup>−1</sup>|<sup>2</sup> = (2 sin π*f*/*f*<sub>s</sub>)<sup>2</sup>. Most of it
   now lives near *f*<sub>s</sub>/2, where the low-pass throws it away. That is
   first-order noise shaping: 1.5 bits per doubling. Do it twice (second
   order): 2.5 bits per doubling. The modulator is ten lines.

![Computed: effective bits against the oversampling ratio for dithered rounding, first-, second- and third-order noise shaping, with this 8-bit ADC's ceiling and the 16- and 24-bit lines of CD and studio audio; and where feedback puts the noise, the noise transfer functions 1 minus z to the minus one to the power 2n](img/dsp_enob.png)

The left panel is the arithmetic: ENOB = log<sub>2</sub>(2<sup>*N*</sup> − 1) + (*n* + ½)
log<sub>2</sub> OSR − *c*<sub>*n*</sub>, with *c* = 0.86, 2.14 and 3.55 bits for orders 1,
2 and 3, from the in-band noise (Δ<sup>2</sup>/12)(π<sup>2*n*</sup>/(2*n* + 1)) OSR<sup>−(2*n*+1)</sup>.
One bit, second order, at 256 times oversampling is 17.9 bits; at 64
times it is 12.9, so the slogan "one bit at 64× is 16 bits" needs a
third-order loop, which is what the DSD of the SACD uses (fifth to
seventh, in fact, at 64 × 44.1 kHz). The dashed line is this ADC's own
ceiling as a measuring instrument, 7.5 bits plus half a bit per doubling:
anything the DAC side does better than that, the ADC cannot see, which
is why the DAC experiments below use the ADALM2000's 12-bit scope as the
instrument instead.

## The ADC side: averaging buys bits only from noise

![Measured, the ADALM2000's W1 driving ADC IN: a code and a half of sine is a staircase without noise and a cloud with two codes of it; low-passed to 195 kilohertz, the staircase stays a staircase while the noisy record becomes a smooth sine; effective bits against the oversampling ratio for no noise, white noise and high-passed noise; and a DC level read as whole codes without noise and to thousandths with it](img/dsp_oversample_adc.png)

<details>
<summary>The whole file: <code>oversample_adc.py</code></summary>

<!-- file: src/dsp/oversample_adc.py -->
```python
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
```

</details>

```console
$ cd src/dsp
$ python3 oversample_adc.py --m2k /dev/ttyUSB0      # W1 into ADC IN: a 1.5-code sine at 9.155 kHz, with and without noise
measured, the ADALM2000's W1 driving ADC IN; the DAC plays 128 + 1.50 sin at 9.155 kHz: about 1.16 ADC codes of sine on 126.83
ENOB against the ADC's full scale, per OSR; then the fitted amplitude and offset at OSR 256
way         OSR 1    OSR 4   OSR 16   OSR 64  OSR 256     amplitude     offset
none         8.20     8.48     8.56     8.61     9.41      1.125       128.028
dither       5.78     6.96     7.99     8.92     9.54      1.146       128.055
shaped       5.54     8.14     9.61    10.24    10.74      1.124       128.044
theory for white error of 1.58 ADC codes rms: 5.54, 6.54, 7.54, 8.54, 9.54
```

A sine a code and a half high is a staircase of three levels, and
averaging the staircase 256 times over gives a smoother staircase: the
"none" row gains a bit in eight doublings, and its fitted amplitude is
wrong. Add two codes of white noise at the source and the single
sample is worse (5.8 bits: the noise is there) but every doubling
returns half a bit, exactly on the textbook line, and the sine comes
back with the right amplitude. Add the same noise *high-passed* instead
(first-differenced, so it lives where the low-pass will remove it) and
it costs nothing at the start and returns more than half a bit per
doubling: 10.7 bits from an 8-bit ADC at OSR 256, which is the whole
page in one row. The ADC's own noise, a tenth of a code, is not enough
to do this by itself; a real ADC with 0.5 code of noise would be, and
that is why datasheets that quote "8 bits" with half a code of noise
are being generous twice.

```console
$ python3 oversample_adc.py --m2k /dev/ttyUSB0 --dc
DAC code   ADC mean, no noise   with 2.0 codes of noise (+- its standard error)
  124         125.000               125.027 +- 0.010
  125         126.000               125.793 +- 0.011
  126         126.664               126.547 +- 0.011
  127         127.002               127.302 +- 0.010
  128         128.000               128.054 +- 0.010
  129         129.000               128.835 +- 0.010
  130         129.726               129.614 +- 0.011
  131         130.199               130.391 +- 0.011
  132         131.000               131.122 +- 0.011
```

A DC level without noise is read as a whole code, however many samples
you average, because every sample is the same wrong answer. With two
codes of noise the mean of 16384 samples resolves a hundredth of a code
and its standard error is a hundredth: an 8-bit converter reading to
thirteen bits, and the differences between the rows are the converters'
real *[differential nonlinearity](https://en.wikipedia.org/wiki/Differential_nonlinearity)*, measured for free. (The "DAC code"
column here is the generator's setting through its own gain, so the
model line of the loopback cable in the figure's last panel does not
apply to it.) This is also why [6.12](6_12_on_the_air.md#612-on-the-air-whispers-and-how-far-they-carry)'s
lock-in read 78.380 codes to three decimals: a 157-code tone at a
frequency incommensurate with the sampling sweeps the ADC's rounding
through every code, so the signal is its own dither, and 2<sup>13</sup> samples
average it down ninety times. A one-code tone cannot dither itself,
which is [2.05](2_05_lockin_peripheral.md#205-a-lock-in-peripheral)'s bias
at small signals.

## The DAC side: one bit, flopping around wildly

<details>
<summary>The whole file: <code>sigma_delta.py</code></summary>

<!-- file: src/dsp/sigma_delta.py -->
```python
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
```

</details>

`sigma_delta.py` takes a slow sine (three cycles per `awgcap.sv` loop,
9.155 kHz, 64 codes), re-quantizes it four ways to 1, 2, 4 or 8 bits
(plain rounding, rounding with TPDF dither, first-order and second-order
error-feedback delta-sigma), and plays the result through the DAC. The
one-bit versions use DAC codes 0 and 255 only. The modulator runs at
25 MS/s and each output is held for two DAC samples: this hardware's
first limitation, because the shaped noise has to stay below the ADC's
12.5 MHz [Nyquist frequency](https://en.wikipedia.org/wiki/Nyquist_frequency), or the loopback would fold the loudest part
of it onto the quietest. Then the instrument (the ADC through the cable,
or here the M2k's scope on the DAC pin) records the stream, a digital
low-pass and decimation by OSR recover the sine, and a sine fit's
residual gives the ENOB:

```console
$ python3 sigma_delta.py --m2k /dev/ttyUSB0 --table
ENOB, measured (textbook) against OSR -- band edge 12.5 MHz / OSR; measured, the DAC pin on an ADALM2000 scope at 100 MS/s
bits  method          OSR 1         OSR 4        OSR 16        OSR 64       OSR 256
   1  plain    0.39 ( 0.00)  0.39 ( 1.00)  0.41 ( 2.00)  0.46 ( 3.00)  0.72 ( 4.00)
   1  dither  -0.45 (-0.79)  0.33 ( 0.21)  1.32 ( 1.21)  2.27 ( 2.21)  3.02 ( 3.21)
   1  order1  -0.19 (-0.86)  3.05 ( 2.14)  4.42 ( 5.14)  4.50 ( 8.14)  4.55 (11.14)
   1  order2  -0.31 (-2.14)  2.01 ( 2.86)  4.75 ( 7.86)  5.11 (12.86)  5.29 (17.86)
   2  plain    1.98 ( 1.58)  1.98 ( 2.58)  2.00 ( 3.58)  2.06 ( 4.58)  2.31 ( 5.58)
   2  dither   1.04 ( 0.79)  1.80 ( 1.79)  2.79 ( 2.79)  3.80 ( 3.79)  4.62 ( 4.79)
   2  order1   1.55 ( 0.73)  3.80 ( 3.73)  6.69 ( 6.73)  8.59 ( 9.73)  8.95 (12.73)
   2  order2   0.79 (-0.56)  4.27 ( 4.44)  5.59 ( 9.44)  5.97 (14.44)  6.29 (19.44)
   4  plain    4.03 ( 3.91)  4.05 ( 4.91)  4.12 ( 5.91)  4.60 ( 6.91)  5.98 ( 7.91)
   4  dither   3.35 ( 3.11)  4.16 ( 4.11)  5.15 ( 5.11)  6.14 ( 6.11)  7.09 ( 7.11)
   4  order1   3.83 ( 3.05)  6.08 ( 6.05)  8.14 ( 9.05)  8.53 (12.05)  8.71 (15.05)
   4  order2   3.10 ( 1.76)  6.79 ( 6.76)  8.51 (11.76)  8.77 (16.76)  8.92 (21.76)
   8  plain    7.34 ( 7.99)  7.72 ( 8.99)  8.08 ( 9.99)  8.27 (10.99)  8.66 (11.99)
   8  dither   7.03 ( 7.20)  7.59 ( 8.20)  8.02 ( 9.20)  8.27 (10.20)  8.58 (11.20)
   8  order1   7.26 ( 7.14)  7.93 (10.14)  8.13 (13.14)  8.27 (16.14)  8.54 (19.14)
   8  order2   6.88 ( 5.85)  7.97 (10.85)  8.16 (15.85)  8.31 (20.85)  8.56 (25.85)
the instrument's own ceiling (0.43 DAC codes rms, white):   8.41   9.41  10.41  11.41  12.41
```

Read it in three passes. **The plain and dithered rows follow the
textbook to a tenth of a bit**: a comparator (1 bit, plain) is worth
nothing however much you average, because its error is the signal's own
shape; dithered, it gains exactly half a bit per doubling and reaches
three bits from one. **The shaped rows start on the textbook and leave
it**: 2-bit first-order rounding is 1.5 bits at the full rate, 3.8 at
OSR 4, 6.7 at 16, 8.6 at 64 and nearly 9 at 256, which is a two-bit DAC
behaving like a nine-bit one, and the bottom-left panel of the opening
figure is the clean sine it makes. **And then they stop**, far below both
the textbook and the instrument's 12-bit ceiling: the one-bit streams at
4.5 to 5.3 bits, the four- and eight-bit shaped ones near 9. The
simulation, with an ideal DAC, does not do this (the 1-bit second-order
row reaches 11 bits there), so the stop is the hardware, and it is the
page's second lesson:

<details>
<summary><b>Detail:</b> why the real one-bit stream stops at five bits</summary>

A one-bit DAC is "linear by construction": two levels can only be wrong
by a gain and an offset, which is the whole reason the audio world went
to one bit. But that argument is about the *levels*. A real DAC also has
*edges*, and an 8-bit AD9708 asked to jump between codes 0 and 255
twelve million times a second does not make every edge identical: each
transition carries a little glitch energy and a slew that differs for
rising and falling, and the stream's low-frequency content then depends
on how many transitions it has, which depends on the signal. That is
inter-symbol interference, a nonlinearity that no amount of filtering
removes, and it grows with the number of transitions: the second-order
stream, which switches more often than the first-order, comes out no
better. A purpose-built one-bit DAC spends its design on making edges
identical (return-to-zero coding, matched current switches), and a
multi-bit delta-sigma DAC avoids the problem by switching less and
*randomizes* which of its unit elements it uses so that their mismatch
becomes noise rather than distortion (dynamic element matching). Our
8-bit DAC pretending to be a 1-bit one shows exactly why those designs
exist; the 2-bit first-order row, with fewer transitions, is the best
compromise this hardware can make, and nine bits from two is still the
point.

</details>

<details>
<summary><b>Detail:</b> the loop has to bite its own tail</summary>

`awgcap.sv` plays its 16384 samples for ever, so the modulator's state at
the end of the loop must equal its state at the start, or there is a
glitch of up to a whole level once per loop, and at OSR 256 that glitch
alone capped the one-bit stream near nine bits in the first attempt.
`sigma_delta.py` searches for a starting state that makes the loop close
(for a first-order modulator: any start whose accumulated error over the
loop is zero; for second order, one linear step more), to a part in
10<sup>9</sup>. The gateware version below has no loop and no such problem,
which is a nice question to ask a student: why?

</details>

## The same thing in gateware

<details>
<summary>The whole file: <code>sigma_delta.sv</code></summary>

<!-- file: src/dsp/sigma_delta.sv -->
```systemverilog
// sigma_delta.sv -- trading speed for bits, in gateware (7.05).  A 16-bit sine from a
// DDS is re-quantized for the 8-bit DAC at 25 MS/s, four ways, each level held for two
// DAC clocks (so that the shaped noise stays below the ADC's 12.5 MHz); and the ADC's
// side is a three-stage CIC decimator that streams 24-bit samples to the laptop, so
// that the recovered waveform can be watched live (sigma_delta_live.py --monitor).
//
// Transmit: phase accumulator + a 16-bit quarter-wave sine table (4096 entries, block
//           RAM) + the amplitude, giving x in 1/65536 of a DAC code; then, once per
//           modulator sample (every other clock):
//             mode 0  8-bit plain:  dac = 128 + round(x)
//             mode 1  1-bit, 1st order:  v = x - e;  dac = v >= 0 ? 255 : 0;  e = y - v
//             mode 2  1-bit, 2nd order:  v = x - 2 e1 + e2;  likewise;  e2 = e1, e1 = y - v
//             mode 3  8-bit, 1st order:  v = x - e;  dac = 128 + round(v);  e = round(v) - v
//           (y = +-127.5 codes for the 1-bit modes).  Error feedback: y = x + (1 - z^-1)^n e.
// Receive:  x = adc - 128 into three integrators at 25 MS/s; every 2^d samples the sum
//           goes through three differentiators (a CIC, Hogenauer 1981: sinc^3, the
//           right order for a 2nd-order modulator) and out as a 24-bit sample, scaled
//           by 2^(16 - 3d) so that +-128 codes is +-2^23 whatever d is.  Each sample is
//           a 4-byte frame on uart_tx: 0xA5, then the 24 bits big-endian.
//
// The laptop's protocol (1,000,000 baud, 8N1; multi-byte integers big-endian):
//   'F' word(4)   the DDS tuning word: f / 25e6 x 2^32 (one step per modulator sample)
//   'A' amp(2)    amplitude in 1/256 DAC code, 0..32767 (= 0..127.996 codes)
//   'M' mode      0..3 as above (default 2); changing it clears the error state
//   'D' d         decimation 2^d, d = 8..16 (default 10: 24,414 samples a second)
//   'S' 0/1       streaming off/on (default off)
//   Unknown bytes are ignored.  The UART carries 25,000 frames a second: d >= 10 streams
//   every sample; at d = 9 every other one is dropped whole (`dropped` counts them).
//
// LEDs: led[0] = streaming; led[4:1] = the decimated signal's size, about 10 dB per LED.
module sigma_delta (
    input  logic       clk,         // 50 MHz
    input  logic       uart_rx,
    output logic       uart_tx,
    output logic [7:0] dac_d = 128,
    output logic       dac_clk,
    input  logic [7:0] adc_d,
    output logic       adc_clk,
    output logic [4:0] led
);
    // ---- the serial port (uart.sv) -----------------------------------------------------
    logic [7:0] rx_data, tx_data = 0;
    logic       rx_valid, tx_start = 0, tx_busy;
    uart_rx #(.CLKS_PER_BIT(50)) urx (.clk(clk), .rx(uart_rx), .data(rx_data), .valid(rx_valid));
    uart_tx #(.CLKS_PER_BIT(50)) utx (.clk(clk), .data(tx_data), .start(tx_start),
                                      .busy(tx_busy), .tx(uart_tx));

    // ---- the settings ----------------------------------------------------------------
    logic [31:0] fword  = 32'd1_572_864;            // 'F': 9155.27 Hz (3 cycles per 327.68 us)
    logic [14:0] amp    = 15'd16384;                // 'A': 64 codes
    logic [1:0]  mode   = 2'd2;                     // 'M'
    logic [4:0]  d      = 5'd10;                    // 'D'
    logic        stream = 0;                        // 'S'
    logic [7:0]  cmd  = 0, left = 0;
    logic [31:0] arg  = 0;
    logic        restart = 0;                       // a new mode or d: clear the states
    always_ff @(posedge clk) begin
        restart <= 0;
        if (rx_valid) begin
            if (cmd == 0)
                case (rx_data)
                    "F": begin cmd <= "F"; left <= 4; end
                    "A": begin cmd <= "A"; left <= 2; end
                    "M": begin cmd <= "M"; left <= 1; end
                    "D": begin cmd <= "D"; left <= 1; end
                    "S": begin cmd <= "S"; left <= 1; end
                    default: ;
                endcase
            else begin
                arg  <= {arg[23:0], rx_data};
                left <= left - 1;
                if (left == 1) cmd <= 0;
                case (cmd)
                    "F": if (left == 1) fword <= {arg[23:0], rx_data};
                    "A": if (left == 1) amp <= {arg[6:0], rx_data};
                    "M": begin mode <= rx_data[1:0]; restart <= 1; end
                    "D": if (rx_data >= 8 && rx_data <= 16) begin d <= rx_data[4:0]; restart <= 1; end
                    "S": stream <= rx_data[0];
                    default: ;
                endcase
            end
        end
    end

    // ---- the modulator's clock: every other cycle --------------------------------------
    logic tick = 0;
    always_ff @(posedge clk) tick <= ~tick;

    // ---- the DDS: a 16-bit sine, from a quarter wave in block RAM ------------------------
    logic signed [15:0] quarter [0:4095];           // sin of (i + 1/2) / 4096 quarter turns
    initial for (int i = 0; i < 4096; i++)
        quarter[i] = $rtoi($floor(32767.0 * $sin(1.5707963267948966 * (i + 0.5) / 4096) + 0.5));
    logic [31:0]        phase = 0;
    logic [11:0]        qa = 0;
    logic               neg1 = 0, neg2 = 0;
    logic signed [15:0] qv = 0, sv = 0;             // the sine, +-32767
    always_ff @(posedge clk) begin
        if (tick) phase <= phase + fword;
        qa   <= phase[30] ? ~phase[29:18] : phase[29:18];   // 2nd and 4th quarters run backwards
        neg1 <= phase[31];                                   // 3rd and 4th are negative
        qv   <= quarter[qa];
        neg2 <= neg1;
        sv   <= neg2 ? -qv : qv;
    end
    logic signed [31:0] prod = 0;                   // sine x amplitude
    logic signed [31:0] x;                          // the sample, in 1/65536 of a DAC code
    always_ff @(posedge clk) prod <= sv * $signed({1'b0, amp});
    assign x = prod >>> 7;                          // (2^15 x 2^8 = 2^23 per code) -> 2^16 per code

    // ---- the modulator: round, or feed the error back and then round ----------------------
    localparam signed [31:0] HALF = 32'sd8_355_840; // 127.5 codes
    logic signed [31:0] e1 = 0, e2 = 0;             // the last two rounding errors
    logic signed [31:0] v, r;                       // the value to round; rounded to a code
    logic signed [8:0]  q;                          // -128..127
    logic               one;
    always_comb begin
        case (mode)
            2'd0:    v = x;
            2'd2:    v = x - (e1 <<< 1) + e2;
            default: v = x - e1;
        endcase
        r   = (v + 32'sd32768) >>> 16;
        q   = (r > 127) ? 9'sd127 : (r < -128) ? -9'sd128 : 9'(r);
        one = (v >= 0);
    end
    always_ff @(posedge clk) begin
        if (restart) begin
            e1 <= 0;
            e2 <= 0;
        end else if (tick) begin
            // ##########################################################################
            // ##  KEY LINE: the error of this rounding is kept, to be subtracted before
            // ##  the next one: y = x + (1 - z^-1) e, and the noise moves up in frequency.
            // ##########################################################################
            case (mode)
                2'd0: dac_d <= 8'(128 + q);
                2'd3: begin dac_d <= 8'(128 + q);          e1 <= (32'(q) <<< 16) - v; end
                2'd1: begin dac_d <= one ? 8'd255 : 8'd0;  e1 <= (one ? HALF : -HALF) - v; end
                2'd2: begin dac_d <= one ? 8'd255 : 8'd0;  e1 <= (one ? HALF : -HALF) - v; e2 <= e1; end
            endcase
        end
    end
    assign dac_clk = ~clk;

    // ---- the ADC at 25 MS/s, as in capture.sv -------------------------------------------
    logic adc_clk_r = 0, new_sample = 0;
    logic signed [8:0] xa = 0;
    always_ff @(posedge clk) begin
        adc_clk_r  <= ~adc_clk_r;
        new_sample <= 0;
        if (adc_clk_r == 0) begin
            xa <= $signed({1'b0, adc_d}) - 9'sd128;
            new_sample <= 1;
        end
    end
    assign adc_clk = adc_clk_r;

    // ---- the CIC: three integrators at 25 MS/s, three combs at 25 MS/s / 2^d --------------
    // 8 bits in, times 2^(3d) <= 2^48 of gain: 56 bits, and the integrators may wrap.
    logic signed [55:0] i1 = 0, i2 = 0, i3 = 0;
    logic signed [55:0] c1 = 0, c2 = 0, c3 = 0, m1 = 0, m2 = 0, m3 = 0;
    logic [15:0]        cnt = 0, last;
    logic               dump = 0, v1 = 0, v2 = 0, v3 = 0, out_new = 0;
    logic signed [23:0] out = 0;
    assign last = 16'((17'd1 << d) - 1);
    always_ff @(posedge clk) begin
        dump <= 0;
        if (restart) begin
            i1 <= 0; i2 <= 0; i3 <= 0; m1 <= 0; m2 <= 0; m3 <= 0; cnt <= 0;
        end else if (new_sample) begin
            // ##########################################################################
            // ##  KEY LINE: a boxcar of boxcars of boxcars.  Integrate three times at
            // ##  the fast rate; differentiate three times at the slow one (below).
            // ##########################################################################
            i1 <= i1 + 56'(xa);
            i2 <= i2 + i1;
            i3 <= i3 + i2;
            if ((cnt & last) == last) begin
                cnt  <= 0;
                dump <= 1;
            end else
                cnt <= cnt + 1;
        end
        v1 <= dump;  v2 <= v1;  v3 <= v2;  out_new <= v3;
        if (dump) begin c1 <= i3 - m1; m1 <= i3; end
        if (v1)   begin c2 <= c1 - m2; m2 <= c1; end
        if (v2)   begin c3 <= c2 - m3; m3 <= c2; end
        if (v3)   out <= 24'(c3 >>> (3 * d - 16));
    end

    // ---- the frames to the laptop: 0xA5 then 3 bytes ----------------------------------------
    logic [31:0] frame   = 0;
    logic [2:0]  nbytes  = 0;
    logic [15:0] dropped = 0;
    always_ff @(posedge clk) begin
        tx_start <= 0;
        if (out_new && stream && nbytes == 0) begin
            frame  <= {8'ha5, out};
            nbytes <= 4;
        end else begin
            if (out_new && stream)
                dropped <= dropped + 1;
            if (nbytes != 0 && !tx_busy && !tx_start) begin
                tx_data  <= frame[31:24];
                tx_start <= 1;
                frame    <= {frame[23:0], 8'h00};
                nbytes   <= nbytes - 1;
            end
        end
    end

    // ---- LEDs ---------------------------------------------------------------------------
    logic [23:0] mag = 0;                           // |out|: 2^16 per ADC code
    always_ff @(posedge clk) if (out_new) mag <= out[23] ? 24'(-out) : 24'(out);
    assign led = {mag >= 24'd2_000_000, mag >= 24'd650_000, mag >= 24'd200_000,
                  mag >= 24'd65_000, stream};       // 1, 3, 10 and 30 codes
endmodule
```

</details>

`sigma_delta.sv` is the modulator and the decimator with no laptop in
the loop: a 16-bit sine from a DDS, re-quantized on the fly in one of
four modes (8-bit plain, 1-bit first order, 1-bit second order, 8-bit
first-order shaped), the DAC playing it at 25 MS/s held twice; and on the
ADC side a three-stage *CIC* decimator (a boxcar of boxcars, Hogenauer's
1981 filter, the standard way to decimate a delta-sigma stream with no
multipliers) by 2<sup>*d*</sup>, streaming 24-bit samples to the laptop at
25 MHz / 2<sup>*d*</sup>. The bits grow in the decimator: 8 in, 24 out. Its
testbench plays a 1 kHz sine at 64 codes through all four modes and
reads it back through the CIC at 63.3 to 63.4 codes (the 1% is the
[sinc](https://en.wikipedia.org/wiki/Sinc_function)<sup>3</sup> droop of the CIC at the band edge), then a 1.5-code sine: 1.49
codes through the shaped mode and 1.19 with a 22% third harmonic
through plain rounding, the staircase again. On the bench, with the
scope on the DAC pin and the gateware playing a 1 kHz sine at 64 codes
in each mode, the live stream reads what the Python one did: the 1-bit
first- and second-order streams 4.4 and 5.2 bits at OSR 256, the 8-bit
shaped one 8.4, plain 8-bit 8.3 (the DAC's edges, again). With the cable back and the
8-bit ADC as the instrument (`sigma_delta.py PORT --table`), the same
streams read a little *higher* than on the scope: the 1-bit second-order
stream 7.0 bits at OSR 256, 4-bit second-order 10.8, plain 8-bit 10.9
against the ADC's own 11.6 ceiling, because a 25 MS/s ADC behind a cable
sees less of the DAC's edges than a 100 MS/s scope on the pin does. The
edges are still the wall. The ADC side through the cable
(`oversample_adc.py PORT`) gives 9.5 bits with white dither and 11.3 with
high-passed dither at OSR 256, on the W1 numbers above. And the
gateware's own CIC, reading its 1-bit second-order stream back through
the cable at 24 kS/s (`sigma_delta_live.py --mode 2 --amp 64 --monitor`),
reports the 64-code sine at 47.5 codes with 2.9 codes of shaped noise
left below 6 kHz, where 0.776 × 64 × the CIC's 0.99 is 49; the
1.5-code sine reads 0.82 codes through plain rounding and 1.03 codes through
the shaped mode against 1.16 expected: the staircase and its cure, live.

```console
$ make sim                      # the four modes, 1 kHz, through the CIC
mode 0,  64.00 codes: DAC stream amplitude  64.012 (3rd harmonic  0.013) ...  73 frames, amplitude  63.431 codes
mode 1,  64.00 codes: DAC stream amplitude  63.998 (3rd harmonic  0.000) ...  73 frames, amplitude  63.309 codes
mode 2,  64.00 codes: DAC stream amplitude  64.003 (3rd harmonic  0.007) ...  73 frames, amplitude  63.254 codes
mode 3,  64.00 codes: DAC stream amplitude  63.998 (3rd harmonic  0.000) ...  73 frames, amplitude  63.291 codes
mode 3,   1.50 codes: DAC stream amplitude   1.500 (3rd harmonic  0.000) ...  73 frames, amplitude   1.486 codes
mode 0,   1.50 codes: DAC stream amplitude   1.200 (3rd harmonic  0.222) ...  73 frames, amplitude   1.190 codes
PASS
```

## What this hardware cannot show, and what would

- An 8-bit DAC playing a 1-bit stream: its edges, above. A real 1-bit
  DAC is one FPGA pin and an RC; this module's DAC is the wrong tool for
  the job it was asked to do here, and shows why.
- No analog reconstruction filter: the scope and the ADC see the raw
  stream, and the low-pass is digital. With a 1 kΩ and 10 nF on DAC OUT
  and a pair of headphones you would *hear* the one-bit stream as a pure
  tone, which is the demonstration this page wants and could not make.
- The ADC's 25 MS/s folds everything above 12.5 MHz, so the modulator
  runs at 25 and not 50 MS/s.
- The ADC as an instrument: a white floor of 7.5 bits plus half a bit
  per doubling, and its own nonlinearity for multi-level streams.
- Too little intrinsic dither (0.1 code), and on this module the ADC
  reads 0.776 of a DAC code, so the ADC's rounding error against the
  DAC's whole codes repeats every 4.5 codes: two codes of noise are
  needed, not one.
- The 327.68 µs loop makes the spectrum a comb of lines 3052 Hz apart,
  and forces the tail-biting trick.

| part | for | about |
| --- | --- | --- |
| 1 kΩ, 10 nF, a 3.5 mm jack and headphones, or a $5 amplified speaker | the analog low-pass, and hearing it | $10 |
| a PCM5102A I<sup>2</sup>S DAC module, or a PCM1808 ADC module | a true 16-bit reference at audio rates to compare with | $5 each |
| an LM311 comparator, 10 kΩ and 1 nF | the analog first-order delta-sigma *ADC* with one FPGA pin, the side this module cannot show (Lattice and Xilinx both have an application note) | $2 |

Wikipedia's [delta-sigma modulation](https://en.wikipedia.org/wiki/Delta-sigma_modulation),
[oversampling](https://en.wikipedia.org/wiki/Oversampling),
[noise shaping](https://en.wikipedia.org/wiki/Noise_shaping) and
[dither](https://en.wikipedia.org/wiki/Dither) pages are good; Analog
Devices' [MT-022](https://www.analog.com/media/en/training-seminars/tutorials/MT-022.pdf)
and [MT-023](https://www.analog.com/media/en/training-seminars/tutorials/MT-023.pdf)
are the engineer's version; Schreier and Temes, *Understanding
Delta-Sigma Data Converters*, is the book; and Lipshitz, Wannamaker and
Vanderkooy's 1992 survey of dither is where fact 1 comes from.

**Try this:**

- The RC and the headphones. Then stream a WAV file over the [UART](https://en.wikipedia.org/wiki/Universal_asynchronous_receiver-transmitter) into a
  FIFO in place of the DDS (88 kB/s carries 44.1 kHz at 16 bits): a USB
  one-bit DAC of your own.
- A third-order modulator: what goes unstable, and at what amplitude?
- Count the transitions in each stream and plot the measured ENOB
  against them: the DAC's edge penalty, measured.
- `--bits 2 --order 1` at OSR 1024 (nine cycles per loop): where does the
  two-bit stream stop?
- The dithered DC sweep over all 256 DAC codes: the DAC's DNL, measured.
- With the loopback cable: `sigma_delta.py PORT --table` with the ADC as
  the instrument, and `sigma_delta_live.py` on the gateware.
