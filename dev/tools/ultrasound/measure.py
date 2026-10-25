"""4.06's measurements: a 40 kHz transducer pair between the DAC and the ADC.

Each step loads the bitstream it needs and saves dev/data/ultra_<step>.npz;
fig_ultrasound.py draws the pictures from those files.  The page's results are the
pair on a cardboard box; dev/data/ultra_bench_*.npz are the same steps run earlier with
the pair lying on the bench (measured with this script, then renamed by hand).

    python3 measure.py all             # everything, about 25 minutes
    python3 measure.py sweep watch     # lockin.bit: 30-64 kHz in 10 Hz steps; 2 min at 40.3 kHz
    python3 measure.py burst window ofdm    # awgcap_slow.bit
    python3 measure.py fsk             # ddc.bit
"""
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
SRC = os.path.join(TOP, "src")
for d in ("ultrasound", "verilog", "twoboard"):
    sys.path.insert(0, os.path.join(SRC, d))
import awgcap_slow as awg                       # noqa: E402
import fsk                                      # noqa: E402
import lockin                                   # noqa: E402
import ofdm_air                                 # noqa: E402
import sweep                                    # noqa: E402

BITS = {"lockin": "verilog/lockin.bit", "awgcap_slow": "ultrasound/awgcap_slow.bit",
        "ddc": "twoboard/ddc.bit"}
_loaded = None


def load(name):
    global _loaded
    if _loaded != name:
        subprocess.run(["openFPGALoader", "-b", "icepi-zero", os.path.join(SRC, BITS[name])],
                       check=True, capture_output=True)
        time.sleep(3.0)                         # something on the board settles for ~2 s
        _loaded = name


def path(name):
    return os.path.join(TOP, "dev", "data", "ultra_%s.npz" % name)


def stamp():
    return time.strftime("%Y-%m-%d %H:%M")


def do_sweep():
    load("lockin")
    li = lockin.LockIn()
    f, z = sweep.sweep(li, np.arange(30000.0, 64000.0 + 5, 10.0))
    np.savez(path("sweep"), f=f, z=z, when=stamp())


def do_watch(seconds=120.0, f0=40300.0):
    load("lockin")
    li = lockin.LockIn()
    li.measure(f0)
    t, z = [], []
    t0 = time.time()
    while time.time() - t0 < seconds:
        z.append(li.measure(f0)[1])
        t.append(time.time() - t0)
    np.savez(path("watch"), t=np.array(t), z=np.array(z), f=f0, when=stamp())


def do_burst(f0=40300.0, ms=3.0, records=16):
    load("awgcap_slow")
    ser = awg.open_port()
    wave = awg.tone_burst(f0, ms, 127, start_ms=1.0)
    awg.upload(ser, wave)
    time.sleep(3 * awg.LOOP)
    x = np.array([awg.record(ser) for _ in range(records)])
    np.savez(path("burst"), x=x, wave=wave, f0=f0, ms=ms, when=stamp())


def do_window(offsets=range(0, 337, 16), records=2):
    """SNR against where the FFT window starts, with QPSK known on every subcarrier."""
    load("awgcap_slow")
    ser = awg.open_port()
    rng = np.random.default_rng(3)
    sent = np.exp(1j * np.pi / 2 * (rng.integers(0, 4, (ofdm_air.NSYM, len(ofdm_air.KS))) + 0.5))
    recs = [ofdm_air.run_loop(ser, sent) for _ in range(records)]
    snr = []
    for off in offsets:
        e = []
        for rec in recs:
            Y = ofdm_air.demux(rec, off)
            for L in range(2):
                H = np.mean(Y[L] / sent, axis=0)
                e.append(np.mean(abs(Y[L] / H - sent) ** 2, axis=0))
        snr.append(1 / np.mean(e, axis=0))
    np.savez(path("window"), offsets=np.array(list(offsets)), snr=np.array(snr),
             ks=ofdm_air.KS, df=ofdm_air.DF, cp=ofdm_air.CP, when=stamp())


def do_ofdm(gaps=(7.0, 10.0, 13.0), loops=20):
    load("awgcap_slow")
    for g in gaps:
        sys.argv = ["ofdm_air.py", "--loops", str(loops), "--gap", str(g),
                    "-o", path("ofdm_gap%d" % g)]
        ofdm_air.main()


def do_fsk(Ms=(48, 24, 16, 12, 8, 6, 5, 4), frames=20, show=(24, 5, 4)):
    load("ddc")
    rng = np.random.default_rng(2)
    out = {"M": np.array(Ms), "when": stamp()}
    errs, tot = [], []
    for M in Ms:
        m = fsk.Modem(None, M)
        e = n = 0
        for k in range(frames):
            bits = rng.integers(0, 2, fsk.MAX_SYMBOLS - len(fsk.BARKER))
            z = m.send_and_listen(bits)
            got, soft, start = fsk.receive(z, M, len(bits))
            e += int(np.sum(got != bits))
            n += len(bits)
            if M in show and k == 0:
                out["z_%d" % M], out["bits_%d" % M] = z, bits
                out["start_%d" % M], out["soft_%d" % M] = start, soft
        errs.append(e)
        tot.append(n)
        print(f"{fsk.FS_IQ / M:7.1f} baud: {e} errors in {n}")
        m.ser.close()
    out["errors"], out["total"] = np.array(errs), np.array(tot)
    np.savez(path("fsk"), **out)


STEPS = {"sweep": do_sweep, "watch": do_watch, "burst": do_burst, "window": do_window,
         "ofdm": do_ofdm, "fsk": do_fsk}

if __name__ == "__main__":
    todo = sys.argv[1:] or ["all"]
    if todo == ["all"]:
        todo = list(STEPS)
    for s in todo:
        print("----", s, stamp())
        STEPS[s]()
