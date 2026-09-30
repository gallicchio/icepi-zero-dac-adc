"""Part 5 figure: the LiteX function generator's four waveforms, set from the
firmware shell ("fg 250000 255 <wave>") and captured on M2k CH1.
Needs the SoC loaded and firmware.bin booted.  --replot redraws."""
import sys, os, time
import numpy as np
from plotstyle import plt, save, C1, INK2
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data", "funcgen.npz")
IMG = os.path.join(HERE, "..", "img", "funcgen.png")
WAVES = ["sine", "square", "triangle", "sawtooth"]
CMDS = ["fg 250000 255 sine", "fg 250000 255 square", "fg 250000 191 triangle",
        "fg 250000 128 sawtooth"]

if "--replot" not in sys.argv:
    import m2k
    from console import Console
    c = Console()
    c.sync()
    m = m2k.M2k()
    out = {}
    for w, cmd in zip(WAVES, CMDS):
        print(c.cmd(cmd))
        time.sleep(0.1)
        t, v = m.ch1(1e8, 4096, trigger_level=0.0)
        out[w] = v
    out["t"] = t
    c.cmd("fg 1000000")
    m.close()
    np.savez(DATA, **out)

d = np.load(DATA)
t = (d["t"] - d["t"][len(d["t"]) // 2]) * 1e6        # the M2k triggers mid-buffer
fig, axes = plt.subplots(2, 2, figsize=(8, 5.4), sharex=True, sharey=True)
for ax, w, cmd in zip(axes.flat, WAVES, CMDS):
    sel = (t > -2) & (t < 10)
    ax.plot(t[sel], d[w][sel], color=C1, lw=1.2)
    ax.set_title(cmd, fontsize=10, fontweight="normal", family="monospace")
    ax.set_ylim(-4.6, 4.6)
for ax in axes[1]:
    ax.set_xlabel("time (µs)")
for ax in axes[:, 0]:
    ax.set_ylabel("DAC output (V)")
fig.suptitle("The LiteX function generator, driven from C: 250 kHz, four waveforms",
             x=0.02, ha="left", fontsize=11, fontweight="bold")
save(fig, IMG)
print("wrote", IMG)
