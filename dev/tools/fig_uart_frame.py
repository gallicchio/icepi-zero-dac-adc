"""1.05's picture of one byte on the serial line, computed from the protocol, not measured:
the line idles at 1, then a 0 start bit, the 8 data bits least-significant first, and a
1 stop bit, each lasting 1 us at 1,000,000 baud (50 clocks of 20 ns).  The byte drawn is
0x53 = 83 = 0b01010011.  The dots are where uart_rx (uart.sv) reads the line: 1.5 bit
times after the start bit's falling edge, then every bit time.

    python3 fig_uart_frame.py        -> ../../tutorial/img/uart_frame.png
"""
import os

import numpy as np
from plotstyle import plt, save, C1, C2, C3, INK, INK2, MUTED

IMG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tutorial", "img")

BYTE = 0x53
bits = [1, 0] + [(BYTE >> k) & 1 for k in range(8)] + [1, 1]       # idle, start, D0..D7, stop, idle
names = ["idle", "start"] + [f"D{k}" for k in range(8)] + ["stop", "idle"]
N = len(bits)                                                       # 12 bit times drawn

fig, ax = plt.subplots(figsize=(9.2, 3.3))
ax.step(np.arange(N + 1), bits + [bits[-1]], where="post", color=INK, lw=1.6)
for k in range(1, N):
    ax.axvline(k, color=MUTED, lw=0.6, ls=":")
for k, (b, name) in enumerate(zip(bits, names)):
    ax.text(k + 0.5, -0.42, name, ha="center", va="center", fontsize=8.5,
            color=C1 if name.startswith("D") else INK2)
    if name.startswith("D"):
        ax.text(k + 0.5, b + (0.12 if b else -0.17), str(b), ha="center", va="center",
                fontsize=9, color=INK, weight="bold")
# where the receiver reads the line: the middle of D0..D7 and of the stop bit
mids = np.arange(2, 11) + 0.5
ax.plot(mids, [bits[int(m)] for m in mids], "o", color=C2, markersize=5.5, zorder=5)
ax.annotate("uart_rx reads the line in the middle of each bit:\n1.5 µs after the start bit's "
            "falling edge, then every 1 µs", (4.5, 0.0), xytext=(5.1, 1.42), fontsize=8.5,
            color=C2, ha="left", va="center", arrowprops=dict(arrowstyle="->", color=C2, lw=1.0))
ax.annotate("", (1, 1.2), (2, 1.2), arrowprops=dict(arrowstyle="<->", color=INK2, lw=0.9))
ax.text(1.5, 1.27, "1 µs = 50 clocks", ha="center", va="bottom", fontsize=8, color=INK2)

ax.set_xlim(0, N)
ax.set_ylim(-0.6, 1.75)
ax.set_xticks(np.arange(0, N + 1, 1))
ax.set_xlabel("time (µs)")
ax.set_yticks([0, 1])
ax.set_ylabel("uart_tx")
ax.grid(axis="y", visible=False)
sec = ax.secondary_xaxis("top", functions=(lambda us: us * 50, lambda c: c / 50))
sec.set_xlabel("clocks of 20 ns", fontsize=9)
sec.set_xticks(np.arange(0, 50 * N + 1, 100))
ax.set_title(f"One byte on the serial line at 1,000,000 baud: 0x{BYTE:02x} = {BYTE} = "
             f"0b{BYTE:08b}, least-significant bit first")
fig.text(0.995, 0.01, "computed, not measured", ha="right", va="bottom", size=8, color=MUTED)
save(fig, os.path.join(IMG, "uart_frame.png"))
print("wrote", os.path.join(IMG, "uart_frame.png"))
