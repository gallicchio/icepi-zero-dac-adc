#!/usr/bin/env python3
"""An echo in the cable: a T with an open stub, simulated, on top of channel.py (or a record).

    import echo
    rec = echo.add_stub(channel.channel(wave), 25.0)        # a 25 m open stub on a T
    rec = echo.add_echo(rec, tau=0.64e-6, a=0.67)           # or just: an echo, 0.64 us late,
                                                            #   2/3 the size of the direct signal
    H = echo.stub_response(f, 25.0)                         # the stub's H(f), relative to no stub

    python3 echo.py                     # a table: stub lengths, their delays and their notches
    python3 echo.py --loss 0.045 --vf 0.66      # ... for RG-58 instead of RG-316

Hang an open-ended cable off a T at the DAC (4.05).  A wave from the DAC reaches the T
and sees two 50-ohm lines in parallel, 25 ohm: 2/3 of its voltage goes on into EACH of
them, and 1/3 bounces back to the DAC, whose 50 ohm absorbs it.  The 2/3 that went into
the stub reflects off the open end (+1: the current must be zero there, so the voltage
doubles) and comes back 2L/v later: at RG-316's velocity factor 0.695, 9.6 ns per metre
of stub.  Back at the T it again sees 25 ohm: 2/3 of it goes on to the ADC, and 1/3,
inverted, goes down the stub for another round trip.  So the ADC gets

    the direct signal (2/3 of what it got without the T), then
    echoes at tau, 2 tau, 3 tau, ...  of size  2/3, -2/9, +2/27, ...  of it,

each round trip also paying the cable's loss twice, rho = 10^(-2 L x dB/m / 20).  With
z = e^(-j 2 pi f tau), the whole thing in the frequency domain is one line:

    H(f) = (2/3) [1 + a z / (1 - b z)]       a = 2/3 rho (the first echo),  b = -rho/3
         = (2/3) (1 + rho z) / (1 + rho z/3)

H = 0 wherever rho z = -1: a lossless stub shorts the T at f = 1/(2 tau), 3/(2 tau), ...,
a comb of notches 1/tau apart, where the stub is an odd number of quarter waves (4.05).
Loss fills them in: a notch bottoms out at (2/3)(1 - rho)/(1 - rho/3), so its depth
measures the cable's loss.  At DC the stub is invisible, H = 1, as it should be.

Two things this leaves out: the DAC's and ADC's own reflections (1.07's ringing), and
the stub's own dispersion.  And `a` is a free parameter in add_echo(): a bigger echo
than 2/3 would need a mismatched T, but it makes a nastier channel to equalize.
"""
import argparse

import numpy as np

C = 299792458.0                  # m/s
VF = 0.695                       # RG-316's velocity factor (RG-58: 0.66)
LOSS = 0.10                      # dB per metre at 10 MHz: RG-316, a typical datasheet value
                                 #   (RG-58: about 0.045; RG-213: about 0.02); grows as sqrt(f)
FS_ADC = 25e6
F_C = 6.25e6                     # psk.py's carrier, for the table below
R = 1.5625e6                     # ... and its symbol rate


def stub_response(f, length, vf=VF, loss=LOSS):
    """H(f) of a T with an open stub `length` metres long, relative to the cable without
    it: the direct path and the whole series of echoes, with the cable's loss."""
    f = np.asarray(f, float)
    tau = 2 * length / (vf * C)                                      # the round trip
    rho = 10 ** (-2 * length * loss * np.sqrt(np.abs(f) / 10e6) / 20)   # ... and its loss
    z = np.exp(-2j * np.pi * f * tau)
    # ##########################################################################
    # ##  KEY LINE: the T splits the wave 2/3 - 1/3, the open end reflects it
    # ##  whole, and the echoes go on for ever, each one -1/3 of the last.
    # ##########################################################################
    return 2 / 3 * (1 + rho * z) / (1 + rho * z / 3)


def echo_response(f, tau, a, b=0.0):
    """H(f) of a direct path plus echoes at tau, 2 tau, 3 tau, ... (seconds) of sizes
    a, a b, a b^2, ...: the textbook echo.  b = 0 is a single echo."""
    z = np.exp(-2j * np.pi * np.asarray(f, float) * tau)
    return 1 + a * z / (1 - b * z)


def apply(x, response, fs=FS_ADC):
    """Pass x, one or more whole loops of samples at fs (so periodic), through the
    frequency response `response(f)`.  Works on a record (25 MS/s) or a waveform (50 MS/s)."""
    x = np.asarray(x, float)
    f = np.fft.rfftfreq(len(x), 1 / fs)
    m = x.mean()                                     # the converters' offset isn't the cable's
    # ##########################################################################
    # ##  KEY LINE: a linear channel multiplies each frequency by one complex
    # ##  number.  The loop repeats, so its FFT bins are exactly its frequencies.
    # ##########################################################################
    return m + np.fft.irfft(np.fft.rfft(x - m) * response(f), len(x))


def add_stub(x, length, fs=FS_ADC, **kw):
    """x with a `length` metre open stub's echoes added (see stub_response)."""
    return apply(x, lambda f: stub_response(f, length, **kw), fs)


def add_echo(x, tau, a, b=0.0, fs=FS_ADC):
    """x with an echo `tau` seconds late, `a` times the size (and b, b^2, ... further ones)."""
    return apply(x, lambda f: echo_response(f, tau, a, b), fs)


def impulse(response, n=64, fs=FS_ADC, nfft=8192):
    """The impulse response h[0..n-1] (one sample each at fs) of `response(f)`."""
    f = np.fft.rfftfreq(nfft, 1 / fs)
    return np.fft.irfft(response(f), nfft)[:n]


def notches(length, vf=VF, fmax=FS_ADC / 2):
    """The stub's notch frequencies below fmax: odd multiples of v / 4L."""
    f1 = vf * C / (4 * length)
    return f1 * np.arange(1, int(fmax / f1) + 1, 2)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vf", type=float, default=VF, help="velocity factor")
    ap.add_argument("--loss", type=float, default=LOSS, help="dB per metre at 10 MHz")
    ap.add_argument("--lengths", default="5,10,15,20,25,30,67,133", help="stub lengths, m")
    args = ap.parse_args()
    f = np.fft.rfftfreq(8192, 1 / FS_ADC)
    band = (f > F_C - (1 + 0.35) * R / 2) & (f < F_C + (1 + 0.35) * R / 2)   # psk.py's band
    print("open stub on a T, velocity factor %.3f, %.3f dB/m at 10 MHz (%.1f ns per metre, round trip)"
          % (args.vf, args.loss, 2e9 / (args.vf * C)))
    print("  length  round trip  ADC samples  symbols at 1.56 / 6.25 Msym/s  first echo  |H| in 5.2-7.3 MHz   notches below 12.5 MHz")
    for L in (float(s) for s in args.lengths.split(",")):
        tau = 2 * L / (args.vf * C)
        rho = 10 ** (-2 * L * args.loss * np.sqrt(F_C / 10e6) / 20)
        H = np.abs(stub_response(f, L, args.vf, args.loss))
        nf = notches(L, args.vf)
        print("  %5.0f m  %7.0f ns  %9.1f    %6.2f  / %5.2f                  %4.2f      %4.2f .. %4.2f         %s MHz"
              % (L, tau * 1e9, tau * FS_ADC, tau * R, tau * 4 * R, 2 / 3 * rho, H[band].min(), H[band].max(),
                 ", ".join("%.2f" % (x / 1e6) for x in nf[:6]) + (", ..." if len(nf) > 6 else "")))
    print("(one symbol at 1.5625 Msym/s is 0.64 us: %.0f m of stub)" % (0.64e-6 * args.vf * C / 2))
