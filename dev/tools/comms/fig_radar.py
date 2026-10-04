"""Chapter 6 figure: radar on a cable.  A T at the DAC with an open-ended stub sends an
echo one round trip later; the compressed chirp shows the direct path and the echo
as two peaks (chirp.py).

comms_radar.png
  left    a chirp sweeping 10 MHz, a 30 m stub: the direct path, the echo at 2 L / v,
          and the echo's echo
  middle  the same stub with a 2 MHz sweep: one range cell is 52 m, the two merge
  right   with noise at the signal's peak power, 10 MHz: a pulse 1/B long (resolution,
          no energy), a pulse 10/B long (energy, no resolution), and the chirp (both)

With --sim the model has no T: the echo is added to the envelope (chirp.stub_echo),
0.67 of the direct signal, then -1/3 of that per further round trip, and the DAC
plays the direct signal at a fixed 20 codes, as a DAC would (the T's sum isn't its
problem).  With a board, put a real T and stub on DAC OUT and give the stub's length
for the annotations: the board then plays each waveform at full scale.

    python3 fig_radar.py --sim | PORT | --replot [--stub 30] [--gamma 0.67]
"""
import numpy as np
import link
from plotstyle import plt, save, C1, C2, C3, MUTED, INK2
import chirp

NAME = "radar"
BW_HI, BW_LO = 10e6, 2e6
SNR = 0.0                                                # noise power = the signal's peak power, in B
GAIN = 20.0                                              # --sim: DAC codes per unit envelope
a = link.args(__doc__, lambda ap: (ap.add_argument("--stub", type=float, default=30.0, help="stub length, m"),
                                   ap.add_argument("--gamma", type=float, default=0.67, help="--sim: echo size")))
if not a.replot:
    Lk = link.Link(a)
    out = {"source": Lk.source, "stub": a.stub, "gamma": a.gamma}
    u = np.arange(chirp.N)
    carrier = np.exp(2j * np.pi * chirp.F_C * u / chirp.FS_DAC)

    def play_rec(env, bw, snr=None, rng=None):
        if a.sim:
            s = np.real(chirp.stub_echo(env, a.stub, a.gamma) * carrier)
            if snr is not None:
                s = s + chirp.white_noise(0.5 / (bw * 10**(snr / 10)), rng)
            Lk.play(128 + GAIN * s)
        else:
            Lk.play(chirp.transmit(env, snr, 0, rng, bw, 0.5))
        return chirp.mixdown(Lk.record())

    for tag, bw in (("hi", BW_HI), ("lo", BW_LO)):
        env = chirp.envelope("chirp", bw)
        out["chirp_" + tag] = chirp.compress(play_rec(env, bw), chirp.reference(env))
    for tag, width in (("short", 1.0), ("long", 10.0), ("chirp", None)):
        env = chirp.envelope("chirp", BW_HI) if width is None else chirp.envelope("pulse", BW_HI, width=width)
        ref = chirp.reference(env)
        out["clean_" + tag] = chirp.compress(play_rec(env, BW_HI), ref)
        out["noisy_" + tag] = chirp.compress(play_rec(env, BW_HI, SNR, rng=3), ref)
    np.savez_compressed(link.data_path(NAME), **out)
d = np.load(link.data_path(NAME))
src = str(d["source"])
L, FS, v = chirp.L, chirp.FS_ADC, chirp.V_CABLE
stub = float(d["stub"])
lag_ns = ((np.arange(L) + L / 2) % L - L / 2) / FS * 1e9
order = np.argsort(lag_ns)
rt = 2 * stub / v * 1e9                                         # the round trip, ns


def db(r, peak=None):
    return 20 * np.log10(np.abs(r) / (np.abs(r).max() if peak is None else peak) + 1e-9)


fig, ax = plt.subplots(1, 3, figsize=(10, 4.2))
for i, (tag, bw) in enumerate((("hi", BW_HI), ("lo", BW_LO))):
    r = db(d["chirp_" + tag])
    k = int(np.argmax(np.abs(d["chirp_" + tag])))
    t0 = lag_ns[k]
    ax[i].plot(lag_ns[order] - t0, r[order], color=C1, lw=1.2)
    for n in (1, 2):
        ax[i].axvline(n * rt, color=C2, lw=0.8, ls="--")
    ax[i].text(rt + 15, -2, "echo: 2L/v\n= %.0f ns" % rt, fontsize=8, color=C2, va="top")
    ax[i].set_xlim(-300, 1000); ax[i].set_ylim(-40, 3)
    ax[i].set_xlabel("delay from the direct path (ns)")
    cell = 1 / bw * 1e9
    ax[i].set_title("%.0f MHz sweep: a cell is %.0f ns = %.0f m\nthe echo sits at %.1f cells"
                    % (bw / 1e6, cell, chirp.cell(bw), rt / cell), fontsize=9.5)
    top = ax[i].secondary_xaxis("top", functions=(lambda t: t * 1e-9 * v / 2, lambda m: m * 2 / v * 1e9))
    top.set_xlabel("stub length that would echo here (m)", fontsize=8, color=INK2)
    top.tick_params(labelsize=8)
ax[0].set_ylabel("compressed output (dB)")
k = int(np.argmax(np.abs(d["clean_chirp"])))
for i, (tag, c, lab) in enumerate((("short", MUTED, "pulse 1/B = 100 ns long"), ("long", C3, "pulse 10/B = 1 µs long"),
                                   ("chirp", C1, "chirp, 328 µs long"))):
    r = db(d["noisy_" + tag], np.abs(d["clean_" + tag]).max())      # relative to its own clean peak
    off = -45 * (2 - i)
    ax[2].plot(lag_ns[order] - lag_ns[k], r[order] + off, color=c, lw=0.8)
    ax[2].axhline(off, color=MUTED, lw=0.4, ls=":")
    ax[2].text(-280, off + 3, lab, fontsize=8, color=INK2, va="bottom")
    far = np.abs((np.arange(L) - k + L / 2) % L - L / 2) > 60
    floor = 10 * np.log10(np.mean(np.abs(d["noisy_" + tag][far])**2)) - 20 * np.log10(np.abs(d["clean_" + tag]).max())
    ax[2].text(990, off - 6, "noise floor %.0f dB:\n%s" % (floor, ("lost", "one blob", "two peaks")[i]),
               fontsize=8, color=INK2, va="top", ha="right")
ax[2].axvline(rt, color=C2, lw=0.8, ls="--")
ax[2].set_xlim(-300, 1000); ax[2].set_ylim(-145, 12); ax[2].set_yticks([])
ax[2].set_xlabel("delay from the direct path (ns)")
ax[2].set_ylabel("dB re each clean peak, 45 dB apart")
ax[2].set_title("Noise at the peak power, %.0f MHz:\nenergy, resolution, or both" % (BW_HI / 1e6), fontsize=9.5)
fig.suptitle(src + "; %.0f m stub%s" % (stub, ", echo %.2f, modelled" % float(d["gamma"]) if "simulated" in src else ""),
             x=0.99, ha="right", fontsize=8, color=MUTED)
save(fig, link.img_path(NAME))
print("stub %.1f m: round trip %.0f ns = %.2f samples; cells: %.1f at 10 MHz, %.1f at 2 MHz"
      % (stub, rt, rt * 1e-9 * FS, rt * 1e-9 * BW_HI, rt * 1e-9 * BW_LO))
for tag in ("hi", "lo"):
    r = np.abs(d["chirp_" + tag]); k = int(np.argmax(r))
    sel = (lag_ns - lag_ns[k] > rt * 0.5) & (lag_ns - lag_ns[k] < rt * 1.5)
    j = np.argmax(np.where(sel, r, 0))
    print("  %s: biggest peak after the direct path at %.0f ns, %.1f dB" % (tag, lag_ns[j] - lag_ns[k], 20 * np.log10(r[j] / r[k])))
for tag in ("short", "long", "chirp"):
    r = np.abs(d["noisy_" + tag]); p = np.abs(d["clean_" + tag]).max(); k = int(np.argmax(np.abs(d["clean_" + tag])))
    far = np.abs((np.arange(L) - k + L / 2) % L - L / 2) > 60
    print("  noisy %-5s: peak %.1f dB re clean, floor (rms beyond 60 samples) %.1f dB" % (tag, 20 * np.log10(r[k] / p), 10 * np.log10(np.mean(r[far]**2) / p**2)))
