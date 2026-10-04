#!/usr/bin/env python3
"""Chapter 6 figure: FT8-style 8-FSK through the cable (src/comms/ft8.py).

    python3 fig_ft8.py PORT          # one board looped back
    python3 fig_ft8.py --sim         # channel.py's model
    python3 fig_ft8.py --replot      # from the saved data

Panels: the frame as a waterfall (what WSJT-X shows), the Costas search over start time
and frequency offset, the 8 tone magnitudes at every symbol with the sent tones, and
the decode rate and symbol error rate against Es/N0 with non-coherent 8-FSK theory
and real FT8's threshold.
"""
import numpy as np
import link
from plotstyle import plt, save, C1, C2, C3, INK, INK2, MUTED
import ft8

NAME = "ft8"
a = link.args(__doc__, lambda ap: ap.add_argument("--frames", type=int, default=10, help="frames per Es/N0 point"))
if not a.replot:
    Lk = link.Link(a)
    rng = np.random.default_rng(1)
    tones = ft8.encode("CQ HMC JASON")
    Lk.play(ft8.transmit(tones))                       # clean, for the waterfall
    rec_clean = Lk.record()
    Lk.play(ft8.transmit(tones, 7.0, rng=rng))         # at FT8's kind of SNR, for the rest
    rec = Lk.record()
    r = ft8.receive(ft8.baseband(rec), ft8.SPS, period=ft8.L)
    print("%s: at Es/N0 7 dB: %r CRC %s, %d data symbols wrong" % (Lk.source, r["text"], r["ok"],
          int(np.sum(r["heard"][ft8.DATA_AT] != tones[ft8.DATA_AT]))))
    esn0 = np.arange(-1.0, 11.5, 1.0)
    rows = ft8.rate_run(Lk.play, Lk.record, esn0, frames=a.frames, seed=2)
    np.savez(link.data_path(NAME), rec=rec, rec_clean=rec_clean, tones=tones, M=r["M"], heard=r["heard"], t0=r["t0"], nu=r["nu"],
             surface=r["surface"], nus=r["nus"], text=r["text"], ok=r["ok"], rows=rows, source=Lk.source, frames=a.frames)
d = np.load(link.data_path(NAME))
src = str(d["source"])

fig, ax = plt.subplots(2, 2, figsize=(13, 9))

# (a) waterfall: 100-sample windows at every symbol position, 2x oversampled in time
rec = d["rec_clean"].astype(float)
z = ft8.baseband(rec)[:ft8.L]
t0 = int(ft8.sync(ft8.baseband(rec), ft8.SPS, 0.5)[0]) % ft8.L
hop = ft8.SPS // 4
starts = np.arange(0, ft8.L - ft8.SPS, hop)
f = (np.arange(-6, 6, 0.25))                                   # in tone spacings
W = np.zeros((len(f), len(starts)))
n = np.arange(ft8.SPS)
for j, s in enumerate(starts):
    seg = z[s:s + ft8.SPS]
    W[:, j] = np.abs(np.exp(-2j * np.pi * np.outer(f, n) / ft8.SPS) @ seg)
W = 20 * np.log10(W / W.max() + 1e-6)
A = ax[0, 0]
A.imshow(W, aspect="auto", origin="lower", cmap="Blues", vmin=-30, vmax=0,
         extent=((starts[0] - t0) / ft8.SPS, (starts[-1] - t0) / ft8.SPS, f[0] + ft8.TONE_OFF + 3.5, f[-1] + ft8.TONE_OFF + 3.5))
for p in ft8.COSTAS_AT:
    A.axvspan(p, p + 7, color=C2, alpha=0.12, lw=0)
A.set_xlim(-2, ft8.NSYM + 2)
A.set_xlabel("symbol (from the frame's start)"); A.set_ylabel("frequency from 6.25 MHz (tone spacings)")
A.set_title("The frame, clean: 79 tones 4 µs long, three Costas arrays (shaded)", loc="left", fontweight="bold")

# (b) the Costas search
S = d["surface"]; nus = d["nus"]
B = ax[0, 1]
roll = int(d["t0"])
Sx = np.roll(S, -roll + S.shape[1] // 2, axis=1)
B.imshow(Sx / Sx.max(), aspect="auto", origin="lower", cmap="Blues",
         extent=((-S.shape[1] // 2) / ft8.SPS, (S.shape[1] // 2) / ft8.SPS, nus[0], nus[-1]))
B.plot(0, d["nu"], "x", color=C2, ms=12, mew=2)
B.set_xlim(-10, 10)
B.set_xlabel("start time (symbols from the one found)"); B.set_ylabel("frequency offset tried (tone spacings)")
B.set_title("The Costas search at Es/N0 7 dB: 21 known symbols vote", loc="left", fontweight="bold")

# (c) magnitudes
M = d["M"]; tones = d["tones"]; heard = d["heard"]
Cc = ax[1, 0]
Cc.imshow(M.T / M.max(), aspect="auto", origin="lower", cmap="Blues", extent=(-0.5, ft8.NSYM - 0.5, -0.5, 7.5))
Cc.plot(np.arange(ft8.NSYM), tones, "o", color=C2, ms=4, mfc="none", label="sent")
wrong = heard != tones
Cc.plot(np.arange(ft8.NSYM)[wrong], heard[wrong], "x", color=INK, ms=6, label="heard wrong (%d)" % wrong.sum())
Cc.set_xlabel("symbol"); Cc.set_ylabel("tone"); Cc.set_yticks(range(8))
Cc.legend(loc="upper right", fontsize=8)
Cc.set_title("The 8 magnitudes at each symbol, 7 dB: decoded %r, CRC %s" % (str(d["text"]), "ok" if d["ok"] else "failed"),
             loc="left", fontweight="bold")

# (d) decode rate and symbol errors
rows = d["rows"]
D = ax[1, 1]
e = np.linspace(-2, 12, 200)
D.plot(e, ft8.ser_theory_8fsk(e), color=INK2, lw=1, label="symbol errors, non-coherent 8-FSK theory")
D.plot(rows[:, 0], rows[:, 2], "o", color=C1, label="symbol errors, measured")
D.plot(rows[:, 0], rows[:, 1], "s-", color=C2, label="frames decoded (CRC ok), %d per point" % int(d["frames"]))
D.axvline(5.0, color=C3, lw=1, ls="--")
D.text(4.9, 0.30, "real FT8 decodes here:\n-21 dB in 2.5 kHz = Es/N0 5 dB\n(LDPC(174,91), 13 characters)", color=C3, fontsize=8, ha="right")
D.set_xlabel("Es/N0 (dB): energy per symbol / noise density  (FT8's scale: this minus 26 dB)")
D.set_ylabel("fraction")
D.set_ylim(-0.02, 1.02); D.set_xlim(-2, 12)
D.legend(loc="upper right", fontsize=8)
D.set_title("What it takes: symbols wrong, and messages through", loc="left", fontweight="bold")

fig.suptitle(src, x=0.99, ha="right", fontsize=8, color=MUTED)
fig.tight_layout()
save(fig, link.img_path(NAME))
