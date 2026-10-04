"""Instructor's bench helper: drive the ADALM2000 (M2k) from Python.

Wiring assumed throughout the tutorials:
    module DAC output  -> M2k scope CH1+ (1-, ground)
    M2k W1 (AWG 1)     -> module ADC input

    import m2k
    m = m2k.M2k()                 # opens and calibrates
    m.w1_sine(1e5, 0.5, 0.0)      # 100 kHz, 0.5 V amplitude, 0 V offset
    m.w1_dc(0.3)
    t, v = m.ch1(1e8, 8192)       # 100 MS/s, 8192 samples of the DAC output
    m.close()

Needs libm2k's Python bindings (built from source into ~/.local, see the
tutorial's appendix).
"""
import numpy as np
import libm2k

IN_RATES = [1e3, 1e4, 1e5, 1e6, 1e7, 1e8]
OUT_RATES = [750, 7.5e3, 75e3, 750e3, 7.5e6, 75e6]


class M2k:
    def __init__(self, uri=None):
        self.ctx = libm2k.m2kOpen(uri) if uri else libm2k.m2kOpen()
        if self.ctx is None:
            raise RuntimeError("no M2k found")
        self.ctx.calibrateADC()
        self.ctx.calibrateDAC()
        self.ain = self.ctx.getAnalogIn()
        self.aout = self.ctx.getAnalogOut()
        self.trig = self.ain.getTrigger()
        self.ain.enableChannel(0, True)
        self.ain.enableChannel(1, True)
        # Otherwise libm2k hands back captures queued up earlier: stale data.
        self.ain.setKernelBuffersCount(1)
        self.set_range(0, high=False)
        self.set_range(1, high=False)

    # ------------------------------------------------------------ outputs
    def _play(self, ch, rate, samples):
        self.aout.setSampleRate(ch, rate)
        self.aout.setOversamplingRatio(ch, 1)
        self.aout.enableChannel(ch, True)
        self.aout.setCyclic(True)
        self.aout.push(ch, list(map(float, samples)))

    def w1_dc(self, volts, ch=0):
        self._play(ch, 750e3, [volts] * 256)

    def w1_sine(self, freq, amp, offset=0.0, ch=0, cycles=None):
        """Continuous sine.  Picks the fastest AWG rate that fits a whole
        number of cycles into a buffer of at most ~64k samples, so the
        frequency is exact to the AWG's own crystal."""
        best = None
        for rate in OUT_RATES[::-1]:
            spc = rate / freq                  # samples per cycle
            if spc < 4:
                continue
            ncyc = cycles or max(1, int(round(65536 / spc)))
            # The M2k's cyclic buffer must be a multiple of 4 samples (it
            # silently drops the remainder, which puts a phase jump at every
            # wrap), so round the length and accept the frequency that gives.
            n = 8 * int(round(ncyc * spc / 8))
            if n < 16 or n > 400000:
                continue
            best = (rate, ncyc, n)
            break
        if best is None:
            raise ValueError("can't make %g Hz" % freq)
        rate, ncyc, n = best
        k = np.arange(n)
        wave = offset + amp * np.sin(2 * np.pi * ncyc * k / n)
        self._play(ch, rate, wave)
        return rate * ncyc / n                  # the frequency actually made

    def w1_wave_exact(self, freq, wavefn, ch=0, nmax=800000, rate=None):
        """Play wavefn(phase_in_cycles) at a frequency as close to freq as the
        AWG allows: searches (rate, cycles, n) with n a multiple of 8.
        Returns the frequency actually made."""
        best = None
        for r in ([rate] if rate else OUT_RATES[::-1]):
            spc = r / freq
            if spc < 6:
                continue
            nmin = 8 * int(np.ceil(spc / 8))
            for n in range(max(nmin, 64), nmax + 1, 8):
                ncyc = int(round(n / spc))
                if ncyc < 1:
                    continue
                err = abs(r * ncyc / n - freq)
                if best is None or err < best[0] - 1e-12:
                    best = (err, r, ncyc, n)
                if err < freq * 1e-10:
                    break
            if best and best[0] < freq * 1e-9:
                break
        err, r, ncyc, n = best
        k = np.arange(n)
        self._play(ch, r, wavefn(ncyc * k / n))
        return r * ncyc / n

    def w1_off(self, ch=0):
        self.aout.stop(ch)

    # ------------------------------------------------------------- inputs
    def set_range(self, ch, high):
        self.ain.setRange(ch, libm2k.PLUS_MINUS_2_5V if high else libm2k.PLUS_MINUS_25V)

    def ch1(self, rate=1e8, n=8192, ch=0, trigger_level=None):
        """Capture n samples of scope channel ch (0 = CH1).  Free-running
        unless trigger_level (volts, rising edge on the same channel)."""
        self.ain.setSampleRate(rate)
        self.ain.setOversamplingRatio(1)
        if trigger_level is None:
            self.trig.setAnalogMode(ch, libm2k.ALWAYS)
        else:
            self.trig.setAnalogSource(ch)
            self.trig.setAnalogMode(ch, libm2k.ANALOG)
            self.trig.setAnalogCondition(ch, libm2k.RISING_EDGE_ANALOG)
            self.trig.setAnalogLevel(ch, trigger_level)
            self.trig.setAnalogDelay(0)
        self.trig.setAnalogStreamingFlag(False)
        self.ain.stopAcquisition()
        data = np.array(self.ain.getSamples(n))
        t = np.arange(n) / rate
        return t, data[ch]

    def close(self):
        try:
            self.aout.stop()
        except Exception:
            pass
        libm2k.contextClose(self.ctx)


def fit_sine(t, v, f_guess=None):
    """Four-parameter least-squares sine fit (IEEE 1057 style):
    v = A sin(2 pi f t + phi) + c.  Returns f, A, phi, c, rms residual."""
    from scipy.optimize import least_squares
    t = np.asarray(t, float)
    v = np.asarray(v, float)
    n = len(v)
    dt = t[1] - t[0]
    if f_guess is None:
        w = np.hanning(n)
        spec = np.abs(np.fft.rfft((v - v.mean()) * w))
        k = int(np.argmax(spec[1:])) + 1
        if 1 <= k < len(spec) - 1:
            a, b, c = np.log(spec[k - 1:k + 2] + 1e-30)
            k = k + 0.5 * (a - c) / (a - 2 * b + c)
        f_guess = k / (n * dt)

    def three(f):
        M = np.column_stack([np.sin(2 * np.pi * f * t), np.cos(2 * np.pi * f * t), np.ones(n)])
        coef, *_ = np.linalg.lstsq(M, v, rcond=None)
        return coef

    s0, c0, off0 = three(f_guess)
    tm = t.mean()                   # fit about the middle: decouples f from phi

    def resid(p):
        f, s, c, off = p
        x = 2 * np.pi * f * (t - tm)
        return s * np.sin(x) + c * np.cos(x) + off - v

    # re-express the 3-parameter solution about tm
    x0 = 2 * np.pi * f_guess * tm
    s1 = s0 * np.cos(x0) - c0 * np.sin(x0)
    c1 = s0 * np.sin(x0) + c0 * np.cos(x0)
    r = least_squares(resid, [f_guess, s1, c1, off0], x_scale=[1 / (n * dt), 1, 1, 1])
    f, s, c, off = r.x
    rms = np.sqrt(np.mean(r.fun ** 2))
    # phase referred back to t = 0
    phi = np.arctan2(c, s) - 2 * np.pi * f * tm
    phi = (phi + np.pi) % (2 * np.pi) - np.pi
    return f, np.hypot(s, c), phi, off, rms
