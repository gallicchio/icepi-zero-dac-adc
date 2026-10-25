"""4.06's figures, from the data measure.py saved (dev/data/ultra_*.npz, the pair on a
cardboard box; ultra_bench_*.npz, the same measurements with the pair lying on the bench).

    python3 fig_ultrasound.py          # writes tutorial/img/ultra_*.png and prints the numbers

ultra_scan.png    the pair's response with lockin.sv, on its cardboard box and (from
                  ultra_bench_*.npz) lying on the bench: 30-64 kHz in dB; the resonance in volts
ultra_delay.png   the resonance with a fit (two resonators and a delay); the group delay
ultra_burst.png   a 3 ms tone burst through the air, recorded with awgcap_slow.sv, and
                  what the sweep's fit predicts for it
ultra_fsk.png     the FSK receiver's soft decisions at 509 and 2035 baud; errors vs baud
ultra_window.png  OFDM's SNR against where the FFT window starts in the cyclic prefix
ultra_ofdm.png    SNR per subcarrier, the bits loaded on each, and Shannon's limit
ultra_const.png   received constellations: 1024-, 256-, 64- and 16-QAM subcarriers
"""
import os
import sys

import numpy as np
from scipy.optimize import least_squares

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(HERE, ".."))                          # plotstyle
for d in ("ultrasound", "verilog", "twoboard"):
    sys.path.insert(0, os.path.join(TOP, "src", d))
from plotstyle import plt, save, dots, C1, C2, C3, MUTED, INK2, GRID   # noqa: E402
import awgcap_slow as awg                                             # noqa: E402
import fsk                                                            # noqa: E402
import ofdm_air                                                       # noqa: E402

DATA = os.path.join(TOP, "dev", "data")
IMG = os.path.join(TOP, "tutorial", "img")
CODES_PER_VOLT = 25.35                       # the ADC (0.00)
VOLTS_PER_CODE_DAC = 0.0307                  # the DAC (0.00)


def load(name, where=""):
    """where = "" for the pair on its box, "bench_" for the pair lying on the bench."""
    return np.load(os.path.join(DATA, "ultra_%s%s.npz" % (where, name)))


def c_air(T):
    return 331.3 + 0.606 * T


# ---- the model: two resonators and a delay ---------------------------------------------
def model(p, f):
    kr, ki, f1, q1, f2, q2, tau = p
    r1 = 1 / (1 + 1j * q1 * (f / f1 - f1 / f))
    r2 = 1 / (1 + 1j * q2 * (f / f2 - f2 / f))
    return (kr + 1j * ki) * r1 * r2 * np.exp(-2j * np.pi * f * tau)


def fit(f, z, lo=37000, hi=44000):
    m = (f >= lo) & (f <= hi)
    best = None
    for tau0 in (100e-6, 300e-6, 500e-6):
        for ph in range(4):
            k0 = 1.3 * np.exp(1j * np.pi / 2 * ph)
            p0 = [k0.real, k0.imag, 39900, 30, 40600, 30, tau0]
            r = least_squares(lambda p: np.concatenate([(model(p, f[m]) - z[m]).real,
                                                        (model(p, f[m]) - z[m]).imag]),
                              p0, x_scale=[1, 1, 100, 10, 100, 10, 1e-4])
            if best is None or r.cost < best.cost:
                best = r
    p = best.x
    if p[2] > p[4]:                                  # order the two resonators by frequency
        p = np.array([p[0], p[1], p[4], p[5], p[2], p[3], p[6]])
    rms = np.sqrt(np.mean(abs(model(p, f[m]) - z[m]) ** 2))
    return p, rms


def artifact(f):
    """lockin.sv's known bad points: frequencies that divide 25 MHz evenly, where its
    reference repeats after a few samples (as fig_cable.py leaves out)."""
    n = np.round(25e6 / f)
    return abs(f - 25e6 / n) < 0.5                  # within the tuning word's rounding


# ---- 1. the sweep ------------------------------------------------------------------------
def group_delay(f, z, half=5):
    ph = np.unwrap(np.angle(z))
    gd = np.full(len(f), np.nan)
    gd[half:-half] = -(ph[2 * half:] - ph[:-2 * half]) / (2 * np.pi * (f[2 * half:] - f[:-2 * half]))
    return gd


def describe(where, label):
    sw = load("sweep", where)
    f, z = sw["f"], sw["z"]
    ok = ~artifact(f) | (abs(z) > 0.01)
    p, rms = fit(f, z)
    kr, ki, f1, q1, f2, q2, tau = p
    k = np.argmax(abs(z))
    m3 = abs(z) > abs(z[k]) / np.sqrt(2)
    print(f"sweep, {label} ({sw['when']}): peak {abs(z[k]) * 1e3:.0f} mV at {f[k]:.0f} Hz; "
          f"3 dB from {f[m3].min():.0f} to {f[m3].max():.0f} Hz ({f[m3].max() - f[m3].min():.0f} Hz)")
    print(f"   fit 37-44 kHz: f1 {f1:.0f} Hz Q1 {q1:.1f}; f2 {f2:.0f} Hz Q2 {q2:.1f}; "
          f"delay {tau * 1e6:.1f} us; |K| {abs(kr + 1j * ki):.3f} V; rms misfit {rms * 1e3:.1f} mV")
    for T in (20, 22, 25):
        print(f"   at {T} C, c = {c_air(T):.1f} m/s: {tau * c_air(T) * 100:.2f} cm of air")
    hi2 = (f > 55000) & (f < 61000)
    k2 = np.argmax(abs(z) * hi2)
    print(f"   second mode: {abs(z[k2]) * 1e3:.0f} mV at {f[k2]:.0f} Hz "
          f"({20 * np.log10(abs(z[k2]) / abs(z[k])):.1f} dB)")
    floor = np.median(abs(z[(f > 30000) & (f < 34000) & ok]))
    print(f"   floor 30-34 kHz: {floor * 1e6:.0f} uV ({20 * np.log10(floor):.0f} dB re 1 V)")
    for x in (36000, 37000, 44000, 45000):
        i = np.argmin(abs(f - x))
        print(f"   {x} Hz: {20 * np.log10(abs(z[i]) / abs(z[k])):.1f} dB re the peak, "
              f"the fit {20 * np.log10(abs(model(p, np.array([x]))[0]) / abs(z[k])):.1f}")
    return dict(f=f, z=z, ok=ok, p=p, k=k, floor=floor)


box = describe("", "on the box")
bench = describe("bench_", "on the bench")
f, z, ok, p, k = box["f"], box["z"], box["ok"], box["p"], box["k"]
kr, ki, f1, q1, f2, q2, tau = p

fig, ax = plt.subplots(2, 1, figsize=(8, 6.6))
ax[0].plot(bench["f"][bench["ok"]] / 1e3, 20 * np.log10(abs(bench["z"][bench["ok"]])), color=MUTED,
           lw=0.7, label="lying on the bench")
ax[0].plot(f[ok] / 1e3, 20 * np.log10(abs(z[ok])), color=C1, lw=0.8, label="on a cardboard box")
ax[0].set_xlabel("frequency (kHz)")
ax[0].set_ylabel("amplitude at the ADC (dB re 1 V)")
ax[0].set_title("The pair, 30–64 kHz: one strong resonance, a weaker mode near 58 kHz")
ax[0].annotate(f"{abs(z[k]):.2f} V at {f[k] / 1e3:.2f} kHz", (f[k] / 1e3, 20 * np.log10(abs(z[k]))),
               xytext=(44, -5), textcoords="data", color=INK2, fontsize=9,
               arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
ax[0].text(30.5, -124, "↑ the floor of one 42 ms average", color=INK2, fontsize=9)
ax[0].set_xlim(30, 64)
ax[0].set_ylim(-128, 10)
ax[0].legend(loc="upper right", fontsize=8)
m = (f >= 37000) & (f <= 44000)
mb = (bench["f"] >= 37000) & (bench["f"] <= 44000)
ax[1].plot(bench["f"][mb] / 1e3, abs(bench["z"][mb]), color=MUTED, lw=1.0, label="lying on the bench")
ax[1].plot(f[m] / 1e3, abs(z[m]), color=C1, lw=1.5, label="on a cardboard box")
ax[1].set_xlabel("frequency (kHz)")
ax[1].set_ylabel("amplitude at the ADC (V)")
ax[1].set_title("The resonance, in volts")
ax[1].legend(loc="upper left", fontsize=8)
ax[1].set_xlim(37, 44)
ax[1].set_ylim(0, 1.15 * max(abs(z).max(), abs(bench["z"]).max()))
save(fig, os.path.join(IMG, "ultra_scan.png"))

fz = np.linspace(37000, 44000, 2000)
zm = model(p, fz)
fig, ax = plt.subplots(2, 1, figsize=(8, 6.6))
dots(ax[0], f[m][::5] / 1e3, abs(z[m][::5]), C1, label="measured (every 5th point)", size=3.5)
ax[0].plot(fz / 1e3, abs(zm), color=C2, lw=1.3,
           label=f"fit: resonators at {f1 / 1e3:.2f} kHz (Q {q1:.0f}) and {f2 / 1e3:.2f} kHz "
                 f"(Q {q2:.0f}), delay {tau * 1e6:.0f} µs")
for fr in (f1, f2):
    ax[0].axvline(fr / 1e3, color=MUTED, lw=0.8, ls="--")
ax[0].set_xlabel("frequency (kHz)")
ax[0].set_ylabel("amplitude at the ADC (V)")
ax[0].set_title("Two resonators, one in each transducer, and a delay")
ax[0].legend(loc="upper left", fontsize=8)
ax[0].set_xlim(37, 44)
ax[0].set_ylim(0, 1.4 * abs(z).max())
gd = group_delay(f, z)
gdm = group_delay(fz, zm, half=1)
ax[1].plot(f[m] / 1e3, gd[m] * 1e6, color=C1, lw=1.0, label="measured: −dφ/dω, over 100 Hz")
ax[1].plot(fz / 1e3, gdm * 1e6, color=C2, lw=1.3, label="the fit")
ax[1].axhline(tau * 1e6, color=C3, lw=1.3, ls="--",
              label=f"the delay alone: {tau * 1e6:.0f} µs, {tau * c_air(22) * 100:.1f} cm of air at 22 °C")
ax[1].set_xlabel("frequency (kHz)")
ax[1].set_ylabel("group delay (µs)")
ax[1].set_title("Group delay: the trip through the air, plus the transducers' ringing")
ax[1].legend(loc="upper right", fontsize=8)
ax[1].set_xlim(37, 44)
ax[1].set_ylim(0, 1100)
save(fig, os.path.join(IMG, "ultra_delay.png"))

# ---- 1b. the phase over two minutes ------------------------------------------------------
for where, label, tw in (("", "on the box", tau), ("bench_", "on the bench", bench["p"][6])):
    w = load("watch", where)
    ph = np.degrees(np.unwrap(np.angle(w["z"])))
    per_k = 360 * float(w["f"]) * tw * 0.606 / c_air(22)         # degrees per kelvin of air
    print(f"watch, {label}, at {float(w['f']):.0f} Hz for {w['t'][-1]:.0f} s: phase {ph.min() - ph.mean():+.2f} "
          f"to {ph.max() - ph.mean():+.2f} deg about its mean, rms {ph.std():.2f} deg; "
          f"amplitude rms {np.std(abs(w['z'])) / np.mean(abs(w['z'])) * 100:.2f}%")
    print(f"   1 deg = {c_air(22) / float(w['f']) / 360 * 1e6:.1f} um of path, or {1000 / per_k:.0f} mK "
          f"of air temperature over {tw * 1e6:.0f} us ({per_k:.1f} deg per K)")


# ---- 2. the burst -------------------------------------------------------------------------
b = load("burst")
half = awg.N // 2
x = np.concatenate([b["x"][:, :half], b["x"][:, half:]]).mean(axis=0)
t_dac, t_rec = awg.times()
t_rec = t_rec[:half]
wave = b["wave"]
# The prediction: the DAC's codes, held for 5.12 us each, through the fitted H(f), then
# averaged over each record period as awgcap_slow.sv does.  The lock-in measured H as
# volts at the ADC for a 127-code stimulus.
up = 16
tf = np.arange(awg.N * up) / (awg.FS_DAC * up)
drive = np.repeat(wave - 128.0, up)                          # zero-order hold
F = np.fft.rfftfreq(len(drive), 1 / (awg.FS_DAC * up))
Hf = np.zeros(len(F), complex)
band = (F > 25000) & (F < 70000)
Hf[band] = model(p, F[band]) / 127
v = np.fft.irfft(np.fft.rfft(drive) * Hf, len(drive))      # volts at the ADC
pred = np.convolve(v, np.ones(2 * up) / (2 * up), "same")    # the record's average
pred_t = tf
pred_codes = np.interp(t_rec, pred_t, pred) * CODES_PER_VOLT
base = np.median(x[(t_rec > 10e-3) & (t_rec < 80e-3)])
start = 1e-3
arrive = start + tau
amp_meas = np.max(abs(x - base)[(t_rec > 2.5e-3) & (t_rec < 4e-3)])
amp_pred = np.max(abs(pred_codes)[(t_rec > 2.5e-3) & (t_rec < 4e-3)])
print(f"burst ({b['when']}): steady amplitude {amp_meas:.1f} codes measured, {amp_pred:.1f} predicted")
# A path through the bench (sound at 1-4 km/s) would arrive by about 1.10 ms and have
# rung up for 230 us by the time the air's sound arrives.  Look for it in the records
# where the ADC was toggling between codes (with no noise at all it can't show small
# signals), and compare with the air's own signal 230 us after it arrives.
f0 = float(b["f0"])


def tone_amp(rec, lo, hi):
    w = (t_rec >= lo) & (t_rec < hi)
    return 2 * abs(np.mean((rec[w] - np.mean(rec[w])) * np.exp(-2j * np.pi * f0 * t_rec[w])))


def bench_bound(bb, tau_air, label):
    recs = [r for r in bb["x"] for r in (r[:half], r[half:])]
    mean = np.mean(recs, axis=0)
    dith = [r for r in recs if np.std(r[(t_rec > 20e-3) & (t_rec < 80e-3)]) > 0.02]
    arr = start + tau_air
    a_pre = np.mean([tone_amp(r, 1.10e-3, arr - 20e-6) for r in dith]) if dith else np.nan
    a_air = tone_amp(mean, arr + 0.18e-3, arr + 0.28e-3)
    print(f"   {label}: {len(dith)} of {len(recs)} records had the ADC toggling; 40.3 kHz between "
          f"1.10 and {(arr - 20e-6) * 1e3:.3f} ms, before the air arrives: {a_pre:.3f} codes; the air's "
          f"own 230 us after arriving: {a_air:.2f} codes: {20 * np.log10(a_pre / a_air):.0f} dB")


bench_bound(b, tau, "on the box")
bench_bound(load("burst", "bench_"), bench["p"][6], "on the bench")

fig, ax = plt.subplots(2, 1, figsize=(8, 6.6))
ax[0].axvspan(1.0, 1.0 + float(b["ms"]), color=GRID, alpha=0.6, lw=0)
ax[0].text(1.05, 1.03 * amp_meas, f"DAC plays {float(b['f0']) / 1e3:.1f} kHz", color=INK2, fontsize=9,
           va="bottom")
ax[0].plot(t_rec * 1e3, x - base, color=C1, lw=0.6, label="recorded (awgcap_slow.sv, 97.7 kS/s)")
env = abs(np.interp(t_rec, pred_t, np.abs(np.fft.ifft(np.fft.fft(pred) * 2 * (np.fft.fftfreq(len(pred)) > 0))))) * CODES_PER_VOLT
ax[0].plot(t_rec * 1e3, env, color=C2, lw=1.3, label="envelope predicted from the sweep's fit")
ax[0].plot(t_rec * 1e3, -env, color=C2, lw=1.3)
ax[0].set_xlim(0, 7)
ax[0].set_ylim(-1.35 * amp_meas, 1.35 * amp_meas)
ax[0].set_xlabel("time from the start of the loop (ms)")
ax[0].set_ylabel("ADC (codes about the mean)")
ax[0].set_title("A 3 ms tone burst: it rings up, and rings down, for about a millisecond")
ax[0].legend(loc="lower right", fontsize=8)
z0 = (t_rec >= 0.9e-3) & (t_rec <= 1.8e-3)
dots(ax[1], t_rec[z0] * 1e3, x[z0] - base, C1, label="recorded", size=4)
ax[1].plot(pred_t * 1e3, pred * CODES_PER_VOLT, color=C2, lw=1.0, label="predicted")
ax[1].axvline(start * 1e3, color=MUTED, lw=0.8, ls="--")
ax[1].axvline(arrive * 1e3, color=C3, lw=1.2, ls="--")
ax[1].text(start * 1e3 + 0.01, 9, "DAC starts", color=INK2, fontsize=9)
ax[1].text(arrive * 1e3 + 0.01, 9, f"+{tau * 1e6:.0f} µs: the sound arrives", color=INK2, fontsize=9)
ax[1].set_xlim(0.9, 1.8)
ax[1].set_ylim(-11, 11)
ax[1].set_xlabel("time from the start of the loop (ms)")
ax[1].set_ylabel("ADC (codes about the mean)")
ax[1].set_title(f"The start: nothing for {tau * 1e6:.0f} µs, then a slow ring-up")
ax[1].legend(loc="lower left", fontsize=8)
save(fig, os.path.join(IMG, "ultra_burst.png"))


# ---- 3. FSK -------------------------------------------------------------------------------
fd = load("fsk")
Ms = fd["M"]
baud = fsk.FS_IQ / Ms
ber = fd["errors"] / fd["total"]
fdb = load("fsk", "bench_")
for bd, e, n, eb, nb in zip(baud, fd["errors"], fd["total"], fdb["errors"], fdb["total"]):
    print(f"fsk ({fd['when']}): {bd:7.1f} baud: {e} errors in {n} on the box, {eb} in {nb} on the bench")
fig, ax = plt.subplots(4, 1, figsize=(8, 11.5))
for a, M in zip(ax[:3], (24, 5, 4)):
    zz, bits, start = fd["z_%d" % M], fd["bits_%d" % M], int(fd["start_%d" % M])
    e = fsk.energies(zz, M)
    soft = (e[1] - e[0]) / (e[1] + e[0] + 1e-12)
    nshow = 24
    t0 = start + len(fsk.BARKER) * M
    n = np.arange(t0 - 2 * M, t0 + nshow * M)
    tt = (n - t0) / M + 0.5                     # each window plotted at its middle
    a.plot(tt, soft[n], color=C1, lw=1.2, label="(E₁ − E₀)/(E₁ + E₀), a symbol's window")
    sent = 2.0 * bits[:nshow] - 1
    a.step(np.arange(nshow + 1), np.r_[sent, sent[-1]], where="post", color=MUTED, lw=1.0,
           label="the bit sent (+1 = 1, −1 = 0)")
    dots(a, np.arange(nshow) + 0.5, soft[t0 + M * np.arange(nshow)], C2, label="the decisions")
    wrong = (soft[t0 + M * np.arange(nshow)] > 0) != (bits[:nshow] > 0)
    a.set_ylim(-1.25, 1.75)
    a.set_yticks([-1, -0.5, 0, 0.5, 1])
    a.set_xlim(-1.5, nshow)
    a.set_xlabel("symbols after the sync word")
    a.set_ylabel("soft value")
    a.set_title(f"{fsk.FS_IQ / M:.0f} baud: tones {fsk.FS_IQ / M:.0f} Hz apart, "
                f"{1e3 * M / fsk.FS_IQ:.2f} ms a symbol; {int(wrong.sum())} of these {nshow} wrong")
    a.legend(loc="upper center", fontsize=8, ncol=3)
zero = fd["errors"] == 0
ax[3].semilogy(baud[~zero], ber[~zero], "o", color=C1, label="measured")
ax[3].semilogy(baud[zero], 1 / fd["total"][zero], "v", color=C1, mfc="none",
               label=f"no errors in {fd['total'][0]} bits (plotted at 1/{fd['total'][0]})")
ax[3].axhline(0.5, color=MUTED, lw=0.8, ls="--")
ax[3].text(300, 0.55, "guessing", color=INK2, fontsize=9)
ax[3].set_xlabel("baud (= bits a second)")
ax[3].set_ylabel("bit error rate")
ax[3].set_xscale("log")
ax[3].set_xticks(baud)
ax[3].set_xticklabels([f"{x:.0f}" for x in baud])
ax[3].minorticks_off()
ax[3].set_title(f"Errors against speed: none to {baud[zero].max():.0f} baud, "
                f"{100 * ber[~zero].min():.0f}% at {baud[~zero].min():.0f}")
ax[3].legend(loc="center left", fontsize=8)
ax[3].set_ylim(1e-4, 1)
save(fig, os.path.join(IMG, "ultra_fsk.png"))


# ---- 4. the window --------------------------------------------------------------------------
wd = load("window")
offs, snr_w = wd["offsets"], wd["snr"]
ks, df, cp = wd["ks"], float(wd["df"]), int(wd["cp"])
inband = (ks * df > 38000) & (ks * df < 43000)
med = 10 * np.log10(np.median(snr_w[:, inband], axis=1))
fs = awg.FS_ADC
print("window: offset (samples, ms) -> median SNR 38-43 kHz")
for o, s in zip(offs, med):
    print(f"   {o:4d} {o / fs * 1e3:5.2f} ms  {s:5.1f} dB")
fig, ax = plt.subplots(figsize=(8, 3.8))
ax.axvspan(0, cp / fs * 1e3, color=GRID, alpha=0.6, lw=0)
ax.text(0.05, med.max() + 3, "the cyclic prefix", color=INK2, fontsize=9)
dots(ax, offs / fs * 1e3, med, C1)
ax.plot(offs / fs * 1e3, med, color=C1, lw=1.0)
ax.axvline((cp / fs + tau) * 1e3, color=C3, lw=1.2, ls="--")
ax.text((cp / fs + tau) * 1e3 + 0.04, med.min() + 2, f"prefix + {tau * 1e6:.0f} µs:\nthe next symbol\narrives",
        color=INK2, fontsize=9)
ax.set_xlabel("where the FFT window starts, after the start of the symbol (ms)")
ax.set_ylabel("median SNR, 38–43 kHz (dB)")
ax.set_title("Start the FFT late: the pair still rings for 2 ms after each symbol")
ax.set_ylim(med.min() - 3, med.max() + 6)
save(fig, os.path.join(IMG, "ultra_window.png"))


# ---- 5. the loading ----------------------------------------------------------------------
runs = [load("ofdm_gap%d" % g) for g in (7, 10, 13)]
for label, r in [("box", r) for r in runs] + [("bench", load("ofdm_gap%d" % g, "bench_")) for g in (7, 10, 13)]:
    nb = int(r["b"].sum())
    print(f"ofdm, {label}, gap {float(r['gap']):.0f} dB: {nb} bits a symbol = {nb / float(r['t_sym']) / 1e3:.1f} kbit/s, "
          f"{int(r['errors'])} errors in {int(r['total'])} ({int(r['errors']) / int(r['total']):.1e}); "
          f"Shannon (probe, less the prefix) {float(r['cap']) / 1e3:.1f} kbit/s; "
          f"loading {[int(np.sum(r['b'] == q)) for q in (1, 2, 4, 6, 8, 10)]}")
r = runs[1]
ks, df, snr, bl = r["ks"], float(r["df"]), r["snr"], r["b"]
fk = ks * df / 1e3
fig, ax = plt.subplots(2, 1, figsize=(8, 6.8), sharex=True)
dots(ax[0], fk, 10 * np.log10(snr), C1)
ax[0].plot(fk, 10 * np.log10(snr), color=C1, lw=0.8)
ax[0].set_ylabel("SNR (dB)")
ax[0].set_title(f"Each 95 Hz subcarrier's SNR, from a probe of QPSK on all {len(ks)}")
ax[0].axhline(10, color=MUTED, lw=0.8, ls="--")
shannon = np.log2(1 + snr)
ax[1].plot(fk, shannon, color=C2, lw=1.3, label="Shannon: log₂(1 + SNR)")
ax[1].bar(fk, bl, width=df / 1e3 * 0.8, color=C1, label=f"bits loaded (gap {float(r['gap']):.0f} dB)")
ax[1].set_ylabel("bits per subcarrier per symbol")
ax[1].set_xlabel("frequency (kHz)")
ax[1].set_title(f"The loading: {int(bl.sum())} bits a symbol, "
                f"{int(bl.sum()) / float(r['t_sym']) / 1e3:.1f} kbit/s; Shannon allows "
                f"{float(r['cap']) / 1e3:.0f}")
ax[1].legend(loc="upper left", fontsize=8)
ax[1].set_xlim(fk[0] - 0.2, fk[-1] + 0.2)
save(fig, os.path.join(IMG, "ultra_ofdm.png"))

# ---- 6. constellations ------------------------------------------------------------------
r = runs[0]                                    # gap 7: the most 1024-QAM
Z, bl, snr0 = r["Z"], r["b"], r["snr"]
fig, ax = plt.subplots(1, 4, figsize=(11, 3.3))
for a, q in zip(ax, (10, 8, 6, 4)):
    cand = np.nonzero(bl == q)[0]
    pts = Z[:, :, cand].ravel()               # every subcarrier carrying this QAM, pooled
    ref = ofdm_air.qam_points(q)
    a.plot(ref.real, ref.imag, "o", color=GRID, ms=2.0 if q >= 8 else 4, zorder=1)
    a.plot(pts.real, pts.imag, ".", color=C1, ms=1.0 if q >= 8 else 2.0, alpha=0.6, zorder=2)
    a.set_aspect("equal")
    a.set_xlim(-1.5, 1.5)
    a.set_ylim(-1.5, 1.5)
    a.set_xticks([])
    a.set_yticks([])
    for sp in a.spines.values():
        sp.set_visible(False)
    a.grid(False)
    lo, hi = 10 * np.log10(snr0[cand].min()), 10 * np.log10(snr0[cand].max())
    a.set_title(f"{2 ** q}-QAM: {len(cand)} subcarriers\nSNR {lo:.0f}–{hi:.0f} dB", fontsize=10)
save(fig, os.path.join(IMG, "ultra_const.png"))
