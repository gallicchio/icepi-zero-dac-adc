"""The figures for 1.08's "The idea": a lock-in's multiply-and-average, done in numpy on
real samples.  awgcap.sv (src/twoboard) plays a waveform through the DAC, a cable takes
it to the ADC, and awgcap records 16384 samples in step with the waveform, so the
reference phase of every sample is known.

    load awgcap.bit on a board whose DAC is cabled to its ADC, then
    python3 fig_lockin_idea.py [--port PORT]      (--replot: redraw from the saved data)

Writes ../../tutorial/img/lockin_idea_block.png, lockin_idea_time.png and
lockin_idea_interferer.png.
"""
import os
import sys

import numpy as np
from plotstyle import plt, save, dots, C1, C2, C3, INK2, MUTED

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src", "twoboard"))
DATA = os.path.join(HERE, "..", "data", "lockin_idea.npz")
IMG = os.path.join(HERE, "..", "..", "tutorial", "img")

N = 16384                 # samples in the DAC's loop (50 MS/s) and in a record (25 MS/s)
K_SIG, K_INT = 328, 393   # whole cycles per loop: 1.0010 MHz and 1.1993 MHz
F_SIG, F_INT = K_SIG * 50e6 / N, K_INT * 50e6 / N
CODES_PER_VOLT = 25.35
n = np.arange(N)

if "--replot" not in sys.argv:
    import awgcap
    port = sys.argv[sys.argv.index("--port") + 1] if "--port" in sys.argv else None
    if port is None:
        from serial.tools import list_ports
        port = next(p.device for p in list_ports.comports() if (p.vid, p.pid) == (0x0403, 0x6015))
    waves = {
        "big":   128 + 127 * np.sin(2 * np.pi * K_SIG * n / N),
        "small": 128 + 16 * np.sin(2 * np.pi * K_SIG * n / N),
        "mixed": 128 + 16 * np.sin(2 * np.pi * K_SIG * n / N) + 100 * np.sin(2 * np.pi * K_INT * n / N),
    }
    rec = {}
    for name, w in waves.items():
        awgcap.upload(port, w)
        rec[name] = np.array([awgcap.record(port) for _ in range(3)])
    np.savez(DATA, **rec)
d = np.load(DATA)

# ADC sample i is taken while the DAC plays its sample 2i.  The DAC played sin(psi);
# calling it cos(theta), as 1.08 does, puts theta a quarter turn behind psi.
theta = 2 * np.pi * K_SIG * (2 * n) / N - np.pi / 2
ref_cos = np.cos(theta)


def lockin(codes, k=K_SIG):
    """The lock-in, in volts: products with the reference and their running averages."""
    th = 2 * np.pi * k * (2 * n) / N - np.pi / 2
    v = (codes - codes.mean()) / CODES_PER_VOLT
    xs, ys = v * np.cos(th), -v * np.sin(th)        # X + jY = < v e^{-j th} >
    run = np.arange(1, N + 1)
    return v, xs, ys, np.cumsum(xs) / run, np.cumsum(ys) / run


def amp_phase(X, Y):
    return 2 * np.hypot(X[-1], Y[-1]), np.degrees(np.arctan2(Y[-1], X[-1]))


for name in ["big", "small", "mixed"]:
    for r in d[name]:
        a, p = amp_phase(*lockin(r)[3:])
        print(f"{name:6s} amplitude {a:.4f} V  phase {p:8.2f} deg")
A_INT = amp_phase(*lockin(d["mixed"][0], K_INT)[3:])[0]
A_SMALL = amp_phase(*lockin(d["small"][0])[3:])[0]
print(f"interferer {A_INT:.3f} V")

t_us = n / 25e6 * 1e6
# For the time plots, start the clock where the stimulus cos(theta) peaks (theta = 0)
t_c = (n - N / (8 * K_SIG)) / 25e6 * 1e6

# ---- figure 1: the idea, on a clean sine -------------------------------------
v, xs, ys, X, Y = lockin(d["big"][0])
amp, ph = amp_phase(X, Y)
fig, ax = plt.subplots(3, 1, figsize=(8, 8.6))
sel = (t_c >= 0) & (t_c < 3.0)
a = ax[0]
a.plot(t_c[sel], amp * ref_cos[sel], color=MUTED, lw=1.0, label="the reference, cos(ωt), drawn at the same height")
dots(a, t_c[sel], v[sel], C1, label="what came back: ADC samples, 25 MS/s")
a.set_ylim(-5, 7.5)
a.set_ylabel("ADC input (V)")
a.set_xlabel("time (µs)")
a.set_title("1. Send cos(ωt), record what comes back. It's later than the reference: phase φ")
a.legend(loc="upper left", fontsize=8, ncol=2)
a = ax[1]
dots(a, t_c[sel], xs[sel], C1, label="signal × cos(ωt)")
dots(a, t_c[sel], ys[sel], C2, label="signal × (−sin ωt)")
a.axhline(X[-1], color=C1, lw=1)
a.axhline(Y[-1], color=C2, lw=1)
a.set_ylim(-4.5, 4.5)
a.set_ylabel("product (V)")
a.set_xlabel("time (µs)")
a.set_title("2. Multiply each sample by cos(ωt) and by −sin(ωt) (lines: their averages)")
a.legend(loc="upper left", fontsize=8, ncol=2)
a = ax[2]
a.semilogx(t_us[1:], X[1:], color=C1, label="X = average of signal × cos")
a.semilogx(t_us[1:], Y[1:], color=C2, label="Y = average of signal × (−sin)")
a.set_xlabel("averaging time (µs)")
a.set_ylabel("running average (V)")
a.set_title("3. Average.  amplitude = 2√(X² + Y²),  phase = atan2(Y, X)")
a.annotate(f"X = {X[-1]:.3f} V, Y = {Y[-1]:.3f} V:  amplitude {amp:.3f} V, phase {ph:.1f}°",
           (t_us[-1], Y[-1]), xytext=(-5, 22), textcoords="offset points", ha="right", color=INK2, fontsize=9)
a.legend(loc="lower left", fontsize=8)
save(fig, os.path.join(IMG, "lockin_idea_time.png"))

# ---- figure 2: picking a small signal out from under a big one --------------
v, xs, ys, X, Y = lockin(d["mixed"][0])
v0, _, _, X0, Y0 = lockin(d["small"][0])
fig, ax = plt.subplots(3, 1, figsize=(8, 8.6))
sel = (t_c >= 0) & (t_c < 6.0)
a = ax[0]
dots(a, t_c[sel], v[sel], C1, size=3.5, label=f"ADC samples: {A_SMALL:.3f} V at 1.001 MHz + {A_INT:.2f} V at 1.199 MHz")
a.plot(t_c[sel], A_SMALL * np.cos(theta[sel] + np.radians(ph)), color=C2, lw=1.2,
       label=f"the part we want: {A_SMALL:.3f} V at 1.001 MHz")
a.set_ylim(-3.5, 5.5)
a.set_ylabel("ADC input (V)")
a.set_xlabel("time (µs)")
a.set_title("A small signal under a big one at a nearby frequency")
a.legend(loc="upper left", fontsize=8)
a = ax[1]
f = np.fft.rfftfreq(N, 1 / 25e6) / 1e6
w = np.hanning(N)
spec = lambda x: 20 * np.log10(np.abs(np.fft.rfft(x * w)) / w.sum() * 2 + 1e-6)
a.plot(f, spec(v), color=C1, lw=0.8, label="the signal")
a.plot(f, spec(xs), color=C2, lw=0.8, label="signal × cos(ωt): every frequency moves by ±1.001 MHz")
dc = 20 * np.log10(abs(xs.mean()))
a.plot([0], [dc], "o", color=C2, markersize=6, clip_on=False)
a.annotate("ours, now at 0 Hz: the X we want", (0.0, dc), xytext=(0.3, 10),
           arrowprops=dict(arrowstyle="->", color=INK2, lw=0.8), color=INK2, fontsize=9)
a.annotate("the big one, now at\n0.2 and 2.2 MHz", (0.198, 3), xytext=(0.55, -30),
           arrowprops=dict(arrowstyle="->", color=INK2, lw=0.8), color=INK2, fontsize=9)
a.set_xlim(-0.03, 3)
a.set_ylim(-80, 20)
a.set_xlabel("frequency (MHz)")
a.set_ylabel("amplitude (dB re 1 V)")
a.set_title("Multiplying shifts every frequency: ours to 0 Hz, everything else elsewhere")
a.legend(loc="upper right", fontsize=8)
a = ax[2]
R = 2 * np.hypot(X, Y)
R0 = 2 * np.hypot(X0, Y0)
a.semilogx(t_us[1:], R[1:], color=C1, label="amplitude, from the mixed signal")
a.semilogx(t_us[1:], R0[1:], color=C3, lw=1, label="the small signal, recorded alone")
a.set_ylim(0, 2.5)
a.set_xlabel("averaging time (µs)")
a.set_ylabel("amplitude (V)")
a.set_title("Averaging is a low-pass filter: the longer it averages, the less of the big one is left")
a.annotate(f"{R[-1]:.3f} V  (alone: {R0[-1]:.3f} V)", (t_us[-1], R[-1]), xytext=(-5, 16),
           textcoords="offset points", ha="right", color=INK2, fontsize=9)
a.legend(loc="upper right", fontsize=8)
save(fig, os.path.join(IMG, "lockin_idea_interferer.png"))
print("wrote lockin_idea_time.png, lockin_idea_interferer.png")


# ---- figure 0: the block diagram (no data) ------------------------------------
def block_diagram():
    import schemdraw
    import schemdraw.dsp as dsp
    from PIL import Image, ImageOps
    SURFACE = "#fcfcfb"
    schemdraw.config(fontsize=11, bgcolor=SURFACE, lw=1.3)
    with schemdraw.Drawing(show=False) as d:
        osc = dsp.Box(w=2.4, h=1.3).label("phase\naccumulator\n(DDS)").anchor("E").at((0, 0))
        dsp.Arrow().at(osc.E).right(1.3).label("cos(ωt)", "top", fontsize=10)
        dsp.Dac().label("DAC", "bottom")
        dsp.Arrow().right(0.8)
        dsp.Box(w=2.6, h=1.3).label("your device\n(cable, filter,\ncrystal...)")
        dsp.Arrow().right(2.6).label("a cos(ωt + φ)\n+ everything else", "top", fontsize=10)
        dsp.Adc().label("ADC", "bottom")
        dsp.Line().right(0.6)
        node = dsp.Dot()
        for sign, ref, out, eq in [(1, "cos(ωt)", "X", "X = (a/2) cos φ"), (-1, "−sin(ωt)", "Y", "Y = (a/2) sin φ")]:
            dsp.Line().at(node.center).up(1.6 * sign) if sign > 0 else dsp.Line().at(node.center).down(1.6)
            dsp.Arrow().right(0.9)
            m = dsp.Mixer().anchor("W").label("multiply", "bottom" if sign > 0 else "top", fontsize=10)
            dsp.Arrow().at(m.E).right(0.9)
            f = dsp.Box(w=2.1, h=1.0).anchor("W").label("average\nfor a time T", fontsize=10)
            dsp.Arrow().at(f.E).right(1.0).label(eq, "right", fontsize=11)
            if sign > 0:
                dsp.Line().at(osc.N).up(2.6)
                dsp.Line().tox(m.N).label(ref, "top", fontsize=10)
                dsp.Arrow().toy(m.N)
            else:
                dsp.Line().at(osc.S).down(2.6)
                dsp.Line().tox(m.S).label(ref, "bottom", fontsize=10)
                dsp.Arrow().toy(m.S)
        path = os.path.join(IMG, "lockin_idea_block.png")
        d.save(path, dpi=130, transparent=False)
    im = Image.open(path).convert("RGBA")
    flat = Image.alpha_composite(Image.new("RGBA", im.size, SURFACE), im).convert("RGB")
    ImageOps.expand(flat, border=16, fill=SURFACE).save(path)


block_diagram()
print("wrote lockin_idea_block.png")
