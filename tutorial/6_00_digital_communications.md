<!-- nav -->
[← 5.08 With a little more hardware](5_08_more_hardware.md#508-with-a-little-more-hardware) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)** &emsp;&emsp;&emsp; [6.01 Eye diagrams and pulse shaping →](6_01_eye_diagrams.md#601-eye-diagrams-and-pulse-shaping)

# 6.00 Digital communications (Hardware Defined Radio)

![Above, this chapter's link: psk.py builds a waveform, the DAC plays it on a 6.25 MHz carrier, a coax carries it to the ADC, and psk.py finds the clock, the carrier and the bits. Below, the same link through the air: at each end a mixer with a local oscillator (an ADF4351 synthesizer), a band filter and an amplifier move the 6.25 MHz signal to and from 915 MHz between two antennas; the FPGA, the Python and the algorithms stay the same](img/hdr.png)

The subtitle is a joke at software-defined radio's expense, and the honest
name is *gateware-defined radio*. **Gateware** is what you load into an
FPGA: the configuration that wires its look-up tables and flip-flops into
the circuit you described in SystemVerilog. It is not software, which runs
on a processor (Chapter 2's VexRiscv, or the laptop); it is not firmware,
which is software that lives in a microcontroller's flash and never changes
(Chapter 2's `adda.c` is firmware); and it is not quite hardware, which is
silicon and solder you cannot change at all. It is a description of
hardware that becomes hardware at the flick of a bitstream, and the people
who build open FPGA designs for a living, the LiteX and Migen projects
this tutorial's Chapter 2 is built on, M-Labs' ARTIQ control system for
quantum experiments, the open SDR boards whose FPGA images are shipped as
"gateware", call it that to keep the three layers straight. When a page
here says something runs "in gateware", it means the logic in the FPGA is
doing it, one clock at a time, with no processor in the loop.


> This chapter is a companion to **[learnSDR](https://github.com/gallicchio/learnSDR)**, a course in
> software-defined radio with GNU Radio, an RTL-SDR and a Pluto, whose
> lessons are videos drawn on a lightboard. learnSDR does its signal
> processing in software, on samples from a dongle; here the hardware is
> yours down to the clock, hence the name. The same ideas run on
> hardware you built yourself, in code short enough to read, and where
> learnSDR stopped (at a [QPSK](https://en.wikipedia.org/wiki/Phase-shift_keying#Quadrature_phase-shift_keying_(QPSK)) modem and a GPS fix), this chapter keeps going.
> Each section links the lessons it builds on, and the chapters of
> **[PySDR](https://pysdr.org)**, Marc Lichtman's textbook, which goes deeper into the theory
> and the Python than these pages do.

**What you need first:** Chapter 1 through [1.08](1_08_lockin.md#108-a-lock-in-amplifier) (the loopback and the lock-in's
cos/−sin are used on every page), and [1.09](1_09_spectrum_analyzer.md#109-a-spectrum-analyzer)'s FFT for [6.07](6_07_ofdm.md#607-ofdm-the-triumph-of-physics-over-math). One board is enough.
The board runs [5.01](5_01_two_clocks.md#501-two-clocks)'s `awgcap.sv`, which you can load without reading Chapter 5
(below). Nothing here needs Chapters 2, 3 or 4; [6.11](6_11_the_modem_in_the_fpga.md#611-the-modem-in-the-fpga) borrows [5.05](5_05_fsk_modem.md#505-a-modem)'s modem as a pattern.

Your phone, your Wi-Fi router and a GPS receiver do the same few things.
They put bits onto a carrier as its phase (and amplitude), shape each symbol
so that the signal stays inside its band, and filter what arrives with the
same shape. They find the transmitter's clock and carrier, neither of which
they know in advance, with two feedback loops. They measure the channel and
undo it. They add redundancy so that a few wrong bits don't matter. Some
spread the signal far wider than it needs to be, so that it hides under the
noise and many users share one frequency. This chapter does each of these
with one board and a cable, or two boards, and Python on the laptop doing
the receiving. By the end the whole modem runs inside the FPGA.

| section | what | learnSDR |
| --- | --- | --- |
| [6.01](6_01_eye_diagrams.md#601-eye-diagrams-and-pulse-shaping) | eye diagrams, pulse shaping and matched filters | [14](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson14.md), [15](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson15.md) |
| [6.02](6_02_psk_and_qpsk.md#602-psk-and-qpsk-finding-the-clock-and-the-carrier) | BPSK and QPSK, with a timing loop, a [Costas loop](https://en.wikipedia.org/wiki/Costas_loop), and a frequency-locked loop for when those aren't enough | [12](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson12.md), [13](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson13.md), [16](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson16.md)–[20](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson20.md) |
| [6.03](6_03_qam.md#603-qam-more-bits-per-symbol) | [QAM](https://en.wikipedia.org/wiki/Quadrature_amplitude_modulation): more bits per symbol, and what each costs | [16](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson16.md) |
| [6.04](6_04_msk_and_gmsk.md#604-msk-and-gmsk-constant-envelope) | MSK and GMSK: the modulations with a constant envelope, which is why GSM and Bluetooth use them | (learnSDR skipped this) |
| [6.05](6_05_the_channel.md#605-the-channel-sounding-it-and-equalizing-it) | the channel: sounding it, and equalizing it | |
| [6.06](6_06_spread_spectrum.md#606-spread-spectrum-the-gps-way) | spread spectrum, the GPS way, and why CDMA lost | [21](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson21.md), [22](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson22.md), [23](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson23.md) |
| [6.07](6_07_ofdm.md#607-ofdm-the-triumph-of-physics-over-math) | OFDM, which won | (never got made) |
| [6.08](6_08_shannons_limit.md#608-shannons-limit-and-how-far-from-it-you-are) | [Shannon's limit](https://en.wikipedia.org/wiki/Shannon%E2%80%93Hartley_theorem), and how far from it you are | |
| [6.09](6_09_error_correcting_codes.md#609-error-correcting-codes) | error-correcting codes: the way to get closer | |
| [6.10](6_10_chirps_and_lora.md#610-chirps-zadoffchu-and-lora-ranging-and-radar-on-a-cable) | chirps, Zadoff–Chu sequences and LoRa: ranging, and radar on a cable | [8b](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson08b.md), [23](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson23.md) |
| [6.11](6_11_the_modem_in_the_fpga.md#611-the-modem-in-the-fpga) | the modem in the FPGA: everything [6.02](6_02_psk_and_qpsk.md#602-psk-and-qpsk-finding-the-clock-and-the-carrier) did, in integers and shifts, bit-exact against its model | [18](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson18.md), [19](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson19.md), [20](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson20.md) |
| [6.12](6_12_on_the_air.md#612-on-the-air-whispers-and-how-far-they-carry) | on the air: an FT8-style text message, forty thousand times too fast on the cable and at real speed through 6.78 MHz, and the antenna ladder from minigrabber leads to a dipole | [24](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson24.md) |
| [6.13](6_13_more_ideas.md#613-more-ideas-and-a-radar-chapter) | more ideas, and a radar chapter (Chapter 8, one day) | [8b](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson08b.md) |

Earlier chapters already did learnSDR's other topics: complex numbers and
what an SDR multiplies by (the lock-in, [1.08](1_08_lockin.md#108-a-lock-in-amplifier); lessons
[3a](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson03a.md), [3b](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson03b.md), [4](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson04.md)), sampling and [aliasing](https://en.wikipedia.org/wiki/Aliasing) ([1.06](1_06_fast_capture.md#106-fast-captures); lesson [6](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson06.md)), the FFT and
windows ([1.09](1_09_spectrum_analyzer.md#109-a-spectrum-analyzer); lesson [7](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson07.md)), two clocks that disagree ([5.01](5_01_two_clocks.md#501-two-clocks); lesson [9](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson09.md)), FSK
([5.05](5_05_fsk_modem.md#505-a-modem); lesson [24](https://github.com/gallicchio/learnSDR/blob/main/lesson24_FSKhardware.grc)) and noise ([5.06](5_06_modem_and_noise.md#506-the-modem-against-noise); lesson [32](https://github.com/gallicchio/learnSDR/blob/main/lesson32b_noiseRXsim.grc)). On-off keying (lessons
[5](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson05.md), [10](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson10.md), [11](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson11.md)) is BPSK with one of its two points at zero; it needs no section.

## The story, in one paragraph

Here is the chapter's opinion, so that you know where it's going. The first
half is about *waveforms*: how to put bits on a sine wave ([6.01](6_01_eye_diagrams.md#601-eye-diagrams-and-pulse-shaping)–[6.04](6_04_msk_and_gmsk.md#604-msk-and-gmsk-constant-envelope)) and
how a receiver recovers them without being told the clock or the carrier
([6.02](6_02_psk_and_qpsk.md#602-psk-and-qpsk-finding-the-clock-and-the-carrier)). The second half is about the *channel*, and it's a story with a
winner. A cable, or the air between two antennas, is a linear system: it
delays, attenuates and echoes, and the echoes make some frequencies
disappear ([6.05](6_05_the_channel.md#605-the-channel-sounding-it-and-equalizing-it)). The 1990s' answer was to spread every user's signal over
the whole band with a clever code and sort the echoes out afterwards (CDMA,
[6.06](6_06_spread_spectrum.md#606-spread-spectrum-the-gps-way)): mathematically beautiful, and it ran 3G phones. It lost. The
channels got wider, the echoes got messier, and the untangling grew with the square of the bandwidth (more chips a second, each needing more taps), while an FFT grows only as N log N. The answer that runs 4G, 5G and Wi-Fi is OFDM ([6.07](6_07_ofdm.md#607-ofdm-the-triumph-of-physics-over-math)): split
the band into many narrow pieces, each of which the channel barely changes,
and fix each with one complex multiplication. The basis functions that do
this are sines and cosines, because sines and cosines are the eigenfunctions
of every linear time-invariant system. That's not a theorem of
communications; it's the physics of the channel, and a physicist could have
told you. Shannon says how many bits a channel can carry ([6.08](6_08_shannons_limit.md#608-shannons-limit-and-how-far-from-it-you-are)), codes get
you there ([6.09](6_09_error_correcting_codes.md#609-error-correcting-codes)), chirps and LoRa show what a wideband signal can do besides
carry bits ([6.10](6_10_chirps_and_lora.md#610-chirps-zadoffchu-and-lora-ranging-and-radar-on-a-cable)), and [6.11](6_11_the_modem_in_the_fpga.md#611-the-modem-in-the-fpga) puts the whole receiver into the FPGA.

## Why a cable, and 6.25 MHz

The board can't reach 915 MHz by itself: its DAC makes 50 million samples a
second and its ADC takes 25 million, so everything here happens below
12.5 MHz. A real radio does the same signal processing at a frequency like
this, and moves the result up to the radio band and back down with a
*mixer* (a multiplier, as in the lock-in) and a *local oscillator*. Moving a
signal in frequency doesn't change its shape, so the algorithms in this
chapter don't care whether a cable or 3 m of air and two mixers sit between
the DAC and the ADC.

The carrier is 6.25 MHz: a quarter of the ADC's sampling rate, in the
middle of its band, away from the converters' offsets near 0 Hz and 12.5 MHz, where the DAC's image (at 50 MHz minus the signal, which the ADC folds back onto it) is strongest. At a quarter of the sampling rate, mixing down
is multiplying by 1, −*j*, −1, *j*, over and over.

## What runs where

The FPGA's job is small: [5.01](5_01_two_clocks.md#501-two-clocks)'s `awgcap.sv` plays a 16384-sample waveform
from the laptop over and over at 50 MS/s, and records 16384 samples at
25 MS/s. Everything else, until [6.11](6_11_the_modem_in_the_fpga.md#611-the-modem-in-the-fpga), is Python *on the laptop*, in
`src/comms/`, talking to the board over the serial port, so every command
in this chapter starts with the laptop's `$` ([0.01](0_01_how_to_use_this_tutorial.md#where-does-this-run) has the whole table of
prompts):

```console
$ cd src/twoboard && make load-awgcap        # one board, DAC OUT cabled to ADC IN
$ cd ../comms
$ python3 psk.py                             # finds the board
$ python3 psk.py /dev/ttyUSB0 /dev/ttyUSB1   # two boards: A plays, B records
$ python3 psk.py --sim                       # no board: channel.py's model of one
```

![What runs where: the laptop (its shell's dollar prompt, CPython with numpy, litex_term, litex_server), the board under bare metal or LiteX (no prompt for awgcap.sv, the BIOS's litex prompt, the firmware's adda prompt), the same board under Linux (root's hash prompt, MicroPython's three chevrons), and a second board (B hash), with the USB and coax cables between them](img/comms_d_where.png)

The model, `channel.py`, is the loopback of [1.07](1_07_closing_the_loop.md#107-closing-the-loop-the-dac-talks-to-the-adc) in a function: 8-bit codes
held for 20 ns each, a gentle low-pass, the measured delay, ADC =
0.776 × DAC + 27.5, noise, and 8-bit codes again. It's close to the cable, but
smoother: the real cable rings after a step, and its gain wanders by ±8% across
the band. Every figure in this chapter says in its corner whether it is
measured or simulated.

![Left: a DAC step through 1 m of cable, measured in 1.07 and modelled: the same delay, but the model doesn't ring. Right: the gain against frequency, measured by [6.07](6_07_ofdm.md#607-ofdm-the-triumph-of-physics-over-math)'s sounding and modelled: the model is flatter than the cable by about 8 percent](img/comms_channel.png)

<details>
<summary>The whole file: <code>channel.py</code></summary>

<!-- file: src/comms/channel.py -->
```python
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
```

</details>

## Hardware for this chapter

Everything in [6.01](6_01_eye_diagrams.md#601-eye-diagrams-and-pulse-shaping)–[6.11](6_11_the_modem_in_the_fpga.md#611-the-modem-in-the-fpga) runs on one board looped back through its cable,
and that is how each was tested, except where [Appendix C](C_how_it_was_tested.md#appendix-c-how-this-tutorial-was-tested) says otherwise. Each of these makes a section more
convincing, in the order you'd want them:

| hardware | what it adds | sections |
| --- | --- | --- |
| **a second board** (with its own ADC/DAC module) | two crystals that disagree: the clock and carrier offsets that [6.02](6_02_psk_and_qpsk.md#602-psk-and-qpsk-finding-the-clock-and-the-carrier)'s loops exist for become real instead of imposed, and [6.11](6_11_the_modem_in_the_fpga.md#611-the-modem-in-the-fpga)'s modem talks to someone else | [6.02](6_02_psk_and_qpsk.md#602-psk-and-qpsk-finding-the-clock-and-the-carrier), [6.03](6_03_qam.md#603-qam-more-bits-per-symbol), [6.04](6_04_msk_and_gmsk.md#604-msk-and-gmsk-constant-envelope), [6.11](6_11_the_modem_in_the_fpga.md#611-the-modem-in-the-fpga) |
| **an SMA T and an open-ended stub** (a few metres of coax with nothing on the far end) | a real echo: the stub reflects the signal back late, which puts notches in the channel, closes the eye, and gives the equalizer and the [cyclic prefix](https://en.wikipedia.org/wiki/Cyclic_prefix) a job | [6.05](6_05_the_channel.md#605-the-channel-sounding-it-and-equalizing-it), [6.07](6_07_ofdm.md#607-ofdm-the-triumph-of-physics-over-math), [6.10](6_10_chirps_and_lora.md#610-chirps-zadoffchu-and-lora-ranging-and-radar-on-a-cable) |
| **a longer cable**, 10 m or more | more loss and more dispersion: the matched filter and the equalizer earn their keep | [6.01](6_01_eye_diagrams.md#601-eye-diagrams-and-pulse-shaping), [6.05](6_05_the_channel.md#605-the-channel-sounding-it-and-equalizing-it) |
| **SMA attenuators** (10, 20 dB) | real signal-to-noise ratios instead of noise added in software | [6.02](6_02_psk_and_qpsk.md#602-psk-and-qpsk-finding-the-clock-and-the-carrier), [6.06](6_06_spread_spectrum.md#606-spread-spectrum-the-gps-way), [6.09](6_09_error_correcting_codes.md#609-error-correcting-codes), [6.10](6_10_chirps_and_lora.md#610-chirps-zadoffchu-and-lora-ranging-and-radar-on-a-cable) |
| **a speaker and a microphone** (the laptop's) | hearing a modulation at 1200 baud, as a 1980s modem did it | [6.04](6_04_msk_and_gmsk.md#604-msk-and-gmsk-constant-envelope) |
| **an RF front end** for 915 MHz or 2.4 GHz | the air; see below | this page, [6.13](6_13_more_ideas.md#613-more-ideas-and-a-radar-chapter) |
| **minigrabber test leads, two tuned loops, an HF amplifier** | the air, one rung at a time: how far a text message carries | [6.12](6_12_on_the_air.md#612-on-the-air-whispers-and-how-far-they-carry) |
| **two 40 kHz ultrasonic transducers** ([4.06](4_06_speed_of_sound.md#406-the-speed-of-sound-at-40-khz)) | a tabletop radar: Doppler, FMCW, synthetic aperture | [6.13](6_13_more_ideas.md#613-more-ideas-and-a-radar-chapter) |

## Going on the air

To make this a radio, put a frequency converter at each end: a mixer with a
local oscillator, a filter for the band, an amplifier, an antenna. The parts
are cheap and common, because they're what radio amateurs and drone
builders use. None of them was tried with this board, so treat this as a
shopping list to check, not a recipe. Prices are what the linked pages said
in October 2026:

| part | for | example, and about what it costs |
| --- | --- | --- |
| local oscillator | the carrier you mix with | an **[ADF4351](https://www.analog.com/en/products/adf4351.html)** synthesizer board, 35 MHz–4.4 GHz, set over SPI (which the FPGA could do): [$27 on eBay](https://www.ebay.com/itm/35M-4-4GHz-PLL-RF-Signal-Source-Frequency-Synthesizer-ADF4351-Development-Board-/322520746831), [$44 at Newegg](https://www.newegg.com/p/2S7-09SH-00151). For bands below 200 MHz, Adafruit's [Si5351A breakout](https://www.adafruit.com/product/2045), $8 |
| mixer | moving 6.25 MHz up to the band and back down | a Mini-Circuits connectorized double-balanced mixer: [ZX05-43MH+](https://www.minicircuits.com/WebStore/dashboard.html?model=ZX05-43MH%2B) (824–4200 MHz, +13 dBm LO), about $47 (its sibling [ZX05-43H-S+ is $46.95 at Digi-Key](https://www.digikey.com/en/products/detail/mini-circuits/ZX05-43H-S/21727733)); for HF and VHF, the [ZX05-1-S+](https://www.digikey.bg/en/products/detail/mini-circuits/ZX05-1-S/25963299), 0.5–500 MHz |
| [low-noise amplifier](https://en.wikipedia.org/wiki/Low-noise_amplifier) | the receiver's first stage | an **SPF5189Z** module, 50 MHz–4 GHz, 0.6 dB noise figure: [about $5–10](https://www.passion-radio.com/sdr-accessory/lna-spf-833.html); Nooelec's [LaNA](https://www.ebay.com/str/NooElec), $35; or Mini-Circuits' [ZX60-P103LN+](https://www.minicircuits.com/WebStore/dashboard.html?model=ZX60-P103LN%2B), 50–3000 MHz, 0.5 dB, $119 |
| transmit amplifier | a few milliwatts into the antenna | the same SPF5189Z module (it delivers about +10 dBm); for [6.04](6_04_msk_and_gmsk.md#604-msk-and-gmsk-constant-envelope)'s experiment, drive it into saturation on purpose |
| band filter | keeping only your band at both ends | Mini-Circuits [VBFZ-925-S+](https://www.minicircuits.com/WebStore/dashboard.html?model=VBFZ-925-S%2B), 800–1050 MHz, $54; a [915 MHz SAW filter with SMA](https://vxb.com/products/915mhz-bandpass-receiver-filter-with-sma-interface), 902–928 MHz, about $62; or an [Abracon AFS915](https://ie.rs-online.com/web/p/signal-filters/2505215) SAW chip, €2, if you'll solder it |
| antennas | the air | 915 MHz whips come with LoRa modules for a few dollars; 2.4 GHz "rubber ducks" from Wi-Fi gear (watch out: many are RP-SMA, not SMA) |
| test gear | checking the transmitter, and a known-good receiver | an [RTL-SDR Blog V4](https://www.rtl-sdr.com/product/rtl-sdr-blog-v4-r828d-rtl2832u-1ppm-tcxo-sma-software-defined-radio-with-dipole-antenna/) dongle, $30–55 (learnSDR's receiver); an [ADALM-PLUTO](https://www.analog.com/en/resources/evaluation-hardware-and-software/evaluation-boards-kits/adalm-pluto.html), about $230, is learnSDR's transmitter and receives too; SMA attenuators and a 50 Ω load |
| connectors | | an SMA T (a proper one is [$116 from Pasternack](https://www.pasternack.com/sma-female-female-female-tee-adapter-pe9246-p.aspx); the $5 kind from Amazon or eBay is fine at these frequencies), RG-316 SMA cables ($3–8 each) |

One catch: a mixer makes *both* the sum and the difference, LO ± 6.25 MHz,
only 12.5 MHz apart. A filter for the whole 902–928 MHz band passes both. Put
the LO so that one of them falls outside the band and gets filtered away, or
use a higher intermediate frequency, or an *IQ mixer*, which cancels the
unwanted one. The receiver has the mirror of the same problem: signals at
LO + 6.25 MHz and LO − 6.25 MHz both land on the same 6.25 MHz, so it
needs the same care.

> [!WARNING]
> **Transmitting.** In the US, 902–928 MHz and 2400–2483.5 MHz are ISM bands
> that FCC Part 15 lets anyone use at low power, within its limits;
> 902–928 MHz is also a radio-amateur band, for which you need a licence.
> Other countries' rules differ. Start with cables and attenuators between
> the two ends, and keep the power tiny.
