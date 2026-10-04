"""Part 7 figure: the LiteX lock-in's reading vs the amplitude W1 applies to the
ADC, from 4 V down to 1 mV, at 100 kHz.  Needs the bare-metal SoC loaded and
firmware.bin booted.  --replot redraws."""
import sys, os, re, time
import numpy as np
from plotstyle import plt, save, dots, C1, INK2, MUTED
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data", "lockin_linearity.npz")
IMG = os.path.join(HERE, "..", "..", "tutorial", "img", "lockin_linearity.png")
F0 = 100e3
PPM = -2.8          # the FPGA's crystal relative to the M2k's, measured in Part 4
N_LOG2 = 24
LSB = 1 / 25.35     # volts per ADC code


def li(c):
    out = c.cmd("li %d %d" % (F0, N_LOG2), timeout=5)
    m = re.search(r"Hz\s+(-?[\d.]+) mV\s+(-?[\d.]+) deg", out)
    return float(m.group(1)) / 1000, float(m.group(2))


if "--replot" not in sys.argv:
    import m2k
    from console import Console
    c = Console()
    c.sync()
    m = m2k.M2k()
    amps = np.geomspace(4.0, 1e-3, 19)
    got = []
    for a in amps:
        m.w1_wave_exact(F0 * (1 + PPM * 1e-6), lambda cy, a=a: a * np.sin(2 * np.pi * cy))
        time.sleep(0.3)
        li(c)                                         # settle
        r = [li(c)[0] for _ in range(3)]
        got.append(r)
        print("W1 %.4f V  ->  lock-in %s V" % (a, " ".join("%.5f" % x for x in r)))
    m.w1_dc(0.0)
    time.sleep(0.3)
    zero = [li(c)[0] for _ in range(5)]
    print("W1 at 0 V -> %s" % zero)
    m.close()
    np.savez(DATA, amps=amps, got=np.array(got), zero=np.array(zero))

d = np.load(DATA)
amps, got, zero = d["amps"], d["got"], d["zero"]
fig, ax = plt.subplots(figsize=(7, 5))
x = np.array([1e-3, 5])
ax.loglog(x, x * got[0].mean() / amps[0], color=MUTED, lw=1.2,
          label="proportional (slope 1), through the 4 V point")
dots(ax, amps, got.mean(1), C1, label="lock-in reading, 2²⁴ samples", size=7)
ax.axvline(LSB, color=INK2, lw=0.8)
ax.annotate("one ADC code\n(39.5 mV)", (LSB * 1.1, 1.5e-3), color=INK2, fontsize=9)
ax.axhline(zero.mean(), color=INK2, lw=0.8)
ax.annotate("reading with W1 at 0 V: DAC crosstalk", (1.1e-3, zero.mean() * 0.62), color=INK2, fontsize=9)
ax.set_xlabel("amplitude applied to the ADC by W1 (V)")
ax.set_ylabel("amplitude the lock-in reports (V)")
ax.set_title("Tracks the input down to about one ADC code, then meets a floor")
ax.legend(loc="upper left")
ax.set_xlim(7e-4, 6)
ax.set_ylim(min(7e-5, zero.mean() / 2), 6)
save(fig, IMG)
print("wrote", IMG)
