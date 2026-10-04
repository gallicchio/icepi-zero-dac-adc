#!/usr/bin/env python3
"""Check fft.sv against numpy, in simulation: no hardware needed.

    python3 fft_check.py           # all the tests, about 10 s
    python3 fft_check.py --plot    # ...and plot them

Each test writes a test signal (ADC codes at 25 MS/s), runs fft_tb.sv on it in
Icarus Verilog, and compares the 512 powers P[k] that come back with

  exact:  numpy's answer for the very same samples: np.fft.rfft of (code - 128)
          times the same window, / N, then |X[k]|^2 averaged over the frames;
  model:  a copy of the FPGA's fixed-point arithmetic in numpy, which should
          agree with the FPGA exactly, bit for bit.

The FPGA's bytes also go through fft.py's parse() and dB scaling.
"""
import argparse
import os
import subprocess
import sys
import tempfile

import numpy as np

import fft                         # fft.py: the laptop side

N, LOG2N = 1024, 10
FS = 25e6
HERE = os.path.dirname(os.path.abspath(__file__))

# ---- the FPGA's tables, computed exactly as fft.sv's `initial` block does -------
n = np.arange(N)
HANN = np.floor(512.0 - 512.0 * np.cos(2 * np.pi * n / N) + 0.5).astype(np.int64)
TW_RE = np.floor(65536.0 * np.cos(2 * np.pi * n[:N // 2] / N) + 0.5).astype(np.int64)
TW_IM = np.floor(-65536.0 * np.sin(2 * np.pi * n[:N // 2] / N) + 0.5).astype(np.int64)
BIT_REVERSE = np.array([int(f"{i:010b}"[::-1], 2) for i in range(N)])


def exact(frames):
    """The exact X[k], k = 0..N/2-1, of each frame (rows of ADC codes)."""
    return np.fft.rfft((frames - 128) * HANN, axis=1)[:, :N // 2] / N


def model(frames, a):
    """fft.sv's arithmetic, step for step.  Returns (P as sent, X of each frame)."""
    def halve(v):                  # v / 2^17, to nearest, exact halves to even
        return (v + 65535 + ((v >> 17) & 1)) >> 17
    Xs, acc = [], 0
    for codes in frames:
        re = np.zeros(N, np.int64)
        im = np.zeros(N, np.int64)
        re[BIT_REVERSE] = (codes - 128) * HANN
        for s in range(LOG2N):     # each stage's butterflies don't overlap: do them all at once
            j = np.arange(N // 2)
            lo = j & ((1 << s) - 1)
            ia = 2 * j - lo
            ib = ia + (1 << s)
            w_re, w_im = TW_RE[lo << (LOG2N - 1 - s)], TW_IM[lo << (LOG2N - 1 - s)]
            t_re = re[ib] * w_re - im[ib] * w_im
            t_im = re[ib] * w_im + im[ib] * w_re
            a_re, a_im = re[ia] << 16, im[ia] << 16
            re[ia], im[ia] = halve(a_re + t_re), halve(a_im + t_im)
            re[ib], im[ib] = halve(a_re - t_re), halve(a_im - t_im)
        Xs.append(re[:N // 2] + 1j * im[:N // 2])
        acc = acc + re[:N // 2]**2 + im[:N // 2]**2
    return np.minimum(acc >> a, 2**32 - 1), np.array(Xs)


def dbfs(p):
    return 10 * np.log10(p / 2**30)


# ---- the tests: (name, D, A, the characters sent, analog signal in codes at 25 MS/s)
def tone(f, amp, phase=0.3):
    return lambda t: amp * np.cos(2 * np.pi * f * t + phase)


def noise(sigma, seed):
    return lambda t: np.random.default_rng(seed).normal(0, sigma, len(t))


BIN = FS / N                       # 24414 Hz: the spacing of k at D = 0
TESTS = [
    ("tone at k = 100 (junk bytes too)", 0, 0, "Q0Q0", [tone(100 * BIN, 100)]),
    ("tone between bins, k = 200.5",    0, 0, "00", [tone(200.5 * BIN, 120)]),
    ("tone + one 40 dB smaller",         0, 0, "00", [tone(150.3 * BIN, 100), tone(300.7 * BIN, 1, 1.0)]),
    ("white noise, 20 codes rms",        0, 0, "00", [noise(20, 1)]),
    ("averaging, A = 2: tone + noise",   0, 2, "02", [tone(77.5 * BIN, 60), noise(10, 2)]),
    ("D = 3, A = 1: 1 MHz + noise",      3, 1, "31", [tone(1e6, 80), noise(3, 3)]),
    ("full-scale sine, k = 64",          0, 0, "00", [tone(64 * BIN, 127.49, 0.0)]),
    ("ADC stuck at 0 (the 32-bit cap)",  0, 0, "00", [lambda t: -200 + 0 * t]),
]


def run_all(tmp):
    """Start every simulation at once (they're independent), then wait for them."""
    vvp = os.path.join(tmp, "fft_tb.vvp")
    subprocess.run(["iverilog", "-g2012", "-o", vvp, "fft_tb.sv", "fft.sv", "uart.sv"],
                   cwd=HERE, check=True)
    jobs = []
    for i, (name, d, a, cmd, parts) in enumerate(TESTS):
        frames = 2**a
        t = np.arange(frames * (N * 2**d + 20000) + 1000) / FS   # frames, and the gaps between them
        analog = 128 + sum(p(t) for p in parts)
        codes = np.clip(np.round(analog), 0, 255).astype(int)
        files = {x: os.path.join(tmp, f"{i}_{x}.txt") for x in ("in", "out", "kept")}
        np.savetxt(files["in"], codes, fmt="%02x")
        ms = int(frames * (N * 2**d / FS + 1e-3) * 1e3 + 30)
        proc = subprocess.Popen(["vvp", "-n", vvp, f"+in={files['in']}", f"+cmd={cmd}",
                                 f"+out={files['out']}", f"+kept={files['kept']}", f"+ms={ms}"],
                                stdout=subprocess.PIPE, text=True)
        jobs.append((proc, files, analog, codes))
    results = []
    for (name, d, a, cmd, parts), (proc, files, analog, codes) in zip(TESTS, jobs):
        log = proc.communicate()[0]
        if "received 2048 bytes (0 framing errors, 0 RAM collisions)" not in log:
            raise SystemExit(f"{name}: simulation failed:\n{log}")
        raw = bytes(int(x, 16) for x in open(files["out"]).read().split())
        kept = np.loadtxt(files["kept"], dtype=str)
        results.append((raw, np.array([int(c, 16) for c in kept[:, 0]]),
                        kept[:, 1].astype(int), analog, codes))
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plot", action="store_true", help="plot each test")
    args = ap.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        results = run_all(tmp)

    ok = True
    err_fixed, err_8bit, rows = [], [], []
    print(f"{'test':34s} D A  peak k  peak dBFS  bins*  worst err  rms err  bit-exact")
    for (name, d, a, cmd, parts), (raw, kept, idx, analog, codes) in zip(TESTS, results):
        # the samples the FPGA kept, as the testbench saw them, frame by frame
        assert len(kept) == 2**a * N, f"{name}: kept {len(kept)} samples"
        assert np.array_equal(kept, codes[idx]), f"{name}: kept samples aren't the test signal"
        steps = np.diff(idx.reshape(-1, N), axis=1)
        assert np.all(steps == 2**d), f"{name}: kept samples aren't 2^D apart"
        frames = kept.reshape(-1, N)

        # ######################################################################
        # ##  KEY LINES: the FPGA's answer (through fft.py), the exact answer,
        # ##  and the bit-exact model.
        # ######################################################################
        P = fft.parse(raw)
        X = exact(frames)
        P_exact = np.mean(abs(X)**2, axis=0)
        P_model, X_model = model(frames, a)

        same = np.array_equal(P, P_model)
        near = P_exact >= P_exact.max() * 1e-6               # * within 60 dB of the peak
        err = 10 * np.log10(np.maximum(P[near], 0.5) / P_exact[near])
        k = int(np.argmax(P))
        print(f"{name:34s} {d} {a}  {k:5d}  {fft.db_full_scale(P)[k]:8.2f}  {near.sum():5d}"
              f"  {abs(err).max():7.4f} dB {np.sqrt(np.mean(err**2)):6.4f} dB  {'yes' if same else 'NO'}")
        ok &= same
        rows.append((name, d, P, P_exact, abs(X_model - X)**2))

        if "stuck" not in name and "full-scale" not in name:      # no clipping here
            err_fixed.append(np.mean(abs(X_model - X)**2))
            X_analog = exact(analog[idx].reshape(-1, N))
            err_8bit.append(np.mean(abs(X - X_analog)**2))
        if name.startswith("white noise"):
            big = P_exact > 100
            from_fpga = 2 * np.mean((np.sqrt(P[big]) - np.sqrt(P_exact[big]))**2)
        if name.startswith("tone at k = 100"):     # fft.py's scaling, against the test signal
            want = 20 * np.log10(100 / 128)
            want_v = 20 * np.log10(100 / fft.ADC_CODES_PER_VOLT)      # 100 codes = 3.94 V
            print(f"{'':34s} fft.py: f = {fft.frequencies(d)[k]:.2f} Hz (want {100 * BIN:.2f}), "
                  f"{fft.db_full_scale(P)[k]:.3f} dBFS (want {want:.3f}), "
                  f"{fft.db_volts(P)[k]:.3f} dB re 1 V (want {want_v:.3f})")
            ok &= (fft.frequencies(d)[k] == 100 * BIN and abs(fft.db_full_scale(P)[k] - want) < 0.05
                   and abs(fft.db_volts(P)[k] - want_v) < 0.05)
        if name.startswith("D = 3"):
            f_peak = fft.frequencies(d)[int(np.argmax(P[1:])) + 1]
            print(f"{'':34s} fft.py: peak at {f_peak:.0f} Hz (want 1000000 +- half a step, "
                  f"{fft.frequencies(d)[1] / 2:.0f} Hz)")
            ok &= abs(f_peak - 1e6) <= fft.frequencies(d)[1] / 2
        if "stuck" in name:
            print(f"{'':34s} P[0] = {int(P[0])} (exact {P_exact[0]:.0f}: capped at 2^32 - 1)")
            ok &= P[0] == 2**32 - 1

    print("* bins compared: those within 60 dB of the peak.  err = 10 log10(P_FPGA / P_exact);"
          "\n  bit-exact: P_FPGA equals the fixed-point model's in all 512 bins")
    floor_fixed, floor_8bit = dbfs(np.mean(err_fixed)), dbfs(np.mean(err_8bit))
    print(f"\nfixed-point error |X_FPGA - X_exact|^2:  {floor_fixed:6.1f} dBFS per k "
          f"(white noise, estimated from the FPGA's P alone: {dbfs(from_fpga):.1f} dBFS)")
    print(f"8-bit rounding noise |X_8bit - X_analog|^2: {floor_8bit:6.1f} dBFS per k "
          f"(theory, 1/12 code^2: {dbfs(fft.FLOOR_8BIT):.1f} dBFS)")
    print(f"the FPGA's arithmetic adds noise {floor_8bit - floor_fixed:.1f} dB below the "
          f"8-bit ADC's own (need at least 10 dB)")
    ok &= floor_8bit - floor_fixed >= 10
    print("PASS" if ok else "FAIL")

    if args.plot:
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 4, figsize=(16, 7), sharey=True)
        for ax, (name, d, P, P_exact, E) in zip(axes.flat, rows):
            f = fft.frequencies(d) / 1e6
            ax.plot(f, dbfs(np.maximum(P_exact, 0.5)), "-", linewidth=1, label="numpy (exact)")
            ax.plot(f, fft.db_full_scale(P), ".", markersize=3, label="FPGA (simulated)")
            ax.plot(f, dbfs(np.maximum(E.mean(axis=0), 1e-3)), ".", markersize=2, color="gray",
                    label="FPGA's arithmetic error")
            ax.axhline(dbfs(fft.FLOOR_8BIT), color="k", linestyle="--", linewidth=0.8,
                       label="8-bit rounding noise")
            ax.set_title(name, fontsize=9)
            ax.set_xlabel("frequency (MHz)")
            ax.set_ylim(-130, 5)
            ax.grid(True)
        for ax in axes[:, 0]:
            ax.set_ylabel("dB re full-scale sine")
        axes[0, 0].legend(fontsize=7, loc="lower left")
        plt.tight_layout()
        plt.show()
    sys.exit(0 if ok else 1)
