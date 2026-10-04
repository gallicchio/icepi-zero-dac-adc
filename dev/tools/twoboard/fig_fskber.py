"""Figure: the FSK modem's bit error rate against SNR per ADC sample, for 16- and 128-sample
receiver windows (data/tb_fsk_ber.npz) and for modem_sync.v's 216 samples with a recovered
bit clock (data/tb_fsk_sync.npz), with the non-coherent FSK curves 1/2 exp(-W SNR / 4)."""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, ".."))
from plotstyle import plt, save, dots, C1, C2, C3
T = os.path.join(HERE, "..", "..")
z = dict(np.load(os.path.join(T, "data", "tb_fsk_ber.npz")))
z["sync"] = np.load(os.path.join(T, "data", "tb_fsk_sync.npz"))["rows"]
fig, ax = plt.subplots(figsize=(9, 4.6))
s = np.linspace(-14, 14, 400)
for key, W, c in (("w16", 16, C1), ("w128", 128, C2), ("sync", 216, C3)):
    r = z[key]                                  # noise snr dwrong dtot bits extra nbits
    snr_db = 10 * np.log10(r[:, 1])
    ax.semilogy(s, 0.5 * np.exp(-W * 10**(s / 10) / 4), color=c, lw=1.2)
    sel = r[:, 4] > 0
    dots(ax, snr_db[sel], r[sel, 4] / r[sel, 6], c, size=6)
    sel = r[:, 2] > 0
    ax.plot(snr_db[sel], r[sel, 2] / r[sel, 3], "o", mfc="none", color=c, markersize=7)
    zero = (r[:, 4] == 0) & (r[:, 1] < 100)
    ax.plot(snr_db[zero], 0.5 / r[zero, 6], "v", color=c, markersize=5, alpha=0.6)
ax.set_ylim(3e-7, 5); ax.set_xlim(-14, 14)
ax.set_xlabel("SNR per ADC sample, A²/2σ² (dB)"); ax.set_ylabel("bit error rate")
ax.set_title("FSK looped back at 115,200 baud, with noise added")
x16, x128 = (10 * np.log10(4 * np.log(500) / w) for w in (16, 128))   # theory at BER 1e-3
ax.annotate("", xy=(x128, 1e-3), xytext=(x16, 1e-3), arrowprops=dict(arrowstyle="->", color="0.3"))
ax.text((x16 + x128) / 2, 1.3e-3, "9 dB = 10 log₁₀(128/16)", ha="center", fontsize=8, color="0.3")
from matplotlib.lines import Line2D
handles = [Line2D([], [], color=C1, lw=3, label="16 samples (modem.sv)"),
           Line2D([], [], color=C2, lw=3, label="128 samples"),
           Line2D([], [], color=C3, lw=3, label="216 samples, bit clock\n(modem_sync.v)"),
           Line2D([], [], color="0.4", lw=1.2, label="theory, ½ exp(−W·SNR/4)"),
           Line2D([], [], color="0.4", marker="o", ls="none", markersize=6, label="through the laptop's UART"),
           Line2D([], [], color="0.4", marker="o", mfc="none", ls="none", markersize=7,
                  label="decisions on recorded\nADC samples"),
           Line2D([], [], color="0.4", marker="v", ls="none", alpha=0.6, label="no errors in\n800 000 bits")]
ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 1.0), fontsize=8)
save(fig, os.path.join(T, "..", "tutorial", "img", "tb_fskber.png"))
