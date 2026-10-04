"""1.10's figures, from am_radio.sv on one board, its DAC cabled to its ADC (101.5 cm RG-316).

    load am_radio.bit, then
    python3 fig_am.py            # record (about 1.5 minutes), then draw
    python3 fig_am.py --replot   # draw from data/am_radio.npz

am_intro.png        the received melody's spectrogram, with the notes it should be
am_selectivity.png  the receiver's response to a bare carrier, against how far it's tuned off
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src", "verilog"))
from plotstyle import plt, save, dots, C1, C2, C3, INK, INK2, MUTED   # noqa: E402

DATA = os.path.join(HERE, "..", "data", "am_radio.npz")
IMG = os.path.join(HERE, "..", "..", "tutorial", "img")
FS = 25_000
OFFSETS = np.arange(-30, 31) * 1e3

if "--replot" not in sys.argv:
    import serial
    import am_radio
    with serial.Serial(am_radio.find_port(), 1_000_000, timeout=2) as ser:
        env, _, g = am_radio.listen(ser, source="melody", seconds=14)
        sel = []
        for off in OFFSETS:
            e, _, _ = am_radio.listen(ser, rx=1e6 + off, source="carrier", seconds=0.3)
            sel.append(e.mean() / am_radio.ENV_PER_CODE)
            print(f"{off / 1e3:+5.0f} kHz: {sel[-1]:9.4f} codes", flush=True)
    np.savez(DATA, melody=env, g=g, offsets=OFFSETS, carrier_codes=np.array(sel))
d = np.load(DATA)

# ---- the melody, as heard ---------------------------------------------------------------
x = d["melody"] / 473.1                         # carrier amplitude in ADC codes, with the tune on it
x = x - x.mean()
NFFT, HOP = 4096, 512
w = np.hanning(NFFT)
frames = [np.abs(np.fft.rfft(w * x[i:i + NFFT])) for i in range(0, len(x) - NFFT, HOP)]
S = 20 * np.log10(np.array(frames).T + 1e-6)
f = np.fft.rfftfreq(NFFT, 1 / FS)
t = (np.arange(S.shape[1]) * HOP + NFFT / 2) / FS
fig, ax = plt.subplots(figsize=(9.5, 4.2))
sel = f < 900
ax.grid(False)
ax.pcolormesh(t, f[sel], S[sel], shading="auto", cmap="magma", vmin=S[sel].max() - 60, vmax=S[sel].max())
NOTES = {"C": 261.63, "D": 293.66, "E": 329.63, "F": 349.23, "G": 392.00}
for name, hz in NOTES.items():
    ax.axhline(hz, color="white", lw=0.4, alpha=0.35)
    nudge = {"E": -9, "F": 9}.get(name, 0)
    ax.text(t[-1] + 0.1, hz + nudge, name + "4", va="center", fontsize=9, color=INK2)
ax.set_xlim(t[0], t[-1])
ax.set_ylim(150, 900)
ax.set_xlabel("time (s)")
ax.set_ylabel("frequency (Hz)")
ax.set_title("Ode to Joy, sent by the DAC as AM at 1 MHz and received by the ADC (measured)")
ax.text(0.01, 0.97, "each note, and its octave above", transform=ax.transAxes, va="top",
        fontsize=8.5, color="white")
save(fig, os.path.join(IMG, "am_intro.png"))

# ---- selectivity ------------------------------------------------------------------------
c = d["carrier_codes"]
on = c[len(c) // 2]
db = 20 * np.log10(np.maximum(c, 1e-4) / on)
fig, ax = plt.subplots(figsize=(8, 3.6))
ax.plot(d["offsets"] / 1e3, db, color=C1, lw=1)
dots(ax, d["offsets"] / 1e3, db, C1, label="measured: a bare 1 MHz carrier, the receiver tuned off by Δf")
ax.axvspan(-4.33, 4.33, color=C3, alpha=0.12, lw=0, label="the audio band it passes (±4.3 kHz, −3 dB)")
ax.set_xlabel("receiver tuned off by Δf (kHz)")
ax.set_ylabel("received carrier (dB)")
ax.set_ylim(-110, 8)
ax.set_title("The receiver's selectivity: a station 10 kHz away is gone")
ax.annotate("the CIC filter's aliases:\na station 21 kHz away\nleaks through at −44 dB", (21, -44), xytext=(9, -30),
            arrowprops=dict(arrowstyle="->", color=INK2, lw=0.8), fontsize=8.5, color=INK2)
ax.legend(loc="lower center", fontsize=8.5)
save(fig, os.path.join(IMG, "am_selectivity.png"))
for off in (5, 10, 20):
    i, j = list(d["offsets"]).index(off * 1e3), list(d["offsets"]).index(-off * 1e3)
    print(f"±{off} kHz: {db[i]:.1f} / {db[j]:.1f} dB")
print("on tune:", round(on, 2), "codes")


# ---- the receiver, as a block diagram (no data) ----------------------------------------
def chain():
    import schemdraw
    import schemdraw.dsp as dsp
    from PIL import Image, ImageOps
    SURFACE = "#fcfcfb"
    schemdraw.config(fontsize=11, bgcolor=SURFACE, lw=1.3)
    with schemdraw.Drawing(show=False) as d:
        dsp.Line().right(0.6).label("ADC IN", "left")
        dsp.Adc().label("ADC\n25 MS/s", "bottom")
        dsp.Line().right(0.6)
        node = dsp.Dot()
        for sign, ref, name in [(1, "cos", "I"), (-1, "−sin", "Q")]:
            (dsp.Line().at(node.center).up(1.2) if sign > 0 else dsp.Line().at(node.center).down(1.2))
            dsp.Arrow().right(0.8)
            m = dsp.Mixer().anchor("W").label(f"× {ref}(2π f$_{{rx}}$ t)", "top" if sign > 0 else "bottom", fontsize=10)
            dsp.Arrow().at(m.E).right(0.7)
            c = dsp.Box(w=2.7, h=1.1).anchor("W").label("CIC filter\nkeep 1 in 1000", fontsize=10)
            dsp.Arrow().at(c.E).right(1.3).label("25 kS/s", "top", fontsize=9)
            fr = dsp.Box(w=2.9, h=1.1).anchor("W").label("FIR filter\n127 taps, 4.3 kHz", fontsize=10)
            dsp.Arrow().at(fr.E).right(0.8).label(name, "top", fontsize=10)
            ends = d.here
            if sign > 0:
                top = ends
            else:
                bot = ends
        dsp.Line().at(top).down(1.2)
        mid = d.here
        dsp.Line().at(bot).up(1.2)
        env = dsp.Box(w=2.3, h=1.0).at((mid[0], mid[1])).anchor("W").label("√(I² + Q²)\nthe envelope", fontsize=10)
        dsp.Arrow().at(env.E).right(1.0).label("sound", "top", fontsize=10)
        dsp.Box(w=2.8, h=1.0).anchor("W").label("UART → laptop\n25,000 a second", fontsize=10)
        path = os.path.join(IMG, "am_chain.png")
        d.save(path, dpi=130, transparent=False)
    im = Image.open(path).convert("RGBA")
    flat = Image.alpha_composite(Image.new("RGBA", im.size, SURFACE), im).convert("RGB")
    ImageOps.expand(flat, border=16, fill=SURFACE).save(path)
    print("wrote am_chain.png")


chain()
