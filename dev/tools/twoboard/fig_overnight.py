"""Figure: two crystals through a night (lockin_log.py on both boards), and each one
against the laptop's NTP-disciplined clock.

    python3 fig_overnight.py data/tb_beat_1M_overnight.npz [data/tb_pc_adjtimex.npz]

Upper: the beat, f_B - f_A, from each board's lock-in phase (mirror images, so one sign
is flipped), in 60 s blocks.  Lower: each board's crystal against the laptop clock, from
when its results arrived: result k is taken at k * 2^20 / 25 MHz of the board's own time.
The optional second file is a log of the laptop kernel's clock discipline (adjtimex, every 10 s):
its frequency steps, at each systemd-timesyncd poll, are marked.
"""
import datetime
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, ".."))
from plotstyle import plt, save, dots, C1, C2, C3
T = os.path.join(HERE, "..", "..")
z = np.load(sys.argv[1]); f0 = float(z["f"])
tau0 = 2**20 / 25e6 * (int(z["every"]) if "every" in z.files else 1)     # board time per row
BLOCK = 60.0


def beat_blocks(d):
    """Beat (ppm of f0) in BLOCK-second pieces of the board's own time."""
    ph = np.unwrap(np.angle(d[:, 1] + 1j * d[:, 2])) / (2 * np.pi)
    t = np.arange(len(d)) * tau0                                 # no lines were lost
    out = []
    for t1 in np.arange(0, t[-1] - BLOCK, BLOCK):
        s = (t >= t1) & (t < t1 + BLOCK)
        if s.sum() > 10:
            out.append((d[s, 0].mean(), np.polyfit(t[s], ph[s], 1)[0] / f0 * 1e6))
    return np.array(out)


def vs_pc(d, block=600.0):
    """Board's fractional frequency against the laptop clock (ppm), in pieces of `block` s."""
    tpc = d[:, 0]
    k = np.arange(len(d))           # row k left the board k * tau0 after row 0, by its clock
    out = []
    for t1 in np.arange(tpc[0], tpc[-1] - block, block):
        s = (tpc >= t1) & (tpc < t1 + block)
        slope = np.polyfit(k[s], tpc[s], 1)[0]                  # laptop seconds per result
        out.append((tpc[s].mean(), (tau0 / slope - 1) * 1e6))
    lost = int(round((tpc[-1] - tpc[0]) / tau0)) + 1 - len(k)   # about 0 if none were lost
    return np.array(out), lost


A, B = z["board0"], z["board1"]
bA, bB = beat_blocks(A), beat_blocks(B)          # A sees f_B - f_A; B sees f_A - f_B
pA, lostA = vs_pc(A)
pB, lostB = vs_pc(B)
t0 = min(A[0, 0], B[0, 0])
tod = lambda t: [datetime.datetime.fromtimestamp(x) for x in t]
print("%d / %d results (lines lost: %d / %d) over %.2f h" % (len(A), len(B), lostA, lostB, (A[-1, 0] - A[0, 0]) / 3600))
print("beat f_B - f_A: from A %+.4f to %+.4f ppm (mean %+.4f); B's view mean %+.4f" %
      (bA[:, 1].min(), bA[:, 1].max(), bA[:, 1].mean(), -bB[:, 1].mean()))
print("against the laptop: A %+.3f .. %+.3f ppm, B %+.3f .. %+.3f ppm; mean B - A %+.4f ppm" %
      (pA[:, 1].min(), pA[:, 1].max(), pB[:, 1].min(), pB[:, 1].max(), (pB[:, 1] - pA[:, 1]).mean()))

fig, ax = plt.subplots(2, 1, figsize=(7.5, 6.4), sharex=True)
dots(ax[0], tod(bA[:, 0]), bA[:, 1], C1, "seen by A's lock-in", size=5)
dots(ax[0], tod(bB[:, 0]), -bB[:, 1], C2, "seen by B's lock-in (sign flipped)", size=2.5)
ax[0].set_ylabel("f_B − f_A (ppm)")
ax[0].set_title("Two crystals through the night: their difference, 60 s at a time")
ax[0].legend()
dots(ax[1], tod(pA[:, 0]), pA[:, 1], C1, "board A", size=4)
dots(ax[1], tod(pB[:, 0]), pB[:, 1], C2, "board B", size=4)
dots(ax[1], tod(pA[:, 0]), pB[:, 1] - pA[:, 1], C3, "B − A", size=4)
if len(sys.argv) > 2:
    n = np.load(sys.argv[2])["rows"]
    steps = np.where(np.abs(np.diff(n[:, 2])) > 1e-6)[0] + 1
    for j, i in enumerate(steps):
        ax[1].axvline(datetime.datetime.fromtimestamp(n[i, 0]), color="0.6", ls=":", lw=1,
                      label="the laptop's NTP corrections (logged from %s)" %
                      datetime.datetime.fromtimestamp(n[0, 0]).strftime("%H:%M") if j == 0 else None)
ax[1].set_ylabel("crystal against the laptop clock (ppm)")
ax[1].set_xlabel("time of day")
ax[1].set_title("Each crystal against the laptop's NTP clock, 10 min at a time")
ax[1].legend(fontsize=8, loc="lower right")
import matplotlib.dates as mdates
ax[1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
save(fig, os.path.join(T, "..", "tutorial", "img", "tb_overnight.png"))
