#!/usr/bin/env python3
"""4.04, the laptop side: a diode clipper's harmonics against the drive.
    python3 clipper.py                  # sweep the amplitude, capture each, save and plot
    python3 clipper.py --from-npz       # redraw the figures from the saved run
    python3 clipper.py --sim            # the same figures from the diode model alone (no board)
Needs Chapter 2's SoC with its firmware running (the prompt is "adda>"), DAC OUT -> the clipper's IN, its OUT -> ADC
IN.  The clipper is 1 k in series, then two 1N4148s, one each way, to ground (AMOD-P's tile p10, or 4.04's
breadboard).  For each amplitude the firmware's function generator plays a sine at 99,945 Hz (524 cycles in the
capture, so every harmonic falls on an FFT bin) and cap 3 records 16384 samples at 3.125 MS/s.
"""
import argparse
import os
import time
import numpy as np
import serial
import cap_plot

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "..", "dev", "data", "clipper")
IMG = os.path.join(HERE, "..", "..", "tutorial", "img")
F_SYS = 50e6
FS = 25e6 / 2**3                     # cap 3: every 8th sample of the 25 MS/s ADC
N = 16384
HZ = 99945                           # 524 x FS / N = 99,945.07 Hz: a whole number of cycles in the capture
V_FULL = 3.9                         # the DAC's full scale (amplitude 255), volts, into the ADC's 20.6 k
AMPS = [4, 6, 8, 11, 16, 22, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 255]
CODES_PER_VOLT, MID = 25.35, 126.7   # the ADC, measured in 1.02
R_SRC, R_SER, R_ADC = 51.0, 1000.0, 20.6e3
IS, NVT = 2.52e-9, 1.752 * 0.02569   # 1N4148: saturation current, emission coefficient x kT/q at 25 C


def fg(port, amp):
    with serial.Serial(port, 115200, timeout=0.3) as ser:
        ser.write(b"\rfg %d %d\r" % (HZ, amp))
        time.sleep(0.3)
        return ser.read(400).decode(errors="replace")


def f_actual():
    tw = (HZ << 32) // int(F_SYS)    # what the firmware's funcgen_set() computes
    return tw * F_SYS / 2**32


def harmonics(v, f, kmax=7):
    """DC and the amplitude and phase of 1f .. kmax f, by a least-squares fit of sines at exactly those frequencies."""
    t = np.arange(len(v)) / FS
    cols = [np.ones_like(t)]
    for k in range(1, kmax + 1):
        cols += [np.cos(2 * np.pi * k * f * t), np.sin(2 * np.pi * k * f * t)]
    c, *_ = np.linalg.lstsq(np.array(cols).T, v, rcond=None)
    a = np.hypot(c[1::2], c[2::2])
    ph = np.arctan2(-c[2::2], c[1::2])
    return c[0], a, ph


def diode_out(vin):
    """The clipper's output for an input (the DAC's open-circuit voltage) vin: solve, sample by sample,
    (vin - v) / (R_SRC + R_SER) = 2 IS sinh(v / NVT) + v / R_ADC  by bisection."""
    lo, hi = -np.abs(vin) - 1e-9, np.abs(vin) + 1e-9
    for _ in range(60):
        m = (lo + hi) / 2
        g = (vin - m) / (R_SRC + R_SER) - 2 * IS * np.sinh(m / NVT) - m / R_ADC
        lo, hi = np.where(g > 0, m, lo), np.where(g > 0, hi, m)
    return (lo + hi) / 2


def model(amps_v, f, kmax=7):
    t = np.arange(N) / FS
    out = []
    for A in amps_v:
        out.append(harmonics(diode_out(A * np.sin(2 * np.pi * f * t)), f, kmax)[1])
    return np.array(out)


def hard_clip(amps_v, vc=0.62, kmax=7):
    """The ideal clipper: the sine cut flat at +-vc (the input divided 20.6 k / 21.65 k first)."""
    th = np.linspace(0, 2 * np.pi, 4096, endpoint=False)
    out = []
    for A in amps_v:
        v = np.clip(A * R_ADC / (R_ADC + R_SRC + R_SER) * np.sin(th), -vc, vc)
        out.append([2 * abs(np.mean(v * np.exp(-1j * k * th))) for k in range(1, kmax + 1)])
    return np.array(out)


def measure(port):
    caps, rows = [], []
    for amp in AMPS:
        fg(port, amp)
        time.sleep(0.2)
        t, code = cap_plot.cap(port, 3)
        v = (code.astype(float) - MID) / CODES_PER_VOLT
        caps.append(code)
        dc, a, ph = harmonics(v, f_actual())
        rows.append((amp, dc, a, ph, code.min(), code.max()))
        print("amplitude %3d (%.2f V): DC %+.3f V, 1f %.3f V, 3f %5.1f dBc, 5f %5.1f dBc, 2f %5.1f dBc; codes %d..%d"
              % (amp, amp / 255 * V_FULL, dc, a[0], 20 * np.log10(a[2] / a[0]), 20 * np.log10(a[4] / a[0]),
                 20 * np.log10(a[1] / a[0]), code.min(), code.max()))
    fg(port, 0)                                          # leave the DAC quiet
    os.makedirs(DATA, exist_ok=True)
    np.savez_compressed(os.path.join(DATA, "icepi_p10.npz"), amps=np.array(AMPS), vin=np.array(AMPS) / 255 * V_FULL,
             codes=np.array(caps, dtype=np.uint8), fs=FS, f=f_actual(), t=time.strftime("%Y-%m-%d %H:%M:%S"),
             label="Icepi Zero DK0GFLAW, AMOD-P p10 (1 k, 2 x 1N4148W), DAC OUT -> IN, OUT -> ADC IN")


def figures(d, sim=False):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    f = float(d["f"]); vin = d["vin"]
    v = (d["codes"].astype(float) - MID) / CODES_PER_VOLT
    H = np.array([harmonics(x, f)[1] for x in v]); DC = np.array([harmonics(x, f)[0] for x in v])
    tag = " (the diode model, not a measurement)" if sim else ""
    # ---- figure 1: the waveforms, and the transfer curve -------------------------------------------------------
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.2))
    t = np.arange(N) / FS
    n = int(round(3 * FS / f))                           # three cycles
    for i, col in zip([AMPS.index(16), AMPS.index(64), AMPS.index(255)], ("C2", "C1", "C3")):
        dc, a, ph = harmonics(v[i], f)
        a1.plot(t[:n] * 1e6, v[i][:n], ".-", ms=2, lw=0.8, color=col, label="%.2f V in" % vin[i])
        a1.plot(t[:n] * 1e6, vin[i] * np.cos(2 * np.pi * f * t[:n] + ph[0]) * R_ADC / (R_ADC + R_SER + R_SRC), ":",
                color=col, lw=0.8)
    a1.set_xlabel("time (us)"); a1.set_ylabel("ADC IN (V)"); a1.grid(alpha=0.3)
    a1.set_title("the clipper's output (dotted: what it would be with no diodes)", fontsize=9); a1.legend(fontsize=8)
    i = len(AMPS) - 1
    dc, a, ph = harmonics(v[i], f)
    x = vin[i] * np.cos(2 * np.pi * f * t + ph[0])
    a2.plot(x, v[i], ",", alpha=0.5, label="measured, %.2f V in" % vin[i] if not sim else "the model")
    xx = np.linspace(-vin[i], vin[i], 400)
    a2.plot(xx, diode_out(xx), "k--", lw=1, label="1 k and two 1N4148s (Shockley)")
    a2.set_xlabel("the DAC's voltage (V)"); a2.set_ylabel("ADC IN (V)"); a2.grid(alpha=0.3); a2.legend(fontsize=8)
    a2.set_title("the transfer curve: out against in", fontsize=9)
    fig.suptitle("AMOD-P p10, a diode clipper, on the Icepi Zero" + tag, fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(IMG, "clipper_wave.png"), dpi=90); plt.close(fig)
    # ---- figure 2: the spectrum at full drive, and the harmonics against the drive -------------------------------
    fig, (b1, b2) = plt.subplots(1, 2, figsize=(11, 4.2))
    w = np.hanning(N)
    sp = np.abs(np.fft.rfft((v[-1] - v[-1].mean()) * w)) / w.sum() * 2
    fr = np.fft.rfftfreq(N, 1 / FS)
    b1.plot(fr / 1e3, 20 * np.log10(sp + 1e-9), lw=0.7)
    for k in range(1, 8):
        b1.annotate("%df" % k, (k * f / 1e3, 20 * np.log10(H[-1][k - 1]) + 3), ha="center", fontsize=7)
    b1.set_xlim(0, 800); b1.set_ylim(-90, 10); b1.set_xlabel("frequency (kHz)"); b1.set_ylabel("dBV")
    b1.set_title("the spectrum at %.2f V in: odd harmonics only" % vin[-1], fontsize=9); b1.grid(alpha=0.3)
    vv = np.geomspace(vin.min(), vin.max(), 60)
    M = model(vv, f); HC = hard_clip(vv)
    for k, col in zip((1, 3, 5, 7, 2), ("C0", "C1", "C2", "C3", "C7")):
        b2.loglog(vin, H[:, k - 1], "o", ms=3.5, color=col, label="%df" % k)
        b2.loglog(vv, M[:, k - 1], "-", lw=0.9, color=col)
        if k % 2:
            b2.loglog(vv, np.maximum(HC[:, k - 1], 1e-6), ":", lw=0.8, color=col)
    b2.set_ylim(3e-4, 2); b2.set_xlabel("the DAC's amplitude (V)"); b2.set_ylabel("amplitude at ADC IN (V)")
    b2.set_title("against the drive: lines the diode model, dotted a hard clip at 0.62 V", fontsize=9)
    b2.grid(alpha=0.3, which="both"); b2.legend(fontsize=8, ncol=2)
    fig.suptitle("AMOD-P p10 on the Icepi Zero: harmonics" + tag, fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(IMG, "clipper_harmonics.png"), dpi=90); plt.close(fig)
    return H, DC


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port")
    ap.add_argument("--from-npz", action="store_true")
    ap.add_argument("--sim", action="store_true")
    a = ap.parse_args()
    path = os.path.join(DATA, "icepi_p10.npz")
    if a.sim:
        t = np.arange(N) / FS; vin = np.array(AMPS) / 255 * V_FULL
        codes = np.array([np.clip(np.round(MID + CODES_PER_VOLT * diode_out(A * np.sin(2 * np.pi * f_actual() * t))), 0, 255)
                          for A in vin]).astype(np.uint8)
        d = dict(f=f_actual(), vin=vin, codes=codes)
    else:
        if not a.from_npz:
            measure(a.port or cap_plot.find_port())
        d = np.load(path)
    H, DC = figures(d, sim=a.sim)
    for i in (0, AMPS.index(64), len(AMPS) - 1):
        print("%.2f V in: 1f %.3f V; 3f %.1f dBc, 5f %.1f, 7f %.1f; 2f %.1f, 4f %.1f; DC %+.4f V"
              % (d["vin"][i], H[i][0], *(20 * np.log10(H[i][k] / H[i][0]) for k in (2, 4, 6, 1, 3)), DC[i]))


if __name__ == "__main__":
    main()
