#!/usr/bin/env python3
"""A pretend board: what awgcap.sv's ADC would record, computed instead of measured.

    import channel
    rec = channel.channel(wave)                     # one board, looped back through 1 m of cable
    rec = channel.channel(wave, ppm=0.76, start=5000.3)   # board A plays, board B records
    rec = channel.channel(wave, noise=3.0)          # a noisier ADC (3 codes rms)

    python3 channel.py                              # print the model's step and frequency
                                                    #   response, to compare with 1.07

`wave` is what awgcap.upload() takes: 16384 DAC codes (0..255), played at 50 MS/s,
over and over.  The result is what awgcap.record() returns: 16384 ADC codes at
25 MS/s (two loops), starting at the receiving board's own loop start.  On the
way, in order:

  1. the DAC rounds to whole codes and HOLDS each one for 20 ns (its steps);
  2. a gentle analog low-pass (two poles at `corner`, 40 MHz by default) stands
     in for the DAC's output stage, the cable and the ADC's input;
  3. the cable and the converters' pipelines delay everything by `delay` ADC
     samples: about 6 (240 ns), as 1.07 measured.  Any fraction is allowed;
     the default 5.7 puts a step's half-way point at sample 518, as measured;
  4. the ADC reads 0.776 codes per DAC code, plus 27.5 (1.07's transfer curve),
     plus `noise` codes rms of random noise, and rounds to whole codes.

For two boards, `start` says where in the transmitter's loop (in DAC samples) the
receiver's record begins, and `ppm` how much faster the transmitter's crystal runs
than the receiver's: its carrier, its symbol rate and its loop all come out that
much fast.  `shift` (Hz) moves the whole spectrum, as a radio's mixer would if its
local oscillator were off.

What it leaves out: the measured cable's slight non-linearity and ringing (1.07),
and the ADC's own anti-alias filtering.  The DAC's images above 25 MHz ARE in
(step 1), and fold back onto the ADC's band as they do on the board.  With one
clock they land exactly on the signal and only change its gain a little.  With
two clocks they land 50 MHz x ppm away from it: 38 Hz at the boards' 0.76 ppm,
harmless, but 100 kHz at a pretend 2000 ppm, an interferer about 21 dB down.
"""
import numpy as np

N = 16384                        # DAC samples per loop: 327.68 us
FS_DAC, FS_ADC = 50e6, 25e6
UP = 16                          # the "analog" time grid: 16 points per DAC sample (800 MS/s)
GAIN, OFFSET = 0.776, 27.5       # ADC code = 0.776 * DAC code + 27.5   (1.07)


def cubic(y, t):
    """y at the fractional indices t (periodic in len(y)): cubic Lagrange interpolation
    through the four nearest samples.  Works for real or complex y."""
    t = np.asarray(t, float)
    i = np.floor(t).astype(int)
    mu = t - i
    L = len(y)
    ym1, y0, y1, y2 = y[(i - 1) % L], y[i % L], y[(i + 1) % L], y[(i + 2) % L]
    c1 = -ym1 / 3 - y0 / 2 + y1 - y2 / 6
    c2 = ym1 / 2 - y0 + y1 / 2
    c3 = -ym1 / 6 + y0 / 2 - y1 / 2 + y2 / 6
    return ((c3 * mu + c2) * mu + c1) * mu + y0


def analog(wave, corner=40e6):
    """One loop of the DAC's output as a voltage, in DAC codes about mid-scale (128),
    on a time grid UP times finer than the DAC's: the held steps, then the
    low-pass.  Returns its spectrum too (for the fractional delay)."""
    w = np.clip(np.round(np.asarray(wave, float)), 0, 255)       # 1. 8 bits
    assert len(w) == N, "a waveform is %d samples, not %d" % (N, len(w))
    # ##########################################################################
    # ##  KEY LINE: the DAC holds each code for one whole sample (20 ns), so on
    # ##  a finer time grid its output is each code repeated UP times.
    # ##########################################################################
    held = np.repeat(w - 128, UP)
    f = np.fft.rfftfreq(N * UP, 1 / (FS_DAC * UP))
    s = 1j * f / corner                                             # 2. two poles
    H = 1 / (1 + np.sqrt(2) * s + s**2)                             #    (Butterworth)
    return np.fft.rfft(held) * H, f


def channel(wave, delay=5.7, noise=0.1, ppm=0.0, start=None, shift=0.0,
            corner=40e6, gain=GAIN, offset=OFFSET, rng=None):
    """16384 DAC codes (looping at 50 MS/s) in, 16384 ADC codes (25 MS/s) out.

    delay   one board, looped back: ADC samples from DAC to ADC (6.0 = 240 ns)
    start   two boards: where the receiver's record starts in the transmitter's
            loop, in DAC samples (any float); overrides `delay`
    ppm     two boards: the transmitter's clock runs this many ppm fast
    shift   Hz: move the received spectrum up (a mixer's LO error)
    noise   ADC noise, codes rms (the real one: about 0.1)
    """
    rng = np.random.default_rng(rng)
    Y, f = analog(wave, corner)
    n = np.arange(N)                                     # ADC sample number
    # Where each ADC sample falls in the transmitter's loop, in DAC samples:
    # 2 DAC samples per ADC sample, stretched by the clock offset, plus the start.
    u0 = -2.0 * delay if start is None else float(start)
    # ##########################################################################
    # ##  KEY LINE: ADC sample n sees the DAC's output at the transmitter's
    # ##  time u = 2n(1 + ppm/1e6) + u0 (in DAC samples, around the loop).
    # ##########################################################################
    u = 2.0 * n * (1 + ppm * 1e-6) + u0
    pos = u * UP                                         # on the fine grid
    if ppm == 0 and shift == 0:
        # Every position has the same fractional part: shift the waveform by that
        # fraction exactly (a phase slope across the spectrum), then just pick points.
        frac = pos[0] - np.floor(pos[0])
        y = np.fft.irfft(Y * np.exp(2j * np.pi * f * frac / (FS_DAC * UP)), N * UP)
        v = y[(np.floor(pos[0]).astype(int) + 2 * UP * n) % (N * UP)]
    elif shift == 0:
        v = cubic(np.fft.irfft(Y, N * UP), pos)
    else:
        # The analytic signal (positive frequencies only), moved by `shift` Hz.
        Ya = 2 * Y; Ya[0] = Y[0]
        full = np.zeros(N * UP, complex); full[:len(Ya)] = Ya
        ya = np.fft.ifft(full)
        v = np.real(cubic(ya, pos) * np.exp(2j * np.pi * shift * n / FS_ADC))
    # 4. the ADC: gain, offset, noise, 8 bits
    adc = offset + gain * (128 + v) + noise * rng.standard_normal(N)
    return np.clip(np.round(adc), 0, 255).astype(int)


def two_boards(wave, ppm=0.76, noise=0.1, rng=None, **kw):
    """Board A plays `wave`, board B records: a random start, and A's clock `ppm` fast."""
    rng = np.random.default_rng(rng)
    return channel(wave, start=rng.uniform(0, N), ppm=ppm, noise=noise, rng=rng, **kw)


if __name__ == "__main__":
    # The model against 1.07's measurements: a step from DAC code 32 to 224 at
    # DAC sample 1024 (ADC sample 512), and the response to a flat multitone.
    step = np.where((np.arange(N) // 1024) % 2 == 1, 224, 32)
    r = channel(step, noise=0)
    half = (r.max() + r.min()) / 2
    first = 512 + np.argmax(r[512:530] > half)
    print("step at ADC sample 512: first sample past half-way %d (1.07 measured 518)" % first)
    print("ADC codes at DAC codes 32 and 224: %.1f and %.1f  (0.776 x DAC + 27.5: %.1f and %.1f)"
          % (r[300], r[800], 0.776 * 32 + 27.5, 0.776 * 224 + 27.5))
    h = np.diff(r[511:524].astype(float)) / 192      # ADC codes per DAC code
    print("impulse response from the step, delays 0..11 samples (1.07 measured 0.74 at 6,")
    print("then -0.018, -0.027, +0.015: ringing this model leaves out):")
    print(np.round(h, 3))
    # One sine at a time, measured as the lock-in would: gain vs frequency.
    # (6.07's channel sounding measured 0.73 to 0.86, rising towards 12 MHz.)
    n = np.arange(N)
    for k in (164, 655, 1311, 2048, 2621, 3277, 3932):    # cycles per loop
        x = 128 + 100 * np.cos(2 * np.pi * k * n / N)
        r = channel(x, noise=0)
        z = 2 * np.mean((r - r.mean()) * np.exp(-2j * np.pi * k * np.arange(N) / (N / 2)))
        print("%5.2f MHz: %.3f ADC codes per DAC code" % (k * FS_DAC / N / 1e6, abs(z) / 100))
