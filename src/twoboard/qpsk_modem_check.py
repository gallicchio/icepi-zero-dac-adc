#!/usr/bin/env python3
"""Check qpsk_modem.sv against modem_fpga_model.py, in simulation: no hardware needed.

    python3 qpsk_modem_check.py                 # all the tests: about a minute
    python3 qpsk_modem_check.py --ppm 2000 --cfo -9500 --noise 3   # the offsets of test 3
    python3 qpsk_modem_check.py --plot          # ...and plot the loops, Verilog against model
    python3 qpsk_modem_check.py --bytes 50      # shorter

The tests (Icarus Verilog runs qpsk_modem_tb.sv; about 60,000 clocks a second):
  1. Looped back: the testbench's cable from the DAC to the ADC (0.776 x + 27.5, 220 ns
     late), random bytes typed at 1 Mbaud from 400 us on, and what comes back.
  2. The transmitter, bit for bit: the DAC codes of test 1 against the model's, given the
     frames the design sent.
  3. The receiver, bit for bit, with two clocks: the DAC codes of test 1 go through the
     channel model (modem_fpga_model.stream_channel: delay, 0.776 x + 27.5, noise, the
     transmitter's clock --ppm fast, so its carrier is 6.25 x ppm Hz high and its symbols
     ppm fast, and a mixer error --cfo on top), into the ADC of a second simulation.  Every
     symbol's loop state, and every byte, against the model on the same codes.
  4. The serial port's hand-offs: 1500 bytes back to back, and 1500 at every phase of the
     256-clock frame (one clock later each), with the output FIFO shrunk to 2 bytes, so
     that a transmitter that can't keep up with 1 Mbaud shows within the run: none may be
     lost, and the bytes must leave faster than they arrive (490 clocks apart, not 500).
  5. (For information) the laptop's port at 115,200 baud: the design's ports are 1 Mbaud,
     so most bytes still come back, but not all of their bits (see the hand-back).
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "comms"))
import modem_fpga_model as M                                 # noqa: E402

SRC = ["qpsk_modem_tb.sv", "qpsk_modem.sv", os.path.join("..", "verilog", "uart.sv")]
COLS = ["zI", "zQ", "mu", "tau", "period", "eg", "phi", "freq", "ec", "q", "locked", "clock"]


def build(tmp, fifo_bits=5):
    vvp = os.path.join(tmp, "qpsk_modem_tb_%d.vvp" % fifo_bits)
    subprocess.run(["iverilog", "-g2012", "-P", "qpsk_modem_tb.FIFO_BITS=%d" % fifo_bits, "-o", vvp] + SRC,
                   cwd=HERE, check=True)
    return vvp


def run(vvp, tmp, name, clocks, adc=None, send=None, loop=False, send_t0=2000, sweep=False, bit_clocks=50):
    """One simulation.  Returns the bytes received (and when), the DAC codes, the frames
    sent, the receiver's state at each symbol, and the testbench's summary line."""
    f = {x: os.path.join(tmp, "%s.%s" % (name, x)) for x in ("adc", "send", "rx", "dac", "frames", "sym")}
    args = ["vvp", "-n", vvp, "+clocks=%d" % clocks, "+rx=" + f["rx"], "+dac=" + f["dac"],
            "+frames=" + f["frames"], "+sym=" + f["sym"], "+send_t0=%d" % send_t0,
            "+send_sweep=%d" % sweep, "+bit_clocks=%d" % bit_clocks]
    if loop:
        args.append("+loop=1")
    if adc is not None:
        np.savetxt(f["adc"], adc, fmt="%d")
        args.append("+adc=" + f["adc"])
    if send is not None:
        np.savetxt(f["send"], np.asarray(send), fmt="%02x")
        args.append("+send=" + f["send"])
    p = subprocess.run(args, capture_output=True, text=True, check=True)
    out = {"log": [l for l in p.stdout.splitlines() if "clocks:" in l][-1]}
    m = re.search(r"(\d+) sent, (\d+) received \((\d+) framing errors\), (\d+) arrived as a frame loaded; the FIFO held at most (\d+); bytes left (\d+) to (\d+) clocks apart", out["log"])
    out["n_sent"], out["n_rx"], out["framing"], out["coincide"], out["fifo_max"], out["gap_min"], out["gap_max"] = (int(x) for x in m.groups())
    rx = np.loadtxt(f["rx"], dtype=str, ndmin=2)
    out["rx"] = np.array([int(x, 16) for x in rx[:, 0]], np.int64) if rx.size else np.zeros(0, np.int64)
    out["rx_at"] = rx[:, 1].astype(np.int64) if rx.size else np.zeros(0, np.int64)
    out["dac"] = np.loadtxt(f["dac"], dtype=np.int64)
    fr = np.loadtxt(f["frames"], dtype=str, ndmin=2)
    out["frames"] = np.array([int(x, 16) for x in fr[:, 0]], np.int64)
    out["frames_at"] = fr[:, 1].astype(np.int64)
    sym = np.loadtxt(f["sym"], dtype=np.int64, ndmin=2)
    out["sym"] = {c: sym[:, i] for i, c in enumerate(COLS)} if sym.size else {c: np.zeros(0, np.int64) for c in COLS}
    return out


def align(a, b, search=2000):
    """The offset L at which b[L:] matches a (the first 4000 samples)."""
    n = min(4000, len(a), len(b) - search)
    for L in range(search):
        if np.array_equal(a[:n], b[L:L + n]):
            return L
    return None


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bytes", type=int, default=200, help="random bytes to send")
    ap.add_argument("--ppm", type=float, default=2000.0, help="test 3: the transmitter's clock offset")
    ap.add_argument("--cfo", type=float, default=-9500.0, help="test 3: a mixer's error, Hz, on top")
    ap.add_argument("--noise", type=float, default=0.1, help="test 3: ADC noise, codes rms")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--plot", nargs="?", const="", metavar="FILE", help="plot the loops (or save to FILE)")
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    data = rng.integers(0, 256, args.bytes)
    ok = True

    with tempfile.TemporaryDirectory() as tmp:
        vvp = build(tmp)

        # ---- 1. looped back through the testbench's cable ----------------------------
        # the bytes start 400 us in, after the loops have settled (about 300 symbols, 200 us)
        T0 = 20000
        clocks = T0 + 500 * args.bytes + 60000
        print("1. LOOPED BACK: %d random bytes at 1 Mbaud, %d clocks (%.1f ms)" % (args.bytes, clocks, clocks / 50e3))
        r1 = run(vvp, tmp, "loop", clocks, send=data, loop=True, send_t0=T0)
        print("   " + r1["log"])
        errs = M.score(data, r1["rx"])
        delay = (r1["rx_at"][:len(data)] - (T0 + 500 * np.arange(len(data)) + 500)) / 50.0 if len(r1["rx"]) else []
        print("   %d bytes came back, %d bit errors; typed-to-echoed delay %.1f to %.1f us"
              % (len(r1["rx"]), errs, np.min(delay), np.max(delay)) if len(delay) else "   nothing came back")
        ok &= errs == 0 and len(r1["rx"]) == len(data)

        # ---- 2. the transmitter against the model ------------------------------------
        print("\n2. THE TRANSMITTER, BIT FOR BIT: the DAC codes of test 1 against the model's,")
        print("   from the %d frames the design sent (%d with a byte)" % (len(r1["frames"]), np.sum((r1["frames"] >> 8) & 1)))
        want = M.tx_dac(M.tx_symbols(r1["frames"]))
        L = align(want, r1["dac"])
        if L is None:
            print("   NO match for the first 4000 DAC codes")
            ok = False
        else:
            n = min(len(want), len(r1["dac"]) - L)
            same = np.array_equal(want[:n], r1["dac"][L:L + n])
            print("   bit-exact over %d codes: %s (the design's DAC is %d clocks behind the model's symbol clock)"
                  % (n, "yes" if same else "NO", L))
            ok &= same
        d = r1["dac"][L + 3000:L + 3000 + 32768] - 128 if L is not None else r1["dac"] - 128
        print("   DAC: rms %.1f codes, peak %d (never clips: the worst case is 108)" % (d.std(), np.abs(d).max()))

        # ---- 3. the receiver against the model, with offsets --------------------------
        print("\n3. THE RECEIVER, BIT FOR BIT: the same DAC codes through the channel model, with the")
        print("   transmitter's clock %+.0f ppm fast (carrier %+.0f Hz, symbols %+.0f ppm), a mixer error"
              " of %+.0f Hz, noise %.1f codes rms" % (args.ppm, args.ppm * 6.25, args.ppm, args.cfo, args.noise))
        adc = M.stream_channel(r1["dac"], ppm=args.ppm, cfo=args.cfo, noise=args.noise, rng=args.seed)
        r3 = run(vvp, tmp, "rx", 2 * len(adc) + 2000, adc=adc)
        print("   " + r3["log"])
        # (the design's first sample is the pin's 128 before the first code)
        m = M.receive(np.concatenate([[128], adc]))
        v = r3["sym"]
        n = min(len(v["zI"]), len(m["zI"]))
        first = None
        for c in ("zI", "zQ", "mu", "period", "eg", "phi", "freq", "ec", "q", "locked"):
            bad = np.flatnonzero(v[c][:n] != m[c][:n])
            if len(bad) and (first is None or bad[0] < first[1]):
                first = (c, bad[0])
        print("   symbols: Verilog %d, model %d; loop states identical: %s"
              % (len(v["zI"]), len(m["zI"]), "yes, all %d" % n if first is None else "NO: first difference in %s at symbol %d" % first))
        ok &= first is None and len(v["zI"]) >= len(m["zI"])
        lk = np.flatnonzero(v["locked"])
        last = slice(-500, None)
        print("   frame lock at symbol %s; found %+.0f ppm and %+.0f Hz (mean of the last 500 symbols)"
              % (lk[0] if len(lk) else "never", (M.PNOM / v["period"][last] - 1e0).mean() * 1e6, v["freq"][last].mean() * M.R_SYM / 2**24))
        got = r3["rx"][r3["rx_at"] < 2 * len(adc)]            # bytes out before the stream ends
        errs = M.score(data, got)
        lost = len(data) - len(got)
        print("   %d bytes came back (model: %d), %d bit errors (%d from the %d byte%s sent before the"
              " lock); bytes identical to the model's: %s"
              % (len(got), len(m["bytes"]), errs, 8 * lost, lost, "" if lost == 1 else "s",
                 "yes" if np.array_equal(got, m["bytes"]) else "NO"))
        ok &= errs == 8 * lost and np.array_equal(got, m["bytes"])
        good = v["locked"] > 0
        good[:max(0, n - 1000)] = False                        # the last 1000 symbols of the stream
        good[n:] = False                                       # (the design runs on into silence)
        zI, zQ = v["zI"][good].astype(float), v["zQ"][good].astype(float)
        S = np.mean(np.abs(zI) + np.abs(zQ)) / 2
        mer = 10 * np.log10(2 * S * S / np.mean((np.abs(zI) - S)**2 + (np.abs(zQ) - S)**2))
        print("   MER over the last 1000 symbols %.1f dB" % mer)

        # ---- 4. the serial port's hand-offs, thousands of bytes --------------------------
        print("\n4. THE SERIAL PORT'S HAND-OFFS: 1500 bytes, the output FIFO shrunk to 2 bytes")
        vvp2 = build(tmp, fifo_bits=1)
        for sweep in (False, True):
            d4 = rng.integers(0, 256, 1500)
            r4 = run(vvp2, tmp, "race%d" % sweep, 20000 + 501 * 1500 + 30000, send=d4, loop=True,
                     send_t0=20000, sweep=sweep)
            errs = M.score(d4, r4["rx"])
            print("   %s: %d sent, %d received, %d bit errors; %d bytes arrived in the clock a frame loaded;"
                  "\n      the FIFO held at most %d; bytes left %d to %d clocks apart (they arrive every %d)"
                  % ("at every phase of the frame" if sweep else "back to back", r4["n_sent"], r4["n_rx"], errs,
                     r4["coincide"], r4["fifo_max"], r4["gap_min"], r4["gap_max"], 501 if sweep else 500))
            ok &= errs == 0 and r4["n_rx"] == 1500 and r4["gap_min"] < 500

        # ---- 5. the laptop's port at 115,200 baud: for information ------------------------
        d5 = rng.integers(0, 256, 40)
        r5 = run(vvp, tmp, "slow", 2000 + 4340 * 40 + 60000, send=d5, loop=True, bit_clocks=434)
        print("\n5. A LAPTOP PORT AT 115,200 BAUD (the design's are 1,000,000): %d of 40 bytes came back,"
              " %d bit errors\n   (the 1 Mbaud receiver samples the slow line like a digitizer; see the page)"
              % (r5["n_rx"], M.score(d5, r5["rx"])))

    print("\nPASS" if ok else "\nFAIL")
    if args.plot is not None:
        import matplotlib
        if args.plot:
            matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        k = np.arange(len(v["zI"]))
        fig, ax = plt.subplots(2, 2, figsize=(11, 8))
        ax[0, 0].plot(v["zI"][~good], v["zQ"][~good], ".", color="0.75", markersize=2, label="before lock")
        ax[0, 0].plot(zI, zQ, ".", markersize=2, label="locked")
        ax[0, 0].set_aspect("equal"); ax[0, 0].set_title("Verilog: symbols after the loops"); ax[0, 0].legend()
        ax[0, 1].plot(k, v["mu"] / 4096, ".", markersize=1.5); ax[0, 1].set_title("mu (fraction of a sample)")
        ax[1, 0].plot(k, (M.PNOM / v["period"] - 1) * 1e6, label="Verilog")
        ax[1, 0].plot(m["sym"] * 0 + np.arange(len(m["sym"])), m["ppm"], "--", label="model")
        ax[1, 0].axhline(args.ppm, color="k", lw=0.5); ax[1, 0].set_title("symbol rate offset found (ppm)"); ax[1, 0].legend()
        ax[1, 1].plot(k, v["freq"] * M.R_SYM / 2**24, label="Verilog")
        ax[1, 1].plot(np.arange(len(m["sym"])), m["hz"], "--", label="model")
        ax[1, 1].axhline(args.ppm * 6.25 + args.cfo, color="k", lw=0.5); ax[1, 1].set_title("carrier offset found (Hz)"); ax[1, 1].legend()
        for a in ax.ravel()[1:]:
            a.set_xlabel("symbol"); a.grid(True)
        fig.tight_layout()
        if args.plot:
            fig.savefig(args.plot, dpi=110); print("plot saved to " + args.plot)
        else:
            plt.show()
    sys.exit(0 if ok else 1)
