"""Figure: OFDM over the cable -- constellations, EVM per subcarrier, channel SNR."""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, ".."))
from plotstyle import plt, save, C1, C2, C3
T = os.path.join(HERE, "..", "..")
D = lambda n: np.load(os.path.join(T, "data", n))
fig = plt.figure(figsize=(8, 8.2))
gs = fig.add_gridspec(3, 3, height_ratios=[1.15, 0.8, 0.8])
for i, (name, title) in enumerate((("tb_ofdm_loop_64.npz", "QAM-64, one board"), ("tb_ofdm_cross_64.npz", "QAM-64, board to board"),
                                  ("tb_ofdm_loop_256.npz", "QAM-256, one board"))):
    ax = fig.add_subplot(gs[0, i])
    if os.path.exists(os.path.join(T, "data", name)):
        z = D(name); Zs = z["Z"][0].ravel()
        ax.plot(Zs.real, Zs.imag, ".", color=(C1, C2, C3)[i], markersize=1.2)
        ax.set_title("%s\n%.1f Mbit/s, BER %s" % (title, z["rate"] / 1e6,
                     "0 in %d" % z["nbits"] if z["errs"] == 0 else "%.1e" % (z["errs"] / z["nbits"])), fontsize=9)
    ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
ax = fig.add_subplot(gs[1, :])
for name, c, lab in (("tb_ofdm_loop_64.npz", C1, "one board"), ("tb_ofdm_cross_64.npz", C2, "board to board")):
    if os.path.exists(os.path.join(T, "data", name)):
        z = D(name); ax.plot(z["fk"] / 1e6, 20 * np.log10(z["evm"]), ".-", color=c, markersize=3, lw=0.8, label=lab)
ax.set_xlabel("subcarrier frequency (MHz)"); ax.set_ylabel("EVM (dB)"); ax.set_title("Error per subcarrier (QAM-64)")
ax.legend()
ax = fig.add_subplot(gs[2, :])
for name, c, lab in (("tb_sound_loop.npz", C1, "one board"), ("tb_sound_cross.npz", C2, "board to board")):
    if os.path.exists(os.path.join(T, "data", name)):
        z = D(name); ax.plot(z["f"] / 1e6, 10 * np.log10(z["snr"]), color=c, lw=0.6, label="%s: noise-only capacity %.0f Mbit/s" % (lab, z["C"] / 1e6))
ax.set_xlabel("frequency (MHz)"); ax.set_ylabel("SNR per 3 kHz bin (dB)"); ax.set_title("Channel sounding: signal against random noise only")
ax.legend(loc="lower left")
save(fig, os.path.join(T, "..", "tutorial", "img", "tb_ofdm.png"))
