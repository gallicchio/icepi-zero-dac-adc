#!/usr/bin/env python3
"""qpsk_modem.sv in Python, integer for integer: the DQPSK modem that runs inside the FPGA.

    python3 modem_fpga_model.py --sim                 # 300 random bytes through the model,
                                                      #   channel.py's cable, loops' states
    python3 modem_fpga_model.py --sim --ppm 2000      # the transmitter's crystal 2000 ppm fast:
                                                      #   carrier +12.5 kHz, symbols +2000 ppm
    python3 modem_fpga_model.py --sim --ppm 2000 --cfo -9500   # ... and the carrier moved back
    python3 modem_fpga_model.py --sim --gains         # ...and the loops' bandwidths and damping
    python3 modem_fpga_model.py --sim --plot

Everything psk.py does in floating point, done again with integers and shifts, exactly as
the Verilog does it: the same tables, the same widths, the same rounding (every shift
rounds towards minus infinity, as Verilog's >>> does).  qpsk_modem_check.py runs the
Verilog on the same samples and checks that the two agree bit for bit.

TRANSMITTER (one DAC sample per 50 MHz clock)
  frame    16 bits = 8 symbols: a 7-bit sync word (Barker's 1110010), a "valid" bit, and
           the byte from the serial port, or 8 bits of a shift register when there's none.
           195,312 frames a second, more than a 1 Mbaud serial port can supply.
  symbols  2 bits each, Gray-coded, as a CHANGE of phase (differential QPSK): 00, 01, 11,
           10 turn the carrier by 0, 90, 180, 270 degrees from the previous symbol.
  pulses   root-raised-cosine, roll-off 0.35, 32 DAC samples per symbol (1.5625 Msymbol/s),
           cut off 6 symbols each side.  The symbols are +-1 +-j, so the pulse shaper is
           13 table look-ups and an adder tree: no multipliers.
  carrier  6.25 MHz = 50 MS/s / 8: cos and sin take the values 0, +-1 and +-0.707, so I on
           cos minus Q on sin is a choice of I, Q, or 0.707 (I +- Q), and 0.707 = 181/256.

RECEIVER (an ADC sample every 2 clocks; everything after the decimator has 8 clocks per sample)
  1. mix down by 6.25 MHz = 25 MS/s / 4: multiply by 1, -j, -1, j (free).  That leaves
     I on the even samples and Q on the odd ones, each with a hole between;
  2. a half-band filter, [-1 0 9 16 9 0 -1] / 32, fills Q's holes at the even samples
     (I's own samples pass through it untouched) and keeps the even ones: 12.5 MS/s.
     Then [1 2 1] and keep 1 in 2: 6.25 MS/s, 4 samples per symbol;
  3. a 3-tap filter (shifts only) that undoes [1 2 1]'s droop across the band;
  4. the matched filter: the same root-raised-cosine, 49 taps, symmetric, so 25 multiplies
     per I and Q, shared between 4 multipliers each over 7 of the 8 clocks;
  5. the timing loop: a counter (the "NCO") says when the next symbol centre falls between
     two samples, and a cubic interpolator (Catmull-Rom's, whose coefficients are halves:
     3 multiplies per axis) computes the signal there and half a symbol earlier.  Gardner's detector
     and a PI loop filter whose gains are shifts;
  6. the Costas loop: turn each symbol by the phase so far (a 1024-entry sine table, 4
     multiplies), find the nearest of the four points, Im(z d*) is +-Q -+ I: no multiplies;
     a PI loop filter with shift gains learns the carrier's frequency;
  7. the symbol's quadrant minus the previous one's is the 2 bits (differential decoding:
     the loop's 90-degree ambiguity cancels out); 8 of those make a frame; a sync word in
     the right place three times running means "locked", and the byte goes to the serial port.
"""
import argparse
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import channel                                              # noqa: E402
import psk                                                  # noqa: E402

F_CLK, FS_DAC, FS_ADC = 50e6, 50e6, 25e6
SPS_DAC, SPS_ADC, SPS = 32, 16, 4        # DAC samples, ADC samples, decimated samples per symbol
R_SYM = FS_DAC / SPS_DAC                 # 1.5625 Msymbol/s
ALPHA = 0.35
SPAN = 6                                 # pulses cut off this many symbols each side
TX_SCALE = 48 * 8                        # pulse table = 384 x rrc: 48 DAC codes per unit symbol, x 8
MF_SCALE = 256                           # matched-filter taps = 256 x rrc
MF_SHIFT = 13                            # matched-filter output = sum of products / 2^13
SYNC = 0b1110010                         # Barker 7
NSYM_FRAME = 8
GRAY = [0b00, 0b01, 0b11, 0b10]          # turn dq (0..3 quarter turns) -> the 2 bits it carries
GRAY_INV = [0, 1, 3, 2]                  # the 2 bits -> dq
ONE = 1 << 16                            # one sample, in the timing NCO's units
PNOM = SPS * ONE                         # 4 samples per symbol
# the loop filters' gains, as shifts (see loop_report())
S1_T, S2_T = 7, 5                        # timing: tau -= e >> S1_T;  integ += e >> S2_T  (integ / 2^8 per sample)
S1_C, S2_C = 7, 2                        # carrier: phi += e << S1_C;  freq += e << S2_C   (phi: 2^24 per turn)

# ---- the tables, as the Verilog's `initial` blocks compute them -------------------
def rrc_table(t):
    """round(rrc(t)) is not what Verilog does: it computes the formula in double precision
    and $rtoi($floor(x + 0.5)); so does this."""
    return np.floor(psk.rrc(t) + 0.5)

PULSE = np.array([[int(np.floor(TX_SCALE * psk.rrc((j - SPAN) + p / SPS_DAC) + 0.5))
                   for p in range(SPS_DAC)] for j in range(2 * SPAN + 1)], np.int64)    # [13][32]
MF = np.array([int(np.floor(MF_SCALE * psk.rrc(k / SPS) + 0.5))
               for k in range(-SPAN * SPS, SPAN * SPS + 1)], np.int64)                  # 49 taps
SINE = np.array([int(np.floor(2047.0 * np.sin(2 * np.pi * i / 1024) + 0.5)) for i in range(1024)], np.int64)


# ---- transmitter ------------------------------------------------------------------
def lfsr_step(s):
    """The idle filler: x^16 + x^14 + x^13 + x^11 + 1, one step (the Verilog steps it once per symbol)."""
    return ((s << 1) & 0xFFFF) | (((s >> 15) ^ (s >> 13) ^ (s >> 12) ^ (s >> 10)) & 1)


def frames_for(data, gap=1, lead=40, trail=40):
    """Frame words for the bytes `data`, one byte every `gap` + 1 frames (a 1 Mbaud serial
    port delivers a byte every 500 clocks, a frame takes 256), with idle frames before (40 =
    200 us: the loops' settling time) and after.  Returns (16-bit words, the frame number of
    each byte)."""
    words, where, s = [], [], 0xACE1
    def idle():
        nonlocal s
        for _ in range(NSYM_FRAME):
            s = lfsr_step(s)
        return (SYNC << 9) | (s & 0xFF)
    for _ in range(lead):
        words.append(idle())
    for b in data:
        where.append(len(words))
        words.append((SYNC << 9) | 0x100 | int(b))
        for _ in range(gap):
            words.append(idle())
    for _ in range(trail):
        words.append(idle())
    return np.array(words, np.int64), np.array(where)


def tx_symbols(words, q0=0):
    """Frame words -> the symbol number q (0..3: 45, 135, 225, 315 degrees) of each symbol."""
    q, out = q0, []
    for w in words:
        for i in range(NSYM_FRAME):
            dibit = (int(w) >> (14 - 2 * i)) & 3
            # ##################################################################
            # ##  KEY LINE: differential coding.  The bits say how far to turn.
            # ##################################################################
            q = (q + GRAY_INV[dibit]) & 3
            out.append(q)
    return np.array(out, np.int64)


def signs(q):
    """The symbol +-1 +-j for q: (sign of I, sign of Q)."""
    q = np.asarray(q)
    return np.where((q == 0) | (q == 3), 1, -1), np.where(q <= 1, 1, -1)


def tx_dac(q):
    """The DAC codes (32 per symbol) for the symbols q, exactly as the FPGA makes them.  The
    FPGA's symbol register starts full of q = 0 (+1 +j), so 6 of those are put in front."""
    q = np.concatenate([np.zeros(SPAN, np.int64), q, np.zeros(SPAN, np.int64)])
    si, sq = signs(q)
    nsym = len(q) - 2 * SPAN                           # DAC samples for these symbols
    m = np.arange(nsym)
    I = np.zeros((nsym, SPS_DAC), np.int64)
    Q = np.zeros((nsym, SPS_DAC), np.int64)
    for j in range(2 * SPAN + 1):
        # ######################################################################
        # ##  KEY LINE: the pulse shaper.  13 symbols overlap at any instant; each
        # ##  adds or subtracts its pulse's table value at this phase of the symbol.
        # ######################################################################
        I += si[m + 2 * SPAN - j][:, None] * PULSE[j][None, :]
        Q += sq[m + 2 * SPAN - j][:, None] * PULSE[j][None, :]
    I, Q = I.ravel(), Q.ravel()
    m8 = np.arange(len(I)) & 7
    # ##########################################################################
    # ##  KEY LINE: onto the carrier, 8 samples per cycle: I cos - Q sin is I, Q
    # ##  or 0.707 (I +- Q); 0.707 = 181/256.  Then / 8 (the table's scale).
    # ##########################################################################
    even = np.select([m8 == 0, m8 == 2, m8 == 4, m8 == 6], [I, -Q, -I, Q], 0)
    odd = np.select([m8 == 1, m8 == 3, m8 == 5, m8 == 7], [I - Q, -I - Q, -I + Q, I + Q], 0)
    s = np.where(m8 & 1, (181 * odd + 1024) >> 11, (even + 4) >> 3)
    return np.clip(128 + s, 0, 255)


# ---- the cable, for a stream of any length ----------------------------------------
def stream_channel(dac, ppm=0.0, cfo=0.0, delay=5.7, noise=0.1, corner=40e6,
                   gain=channel.GAIN, offset=channel.OFFSET, recon=None, rng=None):
    """channel.channel() for a waveform that doesn't loop: DAC codes at 50 MS/s in, ADC
    codes at 25 MS/s out, with the same steps (held codes, a 40 MHz low-pass, a delay of
    5.7 ADC samples, 0.776 x + 27.5, noise, 8 bits).  `ppm`: the transmitter's clock is
    that much fast (its carrier and symbol rate too); `cfo`: move the carrier by this many
    Hz on top (a mixer's error, as channel.py's `shift`).

    `recon`: give the DAC an ideal reconstruction filter (nothing above 25 MHz).  The
    default is to do that when ppm or cfo isn't 0: the bare DAC's image of the signal, at 50 MHz
    minus 6.25 MHz, folds back onto 6.25 MHz, and with one clock it only changes the gain
    a little, but with two clocks it lands 50 MHz x ppm away: 38 Hz at the boards' real
    0.76 ppm, harmless, but 100 kHz at a pretend 2000 ppm, an interferer 21 dB down
    (channel.py).  A mixer error moves the image the other way, 2 x cfo from the signal.
    Either would be a test of the DAC's missing filter, not of the loops."""
    rng = np.random.default_rng(rng)
    UP = channel.UP
    w = np.clip(np.round(np.asarray(dac, float)), 0, 255) - 128
    pad = 64                                                     # silence either side
    held = np.repeat(np.concatenate([np.zeros(pad), w, np.zeros(pad)]), UP)
    f = np.fft.rfftfreq(len(held), 1 / (FS_DAC * UP))
    s = 1j * f / corner
    Y = np.fft.rfft(held) / (1 + np.sqrt(2) * s + s**2)          # two poles at `corner`
    if recon or (recon is None and (ppm != 0 or cfo != 0)):
        Y[f > FS_DAC / 2] = 0
    n_adc = int((len(w) - 2 * delay) / (2 * (1 + ppm * 1e-6)))
    n = np.arange(n_adc)
    # ##########################################################################
    # ##  KEY LINE: ADC sample n sees the DAC's output at the transmitter's time
    # ##  u = 2n(1 + ppm/1e6) - 2 delay, in DAC samples.
    # ##########################################################################
    pos = (2.0 * n * (1 + ppm * 1e-6) - 2.0 * delay + pad) * UP
    if cfo == 0:
        v = channel.cubic(np.fft.irfft(Y, len(held)), pos)
    else:
        Ya = 2 * Y
        Ya[0] = Y[0]
        full = np.zeros(len(held), complex)
        full[:len(Ya)] = Ya
        ya = np.fft.ifft(full)                                   # the analytic signal
        v = np.real(channel.cubic(ya, pos) * np.exp(2j * np.pi * cfo * n / FS_ADC))
    adc = offset + gain * (128 + v) + noise * rng.standard_normal(n_adc)
    return np.clip(np.round(adc), 0, 255).astype(np.int64)


# ---- receiver, front end (numpy: the same integers the FPGA computes) --------------
def rx_frontend(adc, droop_eq=True):
    """ADC codes -> the matched filter's output at 6.25 MS/s, as (I, Q) integer arrays.
    Also returns the half-band stage's output at 12.5 MS/s, for looking at."""
    x = np.asarray(adc, np.int64) - 128
    n = np.arange(len(x))
    # ##########################################################################
    # ##  KEY LINE: mix by 1, -j, -1, j.  I lives on the even samples and Q on
    # ##  the odd ones (the other half of each is zero).
    # ##########################################################################
    zI = np.where(n % 4 == 0, x, np.where(n % 4 == 2, -x, 0))
    zQ = np.where(n % 4 == 3, x, np.where(n % 4 == 1, -x, 0))
    # 1. the half-band interpolator, keeping the even samples: I is the sample itself
    #    (x 16), Q is interpolated from its four odd neighbours (x 16 too, at DC).
    #    (The zeros in front are what the FPGA's empty delay lines hold at power-up.)
    zI, zQ = np.concatenate([np.zeros(6, np.int64), zI]), np.concatenate([np.zeros(6, np.int64), zQ])
    m1 = np.arange(4, len(zI) - 3, 2)
    I1 = 16 * zI[m1]
    Q1 = 9 * (zQ[m1 - 1] + zQ[m1 + 1]) - (zQ[m1 - 3] + zQ[m1 + 3])
    # 2. [1 2 1] and keep 1 in 2: 6.25 MS/s, 4 samples per symbol (x 4)
    I1, Q1 = np.concatenate([np.zeros(2, np.int64), I1]), np.concatenate([np.zeros(2, np.int64), Q1])
    m2 = np.arange(1, len(I1) - 1, 2)
    I2 = I1[m2 - 1] + 2 * I1[m2] + I1[m2 + 1]
    Q2 = Q1[m2 - 1] + 2 * Q1[m2] + Q1[m2 + 1]
    if droop_eq:
        # 3. a little high-pass that lifts the band edge by what [1 2 1] drooped:
        #    y[m] = 4 v[m-1] + 9 (2 v[m-1] - v[m] - v[m-2]) / 32    (x 4 keeps 2 fraction bits)
        def eq(v):
            vp = np.concatenate([np.zeros(2, np.int64), v])
            return 4 * vp[1:-1] + ((2 * vp[1:-1] - vp[2:] - vp[:-2]) * 9 >> 5)
        Ie, Qe = eq(I2), eq(Q2)
    else:
        Ie, Qe = 4 * I2, 4 * Q2
    # ##########################################################################
    # ##  KEY LINE: the matched filter, 49 integer taps, then / 2^13.
    # ##########################################################################
    yI = np.convolve(Ie, MF)[:len(Ie)] >> MF_SHIFT
    yQ = np.convolve(Qe, MF)[:len(Qe)] >> MF_SHIFT
    return yI, yQ, I1, Q1


# ---- receiver, the loops (one symbol at a time, as the FPGA) ------------------------
def farrow(ym1, y0, y1, y2, mu):
    """The value between y0 and y1, mu/4096 of the way, on the cubic through the four
    samples that Keys's a = -1/2 (the Catmull-Rom spline) gives: every coefficient is a
    half, so there's nothing but shifts, adds and three multiplies by mu (Horner)."""
    c1 = (y1 - ym1) >> 1
    c2 = (2 * ym1 - 5 * y0 + 4 * y1 - y2) >> 1
    c3 = (-ym1 + 3 * y0 - 3 * y1 + y2) >> 1
    t1 = c2 + ((mu * c3) >> 12)
    t2 = c1 + ((mu * t1) >> 12)
    return y0 + ((mu * t2) >> 12)


def sat(v, bits):
    """v, kept within a signed number of this many bits (plus the sign)."""
    lo, hi = -(1 << bits), (1 << bits) - 1
    return lo if v < lo else hi if v > hi else v


def quadrant(i, q):
    """The nearest of the four points: q = 0, 1, 2, 3 for 45, 135, 225, 315 degrees."""
    return 0 if (i >= 0 and q >= 0) else 1 if (i < 0 and q >= 0) else 2 if (i < 0) else 3


def rx_loops(yI, yQ, s1_t=S1_T, s2_t=S2_T, s1_c=S1_C, s2_c=S2_C, tau0=2 * ONE):
    """The timing NCO, the interpolator, the Gardner and Costas loops, the decisions and
    the frame sync, sample by sample.  Returns a dict of arrays (one entry per symbol) and
    the bytes received, with the symbol number each arrived at.

    The NCO is a counter tau that says how many samples away the next symbol centre is,
    and loses 1 per sample.  When it drops below 1, the centre falls before the next
    sample: a symbol strobe, and tau is where between the samples (mu); then it gets a
    period, less the loop's correction, added.  Half a period earlier there's a "mid"
    strobe the same way, for Gardner's half-way sample.  The
    interpolator always works two samples behind (it needs the sample after the one it's
    interpolating past), with the mu that was decided for that sample."""
    n = len(yI)
    yI = np.concatenate([np.zeros(3, np.int64), yI]); yQ = np.concatenate([np.zeros(3, np.int64), yQ])
    tau, integ, prop = tau0, 0, 0
    flags = [(False, False, 0)] * 3            # (symbol strobe, mid strobe, mu) at k, k-1, k-2
    yi = [(0, 0)] * 2                          # interpolated values: basepoint k-2 is yi[0]
    mid = prev = (0, 0)
    phi = freq = 0
    q_prev = fr = cnt = hits = misses = 0
    locked = False
    rec = {k: [] for k in ("sym", "mu", "tau", "period", "eg", "zI", "zQ", "phi", "freq", "ec",
                           "q", "locked", "yI", "yQ")}
    out, out_at = [], []
    for k in range(n):
        # 1. basepoint k-3's strobes: its interpolated value was computed last time (yi[0]).
        #    This comes first so that the loop's correction is in before the NCO decides.
        s_k, m_k, mu_k = flags[2]
        if m_k:
            mid = (yi[0][0] >> 1, yi[0][1] >> 1)
        if s_k:
            nI, nQ = yi[0][0] >> 1, yi[0][1] >> 1
            # ##################################################################
            # ##  KEY LINE: Gardner's detector, Re(y_mid* (y_now - y_prev)).
            # ##################################################################
            eg = mid[0] * (nI - prev[0]) + mid[1] * (nQ - prev[1])
            prev = (nI, nQ)
            integ += sat(eg >> s2_t, 20)              # (the saturations only matter for
            prop = sat(eg >> s1_t, 15)                #  junk: they keep tau in 20 bits)
            # the Costas loop: turn by -phi, decide, Im(z d*), update
            idx = (phi >> 14) & 1023
            c, s = SINE[(idx + 256) & 1023], SINE[idx]
            zI = (nI * c + nQ * s) >> 11
            zQ = (nQ * c - nI * s) >> 11
            qd = quadrant(zI, zQ)
            # ##################################################################
            # ##  KEY LINE: the phase detector: +-Q -+ I, the sign from the quadrant.
            # ##################################################################
            ec = (zQ if zI >= 0 else -zQ) - (zI if zQ >= 0 else -zI)
            freq += ec << s2_c
            phi = (phi + freq + (ec << s1_c)) & 0xFFFFFF
            # differential decoding, and the frame
            dq = (qd - q_prev) & 3
            q_prev = qd
            fr = ((fr << 2) | GRAY[dq]) & 0xFFFF
            hit = (fr >> 9) == SYNC
            if locked:
                if cnt == NSYM_FRAME - 1:                  # a whole frame is in
                    misses = 0 if hit else misses + 1
                    if misses >= 8:
                        locked = False
                    elif (fr >> 8) & 1:
                        out.append(fr & 0xFF); out_at.append(len(rec["sym"]))
                    cnt = 0
                else:
                    cnt += 1
            else:
                if hit:
                    hits = hits + 1 if cnt == NSYM_FRAME - 1 else 1
                    cnt = 0
                    if hits >= 3:
                        locked, misses = True, 0
                        if (fr >> 8) & 1:
                            out.append(fr & 0xFF); out_at.append(len(rec["sym"]))
                else:
                    cnt = min(cnt + 1, NSYM_FRAME)
            for key, val in (("sym", k - 3), ("mu", mu_k >> 4), ("tau", tau), ("period", PNOM - sat(integ >> 8, 15)),
                             ("eg", eg), ("zI", zI), ("zQ", zQ), ("phi", phi), ("freq", freq),
                             ("ec", ec), ("q", qd), ("locked", int(locked)), ("yI", nI), ("yQ", nQ)):
                rec[key].append(val)
        # 2. the NCO: does the next symbol centre, or the half-way point before it,
        #    fall before the next sample?
        period = PNOM - sat(integ >> 8, 15)
        if tau < ONE:
            flags = [(True, False, tau)] + flags[:2]
            # ##################################################################
            # ##  KEY LINE: the next centre is one period on, less the loop's
            # ##  correction (the integrator is in `period`, and `prop` is the
            # ##  last symbol's error): psk.py's  t += sps - (k1 e + integ).
            # ##################################################################
            tau = tau + period - prop - ONE
        else:
            half = tau - (period >> 1)
            flags = [(False, 0 <= half < ONE, half & 0xFFFF)] + flags[:2]
            tau = tau - ONE
        # 3. interpolate at basepoint k-2, with the mu decided for it
        mu = flags[2][2] >> 4
        y = (farrow(yI[k], yI[k + 1], yI[k + 2], yI[k + 3], mu),
             farrow(yQ[k], yQ[k + 1], yQ[k + 2], yQ[k + 3], mu))
        yi = [y] + yi[:1]
    r = {k: np.array(v, np.int64) for k, v in rec.items()}
    r["bytes"], r["bytes_at"] = np.array(out, np.int64), np.array(out_at, np.int64)
    r["ppm"] = (PNOM / np.maximum(r["period"], 1) - 1) * 1e6      # symbol rate offset found
    r["hz"] = r["freq"] * R_SYM / 2**24                            # carrier offset found
    return r


def receive(adc, **kw):
    yI, yQ, I, Q = rx_frontend(adc)
    r = rx_loops(yI, yQ, **kw)
    r["mfI"], r["mfQ"], r["hbI"], r["hbQ"] = yI, yQ, I, Q
    return r


# ---- the loops' gains: what the shifts amount to -----------------------------------
def loop_params(K1, K2):
    """Noise bandwidth x symbol time, and damping, of a second-order loop whose
    proportional and integral gains (times the detector's gain) are K1 and K2 per
    update: psk.loop_gains() run backwards."""
    th = math.sqrt(K2 / (4 - 2 * K1 - K2))
    zeta = th * K1 / K2
    return th * (zeta + 1 / (4 * zeta)), zeta


def detector_gains(adc):
    """Measure the detectors' slopes on this signal, with the loops held still: the Gardner
    error per sample of timing error (at 4 samples per symbol), and the Costas error per
    radian, both in the FPGA's integer units."""
    yI, yQ, _, _ = rx_frontend(adc)
    k = np.arange(40 * SPS, len(yI) - 8, SPS)              # nominal symbol centres: every 4th sample
    def at(off):                                             # the symbols at offset `off` samples
        i, mu = int(np.floor(off)), int((off - np.floor(off)) * 4096)
        return (np.array([farrow(yI[j - 1], yI[j], yI[j + 1], yI[j + 2], mu) for j in k + i]) >> 1,
                np.array([farrow(yQ[j - 1], yQ[j], yQ[j + 1], yQ[j + 2], mu) for j in k + i]) >> 1)
    best, kd_t = None, 0
    for off in np.arange(0, 4, 0.25):                        # find the true centre first
        I, Q = at(off)
        p = np.mean(np.abs(I) + np.abs(Q))
        if best is None or p > best[0]:
            best = (p, off)
    off = best[1]
    d = 0.1
    e = []
    for o in (off - d, off + d):
        nI, nQ = at(o)
        mI, mQ = at(o - 2)
        e.append(np.mean(mI[1:] * np.diff(nI) + mQ[1:] * np.diff(nQ)))
    kd_t = (e[1] - e[0]) / (2 * d)
    I, Q = at(off)
    S = np.mean(np.abs(I) + np.abs(Q)) / 2                   # the symbol's size per axis
    return kd_t, 2 * S, S


def loop_report(adc=None, s1_t=S1_T, s2_t=S2_T, s1_c=S1_C, s2_c=S2_C):
    """Print what the shifts mean, measured on `adc`, which must have no rate offset (the
    symbol centres are taken every 4th sample), or by default on a model signal."""
    if adc is None:
        words, _ = frames_for(np.random.default_rng(3).integers(0, 256, 200), gap=1)
        adc = stream_channel(tx_dac(tx_symbols(words)), rng=3)
    kd_t, kd_c, S = detector_gains(adc)
    lines = ["symbol size after the matched filter and interpolator: %.0f per axis" % S,
             "Gardner detector: %.3g per sample of timing error;  Costas: %.0f per radian" % (kd_t, kd_c)]
    K1 = kd_t * 2**-s1_t / ONE
    K2 = kd_t * 2**-s2_t / ONE / 256
    bnt, z = loop_params(K1, K2)
    lines.append("timing loop:  e >> %d and e >> %d:  K1 = %.4f, K2 = %.2e: BnT = %.4f, zeta = %.2f  (psk.py: 0.01, 0.71)"
                 % (s1_t, s2_t, K1, K2, bnt, z))
    K1 = kd_c * 2**s1_c * 2 * np.pi / 2**24
    K2 = kd_c * 2**s2_c * 2 * np.pi / 2**24
    bnt, z = loop_params(K1, K2)
    lines.append("carrier loop: e << %d and e << %d:  K1 = %.4f, K2 = %.2e: BnT = %.4f, zeta = %.2f  (psk.py: 0.02, 0.71)"
                 % (s1_c, s2_c, K1, K2, bnt, z))
    return "\n".join(lines)


# ---- scoring -----------------------------------------------------------------------
def score(sent, got):
    """Bit errors between the bytes sent and the bytes received, lined up with difflib
    (a lost or invented byte counts 8), as modem_ber.py does."""
    import difflib
    sent, got = bytes(int(b) for b in sent), bytes(int(b) for b in got)
    bits = 0
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, sent, got, autojunk=False).get_opcodes():
        if op == "replace":
            n = min(i2 - i1, j2 - j1)
            bits += sum(bin(x ^ y).count("1") for x, y in zip(sent[i1:i1 + n], got[j1:j1 + n]))
            bits += 8 * abs((i2 - i1) - (j2 - j1))
        elif op == "delete" or op == "insert":
            bits += 8 * max(i2 - i1, j2 - j1)
    return bits


def summary(r, sent=None):
    """A few lines about a receive: lock, the offsets found, errors."""
    lines = []
    lk = np.flatnonzero(r["locked"])
    lines.append("symbols: %d; frame lock at symbol %s" % (len(r["sym"]), lk[0] if len(lk) else "never"))
    last = slice(-200, None)
    lines.append("timing loop:  symbol rate offset found %+.0f ppm (mean of the last 200 symbols)" % np.mean(r["ppm"][last]))
    lines.append("Costas loop:  carrier offset found %+.0f Hz" % np.mean(r["hz"][last]))
    if sent is not None:
        got = r["bytes"]
        lines.append("%d bytes sent, %d received, %d bit errors" % (len(sent), len(got), score(sent, got)))
    return "\n".join(lines)


def plot(r, title):
    import matplotlib.pyplot as plt
    k = r["sym"]
    us = k * SPS / 6.25e6 * 1e6
    fig, ax = plt.subplots(2, 3, figsize=(13, 7))
    good = r["locked"] > 0
    ax[0, 0].plot(r["zI"][~good], r["zQ"][~good], ".", color="0.75", markersize=2)
    ax[0, 0].plot(r["zI"][good], r["zQ"][good], ".", markersize=2)
    ax[0, 0].set_aspect("equal"); ax[0, 0].set_title("after the loops (grey: before frame lock)")
    ax[0, 1].plot(us, r["mu"] / 4096, ".", markersize=1.5); ax[0, 1].set_title("mu: where between samples (0..1)")
    ax[0, 2].plot(us, r["ppm"]); ax[0, 2].set_title("symbol rate offset found (ppm)")
    ax[1, 0].plot(us, r["eg"], ".", markersize=1.5); ax[1, 0].set_title("Gardner error")
    ax[1, 1].plot(us, r["hz"] / 1e3); ax[1, 1].set_title("carrier offset found (kHz)")
    ax[1, 2].plot(us, r["ec"], ".", markersize=1.5); ax[1, 2].set_title("Costas error")
    for a in ax.ravel()[1:]:
        a.set_xlabel("time (us)"); a.grid(True)
    fig.suptitle(title); fig.tight_layout(); plt.show()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sim", action="store_true", help="(the only mode: this is the model)")
    ap.add_argument("--bytes", type=int, default=300)
    ap.add_argument("--ppm", type=float, default=0.0, help="transmitter's clock offset, ppm")
    ap.add_argument("--cfo", type=float, default=0.0, help="extra carrier offset, Hz")
    ap.add_argument("--noise", type=float, default=0.1, help="ADC noise, codes rms")
    ap.add_argument("--gains", action="store_true", help="print the loops' bandwidths")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--plot", action="store_true")
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    data = rng.integers(0, 256, args.bytes)
    words, where = frames_for(data, gap=1)
    dac = tx_dac(tx_symbols(words))
    adc = stream_channel(dac, ppm=args.ppm, cfo=args.cfo, noise=args.noise, rng=args.seed)
    print("DAC: %d samples, rms %.1f codes, peak %d; ADC: %d samples" % (len(dac), (dac - 128).std(), np.abs(dac - 128).max(), len(adc)))
    if args.gains:
        print(loop_report())
    r = receive(adc)
    print(summary(r, data))
    if args.plot:
        plot(r, "fixed-point model, ppm %+.0f, cfo %+.0f Hz" % (args.ppm, args.cfo))
