"""6.12's two-board question, asked with one board: the slow FT8-style frame through the
loopback cable, with the transmitter pretending that its crystal is PPM fast (its tones and
its symbol clock scaled together) and drifting by DRIFT ppm over the frame; decoded with
each search width given, in tone spacings either way (1 ppm at 6.78 MHz is 1.14 spacings).

    make load-ddc                     (src/twoboard)
    python3 ft8_crystal.py PORT --ppm 10 --search 3 25
    python3 ft8_crystal.py PORT --ppm 5 --drift -2

The drift is played by rewriting the eight tone words between reads of the I/Q stream.
"""
import argparse
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.join(HERE, "..", "..", "..")
sys.path.insert(0, os.path.join(TOP, "src", "comms"))
sys.path.insert(0, os.path.join(TOP, "src", "twoboard"))
import ddc                                                   # noqa: E402
import ft8                                                   # noqa: E402

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("port")
ap.add_argument("--ppm", type=float, default=0.0, help="the transmitter's crystal, ppm fast")
ap.add_argument("--drift", type=float, default=0.0, help="ppm more by the frame's end")
ap.add_argument("--search", type=float, nargs="+", default=[3.0, 25.0], help="search widths, tone spacings")
ap.add_argument("--text", default="CQ HMC JASON")
a = ap.parse_args()

ser = ddc.open_port(a.port)
tones = ft8.encode(a.text)
base = ft8.slow_tones_hz()


def set_tones(ppm):
    for k, f in enumerate(base):
        ddc.set_tone(ser, k, f * (1 + ppm * 1e-6))


ddc.set_rx(ser, ft8.SLOW_F0)
ddc.set_decim(ser, ft8.SLOW_DECIM)
ddc.set_amp(ser, 100)
set_tones(a.ppm)
ddc.set_symbol(ser, round(2**(ft8.SLOW_LOG2 + 1) / (1 + a.ppm * 1e-6)))
ddc.stream(ser, True)
time.sleep(0.05)
ser.reset_input_buffer()
frame_s = ft8.NSYM * 2**ft8.SLOW_LOG2 / ft8.FS_ADC
rest, got, t0, start = b"", [], time.time(), None
while time.time() - t0 < frame_s + 3.0:
    if start is None and time.time() - t0 > 1.0:            # a second of silence first
        ddc.queue(ser, [int(t) for t in tones])
        start = time.time()
    if start is not None and a.drift:
        set_tones(a.ppm + a.drift * min(1.0, (time.time() - start) / frame_s))
    z, rest = ddc.parse_frames(rest + ser.read(2000))
    if len(z):
        got.append(z)
ddc.stream(ser, False)
z = np.concatenate(got) / ddc.SCALE
z = np.concatenate([z, np.zeros(ft8.SLOW_SPS * ft8.NSYM, complex)])
print("transmitter %+.1f ppm (%+.1f Hz)%s" % (a.ppm, a.ppm * 1e-6 * ft8.SLOW_F0,
      ", drifting %+.1f ppm over the frame" % a.drift if a.drift else ""))
for nu_max in a.search:
    r = ft8.receive(z, ft8.SLOW_SPS, nu_max, nu_step=0.125 if nu_max <= 3 else 0.25)
    wrong = int(np.sum(r["heard"][ft8.DATA_AT] != tones[ft8.DATA_AT]))
    print("  search +-%4.1f spacings: %-4s %-14r found %+6.2f spacings (%+6.1f Hz), %2d of 58 symbols wrong"
          % (nu_max, "OK" if r["ok"] and r["text"].strip() == a.text else "FAIL", r["text"], r["nu"],
             r["nu"] * ft8.SLOW_DF, wrong))
