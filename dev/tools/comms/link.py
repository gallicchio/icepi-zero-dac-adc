"""Shared by the Chapter 6 figure scripts (fig_*.py here): where the data and images go,
and how to reach the board(s) or the model.

Each figure script takes the same arguments:

    python3 fig_psk.py --sim              # run on channel.py's model, save, plot
    python3 fig_psk.py PORT               # one board looped back (awgcap.bit loaded)
    python3 fig_psk.py PORT_A PORT_B      # board A plays, board B records
    python3 fig_psk.py --replot           # redraw from dev/data/comms_*.npz

and writes dev/data/comms_<name>.npz and tutorial/img/comms_<name>.png.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.join(HERE, "..", "..", "..")
sys.path.insert(0, os.path.join(HERE, ".."))                 # plotstyle
sys.path.insert(0, os.path.join(TOP, "src", "comms"))         # channel, psk, eye, cdma
sys.path.insert(0, os.path.join(TOP, "src", "twoboard"))      # awgcap

import numpy as np                                            # noqa: E402
import channel                                                # noqa: E402


def data_path(name):
    return os.path.join(TOP, "dev", "data", "comms_%s.npz" % name)


def img_path(name):
    return os.path.join(TOP, "tutorial", "img", "comms_%s.png" % name)


def args(doc, extra=None):
    ap = argparse.ArgumentParser(description=doc, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ports", nargs="*", help="one port: looped back; two: A plays, B records")
    ap.add_argument("--sim", action="store_true", help="channel.py's model instead of a board")
    ap.add_argument("--replot", action="store_true", help="redraw from the saved data")
    if extra:
        extra(ap)
    a = ap.parse_args()
    if not (a.sim or a.replot or a.ports):
        ap.error("give the board's port(s), or --sim, or --replot")
    return a


class Link:
    """play(wave) then record(), on the board(s) or on the model.  `source` says which,
    for the figure's caption."""

    def __init__(self, a, seed=1, **sim):
        self.sim = a.sim
        if a.sim:
            self.rng = np.random.default_rng(seed)
            self.kw = sim
            self.source = "simulated (channel.py)"
        else:
            import awgcap
            self.awgcap = awgcap
            self.tx, self.rx = a.ports[0], a.ports[-1]
            self.source = "measured, one board looped back" if len(a.ports) == 1 else \
                          "measured, board A to board B"

    def play(self, wave):
        if self.sim:
            self.wave = wave
        else:
            self.awgcap.upload(self.tx, wave)

    def record(self):
        if self.sim:
            return channel.channel(self.wave, rng=self.rng, **self.kw)
        return self.awgcap.record(self.rx)
