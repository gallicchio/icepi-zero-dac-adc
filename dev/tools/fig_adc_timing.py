"""1.04's timing diagram: how adc_leds.sv clocks the AD9280, and when it reads the pins.

Computed from the page's three datasheet numbers and from adc_leds.sv, not measured:
adc_clk toggles on every rising edge of the 50 MHz clock (20 ns high, 20 ns low); the
ADC's data pins change for about t_OD = 25 ns after each rising edge of adc_clk and then
hold the result of the sample taken three ADC clocks earlier; the FPGA reads them
(sample <= adc_d) on the clock edge at which adc_clk rises again, 40 ns after the edge
that released them, so they have been steady for 15 ns.

    python3 fig_adc_timing.py        -> ../../tutorial/img/adc_timing.png
"""
import os

import numpy as np
from plotstyle import plt, save, C1, C2, C3, INK, INK2, MUTED

IMG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tutorial", "img")

T_CLK = 20.0            # ns: the 50 MHz clock
T_ADC = 2 * T_CLK       # ns: adc_clk, 25 MHz
T_OD = 25.0             # ns: the AD9280's output delay (typical, from its datasheet)
T0, T1 = -12.0, 161.0   # ns: the window drawn (sample k's result, 3 ADC clocks on, fits)
H = 0.6                 # height of a logic 1 in each lane
Y_CLK, Y_ADC, Y_D = 3.0, 1.5, 0.0      # y of each lane's logic 0

t = np.linspace(T0, T1, 6001)
clk = ((t % T_CLK) < T_CLK / 2).astype(float)     # rising edges at 0, 20, 40, ... ns
adc = ((t % T_ADC) < T_ADC / 2).astype(float)     # rising edges at 0, 40, 80, ... ns

fig, ax = plt.subplots(figsize=(9.2, 5.0))
ax.plot(t, Y_CLK + H * clk, color=INK, lw=1.4)
ax.plot(t, Y_ADC + H * adc, color=C1, lw=1.4)

# ---- the data bus: changing for t_OD after each rising edge of adc_clk, then valid -----
rises = np.arange(-T_ADC, T1, T_ADC)
for k, r in enumerate(rises):
    ax.add_patch(plt.Rectangle((r, Y_D), T_OD, H, facecolor="none", edgecolor=MUTED,
                               hatch="////", lw=0.8))
    if r + T_OD >= T1:              # the last period's valid box falls off the right edge
        continue
    ax.add_patch(plt.Rectangle((r + T_OD, Y_D), T_ADC - T_OD, H, facecolor="#e6f3ec",
                               edgecolor=C3, lw=1.2))
    d = k - 4                       # this box holds the result of sample k + d
    which = "k" if d == 0 else f"k{d:+d}".replace("-", "−")
    ax.text(r + T_OD + (T_ADC - T_OD) / 2, Y_D + H / 2, which, ha="center", va="center",
            fontsize=8.5, color=C3, weight="bold")
ax.text(T_OD / 2, Y_D + H / 2, "changing", ha="center", va="center", fontsize=8, color=INK2)

# ---- the ADC samples on each rising edge of adc_clk ------------------------------------
for k, r in enumerate(np.arange(0, T1, T_ADC)):
    ax.plot([r], [Y_ADC + H + 0.06], marker="v", color=C1, markersize=6, clip_on=False)
    if r + T_CLK < T1:              # room for the label
        ax.text(r + 2.5, Y_ADC + H + 0.16, f"sample k{'+%d' % k if k else ''}", ha="left",
                va="bottom", fontsize=8, color=C1)
ax.text(T0 + 2, Y_ADC + H + 0.55, "the ADC takes a sample on each rising edge of adc_clk;"
        " its result reaches the pins 3 ADC clocks later", ha="left", va="bottom", fontsize=8,
        color=INK2)

# ---- the FPGA reads the pins on the clk edge at which adc_clk rises again ----------------
for r in np.arange(T_ADC, T1, T_ADC):
    ax.plot([r, r], [Y_D + H, Y_CLK + H], color=C2, lw=1.0, ls="--", zorder=0)
    ax.plot([r], [Y_D + H + 0.02], marker="v", color=C2, markersize=7, clip_on=False)
ax.annotate("sample <= adc_d happens at this clk edge:\nadc_clk is low, and rises here",
            (T_ADC, Y_CLK + 0.3), xytext=(T_ADC + 5, Y_CLK + 0.9), fontsize=8.5, color=C2,
            ha="left", va="bottom", arrowprops=dict(arrowstyle="->", color=C2, lw=1.0))

# ---- the two dimensions in the first ADC period -------------------------------------------
y_dim = Y_D + H + 0.28
for a, b, label, above in [(0, T_OD, "t$_{OD}$ ≈ 25 ns", False),
                           (T_OD, T_ADC, "steady for 15 ns", True)]:
    ax.annotate("", (a, y_dim), (b, y_dim), arrowprops=dict(arrowstyle="<->", color=INK2, lw=0.9))
    ax.text((a + b) / 2, y_dim + (0.07 if above else -0.07), label, ha="center",
            va="bottom" if above else "top", fontsize=8, color=INK2)
ax.text(T_ADC + 3, Y_D + H + 0.1, "← read here", ha="left", va="center", fontsize=8, color=C2)

ax.set_xlim(T0, T1)
ax.set_ylim(-0.25, Y_CLK + H + 1.35)
ax.set_xticks(np.arange(0, T1, T_CLK))
ax.set_xlabel("time (ns)")
ax.set_yticks([Y_CLK + H / 2, Y_ADC + H / 2, Y_D + H / 2])
ax.set_yticklabels(["clk (50 MHz)", "adc_clk (25 MHz)", "adc_d[7:0]"])
ax.tick_params(axis="y", length=0)
ax.grid(axis="y", visible=False)
ax.spines["left"].set_visible(False)
ax.set_title("Clocking the AD9280 and reading its pins (adc_leds.sv)")
fig.text(0.995, 0.995, "computed, not measured", ha="right", va="top", size=8, color=MUTED)
save(fig, os.path.join(IMG, "adc_timing.png"))
print("wrote", os.path.join(IMG, "adc_timing.png"))
