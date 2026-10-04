"""Small opening figures, cropped from figures made by the other scripts (run those first).

    python3 fig_teasers.py      # writes tutorial/img/*_top.png
"""
import os

from PIL import Image

IMG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tutorial", "img")
SURFACE = (252, 252, 251)

# (source, output, [crop boxes stacked top to bottom], in pixels of the source)
CROPS = [
    ("tb_beat.png", "tb_beat_top.png", [(0, 0, 975, 395)]),            # 5.01: the beat
    ("tb_warmup.png", "tb_warmup_top.png", [(0, 0, 975, 385), (0, 768, 975, 832)]),  # 5.02: + the time axis
    ("pll.png", "pll_top.png", [(0, 0, 1040, 375)]),                   # the faster DAC's reach
    ("sawtooth.png", "sawtooth_top.png", [(0, 0, 1040, 395)]),         # 1c
    ("sine.png", "sine_top.png", [(0, 0, 1040, 395)]),                 # 1d
    ("capture.png", "capture_top.png", [(0, 0, 1040, 455)]),           # 1g
    ("loopback_step.png", "loopback_step_top.png", [(0, 0, 1040, 425)]),  # 1h
]
for src, out, boxes in CROPS:
    im = Image.open(os.path.join(IMG, src)).convert("RGB")
    parts = [im.crop(b) for b in boxes]
    canvas = Image.new("RGB", (max(p.width for p in parts), sum(p.height for p in parts)), SURFACE)
    y = 0
    for p in parts:
        canvas.paste(p, (0, y))
        y += p.height
    canvas.save(os.path.join(IMG, out))
    print("wrote", out, canvas.size)

# 4.00: four of the chapter's circuits, two by two
names = ["exp_rc_low.png", "exp_crystal.png", "exp_stub.png", "exp_ultrasound.png"]
ims = [Image.open(os.path.join(IMG, n)).convert("RGB") for n in names]
W = 520
ims = [im.resize((W, int(im.height * W / im.width)), Image.LANCZOS) for im in ims]
H = max(im.height for im in ims)
canvas = Image.new("RGB", (2 * W + 30, 2 * H + 30), SURFACE)
for k, im in enumerate(ims):
    canvas.paste(im, ((k % 2) * (W + 30), (k // 2) * (H + 30) + (H - im.height) // 2))
canvas.save(os.path.join(IMG, "exp_montage.png"))
print("wrote exp_montage.png", canvas.size)
