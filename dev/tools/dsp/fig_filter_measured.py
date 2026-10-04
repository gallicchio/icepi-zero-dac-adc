"""7.03 figure: the loadable filter (filter.sv + filter.py) measured on the M2k bench,
against scipy.

dsp_filter_measured.png: |H| measured (dots) against the quantized design (line) for four
filters loaded by filter.py: the 16-sample moving average, the 2 MHz low-pass, the edge
detector and the one-pole RC at 1 MHz; the moving average's impulse response as the M2k's
scope saw it, with the predicted staircase; and the phase of the RC and the edge detector
if it was measured (--ch2), else the residuals of the four |H| measurements.

    # on the bench (filter.bit loaded; W1 -> ADC IN, DAC OUT -> scope 1), in src/dsp:
    python3 filter.py --moving 16   --m2k -o ../../dev/data/dsp_moving.npz
    python3 filter.py --lowpass 2e6 --m2k -o ../../dev/data/dsp_lowpass.npz
    python3 filter.py --edge        --m2k -o ../../dev/data/dsp_edge.npz
    python3 filter.py --rc 1e6      --m2k -o ../../dev/data/dsp_rc.npz
    python3 filter.py --moving 16   --m2k --impulse -o ../../dev/data/dsp_impulse.npz
    python3 fig_filter_measured.py          # reads those five, writes the figure
    python3 fig_filter_measured.py --sim    # no bench (--sim --replot: redraw): filter.py's sweep
                                            # and impulse_trace run on
                                            # a model of the bench (the ADC's 25.35 codes/V and 8
                                            # bits, filter.simulate, the DAC's 30.7 mV/code held
                                            # 40 ns, the scope's 12 bits), written to
                                            # dev/data/dsp_sim_*.npz; the figure says "simulated"
"""
import os
import sys
import types

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.join(HERE, "..", "..", "..")
sys.path.insert(0, os.path.join(HERE, ".."))                  # plotstyle, m2k (fit_sine)
sys.path.insert(0, os.path.join(TOP, "src", "dsp"))           # filter
from plotstyle import plt, save, dots, C1, C2, C3, INK, INK2, MUTED, GRID, SURFACE   # noqa: E402
import filter as flt                                          # noqa: E402

IMG = os.path.join(TOP, "tutorial", "img", "dsp_filter_measured.png")
DATA = os.path.join(TOP, "dev", "data")
SIM = "--sim" in sys.argv
NAMES = [("moving", dict(moving=16), C1), ("lowpass", dict(lowpass=2e6), C2),
         ("edge", dict(edge=True), C3), ("rc", dict(rc=1e6), C2)]
ADC_PER_V, ADC_ZERO = 25.35, -1.3           # codes per volt, and the code (minus 128) at 0 V (0.00)
DAC_ZERO = -0.02                             # volts at code 128


def data_path(name):
    return os.path.join(DATA, "dsp_%s%s.npz" % ("sim_" if SIM else "", name))


def namespace(**kw):
    d = dict(lowpass=None, highpass=None, bandpass=None, taps=15, moving=None, edge=False, rc=None,
             butter=None, high=False, b=None, a=None)
    d.update(kw)
    return types.SimpleNamespace(**d)


# ---- a model of the bench, for --sim ------------------------------------------------------
class FakeBoard:
    def __init__(self):
        self.src, self.out, self.bq, self.aq = 0, 0, [8192], [8192]

    def upload(self, bq, aq):
        self.bq, self.aq = bq, aq

    def set_src(self, s):
        self.src = s

    def set_out(self, o):
        self.out = o


class FakeScope:
    """W1's sine into the ADC, the board's filter, the DAC held for 40 ns, scope channel 1 at
    100 MS/s; W1 and the board's clock unrelated (a random phase every capture)."""

    def __init__(self, board, seed=7):
        self.board, self.rng = board, np.random.default_rng(seed)
        import m2k
        self.m2k = m2k

    def sine(self, f, amp):
        self.f, self.amp = f, amp
        return f

    def fit(self, t, v, f):
        return self.m2k.fit_sine(t, v, f)

    def grab(self, n=flt.N, rate=1e8, high=True, trigger=None, pre=0):
        b = self.board
        nadc = n // 4 + 400
        # the board's clock against the scope's: ADC sample k is taken at scope time
        # k x 40 ns + s x 10 ns + delta, and the DAC's code for it occupies scope samples 4k + s ..
        s, delta, phi = self.rng.integers(4), self.rng.uniform(0, 1e-8), self.rng.uniform(0, 2 * np.pi)
        tk = np.arange(nadc) / flt.FS + s / rate + delta
        if b.src == 0:
            x = np.clip(np.round(ADC_PER_V * self.amp * np.sin(2 * np.pi * self.f * tk + phi) + ADC_ZERO),
                        -128, 127).astype(int)
        else:
            x = np.roll(flt.stimulus(b.src, nadc), 300)
        y = flt.simulate(b.bq, b.aq, x) if b.out == 0 else x
        v = np.concatenate([np.zeros(s), flt.DAC_V * np.repeat(y, 4) + DAC_ZERO])   # the DAC, held 40 ns
        v = v + 0.002 * self.rng.standard_normal(len(v))
        lsb = 5.0 / 4096 if high else 50.0 / 4096
        v = np.clip(np.round(v / lsb) * lsb, -2.5 if high else -25, 2.5 if high else 25)
        t4 = np.arange(len(v)) / rate
        v2 = self.amp * np.sin(2 * np.pi * self.f * t4 + phi)         # W1 itself, on scope 2
        v2 = np.round(v2 / lsb) * lsb
        if trigger is None:
            return t4[:n], v[1200:1200 + n], v2[1200:1200 + n]
        level, rising = trigger
        for i in range(pre + 1, len(v)):
            if (rising and v[i - 1] < level <= v[i]) or (not rising and v[i - 1] > level >= v[i]):
                return t4[:n], v[i - pre:i - pre + n], v2[i - pre:i - pre + n]
        raise RuntimeError("no trigger")


def simulate_bench():
    board = FakeBoard()
    scope = FakeScope(board)
    freqs = np.geomspace(100e3, 12e6, 40)
    for name, kw, _ in NAMES:
        b, a, title = flt.design(namespace(**kw))
        bq, aq = flt.quantize(b), flt.quantize(a)
        board.upload(bq, aq)
        r = flt.sweep(board, scope, bq, aq, freqs, 1.0, ch2=True, verbose=False)
        Hp = flt.response(bq, aq, r["f"])
        err = flt.db(r["H"]) - flt.db(Hp)
        print("%-8s %-32s measured - predicted: %.2f dB rms (prediction > -40 dB)"
              % (name, title, np.sqrt(np.mean(err[flt.db(Hp) > -40]**2))))
        np.savez(data_path(name), name=title, b=bq, a=aq, bf=b, af=a, fs=flt.FS, H_pred=Hp, amp=1.0,
                 source="simulated (a model of the bench and filter.simulate)", **r)
    b, a, title = flt.design(namespace(moving=16))
    bq, aq = flt.quantize(b), flt.quantize(a)
    board.upload(bq, aq)
    t, v, h = flt.impulse_trace(board, scope, bq, aq)
    np.savez(data_path("impulse"), name=title, b=bq, a=aq, bf=b, af=a, fs=flt.FS, t=t, v=v, h_codes=h,
             source="simulated (a model of the bench and filter.simulate)")


# ---- the figure ----------------------------------------------------------------------------
def main():
    if SIM and "--replot" not in sys.argv:          # --sim --replot: redraw from dsp_sim_*.npz
        simulate_bench()
    missing = [data_path(n) for n in [x[0] for x in NAMES] + ["impulse"] if not os.path.exists(data_path(n))]
    if missing:
        sys.exit("missing %s\nrun filter.py --m2k on the bench as the docstring says, or use --sim" % ", ".join(missing))
    runs = {name: np.load(data_path(name), allow_pickle=True) for name, _, _ in NAMES}
    imp = np.load(data_path("impulse"), allow_pickle=True)
    source = str(runs["moving"]["source"])
    ff = np.geomspace(1e5, 12.5e6, 500)

    fig, axs = plt.subplots(2, 3, figsize=(10, 6.8))
    panels = [axs[0, 0], axs[0, 1], axs[0, 2], axs[1, 0]]
    have_phase = any(np.isfinite(runs[n]["phase"]).any() for n, _, _ in NAMES)
    for ax, (name, kw, color) in zip(panels, NAMES):
        d = runs[name]
        Hp = flt.response(d["b"], d["a"], ff)
        ax.semilogx(ff / 1e6, flt.db(Hp), color=color, lw=1.4, label="scipy, the quantized design")
        dots(ax, d["f"] / 1e6, flt.db(d["H"]), INK, label="measured", size=4)
        err = flt.db(d["H"]) - flt.db(d["H_pred"])
        sel = flt.db(d["H_pred"]) > -40
        ax.set_title("%s\n%.2f dB rms from the design" % (d["name"], np.sqrt(np.mean(err[sel]**2))), fontsize=9.5)
        ax.set_xlim(0.1, 12.5)
        ax.set_ylim(-62, 16)
        ax.set_ylabel("|H| (dB)")
        ax.set_xlabel("frequency (MHz)")
        ax.grid(True, which="both")
        if name == "rc":
            fc = float(kw["rc"])
            ax.semilogx(ff / 1e6, flt.db(1 / (1 + 1j * ff / fc)), color=INK2, lw=0.9, ls="--", label="an RC, 1/(1 + jf/f$_c$)")
        ax.legend(fontsize=7.5, loc="upper left" if name == "edge" else "lower left")
    # the impulse response on the scope
    ax = axs[1, 1]
    t, v, h = imp["t"] * 1e6, imp["v"], imp["h_codes"]
    ax.plot(t, v, color=INK, lw=1.0, label="DAC OUT on the scope, 100 MS/s")
    # the predicted staircase, aligned on the first half-height sample
    k0 = int(np.argmax(np.abs(h) >= 0.5 * np.abs(h).max()))
    i0 = int(np.argmax(np.abs(v - DAC_ZERO) >= 0.5 * np.abs(v - DAC_ZERO).max()))
    best = None
    for shift in range(-4, 5):
        start = i0 - 4 * k0 + shift
        pred = np.full(len(v), DAC_ZERO)
        n = min(len(h) * 4, len(v) - start)
        if start < 0 or n <= 0:
            continue
        pred[start:start + n] = (flt.DAC_V * np.repeat(h, 4) + DAC_ZERO)[:n]
        e = np.sum((pred - v)**2)
        if best is None or e < best[0]:
            best = (e, pred)
    ax.plot(t, best[1], color=C1, lw=1.2, ls="--", label="predicted: 64 × h[k] × 30.7 mV, held 40 ns")
    ax.set_xlim(t[0], min(t[-1], t[i0] + 1.6))
    ax.set_xlabel("time (µs)")
    ax.set_ylabel("DAC OUT (V)")
    ax.set_ylim(min(v) - 0.01, max(v) + 0.5 * (max(v) - min(v)) + 0.01)
    ax.set_title("the impulse response on the scope:\n%s" % str(imp["name"]).split(",")[0], fontsize=9.5)
    ax.legend(fontsize=7.5, loc="upper right")
    # the phase, or the residuals
    ax = axs[1, 2]
    if have_phase:
        for name, color in (("rc", C2), ("edge", C3)):
            d = runs[name]
            ax.semilogx(ff / 1e6, np.degrees(np.angle(flt.response(d["b"], d["a"], ff))), color=color, lw=1.2,
                        label="%s, scipy" % str(d["name"]).split(",")[0])
            pred = np.angle(flt.response(d["b"], d["a"], d["f"]))         # unwrap the dots next to the line
            ph = pred + (d["phase"] - pred + np.pi) % (2 * np.pi) - np.pi
            dots(ax, d["f"] / 1e6, np.degrees(ph), color, size=4)
        ax.set_ylabel("phase (degrees)")
        ax.set_ylim(-200, 200)
        ax.set_title("the phase,\nmeasured against W1 on scope 2", fontsize=9.5)
        ax.legend(fontsize=7.5, loc="lower left")
    else:
        for name, kw, color in NAMES:
            d = runs[name]
            ax.semilogx(d["f"] / 1e6, flt.db(d["H"]) - flt.db(d["H_pred"]), ".-", color=color, lw=0.8, ms=4,
                        label=str(d["name"]).split(",")[0])
        ax.set_ylim(-3, 3)
        ax.set_ylabel("measured − predicted (dB)")
        ax.set_title("measured minus the design, at each frequency", fontsize=9.5)
        ax.legend(fontsize=7.5, loc="upper left")
    ax.set_xlim(0.1, 12.5)
    ax.set_xlabel("frequency (MHz)")
    ax.grid(True, which="both")
    fig.text(0.995, 0.995, source, ha="right", va="top", size=8, color=MUTED)
    fig.suptitle("filter.sv with four filters loaded by filter.py: measured against the design",
                 x=0.01, ha="left", fontsize=11.5, weight="bold", y=0.995)
    save(fig, IMG)
    print("wrote", IMG, "(%s)" % source)


if __name__ == "__main__":
    main()
