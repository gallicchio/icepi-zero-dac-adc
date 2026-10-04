"""Chapter 6 figure: the channel sounded three ways (sound.py), one picture.

comms_sound.png
  top left:     h[n] by the m-sequence, by the step and by the multitone, with 1.07's
                saved measurement (loopback.sv, dev/data/loopback_g1_1m.npz) for comparison
  top right:    |H(f)| by the m-sequence's FFT, by the multitone and by the QPSK signal
                itself (in its band), with 6.07's saved sounding (dev/data/tb_sound_loop.npz)
  bottom left:  the phase of H(f): a straight line is a pure delay
  bottom right: the group delay, -dphase/d(2 pi f): 240 ns, flat, through the cable

    python3 fig_sound.py --sim | PORT | PORT_A PORT_B | --replot
    python3 fig_sound.py --sim --stub 25        # with a simulated 25 m open stub on a T
"""
import os
import numpy as np
import link
from plotstyle import plt, save, dots, C1, C2, C3, MUTED, INK2
import echo
import sound

NAME = "sound"
def more(ap):
    ap.add_argument("--stub", type=float, default=0.0, help="add a simulated open stub, metres (echo.py)")
    ap.add_argument("--label", default="", help="added to the caption, e.g. 'with a T and a 5 m stub'")


a = link.args(__doc__, more)
if not a.replot:
    L = link.Link(a)
    record = (lambda: echo.add_stub(L.record(), a.stub)) if a.stub else L.record
    out = sound.sound(L.play, record, records=4, align=len(a.ports) == 2)
    out["source"] = L.source + (", plus a simulated %g m stub" % a.stub if a.stub else "") + \
                    (", " + a.label if a.label else "")
    np.savez(link.data_path(NAME), **out)
d = np.load(link.data_path(NAME))
src = str(d["source"])
print(src)
print(sound.summary(d))

# 1.07's measurement, by its own method (loopback.py p), for comparison
p = np.load(os.path.join(link.TOP, "dev", "data", "loopback_g1_1m.npz"))["p"].astype(float)
x107 = 2.0 * sound.g1(1023) - 1
y107 = p[1023:16 * 1023].reshape(15, 1023).mean(axis=0)
h107 = np.real(np.fft.ifft(np.fft.fft(y107 - y107.mean()) * np.conj(np.fft.fft(x107)))) / 1024 / 96
snd = np.load(os.path.join(link.TOP, "dev", "data", "tb_sound_loop.npz"))

f = d["f"] / 1e6
band = (5.2, 7.3)                                                # psk.py's QPSK, MHz
fig, ax = plt.subplots(2, 2, figsize=(10, 7.2))
n = np.arange(32)
ax[0, 0].plot(n, h107[:32], color=MUTED, lw=1, label="1.07's measurement (loopback.sv)")
ax[0, 0].plot(n, d["h_multitone"][:32], color=C3, lw=1, label="multitone, divided, inverse FFT")
dots(ax[0, 0], n, d["h_mseq"][:32], C1, label="m-sequence, cross-correlated")
ax[0, 0].plot(n, d["h_step"][:32], "s", color=C2, mfc="none", ms=5, label="step, differenced")
ax[0, 0].set_xlabel("delay (ADC samples of 40 ns)"); ax[0, 0].set_ylabel("h[n] (ADC codes per DAC code)")
ax[0, 0].set_title("Impulse response: three probes, one answer")
ax[0, 0].legend(loc="upper right", fontsize=8)
ax[0, 1].plot(snd["f"] / 1e6, snd["H"], color=MUTED, lw=0.8, label="6.07's sounding (saved)")
ax[0, 1].plot(f, np.abs(d["H_mseq"]), color=C1, lw=0.8, label="FFT of the m-sequence's h[n]")
ax[0, 1].plot(f, np.abs(d["H_multitone"]), color=C3, lw=0.8, label="multitone, Y(f) / X(f)")
ax[0, 1].plot(f, np.abs(d["H_psk"]), color=C2, lw=1.6, label="the QPSK signal itself, Y / X")
ax[0, 1].set_ylabel("|H(f)| (ADC codes per DAC code)")
ax[0, 1].set_title("Gain against frequency")
ax[0, 1].legend(loc="upper left", fontsize=8)
ax[0, 1].set_ylim(0, max(1.35, 1.5 * np.nanmax(np.abs(d["H_multitone"]))))
for name, c, lw in (("mseq", C1, 0.8), ("multitone", C3, 0.8), ("psk", C2, 1.6)):
    H = d["H_" + name].copy()
    H[d["f"] < 0.1e6] = np.nan                                   # nothing to divide by near DC
    ok = np.isfinite(H)
    ph = np.full(len(f), np.nan)
    ph[ok] = np.degrees(np.unwrap(np.angle(H[ok])))
    ph -= 360 * np.round((ph[ok][0] + 360 * f[ok][0] * 0.240) / 360)   # the same branch as the delay line
    ax[1, 0].plot(f, ph, color=c, lw=lw)
    ax[1, 1].plot(f, sound.group_delay(d["f"], H) * 1e9, color=c, lw=lw)
ax[1, 0].plot(f, -360 * f * 0.240, "--", color=MUTED, lw=0.8, label="a pure 240 ns delay")
ax[1, 0].set_ylabel("phase of H(f) (degrees)"); ax[1, 0].legend(loc="upper right", fontsize=8)
ax[1, 0].set_title("Phase: a delay is a straight line")
ax[1, 1].set_ylabel("group delay (ns)")
ax[1, 1].set_title("Group delay, −dφ/d(2πf)")
ax[1, 1].set_ylim(-100, 500)                                 # a notch's group delay dips below zero
ax[1, 1].axhline(240, color=MUTED, lw=0.8, ls="--")
ax[1, 1].text(12.3, 455, "dashed: 240 ns, the 6 samples of 1.07", ha="right", fontsize=8, color=INK2)
for a_ in (ax[0, 1], ax[1, 0], ax[1, 1]):
    a_.set_xlabel("frequency (MHz)"); a_.set_xlim(0, 12.5)
    a_.axvspan(*band, color=C2, alpha=0.08, lw=0)
ax[0, 1].text(6.25, 0.04, "QPSK band", ha="center", fontsize=8, color=INK2)
fig.suptitle(src, x=0.99, ha="right", fontsize=8, color=MUTED)
save(fig, link.img_path(NAME))
