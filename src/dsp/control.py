#!/usr/bin/env python3
"""The laptop side of control.sv (7.06): set the loop up, step it, read the record back,
measure the response, and raise the gain until the loop sings: the pitch is the latency.

    python3 control.py --mode 1 --K 4 --kp 1 --ki 0.02 --step 40      # a step, on the board (finds the port)
    python3 control.py /dev/ttyUSB0 --mode 0 --kp 0.6 --ki 0.01 --step 20   # the real loop, through the cable
    python3 control.py --sim --mode 0 --kp 1.0 --step 20              # no board: control_model.py's loop
    python3 control.py --mode 1 --K 4 --open --step 40                # the plant alone (loop open)
    python3 control.py --mode 0 --gain-sweep 0.3:1.6:0.05             # raise Kp until it oscillates
    python3 control.py --mode 1 --K 4 --L 5 --gain-sweep 1:6:0.25     #   ...the lag, with 5 extra samples of delay
    python3 control.py --mode 1 --K 4 --kp 2 --ki 0.05 --m2k          # the M2k's W1 kicks the ADC, the DAC fights
    python3 control.py --mode 1 --K 4 --kp 2 --ki 0.05 --bode 2e3:3e6:25   # |S(f)|: rejection, and the waterbed
    python3 control.py ... -o dsp_control_step.npz --no-plot
    python3 control.py --show                      # the board's registers and live x, e, u, y ('?')
    python3 control.py --mode 1 ... --dump-bytes control_script.txt   # the bytes, for control_gl_tb.sv

    import control
    dev = control.Board()                              # or Board("/dev/ttyUSB0"), or Sim()
    cfg = control.Config(mode=1, klag=4, kp=1.0, ki=0.02, step=40)
    r = control.step_response(dev, cfg)                # t, sp, pv, e, u, and the metrics
    r = control.gain_sweep(dev, cfg, kps)              # ringing frequency and decay at each Kp

The board runs the loop all the time; the laptop only changes its registers and, with 'C',
asks for 16384 samples of two signals, which the gateware starts 64 samples before a rising
step of the setpoint.  A capture is 65536 bytes at 1 Mbaud: 0.66 s.

The gain sweep: with a proportional controller the loop's phase lag is the plant's plus
the latency's, and where that reaches 180 degrees the loop gain must stay below 1.  For a
pure delay tau (the cable) that is f = 1 / 2 tau, so the oscillation's period is 2 tau:
the latency, measured with a ruler on the record.  A lag or a resonator adds its own
phase, and the sweep shows the critical gain fall as the plant gets slower or the extra
delay ('L') grows.

Signals a capture can hold ('V'): adc (ADC - 128), sp (the setpoint), e, u (the
controller's output in DAC codes, after the rails) and y (the built-in plant's output).
The process variable "pv" is adc in mode 0 and y in modes 1-2.
"""
import argparse
import os
import struct
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import control_model as cm                          # noqa: E402

FS = cm.FS
TS = cm.TS
N = 16384                                           # samples in a capture
PRE = 64                                            # samples before the step
SIG = {"adc": 0, "sp": 1, "e": 2, "u": 3, "y": 4}
CODES_PER_VOLT = 25.35                              # the ADC (0.00)
VOLTS_PER_CODE = 0.0307                             # the DAC
ADC_REST = 127                                      # what 0 V at ADC IN reads (1.07: 0.776 x 128 + 27.5)


# ---- the settings ---------------------------------------------------------------------------
class Config:
    """Everything the laptop sets.  Gains are floats (Kp in codes per code, Ki per sample,
    Kd per sample of difference); the plant by mode, K (lag: 2^K samples), f0 and Q (the
    resonator); the step by setpoint, step (the jump J) and nstep (2^N samples a half)."""

    def __init__(self, mode=0, kp=0.5, ki=0.0, kd=0.0, bias=0, setpoint=0, step=20, nstep=12,
                 klag=4, f0=100e3, qshift=10, ldelay=0, decim=0, osel=0, enable=True, stepping=True):
        self.mode, self.kp, self.ki, self.kd, self.bias = mode, kp, ki, kd, bias
        self.setpoint, self.step, self.nstep = setpoint, step, nstep
        self.klag, self.f0, self.qshift, self.ldelay = klag, f0, qshift, ldelay
        self.decim, self.osel, self.enable, self.stepping = decim, osel, enable, stepping

    @property
    def rword(self):
        return cm.rword_from_f0(self.f0)

    def settings(self):
        """control_model.Settings with these values (the gains as the board's words)."""
        return cm.Settings(mode=self.mode, kp=self.kp, ki=self.ki, kd=self.kd, bias=self.bias,
                           klag=self.klag, rword=self.rword, qshift=self.qshift,
                           ldelay=self.ldelay, enable=self.enable, osel=self.osel)

    def copy(self, **kw):
        c = Config.__new__(Config)
        c.__dict__.update(self.__dict__)
        c.__dict__.update(kw)
        return c

    def describe(self):
        plant = {0: "the real world", 1: "lag, tau = %d samples = %.2f us" % (2**self.klag, 2**self.klag * TS * 1e6),
                 2: "resonator, f0 = %.1f kHz, Q = %.1f" % (cm.f0_from_rword(self.rword) / 1e3, cm.q_of(self.rword, self.qshift))}[self.mode]
        extra = " + %d samples of delay" % self.ldelay if self.mode and self.ldelay else ""
        return "mode %d (%s%s), Kp = %g, Ki = %g, Kd = %g, step %d -> %d" % (
            self.mode, plant, extra, self.kp, self.ki, self.kd, self.setpoint, self.setpoint + self.step)


# ---- the board --------------------------------------------------------------------------------
def find_port():
    """The first FTDI FT231X serial port (USB ID 0403:6015): the Icepi Zero's."""
    from serial.tools import list_ports
    for p in list_ports.comports():
        if (p.vid, p.pid) == (0x0403, 0x6015):
            return p.device
    raise SystemExit("No Icepi Zero found. Is it plugged in? (Or give its port.)")


STATUS_LEN = 32                                     # the '?' frame: 0xA5 + 31 bytes
STATUS_FIELDS = [("kp", ">h"), ("ki", ">h"), ("kd", ">h"), ("sp_base", ">h"), ("jump", ">h"),
                 ("rword", ">H"), ("nstep", "B"), ("stepping", "B"), ("bias", "b"), ("klag", "B"),
                 ("qshift", "B"), ("mode", "B"), ("osel", "B"), ("enable", "B"), ("ldelay", "B"),
                 ("decim", "B"), ("sel", "B"), ("x", ">h"), ("e", ">h"), ("u", ">h"), ("y", ">h")]


def parse_status(raw):
    """The 32 bytes the board sends for '?' -> a dict of its registers and live signals."""
    if len(raw) != STATUS_LEN or raw[0] != 0xA5:
        raise RuntimeError("status: got %d bytes%s: is control.bit loaded?"
                           % (len(raw), "" if len(raw) == 0 else ", first 0x%02x" % raw[0]))
    out, k = {}, 1
    for name, fmt in STATUS_FIELDS:
        n = struct.calcsize(fmt)
        out[name] = struct.unpack(fmt, raw[k:k + n])[0]
        k += n
    out["sel_a"], out["sel_b"] = (out["sel"] >> 4) & 7, out["sel"] & 7
    return out


def format_status(st):
    names = {v: k for k, v in SIG.items()}
    return ("mode %d  Kp %d/1024 Ki %d/65536 Kd %d/256  S %d J %d N %d T %d  B %d  K %d R %d Q %d  O %d E %d L %d X %d  V %s,%s"
            "  |  now: x %d e %d u %d y %d"
            % (st["mode"], st["kp"], st["ki"], st["kd"], st["sp_base"], st["jump"], st["nstep"], st["stepping"],
               st["bias"], st["klag"], st["rword"], st["qshift"], st["osel"], st["enable"], st["ldelay"], st["decim"],
               names.get(st["sel_a"], "?"), names.get(st["sel_b"], "?"), st["x"], st["e"], st["u"], st["y"]))


class ScriptPort:
    """A pretend serial port that writes down what control.py sends, as the script
    control_gl_tb.sv replays: 'g' before each write, 'b HH' per byte, 'c' where a capture
    is read back, 's' where a status frame is."""

    def __init__(self, path):
        self.f = open(path, "w")
        self.timeout = 1.0

    def write(self, data):
        self.f.write("g\n" + "".join("b %02x\n" % b for b in data))

    def read(self, n):
        self.f.write("c\n" if n == 4 * N else "s\n" if n == STATUS_LEN else "")
        self.f.flush()
        return b""

    def reset_input_buffer(self):
        pass

    def close(self):
        self.f.close()


class Board:
    """control.bit on an Icepi Zero, over its serial port.  dump=FILE writes the bytes it
    would send to FILE instead (for control_gl_tb.sv) and reads back nothing."""
    source = "measured"

    def __init__(self, port=None, baud=1_000_000, dump=None):
        self.dump = dump is not None
        if self.dump:
            self.ser = ScriptPort(dump)
        else:
            import serial                               # pip install pyserial
            self.ser = serial.Serial(port or find_port(), baud, timeout=3)
            time.sleep(0.02)
            self.ser.reset_input_buffer()               # the FT231X's junk byte on opening...
            time.sleep(0.005)                           # ...and the board's parser forgets it (1.3 ms)
        self.sent = {}

    def status(self):
        """Ask the board ('?') for its registers and the live x, e, u, y."""
        self.ser.reset_input_buffer()
        self.ser.timeout = 1.0
        self.ser.write(b"?")
        raw = self.ser.read(STATUS_LEN)
        return None if self.dump else parse_status(raw)

    def verify(self, cfg):
        """Read the registers back and compare with cfg; print one line either way."""
        st = self.status()
        if st is None:
            return None
        want = dict(kp=cm.kp_to_word(cfg.kp), ki=cm.ki_to_word(cfg.ki), kd=cm.kd_to_word(cfg.kd),
                    sp_base=int(np.clip(cfg.setpoint, -511, 511)), jump=int(np.clip(cfg.step, -1022, 1022)),
                    rword=int(cfg.rword), nstep=int(np.clip(cfg.nstep, 7 + cfg.decim, 24)),
                    stepping=int(cfg.stepping), bias=int(cfg.bias), klag=int(cfg.klag), qshift=int(cfg.qshift),
                    mode=int(cfg.mode), osel=int(cfg.osel), enable=int(cfg.enable), ldelay=int(cfg.ldelay),
                    decim=int(cfg.decim))
        bad = ["%s sent %d read %d" % (k, v, st[k]) for k, v in want.items() if st[k] != v]
        print("board: " + format_status(st))
        if bad:
            print("board: SETTINGS MISMATCH: " + "; ".join(bad))
        return not bad

    def _cmd(self, c, v=None, nbytes=1):
        if v is None:
            self.ser.write(c.encode())
        elif nbytes == 2:
            self.ser.write(c.encode() + struct.pack(">h", int(v)))
        else:
            self.ser.write(c.encode() + struct.pack(">b" if v < 0 else ">B", int(v)))

    def apply(self, cfg):
        """Send every register of cfg (only the ones that changed since the last apply)."""
        want = {"P": (cm.kp_to_word(cfg.kp), 2), "I": (cm.ki_to_word(cfg.ki), 2), "D": (cm.kd_to_word(cfg.kd), 2),
                "S": (int(np.clip(cfg.setpoint, -511, 511)), 2), "J": (int(np.clip(cfg.step, -1022, 1022)), 2),
                "N": (int(np.clip(cfg.nstep, 7 + cfg.decim, 24)), 1), "T": (int(cfg.stepping), 1),
                "B": (int(np.clip(cfg.bias, -128, 127)), 1), "K": (int(cfg.klag) & 15, 1),
                "R": (int(cfg.rword), 2), "Q": (int(cfg.qshift), 1), "M": (int(cfg.mode), 1),
                "O": (int(cfg.osel), 1), "E": (int(cfg.enable), 1), "L": (int(cfg.ldelay) & 63, 1),
                "X": (int(cfg.decim) & 15, 1)}
        for c, (v, nb) in want.items():
            if self.sent.get(c) != v:
                if c == "R":
                    self.ser.write(b"R" + struct.pack(">H", v))
                else:
                    self._cmd(c, v, nb)
                self.sent[c] = v
        self.cfg = cfg
        self.verify(cfg)

    def capture(self, a, b):
        """16384 samples of signals a and b (names from SIG), as two int arrays."""
        cfg = self.cfg
        self._cmd("V", (SIG[a] << 4) | SIG[b])
        self.ser.reset_input_buffer()
        self.ser.write(b"C")
        wait = (2.0**(cfg.nstep + 1) + N * 2.0**cfg.decim) / FS      # trigger wait plus the record
        self.ser.timeout = 2.0 + wait
        raw = self.ser.read(4 * N)
        if self.dump:
            return np.zeros(N, int), np.zeros(N, int)
        if len(raw) != 4 * N:
            raise RuntimeError("got %d of %d bytes: is control.bit loaded?" % (len(raw), 4 * N))
        w = np.frombuffer(raw, dtype=">i2").reshape(-1, 2)
        return w[:, 0].astype(int), w[:, 1].astype(int)

    def close(self):
        self.ser.close()


# ---- the pretend board ------------------------------------------------------------------------
class Sim:
    """control_model.Loop run exactly as the gateware runs it: the setpoint from the sample
    counter, the capture triggered 64 samples before a rising step, the ADC from the cable
    model (mode 0) or from a disturbance function (modes 1-2, where it is the M2k's W1)."""
    source = "simulated (control_model.py)"

    def __init__(self, cable=None, noise=0.1, seed=1):
        self.cable = cable or cm.Cable(noise=noise, rng=seed)
        self.loop = cm.Loop()
        self.c = 0
        self.disturb = None                             # f(t seconds) -> volts at ADC IN
        self.rng = np.random.default_rng(seed)
        self.noise = noise
        self.dac_log = []

    def apply(self, cfg):
        """New settings, then a full step period of running: the board gets at least that
        between the laptop's commands and its 'C' (a capture is exactly one period, so
        without this every change would land at the start of the next record)."""
        changed = getattr(self, "cfg", None) is None or vars(self.cfg) != vars(cfg)
        self.cfg = cfg
        self.loop.s = cfg.settings()
        if changed:
            self.run(2 ** (cfg.nstep + 1))

    def status(self):
        st = dict(kp=self.loop.s.kp, ki=self.loop.s.ki, kd=self.loop.s.kd, sp_base=self.cfg.setpoint,
                  jump=self.cfg.step, rword=self.cfg.rword, nstep=self.cfg.nstep, stepping=int(self.cfg.stepping),
                  bias=self.cfg.bias, klag=self.cfg.klag, qshift=self.cfg.qshift, mode=self.cfg.mode,
                  osel=self.cfg.osel, enable=int(self.cfg.enable), ldelay=self.cfg.ldelay, decim=self.cfg.decim,
                  sel_a=0, sel_b=3, x=0, e=self.loop.e_prev, u=self.loop.u, y=self.loop.y_state >> 8)
        return st

    def _sp(self, c):
        cfg = self.cfg
        v = cfg.setpoint + (cfg.step if cfg.stepping and (c >> cfg.nstep) & 1 else 0)
        return int(np.clip(v, -511, 511))

    def _x(self):
        if self.cfg.mode == 0:
            return self.cable.step(self.loop.dac) - 128
        v = self.disturb(self.c * TS) if self.disturb else 0.0
        adc = ADC_REST + CODES_PER_VOLT * v + self.noise * self.rng.standard_normal()
        return int(np.clip(round(adc), 0, 255)) - 128

    def _one(self):
        """One ADC sample.  Returns (sp, x, e, u, y, dac) for it."""
        self.c += 1                                     # the gateware counts at edge 2; sp uses c + 1
        sp = self._sp(self.c)
        x = self._x()
        e, u, y = self.loop.step(sp, x)
        self.dac_log.append(self.loop.dac)
        return sp, x, e, u, y, self.loop.dac

    def run(self, n):
        for _ in range(int(n)):
            self._one()

    def capture(self, a, b):
        cfg = self.cfg
        trig = (1 << cfg.nstep) - (PRE << cfg.decim)
        mask = (2 << cfg.nstep) - 1
        rec_a, rec_b = [], []
        if cfg.stepping:
            while (self.c + 1) & mask != trig & mask:   # the store looks at c before it counts
                self._one()
        skip = 1 << cfg.decim
        k = 0
        while len(rec_a) < N:
            vals = self._one()
            if k % skip == 0:
                d = dict(sp=vals[0], adc=vals[1], e=vals[2], u=vals[3], y=vals[4])
                rec_a.append(d[a])
                rec_b.append(d[b])
            k += 1
        return np.array(rec_a), np.array(rec_b)

    def close(self):
        pass


class SimW1:
    """The M2k's W1 and scope channel 1, pretend: W1 becomes the Sim's disturbance, CH1
    reads the Sim's DAC log back as volts."""

    def __init__(self, sim):
        self.sim = sim

    def w1_sine(self, f, amp, offset=0.0):
        self.sim.disturb = lambda t: offset + amp * np.sin(2 * np.pi * f * t)
        return f

    def w1_square(self, f, amp, offset=0.0):
        self.sim.disturb = lambda t: offset + amp * np.sign(np.sin(2 * np.pi * f * t))
        return f

    def w1_off(self):
        self.sim.disturb = None

    def ch1(self, rate=1e6, n=8192):
        """The last n / rate seconds of the DAC output, resampled: (t, volts)."""
        need = int(n * FS / rate)
        self.sim.run(max(0, need - len(self.sim.dac_log)))
        d = np.array(self.sim.dac_log[-need:], float)
        idx = np.minimum((np.arange(n) * FS / rate).astype(int), len(d) - 1)
        return np.arange(n) / rate, (d[idx] - 128) * VOLTS_PER_CODE

    def close(self):
        pass


def open_device(args):
    if args.sim:
        return Sim(cm.Cable(delay=args.delay, tau=args.tau, noise=args.noise), noise=args.noise)
    return Board(args.port, dump=getattr(args, "dump_bytes", None))


def open_w1(args, dev):
    """The M2k (dev/tools/m2k.py), or its pretend version on a Sim."""
    if isinstance(dev, Sim):
        return SimW1(dev)
    sys.path.insert(0, os.path.join(HERE, "..", "..", "dev", "tools"))
    import m2k
    m = m2k.M2k()
    m.w1_square = lambda f, amp, offset=0.0: m.w1_wave_exact(
        f, lambda ph: offset + amp * np.sign(np.sin(2 * np.pi * ph)))
    return m


# ---- a step ----------------------------------------------------------------------------------
def pv_name(cfg):
    return "adc" if cfg.mode == 0 else "y"


def metrics(sp, pv, cfg):
    """Rise time (10-90 %), overshoot, settling time (to within 2 % of the change, or one
    code) and the steady-state error, from the step at sample PRE.  Times in seconds."""
    dt = TS * 2**cfg.decim
    half = 2**(cfg.nstep - cfg.decim)                   # samples the new setpoint lasts
    w = pv[PRE:min(PRE + half, len(pv))].astype(float)
    y0 = pv[:PRE].astype(float).mean()
    y1 = w[-max(8, len(w) // 10):].mean()
    dy = y1 - y0
    out = dict(initial=y0, final=y1, change=dy, error=y1 - sp[PRE])
    if abs(dy) < 2:
        return out
    lo, hi = y0 + 0.1 * dy, y0 + 0.9 * dy
    i10 = int(np.argmax((w - lo) * np.sign(dy) >= 0))
    i90 = int(np.argmax((w - hi) * np.sign(dy) >= 0))
    out["rise"] = (i90 - i10) * dt
    out["delay"] = i10 * dt
    peak = w.max() if dy > 0 else w.min()
    out["overshoot"] = max(0.0, (peak - y1) * np.sign(dy) / abs(dy)) * 100
    band = max(0.02 * abs(dy), 1.0)
    outside = np.nonzero(np.abs(w - y1) > band)[0]
    out["settle"] = (outside[-1] + 1) * dt if len(outside) else 0.0
    return out


def step_response(dev, cfg):
    """Apply cfg, capture (sp, pv) and (e, u) around a rising step; return everything."""
    dev.apply(cfg)
    sp, pv = dev.capture("sp", pv_name(cfg))
    e, u = dev.capture("e", "u")
    t = np.arange(N) * TS * 2**cfg.decim
    r = dict(t=t, sp=sp, pv=pv, e=e, u=u, mode=cfg.mode, kp=cfg.kp, ki=cfg.ki, kd=cfg.kd,
             decim=cfg.decim, nstep=cfg.nstep, source=dev.source, describe=cfg.describe())
    r.update(metrics(sp, pv, cfg))
    return r


def print_metrics(r):
    s = "step %+d codes: " % r["change"]
    if "rise" in r:
        s += "delay %.0f ns, rise %.0f ns, overshoot %.0f %%, settles in %.2f us, " % (
            r["delay"] * 1e9, r["rise"] * 1e9, r["overshoot"], r["settle"] * 1e6)
    s += "steady-state error %+.1f codes" % r["error"]
    print(s)


# ---- the gain sweep -----------------------------------------------------------------------------
def envelope(w):
    """|analytic signal|: the amplitude of a ringing, sample by sample (a Hilbert transform
    by FFT, numpy only)."""
    n = len(w)
    X = np.fft.fft(w)
    h = np.zeros(n)
    h[0] = 1
    h[1:(n + 1) // 2] = 2
    if n % 2 == 0:
        h[n // 2] = 1
    return np.abs(np.fft.ifft(X * h))


def ringing(e, cfg):
    """The ringing after the step in an e record: its frequency (Hz) from the spectrum's
    peak, and its growth per cycle (the slope of the log of its envelope, in nepers per
    cycle: < 0 decays, > 0 grows), the rms of the window's last eighth and of its loudest
    eighth.  Frequency and growth are nan when there is nothing to measure (less than a
    code of ringing)."""
    dt = TS * 2**cfg.decim
    half = 2**(cfg.nstep - cfg.decim)
    w = e[PRE:min(PRE + half, len(e))].astype(float)
    w = w - w[-len(w) // 4:].mean()
    pieces = np.array_split(w, 8)
    rms = np.array([np.sqrt(np.mean(p**2)) for p in pieces])
    tail, loud = rms[-1], rms.max()
    if loud < 1.0:
        return np.nan, np.nan, tail, loud
    spec = np.abs(np.fft.rfft(w * np.hanning(len(w)), 4 * len(w)))
    spec[:4] = 0
    k = int(np.argmax(spec))
    if 1 <= k < len(spec) - 1:
        a, b, c = np.log(spec[k - 1:k + 2] + 1e-30)
        k = k + 0.5 * (a - c) / (a - 2 * b + c)
    f = k / (4 * len(w) * dt)
    env = envelope(w)
    n_per_cycle = max(1.0, 1 / (f * dt))
    # the envelope, smoothed over a cycle, while it is above half a code
    env = np.convolve(env, np.ones(int(n_per_cycle)) / int(n_per_cycle), mode="same")
    k0 = int(2 * n_per_cycle)                           # skip the step's own edge
    good = np.nonzero(env[k0:] > 0.5)[0] + k0
    if len(good) < 3 * n_per_cycle:
        return f, np.nan, tail, loud
    k1 = good[-1]
    t = np.arange(k0, k1 + 1)
    slope = np.polyfit(t, np.log(env[k0:k1 + 1] + 1e-9), 1)[0]      # nepers per sample
    return f, slope * n_per_cycle, tail, loud


def is_unstable(growth, tail, loud):
    """Growing, or sustained and loud.  Just below the critical gain the loop already hums:
    the ADC's own noise, amplified 1 / (1 - Kp G) times at the ringing frequency, so the
    tail is never quiet there; it counts as oscillating once it is loud (10 codes rms)
    and not dying away."""
    return (not np.isnan(growth) and growth > 0.0 and tail > 3.0) or (tail >= 0.7 * loud and tail > 10.0)


def kp_critical(kps, tails, unstable_at):
    """Where the hum diverges: its amplitude goes as 1 / (Kp_crit - Kp) below the critical
    gain, so 1 / amplitude is a straight line through zero at Kp_crit.  Fitted to the last
    three stable points with a measurable hum; falls back to half-way to the first unstable
    gain."""
    k = [(kp, t) for kp, t in zip(kps, tails) if kp < unstable_at and t >= 0.8]
    if len(k) >= 3:
        kk, tt = np.array(k[-3:]).T
        p = np.polyfit(kk, 1 / tt, 1)
        root = -p[1] / p[0]
        if p[0] < 0 and kk[-1] < root <= unstable_at:
            return root
    stable = [kp for kp in kps if kp < unstable_at]
    return 0.5 * (stable[-1] + unstable_at) if stable else unstable_at


def gain_sweep(dev, cfg, kps, stop=True):
    """Step the loop at each Kp (Ki and Kd as in cfg); watch the ringing.  Stops at the
    first Kp where it no longer dies away (if stop).  Returns the table and the two records
    either side of the critical gain, with the estimate between them."""
    rows, recs = [], {}
    last_stable = None
    print("%8s %10s %12s %10s" % ("Kp", "f_ring", "growth/cycle", "tail rms"))
    for kp in kps:
        c = cfg.copy(kp=float(kp))
        dev.apply(c)
        sp, e = dev.capture("sp", "e")
        f, g, tail, loud = ringing(e, c)
        unstable = is_unstable(g, tail, loud)
        rows.append((kp, f, g, tail))
        print("%8.3f %7.3f MHz %+12.4f %10.2f%s" % (kp, f / 1e6, g, tail, "   oscillates" if unstable else ""))
        if unstable:
            recs["unstable"] = dict(kp=kp, sp=sp, e=e, f=f)
            if stop:
                break
        else:
            last_stable = dict(kp=kp, sp=sp, e=e, f=f, growth=g)
    rows = np.array(rows, float)
    out = dict(kps=rows[:, 0], f_ring=rows[:, 1], growth=rows[:, 2], tail=rows[:, 3],
               decim=cfg.decim, nstep=cfg.nstep, mode=cfg.mode, source=dev.source, describe=cfg.describe())
    if last_stable:
        out.update(kp_stable=last_stable["kp"], e_stable=last_stable["e"], sp_stable=last_stable["sp"])
    if "unstable" in recs:
        u = recs["unstable"]
        out.update(kp_unstable=u["kp"], e_unstable=u["e"], sp_unstable=u["sp"], f_osc=u["f"])
        out["kp_crit"] = kp_critical(rows[:, 0], rows[:, 3], u["kp"])
        out["period"] = 1 / u["f"]
        out["tau"] = out["period"] / 2
    return out


def print_sweep(r):
    if "kp_crit" not in r:
        print("no oscillation in this range of Kp")
        return
    plant = cm.Settings(mode=r["mode"])
    print("critical gain Kp = %.3f; oscillates at %.3f MHz, period %.1f samples = %.0f ns"
          % (r["kp_crit"], r["f_osc"] / 1e6, r["period"] / TS, r["period"] * 1e9))
    if r["mode"] == 0:
        print("a pure delay oscillates at an odd number of half cycles per round trip: the loop delay is %.0f ns x (1, 3, 5, ...)"
              " = %.0f, %.0f or %.0f ns; the hum just below the critical gain, at 1/(2 tau), says which"
              % (r["tau"] * 1e9, r["tau"] * 1e9, 3 * r["tau"] * 1e9, 5 * r["tau"] * 1e9))
        print("(the model: Kp = %.3f at %.3f MHz for %d samples of delay and gain %.3f)"
              % (cm.critical_gain(plant, cm.Cable())[0], cm.critical_gain(plant, cm.Cable())[1] / 1e6,
                 cm.LOOP_DELAY, cm.GAIN))


# ---- disturbances from the M2k ----------------------------------------------------------------------
def decim_for(f, periods=10, max_decim=15):
    """A decimation that fits `periods` periods of f in a record, with f under Nyquist."""
    d = 0
    while d < max_decim and N * 2**d * TS * f < periods:
        d += 1
    while d > 0 and f >= FS / 2**(d + 1):
        d -= 1
    return d


def disturbance_demo(dev, w1, cfg, f_dist=5e3, amp=1.0):
    """A square wave from W1 into ADC IN while the loop is closed, then open.  Returns the
    ADC (x), the measurement, u, and the M2k's view of the DAC, for both."""
    c = cfg.copy(stepping=False, decim=decim_for(f_dist, 8))
    f_made = w1.w1_square(f_dist, amp)
    out = dict(f=f_made, amp=amp, decim=c.decim, source=dev.source, describe=cfg.describe(), mode=cfg.mode)
    for name, en in (("closed", True), ("open", False)):
        dev.apply(c.copy(enable=en))
        if isinstance(dev, Sim):
            dev.run(8192 + 8 * 2**cfg.qshift)           # the plant and the integrator settle
        else:
            time.sleep(0.05)
        x, e = dev.capture("adc", "e")
        _, u = dev.capture("sp", "u")
        t_m, v_m = w1.ch1(1e6, 8192)
        meas = c.setpoint - e
        out[name] = dict(x=x, e=e, u=u, meas=meas, t_m2k=t_m, v_m2k=v_m,
                         rms_x=x.std(), rms_meas=meas.std(), rms_u=u.std())
        print("loop %-6s: disturbance %.1f codes rms at the ADC, %.1f codes rms left in the measurement, u %.1f codes rms"
              % (name, x.std(), meas.std(), u.std()))
    out["t"] = np.arange(N) * TS * 2**c.decim
    w1.w1_off()
    rej = out["closed"]["rms_meas"] / max(out["closed"]["rms_x"], 1e-9)
    out["rejection_db"] = 20 * np.log10(max(rej, 1e-9))
    print("the loop leaves %.1f %% of the disturbance: %.1f dB" % (100 * rej, out["rejection_db"]))
    return out


def tone_at(x, f, dt):
    """The complex amplitude of a tone at f in x (least squares on cos and sin)."""
    t = np.arange(len(x)) * dt
    M = np.column_stack([np.cos(2 * np.pi * f * t), np.sin(2 * np.pi * f * t), np.ones(len(x))])
    coef, *_ = np.linalg.lstsq(M, np.asarray(x, float), rcond=None)
    return coef[0] - 1j * coef[1]


def sensitivity_sweep(dev, w1, cfg, freqs, amp=0.5):
    """A sine from W1 at each frequency; |S| = what is left in the measurement over what
    the ADC saw (both from the same capture, so the clock and the scale cancel), and the
    phase; and |u| / |x|, the control effort.  Compared with control_model.sensitivity."""
    c = cfg.copy(stepping=False)
    S, fm = [], []
    print("%10s %9s %9s %9s" % ("f", "|S|", "dB", "model"))
    for f in freqs:
        d = decim_for(f, 12)
        cc = c.copy(decim=d)
        dev.apply(cc)
        f_made = w1.w1_sine(f, amp)
        if isinstance(dev, Sim):
            dev.run(8192 + 8 * 2**cfg.qshift)           # the plant and the integrator settle
        else:
            time.sleep(0.02)
        x, e = dev.capture("adc", "e")
        dt = TS * 2**d
        X, E = tone_at(x, f_made, dt), tone_at(e, f_made, dt)
        s = -E / X                                      # e = sp - meas, sp constant
        S.append(s)
        fm.append(f_made)
        s_m = abs(cm.sensitivity(f_made, c.settings()))
        print("%8.1f kHz %9.3f %+8.1f %9.3f" % (f_made / 1e3, abs(s), 20 * np.log10(abs(s)), s_m))
    w1.w1_off()
    fm, S = np.array(fm), np.array(S)
    ff = np.logspace(np.log10(fm[0] / 2), np.log10(min(fm[-1] * 2, FS / 2)), 600)
    S_model = cm.sensitivity(ff, c.settings())
    k = np.argmax(np.abs(S) >= 1) if np.any(np.abs(S) >= 1) else len(S) - 1
    print("|S| reaches 1 near %.0f kHz (the loop bandwidth); the worst amplification %.2f (+%.1f dB) at %.0f kHz"
          % (fm[k] / 1e3, abs(S).max(), 20 * np.log10(abs(S).max()), fm[np.argmax(abs(S))] / 1e3))
    return dict(f=fm, S=S, f_model=ff, S_model=S_model, amp=amp, source=dev.source,
                describe=cfg.describe(), mode=cfg.mode)


# ---- plots ------------------------------------------------------------------------------------
def plot_step(r):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    t = r["t"] * 1e6
    ax[0].step(t, r["sp"], where="post", color="k", lw=1, label="setpoint")
    ax[0].plot(t, r["pv"], ".-", ms=2, lw=0.8, label="measured (%s)" % ("ADC" if r["mode"] == 0 else "y"))
    ax[0].set_ylabel("ADC codes")
    ax[0].legend(loc="lower right")
    ax[0].set_title(r["describe"] + "\n" + r["source"])
    ax[1].plot(t, r["u"], ".-", ms=2, lw=0.8, color="C1", label="u (controller output, DAC codes)")
    ax[1].set_xlabel("time (µs)")
    ax[1].set_ylabel("DAC codes")
    ax[1].legend(loc="lower right")
    for a in ax:
        a.grid(True)
    span = 8 * 2**(r["nstep"] - r["decim"])
    ax[1].set_xlim(0, min(t[-1], t[min(len(t) - 1, span)]))
    fig.tight_layout()
    plt.show()


def plot_sweep(r):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    ax[0].plot(r["kps"], r["growth"], "o-")
    ax[0].axhline(0, color="k", lw=0.8)
    ax[0].set_xlabel("Kp")
    ax[0].set_ylabel("growth of the ringing per cycle (ln)")
    ax[0].set_title("decays below the critical gain, grows above")
    if "e_unstable" in r:
        dt = TS * 2**r["decim"]
        e = r["e_unstable"]
        t = np.arange(len(e)) * dt * 1e6
        ax[1].plot(t, e, ".-", ms=2, lw=0.8)
        ax[1].set_xlim(0, t[min(len(t) - 1, PRE + 600)])
        ax[1].set_title("Kp = %.3f: %.3f MHz, period %.1f samples" % (r["kp_unstable"], r["f_osc"] / 1e6, r["period"] / TS))
        ax[1].set_xlabel("time (µs)")
        ax[1].set_ylabel("e (codes)")
    for a in ax:
        a.grid(True)
    fig.suptitle(r["describe"] + "  (" + r["source"] + ")")
    fig.tight_layout()
    plt.show()


def plot_disturbance(r):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    t = r["t"] * 1e3
    for name, c in (("open", "C3"), ("closed", "C0")):
        d = r[name]
        ax[0].plot(t, d["meas"], lw=0.8, color=c, label="measurement, loop %s (%.1f codes rms)" % (name, d["rms_meas"]))
        ax[1].plot(t, d["u"], lw=0.8, color=c, label="u, loop %s" % name)
    ax[0].plot(t, r["closed"]["x"], lw=0.6, color="k", alpha=0.4, label="the disturbance at the ADC")
    ax[0].set_ylabel("codes")
    ax[1].set_ylabel("DAC codes")
    ax[1].set_xlabel("time (ms)")
    for a in ax:
        a.legend(loc="upper right", fontsize=8)
        a.grid(True)
    ax[0].set_title("%.1f kHz square wave from W1 into ADC IN; %s\n%s" % (r["f"] / 1e3, r["describe"], r["source"]))
    fig.tight_layout()
    plt.show()


def plot_bode(r):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 1, figsize=(8, 4.5))
    ax.semilogx(r["f_model"], 20 * np.log10(np.abs(r["S_model"])), color="C1", lw=1, label="model: 1 / (1 + C H)")
    ax.semilogx(r["f"], 20 * np.log10(np.abs(r["S"])), "o", label="|S| measured")
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xlabel("frequency of the disturbance (Hz)")
    ax.set_ylabel("|S| (dB): what is left of it")
    ax.set_title("sensitivity: " + r["describe"] + "\n" + r["source"])
    ax.legend()
    ax.grid(True, which="both")
    fig.tight_layout()
    plt.show()


# ---- the command line --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("port", nargs="?", help="serial port (default: the first Icepi Zero)")
    ap.add_argument("--sim", action="store_true", help="control_model.py instead of a board")
    ap.add_argument("--mode", type=int, default=0, help="plant: 0 real world, 1 lag, 2 resonator")
    ap.add_argument("--kp", type=float, default=0.5)
    ap.add_argument("--ki", type=float, default=0.0, help="per sample")
    ap.add_argument("--kd", type=float, default=0.0, help="per sample of difference")
    ap.add_argument("--bias", type=int, default=0, help="DAC = 128 + bias + u")
    ap.add_argument("--setpoint", type=int, default=0, help="ADC codes about mid-scale")
    ap.add_argument("--step", type=int, default=20, help="the setpoint jumps by this")
    ap.add_argument("--N", dest="nstep", type=int, default=12, help="the step lasts 2^N samples (default 12: 164 us)")
    ap.add_argument("--K", dest="klag", type=int, default=4, help="mode 1: time constant 2^K samples")
    ap.add_argument("--f0", type=float, default=100e3, help="mode 2: resonance (Hz)")
    ap.add_argument("--Q", dest="qshift", type=int, default=10, help="mode 2: damping 2^-Q per sample")
    ap.add_argument("--L", dest="ldelay", type=int, default=0, help="modes 1-2: extra samples of delay")
    ap.add_argument("--decim", type=int, default=0, help="capture 1 sample in 2^decim")
    ap.add_argument("--osel", type=int, default=0, help="modes 1-2: the DAC plays 0 = u, 1 = y")
    ap.add_argument("--open", action="store_true", help="loop open: the step goes straight to the plant")
    ap.add_argument("--gain-sweep", metavar="LO:HI:STEP", help="Kp values to try until the loop oscillates")
    ap.add_argument("--m2k", action="store_true", help="W1 square wave into ADC IN, loop closed then open")
    ap.add_argument("--bode", metavar="F0:F1:N", help="W1 sines: the sensitivity function at N frequencies")
    ap.add_argument("--f-dist", type=float, default=5e3, help="--m2k: the square wave's frequency")
    ap.add_argument("--amp", type=float, default=None, help="W1 amplitude in volts (1 V = 25 codes)")
    ap.add_argument("--delay", type=int, default=cm.LOOP_DELAY, help="--sim mode 0: samples around the loop")
    ap.add_argument("--tau", type=float, default=0.0, help="--sim mode 0: an RC between DAC and ADC (s)")
    ap.add_argument("--noise", type=float, default=0.1, help="--sim: ADC noise, codes rms")
    ap.add_argument("--show", action="store_true", help="print the board's registers and live signals, then stop")
    ap.add_argument("--dump-bytes", metavar="FILE", help="write the bytes this run would send to FILE (control_gl_tb.sv replays it); no board")
    ap.add_argument("-o", "--out", help="save the results (.npz)")
    ap.add_argument("--no-plot", action="store_true")
    args = ap.parse_args()
    if args.show:
        print("board: " + format_status(Board(args.port).status()))
        return

    cfg = Config(mode=args.mode, kp=args.kp, ki=args.ki, kd=args.kd, bias=args.bias, setpoint=args.setpoint,
                 step=args.step, nstep=args.nstep, klag=args.klag, f0=args.f0, qshift=args.qshift,
                 ldelay=args.ldelay, decim=args.decim, osel=args.osel, enable=not args.open)
    dev = open_device(args)
    print(cfg.describe(), "(loop open)" if args.open else "")
    if args.dump_bytes:
        args.no_plot = True
    if args.gain_sweep:
        lo, hi, st = map(float, args.gain_sweep.split(":"))
        r = gain_sweep(dev, cfg, np.arange(lo, hi + st / 2, st))
        print_sweep(r)
        plot = plot_sweep
    elif args.m2k:
        w1 = open_w1(args, dev)
        r = disturbance_demo(dev, w1, cfg, args.f_dist, args.amp or 1.0)
        w1.close()
        plot = plot_disturbance
    elif args.bode:
        f0, f1, n = args.bode.split(":")
        w1 = open_w1(args, dev)
        r = sensitivity_sweep(dev, w1, cfg, np.logspace(np.log10(float(f0)), np.log10(float(f1)), int(n)), args.amp or 0.5)
        w1.close()
        plot = plot_bode
    else:
        r = step_response(dev, cfg)
        print_metrics(r)
        plot = plot_step
    dev.close()
    if args.out:
        np.savez(args.out, **{k: v for k, v in r.items() if not isinstance(v, dict)},
                 **{"%s_%s" % (k, kk): vv for k, v in r.items() if isinstance(v, dict) for kk, vv in v.items()})
        print("saved", args.out)
    if not args.no_plot:
        plot(r)


if __name__ == "__main__":
    main()
