"""1.09's explanatory figures (computed, no data):

spectrum_window.png  the Hann window over a frame of 1024 samples, and a windowed tone
spectrum_drift.gif   a pure tone drifting from one FFT bin to the next: without a window it
                     goes from one sharp line to a wide smear; with the Hann window it always
                     looks the same, just moved
fft_butterfly.png    the 8-point FFT as a signal-flow graph: 3 stages of 4 butterflies

    python3 fig_fft_theory.py
"""
import os

import numpy as np
from plotstyle import plt, save, C1, C2, C3, INK, INK2, MUTED, SURFACE

IMG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tutorial", "img")


def pow2_ticks(ax, N, axis="x"):
    """Ticks at 0, a few powers of two, and the last sample, N - 1."""
    ticks = [0] + [2 ** k for k in range(int(np.log2(N)) - 3, int(np.log2(N)))] + [N - 1]
    (ax.set_xticks if axis == "x" else ax.set_yticks)(ticks)


# ---- the Hann window -------------------------------------------------------------------------
N = 1024
n = np.arange(N)
w = 0.5 - 0.5 * np.cos(2 * np.pi * n / N)
fig, ax = plt.subplots(figsize=(8, 3.6))
tone = np.cos(2 * np.pi * 10.4 * n / N)
ax.plot(n, tone, color=MUTED, lw=0.7, label="a tone that doesn't fit the frame (10.4 cycles)")
ax.plot(n, tone * w, color=C1, lw=1.0, label="the same tone, times the window: no jump at the ends")
ax.plot(n, w, color=C3, lw=2.0, label="the Hann window, ½(1 − cos 2πn/N)")
ax.set_xlim(0, N - 1)
pow2_ticks(ax, N)
ax.set_xlabel("sample number n")
ax.set_ylim(-1.15, 2.45)
sec = ax.secondary_xaxis("top", functions=(lambda x: x / 25, lambda t: t * 25))
sec.set_xlabel("time at 25 MS/s (µs)")
ax.legend(loc="upper center", fontsize=8.5, ncol=1)
ax.set_title("A window fades each frame in and out", pad=30)
save(fig, os.path.join(IMG, "spectrum_window.png"))
print("wrote spectrum_window.png")

# ---- a tone drifting between bins -------------------------------------------------------------
from PIL import Image
frames = []
k = np.arange(80, 121)
for i, frac in enumerate(np.concatenate([np.linspace(0, 1, 13), np.linspace(1, 0, 13)[1:-1]])):
    f0 = 100 + frac
    x = np.cos(2 * np.pi * f0 * n / N + 0.3)
    rect = np.abs(np.fft.rfft(x)) / (N / 2)
    hann = np.abs(np.fft.rfft(x * w)) / (w.sum() / 2)
    fig, ax = plt.subplots(figsize=(7, 3.4), dpi=90)
    dB = lambda a: 20 * np.log10(a[k] + 1e-6)
    ax.plot(k, dB(rect), "o-", color=C2, lw=1, markersize=4,
            label="no window")
    ax.plot(k, dB(hann), "o-", color=C3, lw=1, markersize=4, label="Hann window")
    ax.axvline(f0, color=MUTED, lw=0.8, ls="--")
    ax.text(f0 + 0.3, 3, f"the tone: {f0:.2f} bins", fontsize=8.5, color=INK2)
    ax.set_xlim(k[0], k[-1])
    ax.set_ylim(-110, 10)
    ax.set_xlabel("FFT bin k")
    ax.set_ylabel("amplitude (dB)")
    ax.set_title("A pure tone moving from bin 100 to bin 101 and back", fontsize=10)
    ax.legend(loc="lower left", fontsize=8.5)
    fig.tight_layout()
    fig.canvas.draw()
    frames.append(Image.frombuffer("RGBA", fig.canvas.get_width_height(), fig.canvas.buffer_rgba()).convert("RGB"))
    plt.close(fig)
# one palette for every frame, made from several of them, so no colour is missing from it
strip = Image.new("RGB", (frames[0].width, frames[0].height * 4))
for j, fr in enumerate(frames[0:13:4]):
    strip.paste(fr, (0, j * fr.height))
pal = strip.quantize(colors=64, method=0)
q = [fr.quantize(palette=pal, dither=0) for fr in frames]
out = os.path.join(IMG, "spectrum_drift.gif")
q[0].save(out, save_all=True, append_images=q[1:], duration=[700] + [180] * 11 + [700] + [180] * 11, loop=0)
print("wrote spectrum_drift.gif", os.path.getsize(out) // 1024, "kB")

# ---- the 8-point FFT butterfly ----------------------------------------------------------------
M = 8
rev = [int(f"{i:03b}"[::-1], 2) for i in range(M)]
fig, ax = plt.subplots(figsize=(8.6, 5.2))
ax.axis("off")
X = [0, 3, 6, 9]                                   # columns: input, after stage 1, 2, 3
ys = lambda r: 7 - r
for c in X:
    for r in range(M):
        ax.plot(c, ys(r), "o", color=INK, markersize=4, zorder=3)
for r in range(M):
    ax.text(-0.35, ys(r), f"x[{rev[r]}]", ha="right", va="center", fontsize=10)
    ax.text(9.35, ys(r), f"X[{r}]", ha="left", va="center", fontsize=10)
cols = [C1, C2, C3]
for s in range(3):
    span = 2 ** s
    for r in range(M):
        a = r
        if (a // span) % 2:
            continue                                   # a is the top of a butterfly
        b = a + span
        kk = (a % span) * (M // (2 * span))            # twiddle W_8^kk on the lower input
        x0, x1 = X[s], X[s + 1]
        for (r0, r1) in [(a, a), (b, b), (a, b), (b, a)]:
            ax.annotate("", (x1 - 0.08, ys(r1)), (x0 + 0.08, ys(r0)),
                        arrowprops=dict(arrowstyle="-|>", color=cols[s], lw=1.1, mutation_scale=9,
                                        shrinkA=2, shrinkB=2))
        ax.text(x0 + 0.25, ys(b) - 0.3, f"W$^{{{kk}}}$", fontsize=8.5, color=cols[s], ha="left", va="center")
        ax.text(x1 - 0.25, ys(b) - 0.3, "−", fontsize=11, color=cols[s], ha="right", va="center")
    ax.text((X[s] + X[s + 1]) / 2, 8.0, f"stage {s + 1}:\n{2 * span}-point transforms",
            ha="center", va="bottom", fontsize=9.5, color=cols[s])
ax.text(-1.0, -0.8, "inputs in bit-reversed order: x[1] = x[001]\nsits where x[100] = x[4] would",
        fontsize=8.5, color=INK2, va="top", ha="center")
ax.text(9.6, -0.8, "outputs in order", fontsize=8.5, color=INK2, va="top", ha="center")
ax.text(4.5, -2.1, "each butterfly turns a and b into  a + W b  (top) and  a − W b  (bottom),   W$^k$ = e$^{-2πik/8}$",
        fontsize=9.5, color=INK, ha="center", va="top")
ax.set_xlim(-2.6, 10.8)
ax.set_ylim(-2.9, 9.3)
save(fig, os.path.join(IMG, "fft_butterfly.png"))
print("wrote fft_butterfly.png")
