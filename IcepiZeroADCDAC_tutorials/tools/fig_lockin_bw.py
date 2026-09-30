"""Tutorial 4 figure: what the lock-in reports for a signal that is NOT exactly
at the reference frequency.  W1 (-> ADC) plays a 2 V sine near 100 kHz while
lockin.v is set to 100 kHz.  Run with lockin.bit loaded; --replot redraws."""
import sys, os, time, math
import numpy as np
from plotstyle import plt, save, dots, C1, C2, C3, INK2, MUTED
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
DATA = os.path.join(HERE, "..", "data", "lockin_bw.npz")
IMG = os.path.join(HERE, "..", "img", "lockin_bw.png")
F0, AMP = 100e3, 2.0
T_AVG = 2**20 / 25e6                     # one average, in FPGA seconds


def read_results(li, n):
    """n consecutive results -> complex volts (one every T_AVG)."""
    import lockin
    out = []
    while len(out) < n:
        parts = li.ser.readline().split()
        if len(parts) != 3:
            continue
        _, x, y = (int(p, 16) for p in parts)
        out.append(complex(lockin.signed32(x), lockin.signed32(y)) / 65536 * 2 / 127
                   / lockin.ADC_CODES_PER_VOLT)
    return np.array(out)


if "--replot" not in sys.argv:
    import m2k, lockin
    m = m2k.M2k()
    li = lockin.LockIn()
    li.measure(F0)
    # 1. the two crystals disagree slightly: measure it from the beat
    fw = m.w1_wave_exact(F0, lambda c: AMP * np.sin(2 * np.pi * c))
    time.sleep(0.5)
    li.ser.reset_input_buffer(); li.ser.readline()
    z = read_results(li, 60)
    slope = np.polyfit(np.arange(len(z)) * T_AVG, np.unwrap(np.angle(z)), 1)[0]
    beat = slope / 2 / math.pi                      # = f_W1 - f_ref, in Hz
    f_ref = fw - beat                               # the reference, in M2k Hz
    print("beat %.4f Hz: FPGA reference = %.4f Hz on the M2k's clock (%.2f ppm)"
          % (beat, f_ref, (f_ref / F0 - 1) * 1e6))
    # 2. a 2 Hz detuning, as a time series
    fw = m.w1_wave_exact(f_ref + 2.0, lambda c: AMP * np.sin(2 * np.pi * c))
    time.sleep(0.5)
    li.ser.reset_input_buffer(); li.ser.readline()
    zt = read_results(li, 72)
    # 3. amplitude vs detuning
    dets = np.arange(-60, 60.01, 1.5)
    amps = []
    for d in dets:
        fw = m.w1_wave_exact(f_ref + d, lambda c: AMP * np.sin(2 * np.pi * c))
        time.sleep(0.3)
        li.ser.reset_input_buffer(); li.ser.readline()
        amps.append(np.mean(abs(read_results(li, 6))))
        print("detuning %+6.1f Hz: |R| = %.4f V" % (d, amps[-1]))
    m.w1_dc(0.0)
    m.close()
    np.savez(DATA, zt=zt, dets=dets, amps=np.array(amps), beat=beat, f_ref=f_ref)

d = np.load(DATA)
zt, dets, amps = d["zt"], d["dets"], d["amps"]
fig, (a, b) = plt.subplots(2, 1, figsize=(8, 6.6))

t = np.arange(len(zt)) * T_AVG
a.plot(t, zt.real, color=C1, lw=1.0, alpha=0.45)
dots(a, t, zt.real, C1, label="X (in phase)")
a.plot(t, zt.imag, color=C2, lw=1.0, alpha=0.45)
dots(a, t, zt.imag, C2, label="Y (quadrature)")
a.plot(t, abs(zt), color=C3, lw=1.5, label="R = √(X² + Y²)")
a.set_xlabel("time (s)   — one dot per 42 ms average")
a.set_ylabel("lock-in output (V)")
a.set_title("A 2 V sine 2 Hz away from the reference: X and Y rotate at 2 Hz, R stays put")
a.legend(loc="lower right", ncol=3)
a.set_ylim(-2.9, 2.6)

x = np.linspace(dets.min(), dets.max(), 1000)
b.plot(x, AMP * abs(np.sinc(x * T_AVG)), color=MUTED, lw=1.2,
       label="2 V × |sin(πΔf·T)/(πΔf·T)|,  T = 41.9 ms")
dots(b, dets, amps, C1, label="measured R")
b.set_xlabel("signal frequency − reference frequency, Δf (Hz)")
b.set_ylabel("R (V)")
b.set_title("The lock-in's pass band: averaging for T is a sinc filter 1/T = 24 Hz wide")
b.legend(loc="upper right")
b.set_ylim(-0.05, 2.35)
save(fig, IMG)
print("wrote", IMG)
