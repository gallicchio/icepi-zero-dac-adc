<!-- nav -->
[← 6.05 The channel: sounding it, and equalizing it](6_05_the_channel.md#605-the-channel-sounding-it-and-equalizing-it) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)** &emsp;&emsp;&emsp; [6.07 OFDM: the triumph of physics over math →](6_07_ofdm.md#607-ofdm-the-triumph-of-physics-over-math)

# 6.06 Spread spectrum, the GPS way

![Measured, one board looped back: two users share 6.25 MHz under noise 10 dB stronger than both; correlating with each GPS code at every delay finds each user's peak, PRN 1 at 0.64 chips and PRN 2 at 301.06 chips, while PRN 3, not sent, finds nothing; each peak is a triangle two chips wide; and each user's bits come out again, 0 errors, with the noise](img/comms_cdma.png)

Thirty-odd GPS satellites all transmit at the same frequency, 1575.42 MHz, at
the same time, and their signals arrive 20 dB *below* the noise. A receiver
pulls each one out, and measures its delay to a few nanoseconds. The trick is
**spread spectrum**: each satellite multiplies its slow data (50 bits a
second) by its own fast pseudo-random code, 1023 *chips* that repeat every
millisecond. The code spreads the signal over a band twenty thousand times wider
than the data needs (43 dB; the two "satellites" below manage 33 times,
15 dB). A receiver that multiplies by the same code,
lined up, un-spreads that one satellite, and turns everything else, other
satellites and noise alike, into a weak hiss:

![Computed: spreading as multiplication: slow data bits times a fast 31-chip code gives a wide signal 15 dB lower in spectral density; multiplying the received signal by the same code again gives the bits and their narrow spectrum back; multiplying by another user's code leaves only wide hiss. Spectra beside each row on one dB scale](img/comms_d_cdma.png)

2G and 3G phones (IS-95, UMTS), Wi-Fi's
slowest rates and Bluetooth's hopping are cousins; the end of this page says
why the phones gave it up.

The codes are *[Gold codes](https://en.wikipedia.org/wiki/Gold_code)*, the *[C/A code](https://en.wikipedia.org/wiki/GPS_signals#Coarse/Acquisition_code)*s (learnSDR's lessons [21](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson21.md) and [22](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson22.md) build them in GNU Radio): GPS's G1 register ([1.07](1_07_closing_the_loop.md#107-closing-the-loop-the-dac-talks-to-the-adc)) XOR a
second register, G2, tapped at two stages that are different for each
satellite, its *PRN* number. Any two of them barely correlate at any delay,
and each correlates with itself only when lined up.

## Two satellites in one cable

`cdma.py` makes two "satellites", PRN 1 and PRN 2, on one 6.25 MHz carrier.
Each sends 31 bits per loop (the first 8 are GPS's own preamble, 10001011),
each bit 33 chips of its code: 3.12 million chips a second, a spreading gain
of 33, 15.2 dB. PRN 2's code starts 300.4 chips later, as if its satellite
were farther away.

The receiver does what a GPS receiver does to *acquire* a satellite: mix down
(the lock-in's cos and −sin again), then correlate with the code at every
possible delay at once, with FFTs: *c*[*d*] = IFFT(FFT(*z*) · FFT(code)<sup>*</sup>),
all 8192 delays in one line. The data flips the code's sign every 33
chips, so it correlates bit by bit and adds up the powers. At the right delay
there's a peak. Then, at that delay, each bit's correlation is the bit times
the carrier's phase; squaring removes the bits (as learnSDR's [lesson 12](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson12.md)
suggests) and leaves the phase, and the preamble settles which way round:

<details>
<summary>The whole file: <code>cdma.py</code></summary>

<!-- file: src/comms/cdma.py -->
```python
#!/usr/bin/env python3
"""Spread spectrum the GPS way: two data streams on one carrier at once, pulled apart by code.

    python3 cdma.py                     # one board looped back (finds its port)
    python3 cdma.py PORT_A PORT_B       # board A plays, board B records
    python3 cdma.py --sim               # no board: channel.py's model
    python3 cdma.py --snr -15           # bury both signals 15 dB under noise (added at
                                        #   the transmitter, over the DAC's whole 25 MHz)
    python3 cdma.py --power2 15         # make user 2 15 dB louder than user 1 ("near-far")
    python3 cdma.py -o cdma.npz --no-plot

The board runs awgcap.sv (5.01).  Two "satellites" share one 6.25 MHz carrier and the
same instants.  Each multiplies its own data by its own GPS C/A code, 1023 chips long:

    C/A code = G1 xor (two stages of G2, which pair being the satellite's "PRN")

with G1 = x^10 + x^3 + 1 (1.07's register) and G2 = x^10 + x^9 + x^8 + x^6 + x^3 + x^2 + 1,
both started from all ones (IS-GPS-200).  Here PRN 1 and PRN 2.

  chips   1023 per loop: 3.122 Mchip/s, square chips as GPS sends (GPS: 1.023 Mchip/s)
  bits    33 chips each, 31 per loop (GPS: 20 whole codes per bit, 50 bit/s).  Each
          loop's first 8 bits are GPS's own preamble, 10001011; then 23 data bits
  delay   user 2's code starts 300.4 chips after user 1's, as if it were farther away

The receiver mixes down (cos and -sin, as the lock-in) and, for each PRN, finds the
code's delay by correlating with it at every lag at once with FFTs, as a GPS receiver
"acquires" a satellite (learnSDR lesson 23).  The data flip the code's sign every 33
chips, so it correlates bit by bit and adds up the bits' POWERS.  At the delay
found, each bit's correlation is that bit, times the carrier's phase; squaring
removes the data and leaves twice the phase (learnSDR lesson 12's homework), and the
preamble settles the leftover 180 degrees.
"""
import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import channel                                      # noqa: E402
from psk import g1, find_port                      # noqa: E402
from eye import square                             # noqa: E402

N, L = 16384, 8192                  # DAC samples per loop; ADC samples per loop
FS_DAC, FS_ADC = 50e6, 25e6
F_C = 6.25e6
CHIPS = 1023                        # one whole C/A code per loop
PER_BIT = 33                        # chips per data bit: 31 bits per loop
NBIT = CHIPS // PER_BIT
PREAMBLE = np.array([1, 0, 0, 0, 1, 0, 1, 1])     # GPS's telemetry-word preamble
# IS-GPS-200, Table 3-I: which two G2 stages each PRN XORs together.
G2_TAPS = {1: (2, 6), 2: (3, 7), 3: (4, 8), 4: (5, 9), 5: (1, 9), 6: (2, 10), 7: (1, 8),
           8: (2, 9), 9: (3, 10), 10: (2, 3), 11: (3, 4), 12: (5, 6), 13: (6, 7), 14: (7, 8),
           15: (8, 9), 16: (9, 10), 17: (1, 4), 18: (2, 5), 19: (3, 6), 20: (4, 7), 21: (5, 8),
           22: (6, 9), 23: (1, 3), 24: (4, 6), 25: (5, 7), 26: (6, 8), 27: (7, 9), 28: (8, 10),
           29: (1, 6), 30: (2, 7), 31: (3, 8), 32: (4, 9)}


def ca_code(prn):
    """The 1023 chips (0/1) of GPS satellite `prn`'s C/A code."""
    g1r, g2r = [1] * 10, [1] * 10                   # element 0 is stage 1
    s1, s2 = G2_TAPS[prn]
    out = []
    for _ in range(CHIPS):
        # ######################################################################
        # ##  KEY LINE: a Gold code.  G1's last stage, XOR two stages of G2:
        # ##  choosing a different pair delays G2's sequence by a different
        # ##  amount, and gives each satellite its own code.
        # ######################################################################
        out.append(g1r[9] ^ g2r[s1 - 1] ^ g2r[s2 - 1])
        f1 = g1r[2] ^ g1r[9]
        f2 = g2r[1] ^ g2r[2] ^ g2r[5] ^ g2r[7] ^ g2r[8] ^ g2r[9]
        g1r, g2r = [f1] + g1r[:9], [f2] + g2r[:9]
    return np.array(out)


def user_bits(start):
    """One loop of a user's bits: the preamble, then 23 bits of G1 from `start`."""
    return np.concatenate([PREAMBLE, g1(NBIT - len(PREAMBLE), start=start)])


def transmit(users, snr=None, rng=None):
    """users: list of (prn, bits, delay in chips, amplitude, carrier phase).  Returns
    16384 DAC codes."""
    u = np.arange(N)
    s = np.zeros(N)
    for prn, bits, delay, amp, phase in users:
        chips = 1 - 2 * ca_code(prn)                         # 0, 1 -> +1, -1
        data = np.repeat(1 - 2 * bits, PER_BIT)              # each bit lasts 33 chips
        # ######################################################################
        # ##  KEY LINE: spreading.  Multiply each data bit by 33 chips of the
        # ##  code: the bit's spectrum spreads 33 times wider, and its power
        # ##  per hertz drops 33 times (15 dB).
        # ######################################################################
        baseband = square(chips * data, shift=delay * N / CHIPS)
        s += amp * baseband * np.cos(2 * np.pi * F_C * u / FS_DAC + phase)
    if snr is not None:
        noise = np.random.default_rng(rng).standard_normal(N)
        s += noise * np.std(s) * 10**(-snr / 20)
    return 128 + 100 * s / np.abs(s).max()


def replicas(prn):
    """The code as the ADC would see it in one loop, cut into one piece per data bit:
    piece b is the code during bit b and zero elsewhere.  Shape (31, 8192)."""
    n = np.arange(L)
    k = np.floor(n * CHIPS / L).astype(int)                  # which chip sample n falls in
    c = (1 - 2 * ca_code(prn))[k].astype(float)
    pieces = np.zeros((NBIT, L))
    for b in range(NBIT):
        sel = (k // PER_BIT) == b
        pieces[b, sel] = c[sel]
    return pieces


def acquire(z, prn):
    """Correlate one loop of mixed-down samples z with PRN's code at every delay.
    Returns (power vs delay in samples, the per-bit correlations vs delay)."""
    Z = np.fft.fft(z)
    # ##########################################################################
    # ##  KEY LINE: correlation at all 8192 delays at once: multiply the
    # ##  spectrum by the conjugate of the code's, transform back.  One
    # ##  correlation per data bit, since the data flip the code's sign.
    # ##########################################################################
    C = np.fft.ifft(Z[None, :] * np.conj(np.fft.fft(replicas(prn), axis=1)), axis=1)
    return np.sum(np.abs(C)**2, axis=0), C


def despread(C, lag):
    """The bits at delay `lag`: each bit's correlation, the carrier phase from their
    squares, and the bits."""
    d = C[:, lag]
    # ##########################################################################
    # ##  KEY LINE: square away the data.  d = +-A e^(j phi); d^2 = A^2 e^(2j phi)
    # ##  whatever the bit, so half the angle of sum(d^2) is the carrier phase
    # ##  (up to 180 degrees, which the preamble settles).
    # ##########################################################################
    phi = 0.5 * np.angle(np.sum(d**2))
    soft = np.real(d * np.exp(-1j * phi))
    bits = (soft < 0).astype(int)
    if np.sum(bits[:len(PREAMBLE)] != PREAMBLE) > len(PREAMBLE) // 2:   # upside down
        soft, bits, phi = -soft, 1 - bits, phi + np.pi
    return soft, bits, phi


def receive(rec, prns):
    """For each PRN: delay (chips), the correlation-power curve, bits, soft bits."""
    z = 2 * (rec[:L] - rec.mean()) * np.exp(-2j * np.pi * F_C * np.arange(L) / FS_ADC)
    out = {}
    for prn in prns:
        P, C = acquire(z, prn)
        lag = int(np.argmax(P))
        # sub-sample delay: a parabola through the peak and its neighbours
        a, b, c = P[lag - 1], P[lag], P[(lag + 1) % L]
        frac = 0.5 * (a - c) / (a - 2 * b + c)
        soft, bits, phi = despread(C, lag)
        # how far the peak stands above everything else (in dB)
        others = np.delete(P, np.arange(lag - 16, lag + 17) % L)
        out[prn] = dict(P=P, lag=lag, delay=(lag + frac) * CHIPS / L, soft=soft, bits=bits,
                        phi=phi, peak_db=10 * np.log10(P[lag] / np.mean(others)))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ports", nargs="*", help="one port: looped back; two: A plays, B records")
    ap.add_argument("--sim", action="store_true", help="use channel.py's model, not a board")
    ap.add_argument("--snr", type=float, help="add noise at the transmitter: signal/noise in dB over 0-25 MHz")
    ap.add_argument("--power2", type=float, default=0.0, help="user 2's power relative to user 1's, dB")
    ap.add_argument("--delay2", type=float, default=300.4, help="user 2's code delay, chips")
    ap.add_argument("--records", type=int, default=1)
    ap.add_argument("-o", "--out", help="save the results (.npz)")
    ap.add_argument("--no-plot", action="store_true")
    args = ap.parse_args()
    if args.sim:
        rng = np.random.default_rng(1)
        state = {}
        def play(w):
            state["w"] = w
        def record():
            return channel.channel(state["w"], rng=rng)
    else:
        sys.path.insert(0, os.path.join(HERE, "..", "twoboard"))
        import awgcap
        ports = args.ports or [find_port()]
        play = lambda w: awgcap.upload(ports[0], w)
        record = lambda: awgcap.record(ports[-1])
    users = [(1, user_bits(0), 0.0, 1.0, 0.3),
             (2, user_bits(500), args.delay2, 10**(args.power2 / 20), 2.0)]
    play(transmit(users, args.snr, rng=7))
    prns = (1, 2, 3)                                         # PRN 3 isn't on the air
    errs = {1: 0, 2: 0}; nbits = 0
    for i in range(args.records):
        r = receive(record(), prns)
        for prn, bits, *_ in users:
            errs[prn] += int(np.sum(r[prn]["bits"][len(PREAMBLE):] != bits[len(PREAMBLE):]))
        nbits += NBIT - len(PREAMBLE)
    print("chips at %.4f Mchip/s, %d bits per loop per user at %.1f kbit/s; spreading gain %.1f dB"
          % (CHIPS * FS_DAC / N / 1e6, NBIT, NBIT * FS_DAC / N / 1e3, 10 * np.log10(PER_BIT)))
    for prn in prns:
        x = r[prn]
        sent = {1: 0.0, 2: args.delay2}.get(prn)
        print("PRN %d: peak %5.1f dB above the rest, at %8.2f chips%s" %
              (prn, x["peak_db"], x["delay"], "" if sent is None else
               ";  bit errors %d of %d" % (errs[prn], nbits)))
    print("(user 2's delay minus user 1's: sent %.2f chips, measured %.2f)"
          % (args.delay2, r[2]["delay"] - r[1]["delay"]))
    if args.out:
        np.savez(args.out, rec=record(), **{"P%d" % p: r[p]["P"] for p in prns},
                 **{"soft%d" % p: r[p]["soft"] for p in prns},
                 delays=np.array([r[p]["delay"] for p in prns]), peak_db=np.array([r[p]["peak_db"] for p in prns]),
                 errs=np.array([errs[1], errs[2]]), nbits=nbits, snr=np.nan if args.snr is None else args.snr,
                 power2=args.power2, delay2=args.delay2)
    if not args.no_plot:
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 3, figsize=(13, 4))
        chips = np.arange(L) * CHIPS / L
        for prn in prns:
            ax[0].plot(chips, 10 * np.log10(r[prn]["P"] / r[prn]["P"].max() + 1e-12) if prn != 3 else
                       10 * np.log10(r[3]["P"] / r[1]["P"].max()), lw=0.6, label="PRN %d" % prn)
        ax[0].set_xlabel("delay (chips)"); ax[0].set_ylabel("correlation power (dB)")
        ax[0].set_title("acquisition: every delay at once"); ax[0].legend(); ax[0].grid(True)
        for prn in (1, 2):
            lag = r[prn]["lag"]; w = np.arange(lag - 24, lag + 25) % L
            ax[1].plot((np.arange(-24, 25)) * CHIPS / L, np.sqrt(r[prn]["P"][w] / r[prn]["P"][lag]), ".-",
                       label="PRN %d" % prn)
        ax[1].set_xlabel("delay from the peak (chips)"); ax[1].set_ylabel("correlation (amplitude)")
        ax[1].set_title("the peak: a triangle two chips wide"); ax[1].legend(); ax[1].grid(True)
        for prn in (1, 2):
            s = r[prn]["soft"]
            ax[2].plot(np.arange(NBIT), s / np.abs(s).mean(), "o", label="PRN %d" % prn)
        ax[2].set_xlabel("bit"); ax[2].set_ylabel("despread bit (soft)"); ax[2].grid(True)
        ax[2].set_title("each user's bits, pulled apart"); ax[2].legend()
        fig.tight_layout()
        plt.show()


if __name__ == "__main__":
    main()
```

</details>

```console
$ cd src/comms && python3 cdma.py        # awgcap.sv loaded, DAC OUT cabled to ADC IN
chips at 3.1219 Mchip/s, 31 bits per loop per user at 94.6 kbit/s; spreading gain 15.2 dB
PRN 1: peak  13.7 dB above the rest, at     0.64 chips;  bit errors 0 of 23
PRN 2: peak  13.8 dB above the rest, at   301.06 chips;  bit errors 0 of 23
PRN 3: peak   2.8 dB above the rest, at   577.69 chips
(user 2's delay minus user 1's: sent 300.40 chips, measured 300.42)
```

PRN 3, which nobody sent, finds only the largest of its noise bumps. The two
real ones each find their own signal, and the difference of their delays is
right to 0.02 chip, 6 ns: that's how GPS measures distance. With noise
10 dB stronger than both users together, added at the transmitter (`--snr
-10`), the peaks drop to 8 dB but both users' bits still come out with no
errors.

Two numbers to keep apart. The 15.2 dB is chips per bit, and it is also
about the height of each acquisition peak above its floor: a bit's 33-chip
correlation leaves every other delay at 1/33 of the peak's power. The Gold
codes' famous −24 dB (65/1023) never shows up here, because no bit holds a
whole code; GPS, with 20 codes per bit, gets both. And `--snr -10` is the
signal against noise spread over the DAC's whole 0–25 MHz; after
de-spreading, each bit stands about 10 dB above its noise (the scatter of
the dots in the last panel), not 15.2 − 10 = 5 dB.

## Why CDMA lost

Spread spectrum did more than GPS. From 1995 (Qualcomm's IS-95) through 3G
(CDMA2000, and UMTS's wideband CDMA at 3.84 million chips a second) every
phone call in a cell was one of these users: every handset on the same
1.25 MHz (IS-95) or 5 MHz (UMTS), each with its own code, pulled apart by correlation just as PRN 1 and
PRN 2 were above. It was beautiful. Users were separated by mathematics
instead of by frequency or time slots; a cell got quieter, not fuller, when
users left; and the codes resolved the echoes of the city into separate
fingers that a *rake receiver* could add back together. (The near–far
problem of the "Try this" below was real: every handset's power was
adjusted 800 times a second so that none of them shouted.)

Then the channels got wider, and the beauty didn't scale. At 3.84 Mchip/s
an echo 0.26 µs late, 80 m of extra path, is a separate finger; at ten times
the chip rate it's ten fingers, each needing its own tracking loop, and the
chips themselves start to smear into each other, so the receiver needs a
chip-rate equalizer on top of the rake. Every user's code is only
*approximately* orthogonal to every other's once they arrive at different
delays (the [cross-correlation](https://en.wikipedia.org/wiki/Cross-correlation) is about 1/√N, not zero), so the cell's
capacity was limited by its own users' interference, and the whole design
got harder, not easier, with each generation. 4G threw it out. LTE, 5G
and Wi-Fi all use the next section's ([6.07](6_07_ofdm.md#607-ofdm-the-triumph-of-physics-over-math)'s) OFDM, where the echoes are undone by one complex
division per subcarrier, with no fingers at all, and the channels have grown
from 5 MHz to hundreds of MHz without anyone minding. The GPS way survives where
it's genuinely the right tool: many weak transmitters that must share one
frequency and be *ranged* (GPS itself), hopping and hiding (Bluetooth,
military links), and chirps that go very far on very little power
([6.10](6_10_chirps_and_lora.md#610-chirps-zadoffchu-and-lora-ranging-and-radar-on-a-cable)'s LoRa).

<details>
<summary><b>Detail:</b> why the peak is a triangle two chips wide</summary>

A chip is a square pulse. Slide a code past itself and the overlap of each
chip with itself falls linearly to zero over one chip on either side: the
autocorrelation of one chip is a triangle two chips wide, and an [m-sequence](https://en.wikipedia.org/wiki/Maximum_length_sequence)'s
other chips add up to almost nothing ([1.07](1_07_closing_the_loop.md#107-closing-the-loop-the-dac-talks-to-the-adc)). A GPS receiver tracks the peak
with an *early* and a *late* correlator, half a chip either side: when the
two are equal, it's centred, and the slope of the triangle's sides turns a
timing error into a difference it can steer by. That's a delay-locked loop,
the timing loop of [6.02](6_02_psk_and_qpsk.md#602-psk-and-qpsk-finding-the-clock-and-the-carrier) in another form.

</details>

**Try this:**

- The *near-far problem*: make one user much louder (`--power2 15`). At what
  ratio does the quiet one disappear under the loud one's leftover
  correlation? (In simulation: fine at +12 dB, lost at +15.) Mobile phones
  control every handset's power for exactly this reason.
- Bury both users deeper (`--snr -15`, `-20`): where does acquisition fail?
  Then make each bit longer (fewer bits per loop, more chips per bit) and
  watch the spreading gain buy it back.
- Two boards: `python3 cdma.py /dev/ttyUSB0 /dev/ttyUSB1`. The delays now
  include where B's record started in A's loop, but their *difference* is
  still 300.4 chips.
- learnSDR's [lesson 23](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson23.md) receives real GPS with an RTL-SDR at 2.046 MS/s,
  exactly two samples per chip. With the RF parts of [6.00](6_00_digital_communications.md#600-digital-communications-hardware-defined-radio) and a GPS
  antenna, this board's ADC could take the same samples at an IF; `cdma.py`'s
  acquisition is already the right algorithm, with a search over Doppler
  added.

<!-- author -->
<sub>Jason Gallicchio, jason@hmc.edu, Harvey Mudd College</sub>
