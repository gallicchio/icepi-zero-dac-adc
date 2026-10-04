#!/usr/bin/env python3
"""control.sv in Python, bit for bit: the PID loop, its two built-in plants, and a model of
the real-world loop (mode 0) through the cable or an RC, for figures without a board.

    import control_model as cm
    loop = cm.Loop(cm.Settings(mode=1, klag=4, kp=1.0, ki=0.02))
    e, u, y = loop.step(sp=40, x=0)                 # one ADC sample: setpoint, ADC - 128

    cable = cm.Cable(delay=7)                       # mode 0's plant: 1.07's loopback cable
    x = cable.step(loop.dac)                        # what the ADC reads, 7 samples later

    python3 control_model.py --check control_tb_trace.txt   # replay the testbench's trace
    python3 control_model.py                        # the theory numbers 7.06 quotes

Every integer here is the same width and rounds the same way as the gateware (floor on the
shifts, the integrator clamp and anti-windup, the plant's wall at +-2047 codes), so a trace
from control_tb.sv replays exactly, and --sim in control.py is the board minus the analog.

The loop, per ADC sample (control.sv's edges 1 and 2):
    y    = plant output in whole codes (0 in mode 0);  meas = y + x;  e = sp - meas
    u    = (Kp e x 64 + Ki I + Kd (e - e_prev) x 256) >> 16,  Kp, Ki, Kd the 16-bit words
    I   += e  unless the DAC is pinned and e pushes the same way (anti-windup); |I| <= 131071;
         I = 0 while Ki = 0 or the loop is open
    DAC  = 128 + bias + u, saturated;  the plant then sees u from L + 1 samples ago.
Gains as floats: Kp = word / 1024, Ki = word / 65536 per sample, Kd = word / 256.

Theory (floats), for the figures: the plants' frequency responses, the loop's sensitivity
function S = 1 / (1 + C H), and the critical gain of a P controller, where the loop's phase
reaches -180 degrees.  For a pure delay of d samples that is f = fs / 2d and Kp = 1 / G.
"""
import sys

import numpy as np

FS = 25e6                       # the ADC's sample rate
TS = 1 / FS
YMAX = 2047 * 256               # the plant's wall, in codes x 256
IMAX = 131071                   # the integrator's clamp
GAIN, OFFSET = 0.776, 27.5      # the cable: ADC = 0.776 x DAC + 27.5 (1.07)
LOOP_DELAY = 7                  # samples around the real loop (control.sv's count)


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


# ---- the settings, as 16-bit words ----------------------------------------------------
class Settings:
    """The registers the laptop sets.  Gains may be given as floats (kp=1.0) or as the
    words the board holds (kp_word=1024); the words are what the arithmetic uses."""

    def __init__(self, mode=0, kp=0.0, ki=0.0, kd=0.0, bias=0, klag=4, rword=662, qshift=10,
                 ldelay=0, enable=True, osel=0, kp_word=None, ki_word=None, kd_word=None):
        self.kp = kp_word if kp_word is not None else kp_to_word(kp)
        self.ki = ki_word if ki_word is not None else ki_to_word(ki)
        self.kd = kd_word if kd_word is not None else kd_to_word(kd)
        self.bias, self.mode, self.klag = int(bias), int(mode), int(klag)
        self.rword, self.qshift, self.ldelay = int(rword), int(qshift), int(ldelay)
        self.enable, self.osel = bool(enable), int(osel)

    def copy(self, **kw):
        s = Settings.__new__(Settings)
        s.__dict__.update(self.__dict__)
        s.__dict__.update(kw)
        return s


def _word(v, scale):
    return int(clamp(int(round(v * scale)), -32768, 32767))


def kp_to_word(kp):
    return _word(kp, 1024)


def ki_to_word(ki):
    return _word(ki, 65536)


def kd_to_word(kd):
    return _word(kd, 256)


def rword_from_f0(f0):
    """'R' for a resonator at f0: (2 pi f0 / fs)^2 x 2^20."""
    return int(clamp(int(round((2 * np.pi * f0 / FS) ** 2 * 2**20)), 1, 65535))


def f0_from_rword(r):
    return FS / (2 * np.pi) * np.sqrt(r / 2**20)


def q_of(rword, qshift):
    """The resonator's Q: w0 / (damping per sample)."""
    return 2 * np.pi * f0_from_rword(rword) / FS * 2**qshift


# ---- the loop ---------------------------------------------------------------------------
class Loop:
    def __init__(self, s=None):
        self.s = s or Settings()
        self.integ = 0
        self.e_prev = 0
        self.sat_hi = self.sat_lo = False
        self.y_state = 0                # codes x 256
        self.vel = 0                    # codes/sample x 65536
        self.uline = [0] * 64
        self.u = 0
        self.dac = 128

    def step(self, sp, x, s1=None, s2=None):
        """One ADC sample.  sp: the setpoint (already clipped to +-511), x: ADC - 128.
        s1 / s2: the settings as they were at the gateware's edge 1 and edge 2 (they only
        differ while a command is arriving; both default to self.s).  Returns (e, u, y)."""
        s1 = s1 or self.s
        s2 = s2 or self.s
        # ---- edge 1: the error and the three products
        y_int = 0 if s1.mode == 0 else self.y_state >> 8
        meas = y_int + x
        e = sp - meas
        de = e - self.e_prev
        pp, pd, pi = s1.kp * e, s1.kd * de, s1.ki * self.integ
        if not s1.enable or s1.ki == 0:
            self.integ = 0
        elif not ((self.sat_hi and e > 0) or (self.sat_lo and e < 0)):
            self.integ = clamp(self.integ + e, -IMAX, IMAX)
        self.e_prev = e
        u_plant = self.uline[s1.ldelay]
        d = u_plant * 256 - self.y_state
        lag = d >> s1.klag
        prod = (d >> 3) * s1.rword
        damp = self.vel >> s1.qshift
        # ---- edge 2: the output word
        usum = (pp << 6) + pi + (pd << 8)
        u_c = usum >> 16
        dac_c = (u_c if s2.enable else sp) + 128 + s2.bias
        dac_sat = clamp(dac_c, 0, 255)
        u_out = dac_sat - 128 - s2.bias
        self.sat_hi, self.sat_lo = dac_c > 255, dac_c < 0
        self.dac = clamp(y_int + 128, 0, 255) if (s2.mode != 0 and s2.osel) else dac_sat
        # ---- the plant
        vel_new = self.vel + (prod >> 9) - damp
        y_new = self.y_state + lag if s2.mode == 1 else self.y_state + (vel_new >> 8)
        if s2.mode in (0, 3):
            self.y_state, self.vel = 0, 0
        elif y_new > YMAX:
            self.y_state, self.vel = YMAX, 0
        elif y_new < -YMAX:
            self.y_state, self.vel = -YMAX, 0
        else:
            self.y_state, self.vel = y_new, (0 if s2.mode == 1 else vel_new)
        self.uline = [u_out] + self.uline[:-1]
        self.u = u_out
        return e, u_out, y_int


# ---- the real world, for mode 0 ---------------------------------------------------------
class Cable:
    """1.07's loopback: the ADC reads 0.776 x DAC + 27.5, `delay` samples later (control.sv
    counts 7; 1.07's loopback.sv, one clock quicker, measured 6), plus noise.  An RC between
    DAC OUT and ADC IN is the same with tau > 0 (seconds): a first-order lag on the DAC's
    voltage, as 4.08 computes it."""

    def __init__(self, delay=LOOP_DELAY, gain=GAIN, offset=OFFSET, noise=0.1, tau=0.0, rng=1):
        self.delay, self.gain, self.offset, self.noise = int(delay), gain, offset, noise
        self.a = 1 - np.exp(-TS / tau) if tau > 0 else 1.0
        self.line = [128] * self.delay
        self.v = 128.0
        self.rng = np.random.default_rng(rng)

    def step(self, dac):
        """The DAC's word from the previous sample in; what the ADC reads (0..255) at this
        sample out.  The word that went out at sample m is read back at sample m + delay."""
        self.line = [int(dac)] + self.line[:-1]
        self.v += self.a * (self.line[-1] - self.v)               # the RC (or none)
        adc = self.offset + self.gain * self.v + self.noise * self.rng.standard_normal()
        return int(clamp(int(round(adc)), 0, 255))


# ---- theory: frequency responses and the critical gain -------------------------------------
def z_of(f):
    return np.exp(2j * np.pi * np.asarray(f, float) / FS)


def plant_response(f, s, cable=None):
    """H(f): the measurement in ADC codes per code of u, including the loop's delay.
    Mode 0: the cable (a delay of `cable.delay` samples, gain, optional RC); modes 1-2 the
    built-in plants, whose input is u from 2 + L samples ago."""
    z = z_of(f)
    if s.mode == 0:
        c = cable or Cable()
        H = c.gain * z**(-c.delay)
        if c.a < 1:
            H = H * c.a / (1 - (1 - c.a) / z)
        return H
    zd = z**(-(2 + s.ldelay))
    if s.mode == 1:
        a = 2.0**(-s.klag)
        return a * zd / (1 - (1 - a) / z)
    w2, g = s.rword / 2**20, 2.0**(-s.qshift)
    return w2 * z**(-s.ldelay) / ((z - 1) * (z - 1 + g) + w2 * z)


def controller_response(f, s):
    """C(f) = Kp + Ki z^-1 / (1 - z^-1) + Kd (1 - z^-1), the gains as floats."""
    z = z_of(f)
    kp, ki, kd = s.kp / 1024, s.ki / 65536, s.kd / 256
    return kp + ki / (z - 1) + kd * (1 - 1 / z)


def sensitivity(f, s, cable=None):
    """S(f) = 1 / (1 + C H): a disturbance at the ADC appears in the measurement times this.
    Below the loop bandwidth |S| < 1 (rejected), above it |S| > 1 (the waterbed)."""
    return 1 / (1 + controller_response(f, s) * plant_response(f, s, cable))


def critical_gain(s, cable=None, f=None):
    """For a P controller: the frequency where the plant's phase (with the delay) reaches
    -180 degrees, and the Kp that makes the loop gain 1 there.  Returns (Kp, f_osc)."""
    f = np.linspace(1e3, FS / 2 - 1e3, 200000) if f is None else f
    H = plant_response(f, s, cable)
    ph = np.unwrap(np.angle(H))
    k = np.argmax(ph <= -np.pi)
    if k == 0:
        return np.nan, np.nan
    # interpolate the crossing
    f0 = np.interp(-np.pi, [ph[k], ph[k - 1]], [f[k], f[k - 1]])
    g = np.interp(f0, f, np.abs(H))
    return 1 / g, f0


def bandwidth_limit(tau):
    """The ceiling a loop with an integrator has for its unity-gain frequency, from a
    round-trip delay tau: the delay alone eats the integrator's remaining 90 degrees at
    f = 1 / (4 tau).  A comfortable loop sits at about 1 / (10 tau)."""
    return 1 / (4 * tau)


# ---- replaying the testbench's trace ----------------------------------------------------
def parse_settings(fields, prefix):
    """'kp ki kd en mode klag rword qshift ldelay' or 'en bias mode osel' into a Settings."""
    v = list(map(int, fields))
    if prefix == 1:
        return Settings(kp_word=v[0], ki_word=v[1], kd_word=v[2], enable=v[3], mode=v[4],
                        klag=v[5], rword=v[6], qshift=v[7], ldelay=v[8])
    return Settings(enable=v[0], bias=v[1], mode=v[2], osel=v[3])


def check(path):
    """Replay control_tb_trace.txt: every line is one sample,
    'n sp x e u y dac | kp ki kd en mode klag rword qshift ldelay | en bias mode osel'.
    The first group is what the testbench saw, the two settings groups are the registers
    at edge 1 and edge 2 of that sample."""
    loop = Loop()
    n_lines = n_bad = 0
    first_bad = None
    with open(path) as fh:
        for line in fh:
            if not line.strip() or line.startswith("#"):
                continue
            a, b, c = [p.split() for p in line.split("|")]
            n, sp, x, e, u, y, dac = map(int, a)
            s1, s2 = parse_settings(b, 1), parse_settings(c, 2)
            e_m, u_m, y_m = loop.step(sp, x, s1, s2)
            n_lines += 1
            if (e_m, u_m, y_m, loop.dac) != (e, u, y, dac):
                n_bad += 1
                if first_bad is None:
                    first_bad = (n, (e, u, y, dac), (e_m, u_m, y_m, loop.dac))
    print("%s: %d samples replayed, %d differ" % (path, n_lines, n_bad))
    if first_bad:
        print("  first difference at sample %d: gateware (e, u, y, dac) = %s, model %s" % first_bad)
    return n_bad == 0


def theory():
    cable = Cable()
    s = Settings(mode=0, kp=1.0)
    kp, f = critical_gain(s, cable)
    print("mode 0, the cable (gain %.3f, delay %d samples = %.0f ns): a P loop oscillates from"
          " Kp = %.3f at %.3f MHz (period %.1f samples = 2 x the delay)"
          % (GAIN, LOOP_DELAY, LOOP_DELAY * TS * 1e9, kp, f / 1e6, FS / f))
    print("   bandwidth ceiling with an integrator, 1/(4 tau): %.0f kHz; comfortable, 1/(10 tau): %.0f kHz"
          % (bandwidth_limit(LOOP_DELAY * TS) / 1e3, 1 / (10 * LOOP_DELAY * TS) / 1e3))
    for klag in (3, 4, 5, 6):
        for L in (0, 5):
            s = Settings(mode=1, klag=klag, ldelay=L)
            kp, f = critical_gain(s)
            print("mode 1, K = %d (tau = %3d samples = %5.2f us), L = %d (round trip %d samples):"
                  " Kp_crit = %6.2f at %.3f MHz" % (klag, 2**klag, 2**klag * TS * 1e6, L, 2 + L, kp, f / 1e6))
    for f0, qs in ((100e3, 10), (100e3, 8), (300e3, 9)):
        r = rword_from_f0(f0)
        s = Settings(mode=2, rword=r, qshift=qs)
        kp, f = critical_gain(s)
        print("mode 2, R = %5d (f0 = %.1f kHz), Q shift %2d (Q = %5.1f): Kp_crit = %.3f at %.3f MHz"
              % (r, f0_from_rword(r) / 1e3, qs, q_of(r, qs), kp, f / 1e6))


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--check":
        sys.exit(0 if check(sys.argv[2]) else 1)
    theory()
