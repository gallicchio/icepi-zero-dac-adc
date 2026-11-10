#!/usr/bin/env python3
"""The two-board picture: A's DAC as X against B's DAC as Y, from icepi_samples.txt (tb_icepi.v) -> ../renders/icepi_show_sheet.png
(the first frame of each mode and finale) and ../renders/icepi_show.gif (every recorded frame)"""
import os, sys, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "host"))
import scene
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = GIFS = os.path.join(HERE, "..", "renders"); os.makedirs(GIFS, exist_ok=True)   # not in git
frames, cur, modes, mode = [], [], [], None
for line in open(os.path.join(HERE, "icepi_samples.txt")):
    if line[0] == "F":
        if cur and mode is not None: frames.append(np.array(cur)); modes.append(mode)   # frames before the first mode marker: the start-up, left out
        cur = []
    elif line[0] == "M":                                   # a new mode: what came before it is the last one's (its frame's end)
        if cur and mode is not None: frames.append(np.array(cur)); modes.append(mode)
        cur = []; mode = (int(line.split()[1]), int(line.split()[2]))
    else:
        x, y = line.split()
        if x != "x" and y != "x": cur.append((int(x), int(y)))
print(len(frames), "frames; samples per frame:", [len(f) for f in frames])
imgs = [scene.phosphor(np.column_stack([(f[:, 0] - 128) / 127.0, (f[:, 1] - 128) / 127.0, np.ones(len(f))]), jump_weight=1.0) for f in frames]
scene.to_gif(imgs, os.path.join(GIFS, "icepi_show.gif"), fps=6)
import matplotlib, json; matplotlib.use("Agg"); import matplotlib.pyplot as plt
fins = json.load(open(os.path.join(HERE, "..", "host", "finales.json")))
names = {1: "the seal, its 3D globe", 2: "the seal turns over"}
def name(m): return "mode %d: %s" % (m[0], names[m[0]]) if m[0] < 3 else "finale %d: %s" % (m[1], fins[m[1]]["kind"])
firsts = [(m, i) for i, m in enumerate(modes) if i == 0 or modes[i - 1] != m]
cols = 5; rows = (len(firsts) + cols - 1) // cols
fig, axs = plt.subplots(rows, cols, figsize=(4.0 * cols, 3.5 * rows), facecolor="black")
for ax in axs.flat: ax.axis("off")
def tile(m, i):
    """the seal's modes: their second frame (a whole one: the seal is longer than the FIFO); a finale: all its samples
    together (its frames are shorter than the FIFO holds and the frame marks are the engine's, which runs ahead of the
    DACs, so one mark-to-mark window can hold part of one frame and part of the next)"""
    if m[0] < 3: return imgs[min(i + 1, len(imgs) - 1)]
    f = np.vstack([fr for fr, mm in zip(frames, modes) if mm == m]); f = f[f[:, 1] >= 16]     # not the park and the burst, below the drawing
    return scene.phosphor(np.column_stack([(f[:, 0] - 128) / 127.0, (f[:, 1] - 128) / 127.0, np.ones(len(f))]), jump_weight=1.0)
for ax, (m, i) in zip(axs.flat, firsts):
    ax.imshow(tile(m, i)); ax.set_title(name(m), color="0.85", fontsize=9)
fig.suptitle("two Icepi Zero stacks, simulated: board A's 8-bit DAC as X, board B's as Y, B in step through A's burst", color="white", fontsize=10)
fig.savefig(os.path.join(OUT, "icepi_show_sheet.png"), dpi=90, bbox_inches="tight", facecolor="black"); print("wrote icepi_show_sheet.png, icepi_show.gif")
