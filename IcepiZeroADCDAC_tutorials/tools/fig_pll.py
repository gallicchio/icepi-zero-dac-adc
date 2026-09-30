"""Part 4 figure: lock-in sweeps through the 16.5 cm cable with the DAC at 50 MS/s
(lockin.v) and at 100 MS/s (lockin_pll.v).  Data from cable_sweep.py:

    python3 cable_sweep.py 16cm_dac50  --fmax 24.9e6 --repeat 3                 # lockin.bit
    python3 cable_sweep.py 16cm_dac100 --fmax 24.9e6 --repeat 3 --fclk 100e6    # lockin_pll.bit
    python3 cable_sweep.py 16cm_dac100_hi --fmin 25.1e6 --fmax 49.9e6 --repeat 3 --fclk 100e6

The 50 MS/s DAC's output has an image at 50 MHz - f, which the 25 MS/s ADC folds
back onto f.  At 100 MS/s the image is at 100 MHz - f, where the analog chain
passes almost nothing, so that sweep shows the response alone.  From it we
predict what the 50 MS/s reading *should* be without its image (T), and how big
its image is (the response at 50 MHz - f): the difference Z50 - T should be the
size of the image."""
import os
import numpy as np
from plotstyle import plt, save, dots, C1, C2, INK2, MUTED
HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, "..", "img", "pll.png")
DATA = os.path.join(HERE, "..", "data")
a = np.load(os.path.join(DATA, "cable_16cm_dac50.npz"))
b = np.load(os.path.join(DATA, "cable_16cm_dac100.npz"))
c = np.load(os.path.join(DATA, "cable_16cm_dac100_hi.npz"))
f = a["f"]
assert np.allclose(f, b["f"], atol=1)
Z50, Z100lo = a["z"].mean(0), b["z"].mean(0)
f100 = np.concatenate([b["f"], c["f"]])
Z100 = np.concatenate([Z100lo, c["z"].mean(0)])


def bad(x):
    """Simple fractions of 25 MHz: the reference repeats after a few samples
    and the readings scatter (see "Try this" in Part 4).  Leave them out."""
    return np.any([abs(x - q) < 60e3 for q in np.arange(1, 21) * 2.5e6], axis=0)


ok = ~bad(f)
ok100 = ~bad(f100)
sinc = np.sinc                  # numpy's sinc(x) is sin(pi x)/(pi x)

# the two DACs' timing differs by one DAC clock period: fit it where images are negligible
lo = (f < 5e6) & ok
dtau = -np.polyfit(f[lo], np.unwrap(np.angle(Z50 / Z100lo))[lo], 1)[0] / 2 / np.pi


def as_dac50(g):
    """The response at frequency g as the 50 MS/s DAC would see it, image-free:
    the 100 MS/s measurement, with the other sinc droop and timing."""
    z = np.interp(g, f100, Z100.real) + 1j * np.interp(g, f100, Z100.imag)
    return z * sinc(g / 50e6) / sinc(g / 100e6) * np.exp(-2j * np.pi * g * dtau)


T = as_dac50(f)                 # the 50 MS/s tone without its image
err = abs(Z50 - T)              # what the image did to the reading
image = abs(as_dac50(50e6 - f))  # how big the image is at the ADC

fig, (p1, p2, p3) = plt.subplots(3, 1, figsize=(8, 8.6))
MHz = f / 1e6

p1.plot(f100[ok100] / 1e6, abs(Z100[ok100]), color=C2, label="DAC at 100 MS/s (lockin_pll.v)")
p1.plot(MHz[ok], abs(Z50[ok]), color=C1, label="DAC at 50 MS/s (lockin.v)")
for x in (12.5, 25):
    p1.axvline(x, color=MUTED, lw=0.8, ls=":")
p1.text(12.7, 0.25, "ADC Nyquist", color=INK2, fontsize=8)
p1.text(25.2, 0.25, "50 MS/s DAC's Nyquist", color=INK2, fontsize=8)
p1.set_ylabel("amplitude at the ADC (V)")
p1.set_xlabel("frequency (MHz)")
p1.set_xlim(0, 50)
p1.set_ylim(0, 4.8)
p1.set_title("DAC → 16.5 cm RG-316 → ADC: amplitude with the DAC at 50 and 100 MS/s")
p1.legend(loc="upper right")

sel = ok & ~bad(50e6 - f)
dots(p2, MHz[sel], err[sel], C1, label="|50 MS/s reading − image-free prediction|", size=4)
p2.plot(MHz[sel], image[sel], color=MUTED, lw=1.4, label="the image's size: the response at 50 MHz − f")
p2.set_ylabel("volts at the ADC")
p2.set_xlabel("frequency (MHz)")
p2.set_xlim(0, 25)
p2.set_title("The 50 MS/s reading's error is its image, folded back onto f")
p2.legend(loc="upper left")

fit = (f <= 8e6) & ok
for z, c_, lab in ((Z50, C1, "50 MS/s"), (Z100lo, C2, "100 MS/s")):
    ph = np.unwrap(np.angle(z))
    p = np.polyfit(f[fit], ph[fit], 1)
    res = np.degrees(ph - np.polyval(p, f))
    dots(p3, MHz[ok], res[ok], c_, label="%s: delay %.1f ns" % (lab, -p[0] / 2 / np.pi * 1e9), size=4)
p3.axvline(8, color=MUTED, lw=0.8, ls=":")
p3.set_ylabel("phase − straight line (deg)")
p3.set_xlabel("frequency (MHz)")
p3.set_xlim(0, 25)
p3.set_title("Phase after a straight-line fit up to 8 MHz: the same bend at both rates")
p3.legend(loc="lower left")
save(fig, IMG)
print("wrote", IMG, "; the DACs' timing differs by %.2f ns" % (dtau * 1e9))
for fm in (4, 8, 12.4, 16, 20.1, 24.9):
    i = np.argmin(abs(MHz - fm))
    print("%5.1f MHz: 50 MS/s %.3f V, 100 MS/s %.3f V, image-free 50 MS/s %.3f V, error %.3f V, image %.3f V"
          % (MHz[i], abs(Z50[i]), abs(Z100lo[i]), abs(T[i]), err[i], image[i]))
