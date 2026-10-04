#!/usr/bin/env python3
"""7.04, the laptop side: design a filter with scipy and load it into the filter
peripheral through LiteX's UART bridge, as remote.py does for Chapter 2's registers.

The designs, the quantization and the predictions are 7.03's, imported from
src/dsp/filter.py (the same options: --lowpass FC, --highpass FC, --bandpass F1 F2,
--taps N, --moving N, --edge, --rc FC, --butter ORDER FC [--high], --b 1,2,1 --a 1,-0.5).
Only the last step differs: instead of bytes to filter.sv's serial-port parser, each
coefficient is a register write, by name, through litex_server.

    python3 icepi_adda_soc.py --build --uart-name=crossover+uartbone --output-dir build/bone
    openFPGALoader -b icepi-zero build/bone/gateware/icepi_zero.bit
    litex_server --uart --uart-port /dev/ttyUSB0 &

    python3 filter_remote.py --lowpass 2e6 --on          # 15-tap windowed sinc; the DAC plays it
    python3 filter_remote.py --butter 2 2e6              # a 2nd-order Butterworth (an IIR)
    python3 filter_remote.py --rc 250e3                  # a one-pole RC at 250 kHz
    python3 filter_remote.py --src 1 --capture -o imp.npz   # impulse in; 16384 ADC samples out
    python3 filter_remote.py --show                      # what the registers hold

--src 0 ADC, 1 impulse, 2 step, 3 noise, 4 tone;  --out 0 the output, 1 the input;
--tone F;  --on / --off: the DAC plays the filter / the function generator.
"""
import argparse
import os
import sys
import time

import numpy as np
from litex import RemoteClient

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "dsp"))
import filter as dsp            # 7.03's design(), quantize(), table(), simulate(): the same filter

DESIGNS = ["lowpass", "highpass", "bandpass", "moving", "edge", "rc", "butter", "b"]


def load(wb, bq, aq):
    """The 16 b and 4 a registers, by name; the unused ones zero.  aq[0] is a_0 = 8192."""
    # ######################################################################################
    # ##  KEY LINES: a register write per coefficient, over the serial port, onto the bus.
    # ##  The multipliers use each new value on their next sample; nothing is compiled.
    # ######################################################################################
    for k in range(dsp.NB):
        getattr(wb.regs, "filter_b%d" % k).write(int(bq[k] if k < len(bq) else 0) & 0xffff)
    for k in range(1, dsp.NA + 1):
        getattr(wb.regs, "filter_a%d" % k).write(int(aq[k] if k < len(aq) else 0) & 0xffff)


def signed16(v):
    return v - 65536 if v & 0x8000 else v


def show(wb):
    """Read the registers back and print them."""
    b = [signed16(getattr(wb.regs, "filter_b%d" % k).read()) for k in range(dsp.NB)]
    a = [signed16(getattr(wb.regs, "filter_a%d" % k).read()) for k in range(1, dsp.NA + 1)]
    src, status = wb.regs.filter_src.read(), wb.regs.filter_status.read()
    print("filter: b =", " ".join(str(v) for v in b))
    print("        a =", " ".join(str(v) for v in a), "  (x 8192)")
    print("        src %s, out %s, tone %.0f Hz; the DAC plays %s%s%s" % (
        dsp.SRC_NAMES[src] if src < 5 else "?",
        "the input" if wb.regs.filter_out.read() else "the output",
        wb.regs.filter_tone.read() * dsp.FS / 2**32,
        "the filter" if wb.regs.filter_dac_source.read() else "the function generator (--on to switch)",
        ", running" if status & 1 else "", ", clipped" if status & 2 else ""))
    return b, a


def capture(wb):
    """2.04's capture: 16384 ADC samples at 25 MS/s, straight off the bus (remote.py)."""
    wb.regs.capture_config.write(0)                   # every sample, no trigger
    wb.regs.capture_control.write(1)                  # start
    while not wb.regs.capture_status.read() & 2:
        time.sleep(0.001)
    buf = wb.mems.capture_buf
    words = wb.read(buf.base, buf.size // 4)
    return np.array(words, dtype="<u4").view(np.uint8).astype(int)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_argument_group("design (filter.py's)")
    g.add_argument("--lowpass", type=float, metavar="FC")
    g.add_argument("--highpass", type=float, metavar="FC")
    g.add_argument("--bandpass", type=float, nargs=2, metavar=("F1", "F2"))
    g.add_argument("--taps", type=int, default=15)
    g.add_argument("--moving", type=int, metavar="N")
    g.add_argument("--edge", action="store_true")
    g.add_argument("--rc", type=float, metavar="FC")
    g.add_argument("--butter", type=float, nargs=2, metavar=("ORDER", "FC"))
    g.add_argument("--high", action="store_true", help="--butter: a high-pass")
    g.add_argument("--b", help="raw b's, comma-separated")
    g.add_argument("--a", help="raw a's, comma-separated (a_0 first)")
    g = ap.add_argument_group("the registers")
    g.add_argument("--csr-csv", default=os.path.join(HERE, "build", "bone", "csr.csv"))
    g.add_argument("--src", type=int)
    g.add_argument("--out", type=int)
    g.add_argument("--tone", type=float)
    g.add_argument("--on", action="store_true")
    g.add_argument("--off", action="store_true")
    g.add_argument("--capture", action="store_true")
    g.add_argument("--show", action="store_true")
    g.add_argument("-o", "--save", metavar="NAME.npz")
    args = ap.parse_args()

    wb = RemoteClient(csr_csv=args.csr_csv)
    wb.open()
    saved = {}
    if any(getattr(args, d) not in (None, False) for d in DESIGNS):
        b, a, name = dsp.design(args)
        bq, aq = dsp.quantize(b), dsp.quantize(a)
        dsp.table(b, a, bq, aq, name)
        load(wb, bq, aq)
        print("loaded")
        saved.update(name=name, b=bq, a=aq, bf=b, af=a, fs=dsp.FS)
    if args.src is not None:
        wb.regs.filter_src.write(args.src)
    if args.out is not None:
        wb.regs.filter_out.write(args.out)
    if args.tone is not None:
        wb.regs.filter_tone.write(int(round(args.tone / dsp.FS * 2**32)) & 0xffffffff)
    if args.on:
        wb.regs.filter_dac_source.write(1)
    if args.off:
        wb.regs.filter_dac_source.write(0)
    if args.capture:
        rec = capture(wb)
        print("%d samples at 25 MS/s; codes %d..%d, mean %.1f" % (len(rec), rec.min(), rec.max(), rec.mean()))
        saved.update(rec=rec, source="ADC capture, 2.04's peripheral")
    if args.show or not saved and not (args.src is not None or args.out is not None or args.tone or args.on or args.off):
        show(wb)
    if args.save:
        np.savez(args.save, **saved)
        print("saved", args.save)
    wb.close()


if __name__ == "__main__":
    main()
