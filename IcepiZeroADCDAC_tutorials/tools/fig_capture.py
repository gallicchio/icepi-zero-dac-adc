"""Tutorial 3 figure: ADC captures through capture.v, driven by the M2k's W1.
Run with capture.bit loaded.  --replot redraws from the saved data."""
import sys, os, time
import numpy as np
from plotstyle import plt, save, dots, C1, C2, INK2, MUTED
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
DATA = os.path.join(HERE, "..", "data", "capture.npz")
IMG = os.path.join(HERE, "..", "img", "capture.png")
ADC_V = lambda code: (np.asarray(code, float) - 126.7) / 25.35   # measured, see tutorial

if "--replot" not in sys.argv:
    import m2k, capture
    m = m2k.M2k()
    f1 = m.w1_sine(1.1e6, 4.0)
    time.sleep(0.3)
    _, c1 = capture.capture("/dev/ttyUSB0", 0)
    f2 = m.w1_sine(10.1e6, 4.0)
    time.sleep(0.3)
    _, c2a = capture.capture("/dev/ttyUSB0", 0)
    _, c2b = capture.capture("/dev/ttyUSB0", 1)
    m.w1_dc(0.0)
    m.close()
    np.savez(DATA, f1=f1, c1=c1, f2=f2, c2a=c2a, c2b=c2b)

d = np.load(DATA)
import m2k
fig, (a, b) = plt.subplots(2, 1, figsize=(8, 6.4))

# ---- panel a: 1.1 MHz at 25 MS/s --------------------------------------------
fs = 25e6
t = np.arange(len(d["c1"])) / fs
sel = t < 3e-6
v = ADC_V(d["c1"])
f, A, ph, off, rms = m2k.fit_sine(t, v)
tf = np.linspace(0, 3e-6, 2000)
a.plot(tf * 1e6, off + A * np.sin(2 * np.pi * f * tf + ph), color=MUTED, lw=1.0,
       label="least-squares sine fit")
dots(a, t[sel] * 1e6, v[sel], C1, label="ADC samples, every 40 ns")
a.set_xlabel("time (µs)")
a.set_ylabel("ADC input (V)")
a.set_title("A 1.1 MHz, 4 V sine from the M2k, captured by capture.v at 25 MS/s")
a.legend(loc="upper right", ncol=2)
a.set_ylim(-5.2, 6.2)

# ---- panel b: 10.1 MHz at 25 MS/s and at 12.5 MS/s ---------------------------
va, vb = ADC_V(d["c2a"]), ADC_V(d["c2b"])
ta = np.arange(len(va)) / 25e6
tb = np.arange(len(vb)) / 12.5e6
# show the true 10.1 MHz wave, aligned to the 12.5 MS/s record
fB, AB, phB, offB, _ = m2k.fit_sine(tb, vb)          # finds the 2.4 MHz alias
tf = np.linspace(0, 1.2e-6, 4000)
selb = tb < 1.2e-6
f2 = float(d["f2"]) * (1 - 2.85e-6)                   # as the FPGA's clock sees it
# the alias at fs - f has the opposite phase sense: sin(2pi f t + phi) = -sin(2pi (fs-f) t - phi)
b.plot(tf * 1e6, offB - AB * np.sin(2 * np.pi * f2 * tf - phB), color=MUTED, lw=1.0,
       label="the real 10.1 MHz input")
b.plot(tf * 1e6, offB + AB * np.sin(2 * np.pi * fB * tf + phB), color=C2, lw=1.0, alpha=0.6)
dots(b, tb[selb] * 1e6, vb[selb], C2, label="samples at 12.5 MS/s (-d 1)", size=6)
b.annotate("the samples trace out 12.5 − 10.1 = %.1f MHz" % (fB / 1e6),
           (0.36, 4.75), color=INK2, fontsize=9)
b.set_xlabel("time (µs)")
b.set_ylabel("ADC input (V)")
b.set_title("Aliasing: 10.1 MHz sampled below twice its frequency looks like 2.4 MHz")
b.legend(loc="lower right", ncol=2)
b.set_ylim(-6.2, 5.6)
save(fig, IMG)
print("wrote", IMG, " fit a: f=%.4f MHz A=%.3f V rms=%.1f mV; alias %.4f MHz" % (f / 1e6, A, rms * 1e3, fB / 1e6))
