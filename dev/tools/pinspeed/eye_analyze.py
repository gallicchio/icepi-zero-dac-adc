"""ADC eye scan at 31.25 and 25 MS/s: SINAD and wild samples at each capture point."""
import os, numpy as np, re
HERE = os.path.dirname(os.path.abspath(__file__))
K = 145
z = np.load(os.path.join(HERE, "..", "..", "data", "pinspeed_eye.npz"))
def fold(b, N): b %= N; return min(b, N - b)
def score(x):
    N = len(x); X = np.fft.rfft(x - x.mean()); P = np.abs(X)**2
    hb = [fold(h*K, N) for h in range(2, 10)]
    noise = P.copy(); noise[0] = 0; noise[K] = 0; noise[hb] = 0
    sinad = 10*np.log10(P[K] / (noise.sum() + P[hb].sum())); snr = 10*np.log10(P[K]/noise.sum())
    # reconstruct fundamental + harmonics and count wild samples
    Y = np.zeros_like(X); Y[K] = X[K]; Y[hb] = X[hb]; fit = np.fft.irfft(Y, N) + x.mean()
    wild = int((abs(x - fit) > 8).sum())
    return snr, sinad, wild
out = {}
for name in sorted(z.files):
    m = re.match(r"eye_([\d.]+)_(\d)ns_L(\d)", name); fadc, ns, load = float(m.group(1)), int(m.group(2)), int(m.group(3))
    R = int(round(125 / fadc)); nadc = {31.25: 4096, 25.0: 3276}[fadc]
    for c, raw in enumerate(z[name]):
        raw = raw.astype(float)
        # residue of the first raw sample after each change of ADC data: the most common one anchors the grid
        ch = np.where(np.diff(raw) != 0)[0] + 1
        anchor = np.bincount(ch % R, minlength=R).argmax()
        for j in range(R):                    # j = raw samples after the anchor (8 ns each)
            x = raw[(anchor + j) % R::R][:nadc]
            if len(x) < nadc: x = raw[(anchor + j) % R::R][:nadc - 1]
            out.setdefault((fadc, ns, load, j), []).append(score(x[:nadc - 1] if len(x) < nadc else x))
for fadc in (31.25, 25.0):
    R = int(round(125 / fadc))
    print("ADC at %g MS/s: SINAD dB [wild samples per %d] for capture point j (8 ns steps after the change point), per ADC-clock shift" % (fadc, {31.25: 4096, 25.0: 3276}[fadc]))
    for ns in (0, 2, 4, 6):
        for load in (0, 1):
            cells = []
            for j in range(R):
                v = np.array(out[(fadc, ns, load, j)]); cells.append("%5.1f [%4d]" % (v[:, 1].mean(), v[:, 2].mean()))
            print("  shift %d ns, load %d:  %s" % (ns, load, "  ".join(cells)))
