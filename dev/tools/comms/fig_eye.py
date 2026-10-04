"""Chapter 6 figures: eye diagrams of baseband BPSK (eye.py), square and root-raised-
cosine pulses, raw and after the matched filter, at rising symbol rates.

comms_eye.png        through the cable as it is
comms_eye_noise.png  with noise added at the transmitter (rms 0.7 x the signal's,
                     spread over the DAC's whole 0-25 MHz)
comms_eye_slow.png   square pulses, raw, through a slow cable: in --sim a 3 MHz
                     two-pole low-pass; on a board, put a low-pass filter in the
                     cable (an RC as in 4.02, R C about 50 ns) and run with --slow

    python3 fig_eye.py --sim | PORT | PORT_A PORT_B | --replot
"""
import numpy as np
import link
from plotstyle import plt, save, C1, C2, MUTED
import eye

NAME = "eye"
RATES = (511, 2047, 4095)                      # 1.56, 6.25, 12.5 Mbaud
SLOW = (255, 511, 1023, 2047, 4095)
COLS = (("square", "raw"), ("square", "matched"), ("rrc", "raw"), ("rrc", "matched"))
a = link.args(__doc__, lambda ap: ap.add_argument("--slow", action="store_true",
              help="board: only the slow-cable figure (a low-pass is in the cable)"))


def measure(L, rates, noise, pulses=("square", "rrc")):
    out = {}
    for nsym in rates:
        for pulse in pulses:
            L.play(eye.waveform(nsym, pulse, noise, rng=nsym))
            rec = L.record()
            x = rec[:eye.L] - rec.mean()
            for kind, y in (("raw", x), ("matched", eye.matched(x, nsym, pulse))):
                y = y / np.median(np.abs(y))
                ph = eye.fold(y, nsym)
                out["%s_%s_%d" % (pulse, kind, nsym)] = np.array([ph, y], dtype=np.float32)
    return out


if not a.replot:
    out = {}
    if not a.slow:
        L = link.Link(a)
        out.update({"clean_" + k: v for k, v in measure(L, RATES, 0.0).items()})
        out.update({"noise_" + k: v for k, v in measure(L, RATES, 0.7).items()})
        out["source"] = L.source
        np.savez_compressed(link.data_path(NAME), **out)
    L = link.Link(a, corner=3e6)
    slow = measure(L, SLOW, 0.0, pulses=("square",))
    slow["source"] = L.source + (", 3 MHz cable" if a.sim else ", low-pass in the cable")
    np.savez_compressed(link.data_path(NAME + "_slow"), **slow)
d = np.load(link.data_path(NAME))
ds = np.load(link.data_path(NAME + "_slow"))


def panel(ax_, ph, y, color):
    for shift in (-1, 0, 1):
        ax_.plot(ph + shift, y, ".", color=color, markersize=0.7, alpha=0.6, rasterized=True)
    op = eye.opening(ph, y)
    ax_.text(0.02, 0.03, "open %.0f%%" % (100 * op) if op > 0 else "shut", transform=ax_.transAxes,
             fontsize=8, color="#52514e")
    ax_.set_xlim(-1, 1); ax_.set_ylim(-2.1, 2.1)
    ax_.set_xticks([-1, 0, 1]); ax_.set_yticks([-1, 0, 1])


for prefix, fname, title in (("clean_", "eye", "through the cable"),
                             ("noise_", "eye_noise", "with noise, 0.7 x the signal, at the transmitter")):
    fig, ax = plt.subplots(len(RATES), 4, figsize=(10, 2.3 * len(RATES) + 0.6), sharex=True, sharey=True)
    for i, nsym in enumerate(RATES):
        for j, (pulse, kind) in enumerate(COLS):
            ph, y = d["%s%s_%s_%d" % (prefix, pulse, kind, nsym)]
            panel(ax[i, j], ph, y, C1 if pulse == "square" else C2)
            if i == 0:
                ax[i, j].set_title("%s pulses, %s" % (pulse.replace("rrc", "RRC"),
                                   "matched filter" if kind == "matched" else "as recorded"), fontsize=9)
        ax[i, 0].set_ylabel("%.2f Mbaud" % (nsym * eye.FS_DAC / eye.N / 1e6))
    for a_ in ax[-1]:
        a_.set_xlabel("time (symbols)")
    fig.suptitle("Eye diagrams, BPSK at baseband, %s  —  %s" % (title, d["source"]), fontsize=9, color=MUTED)
    save(fig, link.img_path(fname))

fig, ax = plt.subplots(1, len(SLOW), figsize=(12, 2.8), sharey=True)
for i, nsym in enumerate(SLOW):
    ph, y = ds["square_raw_%d" % nsym]
    panel(ax[i], ph, y, C1)
    ax[i].set_title("%.2f Mbaud" % (nsym * eye.FS_DAC / eye.N / 1e6), fontsize=9)
    ax[i].set_xlabel("time (symbols)")
ax[0].set_ylabel("square pulses, as recorded")
fig.suptitle("The eye closes as the symbols get shorter than the cable's response  —  %s" % ds["source"],
             fontsize=9, color=MUTED)
save(fig, link.img_path(NAME + "_slow"))
