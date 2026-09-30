"""Tutorial 2b figure: the DDS sine (sine.v) on M2k CH1, time and spectrum.
Run with sine.bit loaded.  --replot redraws from the saved data."""
import sys, os
import numpy as np
from plotstyle import plt, save, dots, C1, INK2, MUTED
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data", "sine.npz")
IMG = os.path.join(HERE, "..", "img", "sine.png")

if "--replot" not in sys.argv:
    import m2k
    m = m2k.M2k()
    t, v = m.ch1(1e8, 65536, trigger_level=0.0)
    m.close()
    np.savez(DATA, t=t, v=v)
d = np.load(DATA)
t, v = d["t"], d["v"]
import m2k
f, A, ph, off, rms = m2k.fit_sine(t, v)

fig, (a, b) = plt.subplots(2, 1, figsize=(8, 6.2))
i0 = int(np.argmax((v[:-1] < 0) & (v[1:] >= 0)))       # a rising zero crossing
tt = (t - t[i0]) * 1e6
sel = (tt >= 0) & (tt < 2.5)
a.plot(tt[sel], v[sel], color=C1, lw=1.0, alpha=0.5)
dots(a, tt[sel], v[sel], C1, label="M2k samples, every 10 ns", size=3.5)
a.set_xlabel("time (µs)")
a.set_ylabel("DAC output (V)")
a.set_title("sine.v with TW = 85899346: f = %.4f MHz, amplitude %.2f V" % (f / 1e6, A))
a.legend(loc="upper right")
a.set_ylim(-4.6, 5.2)

w = np.blackman(len(v))
spec = np.abs(np.fft.rfft((v - v.mean()) * w))
fr = np.fft.rfftfreq(len(v), t[1] - t[0])
db = 20 * np.log10(spec / spec.max() + 1e-12)
sel = fr <= 25e6
b.plot(fr[sel] / 1e6, db[sel], color=C1, lw=1.0)
for h in (3, 7):
    j = np.argmin(abs(fr - h * f))
    k = j - 5 + int(np.argmax(db[j - 5:j + 6]))
    b.annotate("%d × f: %.0f dB" % (h, db[k]), (fr[k] / 1e6 + 0.3, db[k] + 1), color=INK2,
               fontsize=9, ha="left")
b.set_xlabel("frequency (MHz)")
b.set_ylabel("power relative to 1 MHz (dB)")
b.set_title("Its spectrum: odd harmonics from 8-bit rounding, all ≥ 46 dB below the tone")
b.set_ylim(-110, 8)
save(fig, IMG)
print("wrote", IMG, "f=%.3f Hz A=%.3f V" % (f, A))
