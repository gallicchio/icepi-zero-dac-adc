"""Part 4 figure: lock-in sweeps of DAC -> RG-316 -> ADC with two cable lengths.
Data from cable_sweep.py (data/cable_1m.npz, data/cable_16cm.npz)."""
import os
import numpy as np
from plotstyle import plt, save, dots, C1, C2, INK2, MUTED
HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, "..", "..", "tutorial", "img", "cable.png")
a = np.load(os.path.join(HERE, "..", "data", "cable_1m.npz"))
b = np.load(os.path.join(HERE, "..", "data", "cable_16cm.npz"))
f = a["f"]
za, zb = a["z"].mean(0), b["z"].mean(0)
# frequencies that are simple fractions of 25 MHz: the lock-in's references
# repeat after a few samples there and the readings scatter; leave them out
bad = np.zeros(len(f), bool)
for q in np.arange(1, 11) * 2.5e6:
    bad |= abs(f - q) < 60e3
ok = ~bad & (f < 12.4e6)
fit = ok & (f <= 8e6)
MHz = f / 1e6


def delay(z):
    p = np.polyfit(f[fit], np.unwrap(np.angle(z))[fit], 1)
    return -p[0] / 2 / np.pi


ta, tb = delay(za), delay(zb)
fig, (p1, p2, p3) = plt.subplots(3, 1, figsize=(8, 8.4), sharex=True)

p1.plot(MHz[ok], abs(za[ok]), color=C1, label="101.5 cm")
p1.plot(MHz[ok], abs(zb[ok]), color=C2, label="16.5 cm")
p1.set_ylabel("amplitude at the ADC (V)")
p1.set_title("DAC → RG-316 → ADC, measured with lockin.sv: amplitude")
p1.legend(loc="lower left", ncol=2)
p1.set_ylim(3.4, 4.4)

for z, t, c, lab in ((za, ta, C1, "101.5 cm"), (zb, tb, C2, "16.5 cm")):
    p2.plot(MHz[ok], np.degrees(np.unwrap(np.angle(z))[ok]), color=c,
            label="%s: slope = %.1f ns" % (lab, t * 1e9))
p2.set_ylabel("phase (degrees)")
p2.set_title("Phase: a straight line whose slope is the delay (−360° × f × τ)")
p2.legend(loc="lower left")

d = np.degrees(np.unwrap(np.angle(za / zb)))
p = np.polyfit(f[fit], d[fit], 1)
dots(p3, MHz[ok], d[ok], C1, label="phase(101.5 cm) − phase(16.5 cm)", size=4)
x = np.array([0, 12.4])
p3.plot(x, np.polyval(p, x * 1e6), color=MUTED, lw=1.2,
        label="fit up to 8 MHz: %.2f ns for 85.0 cm" % (-p[0] / 360 * 1e9))
p3.set_ylabel("phase difference (degrees)")
p3.set_xlabel("frequency (MHz)")
p3.set_title("The cable alone: 4.58 ns per metre, velocity factor 0.73")
p3.legend(loc="lower left")
save(fig, IMG)
print("wrote", IMG, "delays %.3f %.3f ns" % (ta * 1e9, tb * 1e9))
