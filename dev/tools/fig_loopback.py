"""1.07's figures: loopback.sv's square wave, staircase and pseudo-random sequence
coming back through the ADC.  Data recorded with loopback.py's record() into
data/loopback_*.npz."""
import os
import numpy as np
from plotstyle import plt, save, dots, C1, C2, INK2, MUTED
HERE = os.path.dirname(os.path.abspath(__file__))
L1 = np.load(os.path.join(HERE, "..", "data", "loopback_1m.npz"))
L2 = np.load(os.path.join(HERE, "..", "data", "loopback_16cm.npz"))
V = lambda code: (np.asarray(code, float) - 126.7) / 25.35      # ADC code -> volts

# ---- figure 1: the edge, in samples and in equivalent time -------------------
fig, (a, b) = plt.subplots(2, 1, figsize=(8, 6.6))
s = L1["s"].reshape(16, 1024).mean(0)
i = np.arange(504, 528)
a.plot(i, V(s[i]), color=C1, lw=1.0, alpha=0.5)
dots(a, i, V(s[i]), C1, label="ADC samples (101.5 cm cable), mean of 16 edges", size=6)
a.axvline(512, color=INK2, lw=0.8)
a.annotate("DAC code changes:\nsample 512", (512.3, 1.2), color=INK2, fontsize=9)
a.annotate("the ADC sees it:\nsample 518", (518.3, -1.6), color=INK2, fontsize=9)
a.set_xlabel("sample number n (one every 40 ns)")
a.set_ylabel("ADC input (V)")
a.set_title("loopback.py s: a DAC step shows up 6 samples = 240 ns later")
a.legend(loc="upper left")
a.set_ylim(-3.6, 4.4)

# Equivalent time.  Sample n is taken by the ADC 160 ns (4 samples) before the
# FPGA records it; the DAC latches its new code 30 ns after n becomes 512
# ("s"), or 50 ns after ("t").  So, relative to the DAC latching the code:
for L, c, lab in ((L1, C1, "101.5 cm"), (L2, C2, "16.5 cm")):
    es = L["s"].reshape(16, 1024).mean(0)
    et = L["t"].reshape(16, 1024).mean(0)
    n = np.arange(510, 524)
    ts = (n - 512) * 40 - 160 - 30
    tt = (n - 512) * 40 - 160 - 50
    t = np.r_[ts, tt]
    v = V(np.r_[es[n], et[n]])
    o = np.argsort(t)
    b.plot(t[o], v[o], color=c, lw=1.0, alpha=0.5)
    dots(b, t[o], v[o], c, label=lab, size=6)
b.axvline(0, color=INK2, lw=0.8)
b.annotate("the DAC latches\nthe new code", (3, 1.2), color=INK2, fontsize=9)
b.set_xlabel("time after the DAC latched the new code (ns)   — a dot every 20 ns")
b.set_ylabel("ADC input (V)")
b.set_title("Interleaving \"s\" and \"t\": the step arrives ~35 ns later, sooner on the short cable")
b.legend(loc="upper left", ncol=2)
b.set_ylim(-3.6, 4.4)
b.set_xlim(-120, 260)
save(fig, os.path.join(HERE, "..", "..", "tutorial", "img", "loopback_step.png"))

# ---- figure 2: the staircase: DAC code -> ADC code ----------------------------
r = L1["r"].reshape(256, 64)[:, 16:].mean(1)
k = np.arange(256)
p = np.polyfit(k, r, 1)
fig, (c1, c2) = plt.subplots(1, 2, figsize=(8, 3.6))
dots(c1, k, r, C1, size=3)
c1.plot(k, np.polyval(p, k), color=MUTED, lw=1.0)
c1.set_xlabel("DAC code")
c1.set_ylabel("ADC code")
c1.set_title("loopback.py r: ADC = %.4f × DAC + %.2f" % (p[0], p[1]), fontsize=10)
res = r - np.polyval(p, k)
dots(c2, k, res, C1, size=3)
c2.set_xlabel("DAC code")
c2.set_ylabel("ADC code − straight line")
c2.set_title("Residual: within ±½ code, the ADC's rounding", fontsize=10)
c2.set_ylim(-1, 1)
save(fig, os.path.join(HERE, "..", "..", "tutorial", "img", "loopback_stairs.png"))
print("slope %.4f offset %.2f  max |res| %.2f" % (p[0], p[1], abs(res).max()))

# ---- figure 3: the pseudo-random stimulus -> the loop's impulse response -------
# GPS's G1 (x^10 + x^3 + 1, from all ones), as loopback.sv plays it.  Recorded through
# the 101.5 cm cable into data/loopback_g1_1m.npz.
M, state, x = 1023, 0x3FF, []
for _ in range(M):
    x.append(1.0 if state & 0x200 else -1.0)
    state = ((state << 1) | (((state >> 9) ^ (state >> 2)) & 1)) & 0x3FF
x = np.array(x)
L3 = np.load(os.path.join(HERE, "..", "data", "loopback_g1_1m.npz"))
y = L3["p"].astype(float)[M:16 * M].reshape(15, M).mean(0)
h = np.real(np.fft.ifft(np.fft.fft(y - y.mean()) * np.conj(np.fft.fft(x)))) / (M + 1) / 96
# the same loop's impulse response from the step of mode "s": the step response's differences
st = L1["s"].astype(float).reshape(16, 1024).mean(0)
h_step = np.diff(st[505:530]) / 192
fig, ax = plt.subplots(figsize=(8, 3.8))
k = np.arange(16)
ax.vlines(k, 0, h[k], color=C1, lw=2)
dots(ax, k, h[k], C1, size=7, label="h[k] from the pseudo-random sequence, one capture")
ax.plot(np.arange(506, 530) - 512, h_step, "o", mfc="none", mec=C2, mew=1.4, markersize=7,
        label="h[k] from the step of mode s")
ax.axhline(0, color=INK2, lw=0.8)
ax.annotate("h[6] = %.2f: most of the signal\narrives 6 samples = 240 ns later" % h[6], (6.4, 0.66),
            color=INK2, fontsize=9)
ax.annotate("then a little ringing", (7.4, -0.17), color=INK2, fontsize=9)
ax.set_xlabel("delay k (samples of 40 ns)")
ax.set_ylabel("ADC codes per DAC code")
ax.set_title("loopback.py p: the impulse response of the DAC → 101.5 cm cable → ADC loop")
ax.set_ylim(-0.3, 1.05)
ax.set_xlim(-0.5, 15.5)
ax.set_xticks(k)
ax.legend(loc="upper left", fontsize=8.5)
save(fig, os.path.join(HERE, "..", "..", "tutorial", "img", "loopback_prbs.png"))
print("h[0:12] =", np.round(h[:12], 3))
print("from the step, k = 6..9:", np.round(h_step[7:11], 3))
