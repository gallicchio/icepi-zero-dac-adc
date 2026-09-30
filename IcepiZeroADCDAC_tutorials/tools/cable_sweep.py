"""Instructor's cable characterization with lockin.bit: DAC -> cable -> ADC.

    python3 cable_sweep.py NAME [--fmax 24e6] [--step 100e3] [-a 4] [--repeat 1]
    python3 cable_sweep.py NAME --fclk 100e6 ...     # with lockin_pll.bit (DAC at 100 MS/s)

Sweeps the lock-in linearly from --step to --fmax in steps of --step and saves
f, complex response (volts at the ADC) for every repeat to data/cable_NAME.npz.
"""
import argparse, os, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import lockin

ap = argparse.ArgumentParser()
ap.add_argument("name")
ap.add_argument("--fmin", type=float, default=None)
ap.add_argument("--fmax", type=float, default=12.4e6)
ap.add_argument("--step", type=float, default=100e3)
ap.add_argument("-a", "--averages", type=int, default=4)
ap.add_argument("--repeat", type=int, default=1)
ap.add_argument("--fclk", type=float, default=50e6, help="the DDS clock: 100e6 for lockin_pll.bit")
args = ap.parse_args()
lockin.F_CLK = args.fclk

freqs = np.arange(args.fmin or args.step, args.fmax + 1, args.step)
li = lockin.LockIn()
out = []
t0 = time.time()
for r in range(args.repeat):
    row = []
    for f in freqs:
        fa, z = li.measure(f, args.averages)
        row.append(z)
    out.append(row)
    print("sweep %d done, %.0f s" % (r + 1, time.time() - t0), flush=True)
f_actual = np.array([lockin.tuning_word(f) * lockin.F_CLK / 2**32 for f in freqs])
z = np.array(out)
np.savez(os.path.join(HERE, "..", "data", "cable_%s.npz" % args.name), f=f_actual, z=z,
         when=time.time(), fclk=args.fclk)
ph = np.unwrap(np.angle(z[0]))
sel = f_actual < 12e6
if not sel.any():
    sys.exit(0)
p = np.polyfit(f_actual[sel], ph[sel], 1)
print("points %d; |z| at %.1f MHz = %.3f V, at %.1f MHz = %.3f V" %
      (len(f_actual), f_actual[0] / 1e6, abs(z[0, 0]), f_actual[sel][-1] / 1e6, abs(z[0][sel][-1])))
print("phase slope (<12 MHz): %.4f deg/MHz -> delay %.2f ns; intercept %.2f deg" %
      (np.degrees(p[0]) * 1e6, -p[0] / (2 * np.pi) * 1e9, np.degrees(p[1])))
