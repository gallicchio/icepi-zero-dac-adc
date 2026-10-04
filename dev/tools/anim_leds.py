"""Animations of the Icepi Zero's LEDs, driven by Verilator simulations of the designs.

    python3 anim_leds.py --render PCB   # (once) 3D render of the Icepi Zero's .kicad_pcb with kicad-cli
    python3 anim_leds.py --sim          # simulate counter.sv and adc_leds.sv (about a minute)
    python3 anim_leds.py                # draw tutorial/img/anim_counter.gif and anim_adc_leds.gif

The render comes from the Icepi Zero's own KiCad design (github.com/cheyao/icepi-zero),
top side, USB connectors down.  The LEDs are D1..D5 at x = 166.42 ... 178.35 mm, y = 112.25 mm
on a board that spans x = 116..181 mm, y = 90..120 mm; D1, the leftmost, is led[4].
The simulations run the real designs for 2^28 clocks (5.4 s of board time), and every
frame shows the LEDs as they were at that moment of simulated time.
"""
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "src", "verilog")
DATA = os.path.join(HERE, "..", "data")
IMG = os.path.join(HERE, "..", "..", "tutorial", "img")
RENDER = os.path.join(DATA, "icepi_zero_render.png")
SIMDIR = os.path.join(HERE, "..", "..", "tools", "anim_sim")   # scratch, git-ignored
F_CLK = 50e6
LED_X_MM = [166.4175, 169.3725, 172.36, 175.36, 178.35]          # D1..D5 = led[4]..led[0]
LED_Y_MM = 112.25
BOARD_MM = (116.0, 90.0, 181.0, 120.0)
SURFACE = (252, 252, 251)
FONT = os.path.join(os.path.dirname(__import__("matplotlib").__file__), "mpl-data", "fonts", "ttf", "DejaVuSans.ttf")
FONT_MONO = FONT.replace("DejaVuSans.ttf", "DejaVuSansMono.ttf")


def render(pcb):
    kc = os.path.expanduser("~/.local/kicad10/AppDir")
    env = dict(os.environ, LD_LIBRARY_PATH=f"{kc}/usr/lib:{kc}/usr/lib/x86_64-linux-gnu",
               KICAD10_3DMODEL_DIR=f"{kc}/share/kicad/3dmodels")
    subprocess.run([f"{kc}/usr/bin/kicad-cli", "pcb", "render", "--side", "top", "--width", "2400",
                    "--height", "1500", "--zoom", "1.4", "--quality", "high", "--background", "opaque",
                    "--preset", "follow_pcb_editor", "--use-board-stackup-colors",   # green solder mask
                    "-o", RENDER, pcb], check=True, env=env)


HARNESS = {
    "counter": r'''
#include "Vcounter.h"
#include <cstdio>
#include <cstdint>
int main() {
    Vcounter t; t.clk = 0; t.eval(); unsigned last = 99;
    for (uint64_t c = 0; c < (1ull << 28) + 2; c++) {
        t.clk = 1; t.eval();
        if (t.led != last) { printf("%llu %u\n", (unsigned long long)c, t.led); last = t.led; }
        t.clk = 0; t.eval();
    }
}''',
    # adc_leds: the DAC's ramp goes through a cable to the ADC.  The ADC is modelled with
    # the measured transfer (code = 0.776 x DAC + 27.5) and its 6-sample delay (1.07).
    "adc_leds": r'''
#include "Vadc_leds.h"
#include <cstdio>
#include <cstdint>
#include <cmath>
int main() {
    Vadc_leds t; t.clk = 0; t.adc_d = 128; t.eval();
    unsigned hist[16] = {0}; unsigned h = 0, last = 99, lastclk = 0;
    for (uint64_t c = 0; c < (1ull << 28) + 2; c++) {
        t.clk = 1; t.eval();
        if (t.adc_clk && !lastclk) {                       // the ADC samples on adc_clk's rising edge
            int code = (int)lround(0.776 * t.dac_d + 27.5);
            hist[h++ & 15] = code;
            t.adc_d = hist[(h - 6) & 15];                  // and answers 6 samples later
        }
        lastclk = t.adc_clk;
        if (t.led != last || (c & ((1u << 19) - 1)) == 0) {
            printf("%llu %u %u %u\n", (unsigned long long)c, t.led, t.dac_d, t.adc_d);
            last = t.led;
        }
        t.clk = 0; t.eval();
    }
}''',
}


def simulate(name):
    d = os.path.join(SIMDIR, name)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "harness.cpp"), "w").write(HARNESS[name])
    subprocess.run(["verilator", "--cc", "--exe", "--build", "-O3", "-j", "8", "-Wno-fatal",
                    "-Mdir", os.path.join(d, "obj"), os.path.join(SRC, name + ".sv"),
                    os.path.join(d, "harness.cpp"), "-o", "sim"], check=True, stdout=subprocess.DEVNULL)
    out = subprocess.run([os.path.join(d, "obj", "sim")], check=True, capture_output=True, text=True).stdout
    rows = np.array([[int(x) for x in line.split()] for line in out.splitlines()])
    np.save(os.path.join(DATA, f"anim_{name}.npy"), rows)
    print(name, len(rows), "rows")


def board_image(width):
    """The render cropped to the board and scaled to `width`, and the LEDs' pixel positions."""
    im = Image.open(RENDER).convert("RGB")
    a = np.asarray(im).astype(int)
    # the board is the dark (green and black) region on the light background: the rows and
    # columns that are mostly dark give its bounding box
    dark = a.sum(axis=2) < 300
    rows, cols = np.nonzero(dark.mean(axis=1) > 0.3)[0], np.nonzero(dark.mean(axis=0) > 0.3)[0]
    x0, x1, y0, y1 = cols.min(), cols.max(), rows.min(), rows.max()
    sx = (x1 - x0) / (BOARD_MM[2] - BOARD_MM[0])
    sy = (y1 - y0) / (BOARD_MM[3] - BOARD_MM[1])
    px = lambda xmm, ymm: (x0 + (xmm - BOARD_MM[0]) * sx, y0 + (ymm - BOARD_MM[1]) * sy)
    pad = int(0.04 * (x1 - x0))
    box = (x0 - pad, y0 - pad, x1 + pad, y1 + int(2.2 * pad))   # room below for the USB plugs
    k = width / (box[2] - box[0])
    board = im.crop(box).resize((width, int((box[3] - box[1]) * k)), Image.LANCZOS)
    leds = [((px(x, LED_Y_MM)[0] - box[0]) * k, (px(x, LED_Y_MM)[1] - box[1]) * k) for x in LED_X_MM]
    return board, leds, sx * k


def light(img, leds, pxmm, bits):
    """Draw the five LEDs: lit ones glow, dark ones are grey.  bits[0] is led[4] (leftmost)."""
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    g = ImageDraw.Draw(glow)
    top = ImageDraw.Draw(img)
    w, h = 0.8 * pxmm, 0.42 * pxmm
    for (x, y), on in zip(leds, bits):
        if on:
            r = 1.9 * pxmm
            g.ellipse((x - r, y - r, x + r, y + r), fill=(235, 245, 255, 230))
    glow = glow.filter(ImageFilter.GaussianBlur(0.8 * pxmm))
    img.paste(glow, (0, 0), glow)
    for (x, y), on in zip(leds, bits):
        top.rectangle((x - w, y - h, x + w, y + h), fill=(255, 255, 255) if on else (110, 108, 100))


def lit_board(parts, bits):
    """The board, lit as `bits` (led[4] first)."""
    board, leds, pxmm = parts
    b = board.copy()
    light(b, leds, pxmm, bits)
    return b


def caption(img, lines, height, size=18):
    out = Image.new("RGB", (img.width, img.height + height), SURFACE)
    out.paste(img, (0, 0))
    d = ImageDraw.Draw(out)
    f = ImageFont.truetype(FONT_MONO, size)
    for i, line in enumerate(lines):
        d.text((img.width // 2, img.height + height * (0.3 + 0.42 * i)), line, fill=(40, 40, 40), font=f, anchor="mm")
    return out


def save_gif(frames, times, out):
    """One shared palette, so that unchanged pixels stay identical and GIF stores only changes."""
    pal = frames[len(frames) // 2].quantize(colors=200, method=0)          # median cut
    q = [f.quantize(palette=pal, dither=0) for f in frames]      # no dithering
    q[0].save(out, save_all=True, append_images=q[1:], duration=durations(times), loop=0, optimize=False)
    try:    # ImageMagick, if it's there: store each frame as only what changed
        subprocess.run(["convert", out, "-layers", "Optimize", out], check=True)
    except (OSError, subprocess.CalledProcessError):
        pass
    print("wrote", out, os.path.getsize(out) // 1024, "kB")


def durations(times_s):
    """GIF frame durations in ms (10 ms units), rounded so that the total time stays exact."""
    edges = np.round(np.asarray(times_s) * 100).astype(int) * 10
    return list(np.diff(edges))


def anim_counter():
    rows = np.load(os.path.join(DATA, "anim_counter.npy"))
    parts = board_image(720)
    frames, times = [], []
    for c, led in rows[:-1]:
        f = lit_board(parts, [(led >> (4 - i)) & 1 for i in range(5)])
        frames.append(caption(f, [f"counter.sv, simulated:  led[4:0] = count[27:23] = {led:05b} = {led}",
                                  f"t = {c / F_CLK:4.2f} s  (a step every 2^23 x 20 ns = 0.168 s)"], 58))
        times.append(c / F_CLK)
    times.append(rows[-1][0] / F_CLK)
    save_gif(frames, times, os.path.join(IMG, "anim_counter.gif"))


def anim_adc_leds():
    import matplotlib
    matplotlib.use("Agg")
    sys.path.insert(0, HERE)
    from plotstyle import plt, C1, C2, INK2
    rows = np.load(os.path.join(DATA, "anim_adc_leds.npy"))
    t = rows[:, 0] / F_CLK
    dac_v = 0.0307 * rows[:, 2] - 3.95
    adc_v = (rows[:, 3] - 126.7) / 25.35
    parts = board_image(560)
    frames, times = [], []
    T = (1 << 28) / F_CLK
    for tf in np.arange(0, T, 0.1):
        i = np.searchsorted(t, tf, side="right") - 1
        led, adc = rows[i, 1], rows[i, 3]
        fig, ax = plt.subplots(figsize=(3.6, 2.9), dpi=100)
        sel = t <= tf
        ax.plot(t[sel], adc_v[sel], color=C1, lw=1.5)
        ax.plot(t[i], adc_v[i], "o", color=C1)
        ax.set_xlim(0, T)
        ax.set_ylim(-5, 5)
        ax.set_xlabel("time (s)")
        ax.set_ylabel("ADC input (V)")
        ax.set_title("The DAC's slow ramp, at the ADC", fontsize=10)
        fig.tight_layout()
        fig.canvas.draw()
        plot = Image.frombuffer("RGBA", fig.canvas.get_width_height(), fig.canvas.buffer_rgba()).convert("RGB")
        plt.close(fig)
        f = lit_board(parts, [(led >> (4 - k)) & 1 for k in range(5)])
        f = caption(f, [f"ADC code {adc:3d} = {adc:08b}", f"LEDs: its top 5 bits, {led:05b}"], 58)
        frame = Image.new("RGB", (f.width + plot.width, max(f.height, plot.height)), SURFACE)
        frame.paste(f, (0, (frame.height - f.height) // 2))
        frame.paste(plot, (f.width, (frame.height - plot.height) // 2))
        frames.append(frame)
        times.append(tf)
    times.append(T)
    save_gif(frames, times, os.path.join(IMG, "anim_adc_leds.gif"))


if __name__ == "__main__":
    if "--render" in sys.argv:
        render(sys.argv[sys.argv.index("--render") + 1])
    if "--sim" in sys.argv:
        simulate("counter")
        simulate("adc_leds")
    anim_counter()
    anim_adc_leds()
