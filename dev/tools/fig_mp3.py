"""1.05's opening cartoon: music from a phone or MP3 player, into the ADC's SMA input, over
USB to the laptop, and out of the laptop's speaker (stream.py --play).  No data.

    python3 fig_mp3.py        # writes ../../tutorial/img/mp3_to_adc.png
"""
import os

import numpy as np
from matplotlib.patches import Circle, FancyBboxPatch, Polygon, Rectangle, Arc
from plotstyle import plt, save, C1, C2, INK, INK2, MUTED

IMG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tutorial", "img")
GOLD, PCB_GREEN, PCB_BLACK, CABLE = "#c9a227", "#2f8f4e", "#1d1d1f", "#8a8a8a"

from matplotlib.transforms import Affine2D
from fig_stack import stack, cable, PROG, ADC_C

fig, ax = plt.subplots(figsize=(9.6, 4.6))
ax.set_xlim(-58, 176)
ax.set_ylim(-32, 86)
ax.set_aspect("equal")
ax.axis("off")
# the stack is drawn in millimetres (fig_stack.py); the player and the laptop in their own
# units, scaled and moved into place by T
T = None


def at(k, dx, dy):
    global T
    T = Affine2D().scale(k).translate(dx, dy) + ax.transData


def box(x, y, w, h, color, r=0.12, **kw):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                fc=color, ec=kw.pop("ec", "none"), lw=kw.pop("lw", 1), transform=T, **kw))


def note(x, y, text, **kw):
    ax.text(x, y, text, fontsize=kw.pop("fontsize", 10.5), color=kw.pop("color", INK2), transform=kw.pop("transform", T), **kw)


# ---- the MP3 player ------------------------------------------------------------------
at(17, -58.8, -8.5)
box(0.4, 0.5, 1.5, 2.6, "#3b3b40", r=0.2)
box(0.55, 1.95, 1.2, 0.95, "#bfe0f5", r=0.06)
note(1.15, 2.55, "♪", ha="center", va="center", fontsize=18, color="#1f4e79")
note(1.15, 2.15, "track 3 / 12", ha="center", va="center", fontsize=7, color="#1f4e79")
ax.add_patch(Circle((1.15, 1.18), 0.48, fc="#d9d9de", ec="none", transform=T))
ax.add_patch(Circle((1.15, 1.18), 0.17, fc="#3b3b40", ec="none", transform=T))
for a, s in [(90, "MENU"), (0, "▶▶"), (180, "◀◀"), (270, "▶ ❙❙")]:
    note(1.15 + 0.33 * np.cos(np.radians(a)), 1.18 + 0.33 * np.sin(np.radians(a)), s,
         ha="center", va="center", fontsize=5, color="#3b3b40")
# headphone plug in the jack on top
ax.add_patch(Rectangle((1.4, 3.1), 0.12, 0.25, fc="#b0b0b0", ec="none", transform=T))
box(1.36, 3.35, 0.2, 0.32, "#555", r=0.04)
note(1.15, 0.12, "a phone or\nMP3 player", ha="center", va="top", fontsize=11, color=INK)
plug = T.transform((1.46, 3.67))
plug = tuple(ax.transData.inverted().transform(plug))

# ---- the stack, from above, and the cable from the headphone output to ADC IN --------------
adc, dac = stack(ax, unused=("DAC OUT",), usb=False)
cable(ax, plug, adc, bend=16, bend1=14, color=ADC_C, arrow=True)
note(-6, 81, "headphone output, about ±1 V", ha="center", fontsize=10.5, transform=ax.transData)
note(-6, 76.5, "3.5 mm-to-SMA cable", ha="center", fontsize=10.5, color=MUTED, transform=ax.transData)

# ---- the laptop, with its speaker ------------------------------------------------------
at(21, -78, -20)
box(8.75, 1.4, 2.4, 1.6, "#2b2b2e", r=0.08)
box(8.87, 1.52, 2.16, 1.36, "#f4f4f2", r=0.03)
t = np.linspace(0, 1, 200)
wave = 0.32 * np.sin(2 * np.pi * 5 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.9 * t))
ax.plot(8.97 + 1.96 * t, 2.2 + wave, color=C1, lw=1.0, transform=T)
ax.add_patch(Polygon([(8.5, 1.4), (11.4, 1.4), (11.65, 1.15), (8.25, 1.15)], fc="#4a4a4e", ec="none", transform=T))
ax.add_patch(Polygon([(10.95, 3.55), (11.1, 3.55), (11.3, 3.75), (11.3, 3.15), (11.1, 3.35), (10.95, 3.35)],
                     fc=INK, ec="none", transform=T))
for r in (0.2, 0.35, 0.5):
    ax.add_patch(Arc((11.3, 3.45), 2 * r, 2 * r, theta1=-45, theta2=45, color=C2, lw=1.6, transform=T))
note(9.95, 0.95, "python3 stream.py -n 500000 --play", ha="center", va="top", fontsize=9.5,
     color=INK, family="monospace")
note(10.7, 3.45, "your music, from\nthe laptop's speaker", ha="right", fontsize=10.5, va="center")
port = tuple(ax.transData.inverted().transform(T.transform((8.33, 1.27))))

# ---- the PROG USB port to the laptop -------------------------------------------------------
ax.add_patch(Rectangle((PROG - 2.5, -9), 5, 4.5, fc="#333", ec="none", zorder=2))
cable(ax, (PROG, -9), port, bend=-7, bend1=-7, color="#333", lw=3, arrow=True)
note(PROG - 6, -18, "PROG USB (marked Flash)", fontsize=10.5, color=INK, va="top", transform=ax.transData)
note(PROG - 6, -23.5, "50,000 samples a second", fontsize=10.5, va="top", transform=ax.transData)

save(fig, os.path.join(IMG, "mp3_to_adc.png"))
print("wrote mp3_to_adc.png")
