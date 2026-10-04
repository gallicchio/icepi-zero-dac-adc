"""Drive-strength experiment: SNR, harmonics and spurs of a DAC sine seen through the cable by the ADC."""
import os, numpy as np, re
HERE = os.path.dirname(os.path.abspath(__file__))
N = 16384; K = {"1M": 721, "10M": 6619}
z = np.load(os.path.join(HERE, "..", "..", "data", "pinspeed_drive.npz"))
def metrics(y, k):
    """y: (n, N) codes.  Coherent FFT: fundamental at bin k, harmonics 2..9 at folded bins."""
    P = (np.abs(np.fft.rfft(y - y.mean(axis=1, keepdims=True), axis=1))**2).mean(0)   # averaged power
    def fold(b): b %= N; return min(b, N - b)
    hb = [fold(h * k) for h in range(2, 10)]
    p1 = P[k]; ph = P[hb]
    noise = P.copy(); noise[0] = 0; noise[k] = 0; noise[hb] = 0
    A = 2 * np.sqrt(p1) / N                                   # amplitude, codes
    thd = 10 * np.log10(ph.sum() / p1)
    snr = 10 * np.log10(p1 / noise.sum())
    sinad = 10 * np.log10(p1 / (noise.sum() + ph.sum()))
    j = np.argmax(noise); spur = 10 * np.log10(noise[j] / p1)
    return A, 10*np.log10(ph[0]/p1), 10*np.log10(ph[1]/p1), thd, snr, sinad, (sinad - 1.76) / 6.02, spur, j * 25e6 / N
rows = []
for name in [n for n in z.files if not re.search(r"_r\d$", n)]:
    m = re.match(r"dac(\d+)_(\w+)_(.*)", name); F, tone, cfg = int(m.group(1)), m.group(2), m.group(3)
    y = z[name].astype(float)
    rows.append((tone, F, cfg) + metrics(y, K[tone]))
order = {"4S-4S": 0, "8S-8S": 1, "4S-8F": 2, "16F-16F": 3}
print("tone  F    data-clk   A(codes)  H2(dBc) H3(dBc) THD(dB) SNR(dB) SINAD  ENOB  max spur (dBc @ MHz)")
for r in sorted(rows, key=lambda r: (r[0], r[1], order[r[2]])):
    print("%-4s %4d  %-8s  %7.2f  %7.1f %7.1f %7.1f %7.1f %6.1f %5.2f  %6.1f @ %.3f" % r)
