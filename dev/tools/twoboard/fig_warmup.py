"""Figure: a board heats itself and its crystal moves (data/tb_warmup.npz)."""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, ".."))
from plotstyle import plt, save, C1, C2, C3
T = os.path.join(HERE, "..", "..")
z = np.load(os.path.join(T, "data", "tb_warmup.npz"))
L, H = z["lockin"], z["heater"]; on, off = float(z["on"]), float(z["off"])
t = L[:, 0]; ph = np.unwrap(np.angle(L[:, 1] + 1j * L[:, 2])) / (2 * np.pi)      # turns
# frequency of the heater board relative to the lock-in board, in 10 s windows
w = 10.0; edges = np.arange(0, t[-1], w); fc, ff = [], []
for a in edges:
    s = (t >= a) & (t < a + w)
    if s.sum() > 20:
        fc.append(a + w / 2); ff.append(np.polyfit(t[s], ph[s], 1)[0])
fc, ff = np.array(fc), np.array(ff)
fig, ax = plt.subplots(2, 1, figsize=(7.5, 6.4), sharex=True)
ax[0].axvspan(on / 60, off / 60, color=C2, alpha=0.12, lw=0)
ax[0].plot(fc / 60, ff / 1e6 * 1e9 / 1, ".", color=C1, markersize=3.5)
ax[0].set_ylabel("f_heater − f_other\n(parts per billion)")
ax[0].set_title("Heating one board with its own logic (shaded: heater on)")
code = H[:, 1].astype(int) & 63
table = {29: 29, 30: 40, 31: 50, 32: 60, 33: 70}
ax[1].axvspan(on / 60, off / 60, color=C2, alpha=0.12, lw=0)
ax[1].plot(H[:, 0] / 60, [table.get(c, np.nan) for c in code], ".", color=C3, markersize=2.5)
ax[1].set_ylabel("die temperature\nfrom the DTR (°C)"); ax[1].set_xlabel("time (minutes)")
ax[1].set_title("The FPGA's own thermometer (coarse: 29, 40, 50, 60 °C ...)")
save(fig, os.path.join(T, "..", "tutorial", "img", "tb_warmup.png"))
print("frequency (ppb): first 5 min %.1f, last 2 min of heating %.1f, last 5 min %.1f" %
      (ff[fc < 300].mean() * 1e3, ff[(fc > off - 120) & (fc < off)].mean() * 1e3, ff[fc > fc[-1] - 300].mean() * 1e3))
