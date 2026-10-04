"""7.06, drawn, not measured: the loop as a block diagram with where its latency hides, and
the three plants control.sv can close it through.

    python3 fig_control_diagrams.py       # writes ../../../tutorial/img/dsp_control_d_loop.png
                                          #    and ../../../tutorial/img/dsp_control_d_plants.png

The nanoseconds are control.sv's count, from 1.07's table and the datasheets: the AD9280
samples, its 3-stage pipeline plus 25 ns puts the word on the pins 145 ns later, the FPGA
registers it on the next sampling edge (160 ns), the controller takes 2 clocks (40 ns), the
AD9708 latches the word 10 ns after it changes and its output reaches ADC IN about 35 ns
later (32 ns plus 4.6 ns per metre of cable), and the ADC samples it on its next edge: 280 ns
in all, 7 samples, with the signal arriving a few ns after the 6th edge.  The sketches under
the plants are the model's own step responses (control_model.py).
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.join(HERE, "..", "..", "..")
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(TOP, "src", "dsp"))
from plotstyle import plt, C1, C2, C3, INK, INK2, MUTED, AXIS, SURFACE   # noqa: E402
from fig_openers import canvas, box, label, node, arrow, chip, NEUTRAL, BLUE_BG, ORANGE_BG, GREEN_BG, MONO   # noqa: E402
import control_model as cm                                               # noqa: E402

IMG = os.path.join(TOP, "tutorial", "img")


def circle_op(ax, cx, cy, sym="−", r=1.3, size=11):
    from matplotlib.patches import Circle
    ax.add_patch(Circle((cx, cy), r, fc=SURFACE, ec=INK2, lw=1.2, zorder=4))
    ax.text(cx, cy - 0.05, sym, ha="center", va="center", size=size, color=INK, zorder=5)


def inset(fig, ax, x, y, w, h):
    """Small axes at canvas position (x, y) of size (w, h), in the canvas's tenths of an inch."""
    W, H = fig.get_size_inches() * 10
    a = fig.add_axes([x / W, y / H, w / W, h / H])
    a.set_xticks([])
    a.set_yticks([])
    a.grid(False)
    for s in ("top", "right"):
        a.spines[s].set_visible(False)
    a.patch.set_alpha(0)
    return a


# ==== the loop and its latency ====================================================================
def fig_loop():
    W, H = 10.5, 5.0
    fig, ax = canvas(W, H)
    yb = 37                                   # the row of blocks
    # the FPGA
    box(ax, 3, yb - 10, 44, 20, fc="#f7f6f1", ec=AXIS, lw=1.0, ls="--")
    ax.text(4, yb + 8.6, "the FPGA (control.sv)", size=8.5, color=INK2, va="bottom")
    label(ax, 7.5, yb, ["setpoint"], size=9)
    circle_op(ax, 15, yb, "−")
    arrow(ax, (11, yb), (13.7, yb))
    node(ax, 25, yb, 12, 7, [("PID", {"weight": "bold"}), "Kp e + Ki Σe + Kd Δe", "2 clocks = 40 ns"], fc=GREEN_BG, size=8)
    arrow(ax, (16.3, yb), (19, yb))
    ax.text(17.6, yb + 1.2, "e", size=9, color=INK, ha="center", va="bottom")
    arrow(ax, (31, yb), (36, yb))
    ax.text(33.5, yb + 1.2, "u", size=9, color=INK, ha="center", va="bottom")
    label(ax, 41.5, yb, ["128 + bias + u,", "then the rails"], size=8)
    arrow(ax, (47, yb), (52, yb))
    chip(ax, 58, yb, 11, 7, [("AD9708 DAC", {"size": 8.5}), ("latch 10 ns", {"size": 7.5}), ("settle ~35 ns", {"size": 7.5})], pins=4)
    arrow(ax, (64.5, yb), (69, yb))
    node(ax, 77.5, yb, 15, 8.5, [("the plant", {"weight": "bold"}), "a cable (5 ns/m), an RC,", "an LED and a photodiode,",
                                 "or inside the FPGA"], fc=ORANGE_BG, size=7.4)
    arrow(ax, (85, yb), (89, yb))
    chip(ax, 95.5, yb, 11, 7, [("AD9280 ADC", {"size": 8.5}), ("pipeline + 25 ns", {"size": 7.5}), ("= 145 ns", {"size": 7.5})], pins=4)
    # the return path, under everything, back to the summing node
    yr = yb - 12
    arrow(ax, (95.5, yb - 4.5), (95.5, yr), style="-")
    arrow(ax, (95.5, yr), (15, yr), style="-")
    arrow(ax, (15, yr), (15, yb - 1.4))
    label(ax, 55, yr - 2.0, ["the measurement, 8 bits, once every 40 ns, registered on the next sampling edge: 160 ns after the ADC sampled"], size=8, color=INK2)

    # ---- the timeline: where the 280 ns go
    x0, x1 = 8, 91
    yt = 8.0
    scale = (x1 - x0) / 280.0
    segs = [(0, 160, BLUE_BG, C1, "ADC: sample, 3-stage pipeline, word on the pins at 145 ns,\nregistered by the FPGA at 160 ns"),
            (160, 200, GREEN_BG, C3, "gateware\n2 clocks"),
            (200, 210, "#eeeeee", INK2, ""),
            (210, 245, ORANGE_BG, C2, "DAC settles,\ncable"),
            (245, 280, "#f3f1ea", MUTED, "waits for the\nnext edge")]
    for t0, t1, fc, ec, txt in segs:
        box(ax, x0 + t0 * scale, yt, (t1 - t0) * scale, 4.5, fc=fc, ec=ec, r=0.3)
        if txt:
            ax.text(x0 + 0.5 * (t0 + t1) * scale, yt - 1.2, txt, ha="center", va="top", size=7.3, color=INK2)
    ax.plot([x0 + 205 * scale] * 2, [yt - 0.3, yt - 4.6], color=INK2, lw=0.6)
    ax.text(x0 + 205 * scale, yt - 4.8, "the DAC latches: 10 ns", ha="center", va="top", size=7, color=INK2)
    for t, lbl in ((0, "0"), (160, "160"), (200, "200"), (245, "~245"), (280, "280 ns")):
        ax.plot([x0 + t * scale] * 2, [yt - 0.6, yt + 5.1], color=INK2, lw=0.7)
        ax.text(x0 + t * scale, yt + 5.3, lbl, ha="center", va="bottom", size=7.5, color=INK)
    for k in range(8):
        ax.plot([x0 + 40 * k * scale] * 2, [yt + 4.5, yt + 4.5 + 0.9], color=INK, lw=1.0)
    ax.text(x0 - 1, yt + 2.2, "ADC sampling edges, 40 ns apart", ha="right", va="center", size=7.5, color=INK2, rotation=90)
    ax.text(x1 + 1.5, yt + 2.2, "7 samples", ha="left", va="center", size=9, color=INK, weight="bold")
    ax.text(0.5 * (x0 + x1), yt + 9.0,
            "Where the latency hides: 280 ns from the ADC sampling the input to the ADC sampling the response.\n"
            "Two thirds of it is the ADC's pipeline; the controller is one seventh.",
            ha="center", va="bottom", size=8.8, color=INK)
    ax.text(W * 10 - 0.5, 0.6, "drawn from 1.07's table and control.sv's count, not measured", ha="right", va="bottom", size=8, color=MUTED)
    fig.savefig(os.path.join(IMG, "dsp_control_d_loop.png"), dpi=130, facecolor=fig.get_facecolor())
    plt.close(fig)
    print("wrote dsp_control_d_loop.png")


# ==== the three plants ===========================================================================
def sketch_step(a, y, t_us, color, label_txt):
    a.plot(t_us, y, color=color, lw=1.2)
    a.axhline(40, color=MUTED, lw=0.6, ls="--")
    a.set_xlim(t_us[0], t_us[-1])
    a.set_ylim(min(y.min(), 0) - 5, max(y.max(), 40) + 8)
    a.caption = label_txt


def fig_plants():
    W, H = 10.5, 4.6
    fig, ax = canvas(W, H)
    cols = [3, 38, 72]
    cw = 31
    titles = [("'M' 0: the real world", "the loop closes through whatever sits between DAC OUT\n"
               "and ADC IN: the cable is a pure delay (gain 0.776), an RC\na lag, an LED and a photodiode a noise-eater, a piezo\na resonator"),
              ("'M' 1: a lag in the FPGA", "y ← y + (u − y) / 2^K, time constant 2^K samples;\nthe ADC adds to y: the M2k's W1 is a disturbance\nthe controller must fight"),
              ("'M' 2: a resonator in the FPGA", "v ← v + ω₀² (u − y) − v / 2^Q;  y ← y + v\n(a mass on a spring; f₀ and Q from 'R' and 'Q');\nsame disturbance input")]
    for k, (x, (ttl, txt)) in enumerate(zip(cols, titles)):
        box(ax, x, 3, cw, H * 10 - 6, fc="#f7f6f1", ec=AXIS, lw=1.0, r=1.2)
        ax.text(x + 1.5, H * 10 - 5, ttl, size=9.5, weight="bold", color=INK, va="top")
        ax.text(x + 1.5, H * 10 - 8.6, txt, size=7.2, color=INK2, va="top")
    yb = 24
    # mode 0
    x = cols[0]
    node(ax, x + 6, yb, 9, 6, ["PID", "u"], fc=GREEN_BG, size=8)
    arrow(ax, (x + 10.5, yb), (x + 13.5, yb))
    chip(ax, x + 16.5, yb, 5.5, 5, [("DAC", {"size": 7})], pins=2)
    arrow(ax, (x + 19.5, yb), (x + 22, yb))
    node(ax, x + 25, yb, 5.5, 6, ["cable", "RC, ..."], fc=ORANGE_BG, size=7)
    ax.text(x + 23, yb + 4.4, "DAC OUT → ADC IN", ha="center", size=6.3, color=INK2)
    arrow(ax, (x + 25, yb - 3), (x + 25, yb - 7), style="-")
    arrow(ax, (x + 25, yb - 7), (x + 6, yb - 7), style="-")
    chip(ax, x + 15, yb - 7, 5.5, 4, [("ADC", {"size": 7})], pins=2)
    arrow(ax, (x + 6, yb - 7), (x + 6, yb - 3.2))
    ax.text(x + 7, yb - 5.6, "7 samples\naround", size=6.5, color=INK2, va="center")
    # mode 1 and 2
    for k, (x, name, fc) in enumerate(((cols[1], "lag", BLUE_BG), (cols[2], "resonator", BLUE_BG))):
        node(ax, x + 5, yb, 8, 6, ["PID", "u"], fc=GREEN_BG, size=8)
        arrow(ax, (x + 9, yb), (x + 11, yb))
        node(ax, x + 13.5, yb, 4.5, 5, ["z⁻ᴸ"], fc=NEUTRAL, size=8)
        arrow(ax, (x + 15.8, yb), (x + 18, yb))
        node(ax, x + 22, yb, 7.5, 6, [name, "y"], fc=fc, size=8)
        circle_op(ax, x + 22, yb - 8, "+", r=1.2, size=10)
        arrow(ax, (x + 22, yb - 3), (x + 22, yb - 6.7))
        chip(ax, x + 28.5, yb - 8, 4.5, 4, [("ADC", {"size": 6.5})], pins=2)
        arrow(ax, (x + 26, yb - 8), (x + 23.3, yb - 8))
        ax.text(x + 28.5, yb - 11.4, "W1 in:\ndisturbance", ha="center", va="top", size=6.3, color=INK2)
        arrow(ax, (x + 22, yb - 9.3), (x + 22, yb - 12), style="-")
        arrow(ax, (x + 22, yb - 12), (x + 5, yb - 12), style="-")
        arrow(ax, (x + 5, yb - 12), (x + 5, yb - 3.2))
        ax.text(x + 6, yb - 10.6, "measurement\n= y + ADC", size=6.3, color=INK2, va="center")
        ax.text(x + 13.5, yb + 3.6, "'L' extra delay", ha="center", size=6.3, color=INK2)
        chip(ax, x + 28, yb + 2, 4, 3.5, [("DAC", {"size": 6.5})], pins=2)
        ax.text(x + 28, yb + 4.4, "'O': plays u or y", ha="center", va="bottom", size=6.3, color=INK2)
    # sketches: the model's own step responses
    n = 300
    t_us = np.arange(n) * cm.TS * 1e6
    # mode 0: the cable: a step of 40 DAC codes seen by the ADC 7 samples later
    cab = cm.Cable(noise=0.0)
    y0 = np.array([cab.step(128 + (40 if i >= 1 else 0)) - 128 for i in range(n)], float)
    a = inset(fig, ax, cols[0] + 2, 5.2, cw - 4, 4.6)
    sketch_step(a, y0 / cm.GAIN * 1.0, t_us, C2, "the cable: a step, 280 ns late (÷0.776)")
    # mode 1: the lag, K = 4
    loop = cm.Loop(cm.Settings(mode=1, klag=4, enable=False))
    y1 = np.array([loop.step(40, 0)[2] for i in range(n)], float)
    a = inset(fig, ax, cols[1] + 2, 5.2, cw - 4, 4.6)
    sketch_step(a, y1, t_us, C1, "K = 4: τ = 16 samples = 0.64 µs")
    # mode 2: the resonator, 100 kHz, Q = 25.7
    loop = cm.Loop(cm.Settings(mode=2, rword=662, qshift=10, enable=False))
    n2 = 1500
    y2 = np.array([loop.step(40, 0)[2] for i in range(n2)], float)
    a = inset(fig, ax, cols[2] + 2, 5.2, cw - 4, 4.6)
    sketch_step(a, y2, np.arange(n2) * cm.TS * 1e6, C1, "f₀ = 100 kHz, Q = 25.7")
    for x, lbl in zip(cols, ("the cable alone: a step, 280 ns late (12 µs shown)",
                             "the lag alone, K = 4: τ = 0.64 µs (12 µs shown)",
                             "the resonator alone: 100 kHz, Q = 25.7 (60 µs shown)")):
        ax.text(x + 1.5, 3.7, lbl, size=6.3, color=INK2)
    ax.text(W * 10 - 0.5, 0.6, "drawn; the sketches are control_model.py's step responses", ha="right", va="bottom", size=8, color=MUTED)
    fig.savefig(os.path.join(IMG, "dsp_control_d_plants.png"), dpi=130, facecolor=fig.get_facecolor())
    plt.close(fig)
    print("wrote dsp_control_d_plants.png")


if __name__ == "__main__":
    fig_loop()
    fig_plants()
