"""Chapter 6 figure: Shannon's limit against the modulations, and against the cable.

comms_capacity.png   left: spectral efficiency against Eb/N0: Shannon's curve, what BPSK,
                     QPSK, 16-QAM and 64-QAM can reach at best (constrained capacity),
                     where they sit uncoded at BER 1e-5, and where DVB-S2's LDPC-coded
                     modes sit; right: the cable in bit/s per hertz against frequency:
                     what Shannon allows from 6.07's sounding and from QAM-64's EVM, and
                     what OFDM and 6.02's QPSK carried.

With --sim or PORT it runs 6.02's QPSK once, with no added noise, for the MER the link
gives QPSK (its own SNR).  The OFDM and sounding curves are 6.07's measured data,
dev/data/tb_ofdm_loop_64.npz and tb_sound_loop.npz (one board, the 101.5 cm cable).

    python3 fig_capacity.py --sim | PORT | PORT_A PORT_B | --replot
"""
import math
import os
import types
import numpy as np
import link
from plotstyle import plt, save, C1, C2, C3, INK, INK2, MUTED
import capacity as cp
import psk

NAME = "capacity"
C4 = "#eda100"                                        # the palette's fourth slot (yellow)
a = link.args(__doc__)
if not a.replot:
    L = link.Link(a)
    opts = types.SimpleNamespace(sro=0, cfo=0, diff=False, bnt_timing=0.01, bnt_carrier=0.02, skip=400)
    r = psk.run_once(opts, 4, L.play, L.record, rng=1)
    print("%s: QPSK with no added noise: %d errors in %d bits, MER %.1f dB" % (L.source, r["errs"], r["nbits"], r["mer"]))
    np.savez(link.data_path(NAME), mer=r["mer"], errs=r["errs"], nbits=r["nbits"], source=L.source)
d = np.load(link.data_path(NAME))
mer, src = float(d["mer"]), str(d["source"])

# ---- the theory ----------------------------------------------------------------------
eta = np.linspace(0.02, 8.5, 500)
esn0 = np.linspace(-12, 32, 89)
curves = {M: cp.constrained_curve(M, esn0) for M in (2, 4, 16, 64)}
rows = cp.table(1e-5)                                 # (M, eta, Shannon, uncoded, gap)
# DVB-S2 (ETSI EN 302 307-1, Table 13): spectral efficiency and the Es/N0 at which each
# LDPC + BCH coded mode is "quasi error free" (a packet error rate of 1e-7) on an ideal
# channel.  Eb/N0 = Es/N0 - 10 log10(eta).  Five of the 28 modes.
DVBS2 = [("QPSK 1/2", 0.989, 1.00), ("QPSK 3/4", 1.487, 4.03), ("8PSK 3/4", 2.228, 7.91),
         ("16APSK 3/4", 2.967, 10.21), ("32APSK 4/5", 3.952, 13.64)]

# ---- the cable -----------------------------------------------------------------------
T = link.TOP
ofdm = np.load(os.path.join(T, "dev", "data", "tb_ofdm_loop_64.npz"))
snd = np.load(os.path.join(T, "dev", "data", "tb_sound_loop.npz"))
df = 25e6 / 256                                       # subcarrier spacing, 97.66 kHz
fk, evm = ofdm["fk"], ofdm["evm"]
eff_evm = np.log2(1 + 1 / evm**2)                     # bit/s/Hz each subcarrier could carry
C_evm = np.sum(eff_evm) * df
f_s, snr_s = snd["f"], snd["snr"]
C_snd = float(snd["C"])
k = 32                                                # smooth the 3 kHz bins to 100 kHz
eff_snd = np.convolve(np.log2(1 + snr_s), np.ones(k) / k, mode="valid")
f_snd = f_s[k // 2:k // 2 + len(eff_snd)]
B_ofdm = len(fk) * df
f_lo, f_hi = (fk[0] - df / 2) / 1e6, (fk[-1] + df / 2) / 1e6
used64 = float(ofdm["rate"]) / B_ofdm                 # bit/s/Hz QAM-64 OFDM carried
used256 = cp.CABLE["qam256_rate"] / B_ofdm
q_lo, q_hi = (x / 1e6 for x in cp.CABLE["qpsk_band"])
Bq = (q_hi - q_lo) * 1e6
used_q = cp.CABLE["qpsk_rate"] / Bq
eff_q = math.log2(1 + 10**(mer / 10))                 # at the MER the link gives QPSK
print("cable: Shannon from the sounding %.0f Mbit/s (3 kHz-12.4 MHz); from QAM-64's EVM %.1f Mbit/s over %.2f MHz"
      % (C_snd / 1e6, C_evm / 1e6, B_ofdm / 1e6))
print("       QAM-64 OFDM carried %.1f Mbit/s = %.0f%%; QPSK %.3f Mbit/s = %.1f%% (and %.0f%% of its own %.1f MHz at MER %.1f dB: %.1f Mbit/s)"
      % (ofdm["rate"] / 1e6, 100 * ofdm["rate"] / C_evm, cp.CABLE["qpsk_rate"] / 1e6,
         100 * cp.CABLE["qpsk_rate"] / C_evm, 100 * cp.CABLE["qpsk_rate"] / (Bq * eff_q), Bq / 1e6, mer, Bq * eff_q / 1e6))

# ---- draw ----------------------------------------------------------------------------
fig, ax = plt.subplots(1, 2, figsize=(11, 5.4), gridspec_kw=dict(width_ratios=[1.25, 1]))

# left: Eb/N0
from matplotlib.lines import Line2D
A = ax[0]
A.plot(cp.shannon_ebn0(eta), eta, color=INK, lw=1.8)
lim = 10 * math.log10(math.log(2))
A.axvline(lim, color=MUTED, lw=0.9, ls="--")
A.text(lim + 0.3, 5.0, "−1.59 dB: nothing gets\nthrough to the left of this,\nhowever wide the band", ha="left", va="center", fontsize=8, color=INK2)
cols = {2: C1, 4: C2, 16: C3, 64: C4}
for M, (eb, I) in curves.items():
    ok = I > 0.03
    A.plot(eb[ok], I[ok], color=cols[M], lw=1.3)
    A.text(21.7, math.log2(M) + 0.12, cp.NAMES[M], ha="right", va="bottom", fontsize=8, color=cols[M])
for M, e, sh, un, gap in rows:
    A.plot(un, e, "o", color=cols[M], markersize=7, markeredgecolor="white", markeredgewidth=1)
    A.annotate("%.1f dB" % un, (un, e), xytext=(0, -11), textcoords="offset points", fontsize=7.5, color=INK2, ha="center")
# the gap at 2 bit/s/Hz
sh2, un2 = rows[1][2], rows[1][3]
A.annotate("", xy=(un2 - 0.2, 2), xytext=(sh2 + 0.15, 2), arrowprops=dict(arrowstyle="<->", color=INK2, lw=1))
A.text(un2 + 0.6, 2.3, "%.1f dB: the gap uncoded QPSK leaves,\nat 2 bit/s/Hz" % (un2 - sh2), ha="left", va="center", fontsize=8.5, color=INK2)
for name, e, esn0_db in DVBS2:
    eb = esn0_db - 10 * math.log10(e)
    A.plot(eb, e, "D", color=INK2, markersize=5, markerfacecolor="white", markeredgewidth=1.2)
A.annotate("QPSK, rate-1/2 LDPC", (1.05, 0.989), xytext=(5, -9), textcoords="offset points", fontsize=7.5, color=INK2)
A.annotate("32APSK, rate 4/5", (13.64 - 10 * math.log10(3.952), 3.952), xytext=(6, -11), textcoords="offset points", fontsize=7.5, color=INK2)
A.set_xlim(-3, 22); A.set_ylim(0, 8)
A.set_xlabel("Eb/N0 (dB): energy per information bit / noise power per hertz")
A.set_ylabel("spectral efficiency (bit/s per Hz of symbol rate)")
A.set_title("How many bits a hertz can carry, against the energy each bit costs")
A.legend(handles=[Line2D([], [], color=INK, lw=1.8, label="Shannon: log₂(1 + S/N), with the best code there is"),
                  Line2D([], [], color=INK2, lw=1.3, label="those points only, with the best code (one colour each)"),
                  Line2D([], [], color=INK2, marker="o", ls="", markersize=7, label="uncoded, at BER 10⁻⁵"),
                  Line2D([], [], color=INK2, marker="D", ls="", markersize=5, markerfacecolor="white", label="DVB-S2's LDPC-coded modes (its standard's table)")],
         loc="upper left", fontsize=8)

# right: the cable
B = ax[1]
B.plot(f_snd / 1e6, eff_snd, color=INK2, lw=0.9, label="Shannon, noise only (6.07's sounding): %.0f Mbit/s" % (C_snd / 1e6))
B.plot(fk / 1e6, eff_evm, ".-", color=C1, lw=0.9, markersize=3, label="Shannon at QAM-64's EVM per subcarrier: %.0f Mbit/s" % (C_evm / 1e6))
B.fill_between([f_lo, f_hi], 0, used64, color=C1, alpha=0.22, lw=0,
               label="OFDM QAM-64 carried: %.1f Mbit/s, no errors (%.0f%%)" % (ofdm["rate"] / 1e6, 100 * ofdm["rate"] / C_evm))
B.plot([f_lo, f_hi], [used256, used256], color=C1, lw=1, ls=":",
       label="OFDM QAM-256: %.1f Mbit/s, but 1 bit in %.0f wrong" % (cp.CABLE["qam256_rate"] / 1e6, 1 / cp.CABLE["qam256_ber"]))
B.fill_between([q_lo, q_hi], 0, used_q, color=C2, alpha=0.6, lw=0,
               label="QPSK (6.02) carried: %.2f Mbit/s (%.1f%% of the cable)" % (cp.CABLE["qpsk_rate"] / 1e6, 100 * cp.CABLE["qpsk_rate"] / C_evm))
B.plot([q_lo, q_hi], [eff_q, eff_q], color=C2, lw=1.6, ls="--",
       label="Shannon at QPSK's own MER, %.0f dB: %.0f Mbit/s in its %.1f MHz" % (mer, Bq * eff_q / 1e6, Bq / 1e6))
B.text((q_lo + q_hi) / 2, used_q + 0.25, "QPSK\n%.2f" % used_q, ha="center", va="bottom", fontsize=8, color=INK2)
B.text((f_lo + f_hi) / 2, used64 - 0.3, "OFDM, QAM-64: %.2f bit/s/Hz" % used64, ha="center", va="top", fontsize=8.5, color=INK2)
B.set_xlim(0, 12.5); B.set_ylim(0, 20); B.set_yticks([0, 5, 10, 15, 20])
B.set_xlabel("frequency (MHz)")
B.set_ylabel("bit/s per hertz")
B.set_title("The cable: what it could carry, and what it did")
B.legend(loc="upper left", fontsize=7.5)
fig.suptitle("theory, with the cable as 6.07 measured it; QPSK's MER %s" % src, x=0.99, ha="right", fontsize=8, color=MUTED)
save(fig, link.img_path(NAME))
