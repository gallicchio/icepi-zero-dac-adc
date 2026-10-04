"""Shared by the Chapter 7 DSP figure scripts (fig_*.py here): where the data and images
go, and how to reach the board, the scope, or the model.

Each figure script takes the same arguments:

    python3 fig_sigma_delta.py --sim          # channel.py's model: save, plot
    python3 fig_sigma_delta.py PORT           # one board looped back (awgcap.bit loaded)
    python3 fig_sigma_delta.py --m2k PORT     # the board plays, an ADALM2000 scope records the DAC pin
    python3 fig_sigma_delta.py --replot       # redraw from dev/data/dsp_*.npz

and writes dev/data/dsp_<name>.npz and tutorial/img/dsp_<name>.png.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.join(HERE, "..", "..", "..")
sys.path.insert(0, os.path.join(HERE, ".."))                 # plotstyle, m2k
sys.path.insert(0, os.path.join(TOP, "src", "dsp"))           # sigma_delta, oversample_adc
sys.path.insert(0, os.path.join(TOP, "src", "comms"))         # channel
sys.path.insert(0, os.path.join(TOP, "src", "twoboard"))      # awgcap


def data_path(name):
    return os.path.join(TOP, "dev", "data", "dsp_%s.npz" % name)


def img_path(name):
    return os.path.join(TOP, "tutorial", "img", "dsp_%s.png" % name)


def args(doc, extra=None, computed=False):
    ap = argparse.ArgumentParser(description=doc, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("port", nargs="?", help="the board's serial port")
    ap.add_argument("--sim", action="store_true", help="channel.py's model instead of a board")
    ap.add_argument("--m2k", action="store_true", help="record the DAC pin with an ADALM2000 scope")
    ap.add_argument("--m2k-samples", type=int, default=2**19)
    ap.add_argument("--replot", action="store_true", help="redraw from the saved data")
    ap.add_argument("--seed", type=int, default=1)
    if extra:
        extra(ap)
    a = ap.parse_args()
    if not (computed or a.sim or a.replot or a.port):
        ap.error("give the board's port, or --sim, or --replot")
    return a
