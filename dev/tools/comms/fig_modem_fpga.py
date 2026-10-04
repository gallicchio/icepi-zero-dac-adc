"""Chapter 6 figure: the FPGA modem's loops (modem_fpga_model.py, integers and shifts)
against psk.py's floating-point ones, on the same samples.

comms_modem_fpga.png  the fixed-point receiver's symbols after the loops, and the symbol
                      rate and carrier offset each receiver finds, against time, with the
                      transmitter's clock 2000 ppm fast and its carrier moved to +3 kHz

    python3 fig_modem_fpga.py --sim | --replot

Simulation only: qpsk_modem.bit keeps its loops' state inside the FPGA (the testbench
reads it out, the board has no command for that), so there is nothing to measure here;
qpsk_modem_check.py shows the Verilog and this model agree to the last bit.
"""
import numpy as np
import link
from plotstyle import plt, save, C1, C2, MUTED
import psk
import modem_fpga_model as M

NAME = "modem_fpga"
PPM, CFO = 2000.0, -9500.0                      # the transmitter's clock, and a mixer error on top
a = link.args(__doc__)
if a.ports:
    raise SystemExit("this figure is simulated only: the board can't export its loops' state (see the docstring)")
if not a.replot:
    rng = np.random.default_rng(1)
    data = rng.integers(0, 256, 400)
    words, _ = M.frames_for(data, gap=1, lead=60)
    dac = M.tx_dac(M.tx_symbols(words))
    adc = M.stream_channel(dac, ppm=PPM, cfo=CFO, rng=1)
    r = M.receive(adc)                                        # the fixed-point receiver
    y = psk.matched(adc)                                      # psk.py's, in floating point
    zs, times, ted, period = psk.timing_loop(y, 16)
    zs = zs / np.sqrt(np.mean(np.abs(zs)**2))
    zc, phi, w, ec = psk.costas(zs, 4)
    np.savez(link.data_path(NAME), source="simulated (channel.py's model)", ppm=PPM, hz=PPM * 6.25 + CFO,
             errs=M.score(data, r["bytes"]), nbytes=len(data),
             **{"m_" + k: r[k] for k in ("sym", "mu", "ppm", "hz", "zI", "zQ", "locked", "eg", "ec")},
             p_times=times, p_period=period, p_w=w, p_zc=zc, p_sps=16.0)
d = np.load(link.data_path(NAME))
src = str(d["source"])
print("%s: %d bit errors in %d bits" % (src, d["errs"], 8 * int(d["nbytes"])))

R = M.R_SYM
fig, ax = plt.subplots(2, 3, figsize=(10.5, 7))
k = d["m_sym"]
us = k / 6.25e6 * 1e6                                       # the time of each symbol, in us
locked = d["m_locked"] > 0
S = np.mean(np.abs(d["m_zI"][locked]) + np.abs(d["m_zQ"][locked])) / 2
zI, zQ = d["m_zI"] / S, d["m_zQ"] / S
ax[0, 0].plot(zI[~locked], zQ[~locked], ".", color=MUTED, markersize=2, label="before frame lock")
ax[0, 0].plot(zI[locked], zQ[locked], ".", color=C1, markersize=2, label="locked")
ax[0, 0].set_aspect("equal"); ax[0, 0].set_xlim(-1.8, 1.8); ax[0, 0].set_ylim(-1.8, 1.8)
ax[0, 0].set_xlabel("I"); ax[0, 0].set_ylabel("Q"); ax[0, 0].legend(loc="center", fontsize=7, markerscale=3)
ax[0, 0].set_title("Symbols after the loops (integers)")
pk = np.arange(len(d["p_times"]))
pus = pk / R * 1e6
ax[0, 1].plot(pus, (d["p_sps"] / d["p_period"] - 1) * 1e6, color=C2, lw=1, label="psk.py (floating point)")
ax[0, 1].plot(us, d["m_ppm"], color=C1, lw=1, label="FPGA model (integers)")
ax[0, 1].axhline(float(d["ppm"]), color=MUTED, ls="--", lw=1)
ax[0, 1].set_ylabel("symbol-rate offset found (ppm)"); ax[0, 1].set_ylim(-500, 3000)
ax[0, 1].set_title("Timing loop: the rate it finds\n(sent: %+.0f ppm)" % d["ppm"]); ax[0, 1].legend(loc="lower right")
ax[0, 2].plot(pus, d["p_w"] * R / (2 * np.pi) / 1e3, color=C2, lw=1, label="psk.py")
ax[0, 2].plot(us, d["m_hz"] / 1e3, color=C1, lw=1, label="FPGA model")
ax[0, 2].axhline(float(d["hz"]) / 1e3, color=MUTED, ls="--", lw=1)
ax[0, 2].set_ylabel("carrier offset found (kHz)"); ax[0, 2].set_ylim(-2, 5)
ax[0, 2].set_title("Costas loop: the offset it finds\n(sent: %+.1f kHz)" % (d["hz"] / 1e3)); ax[0, 2].legend(loc="lower right")
ax[1, 0].plot(us, d["m_mu"] / 4096, ".", color=C1, markersize=1)
ax[1, 0].set_ylabel("mu: fraction of a sample"); ax[1, 0].set_ylim(0, 1)
ax[1, 0].set_title("The symbol centre slides between\nsamples (first 0.5 ms)")
ax[1, 1].plot(us, d["m_eg"] / 1e5, ".", color=C1, markersize=1)
ax[1, 1].set_ylabel("Gardner error (x 10^5)"); ax[1, 1].set_ylim(-8, 8)
ax[1, 1].set_title("Gardner error, each symbol")
ax[1, 2].plot(us, d["m_ec"], ".", color=C1, markersize=1)
ax[1, 2].set_ylabel("Costas error (integer units)"); ax[1, 2].set_ylim(-800, 800)
ax[1, 2].set_title("Costas error, each symbol")
for a_ in list(ax[0, 1:]) + list(ax[1, :]):
    a_.set_xlabel("time (µs)")
    a_.set_xlim(0, us[-1])
ax[1, 0].set_xlim(0, 500)
fig.suptitle(src, x=0.99, ha="right", fontsize=8, color=MUTED)
save(fig, link.img_path(NAME))
