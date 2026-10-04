"""Instructor's run for modem_sync.v: for each NOISE (AMP 25), the SNR per sample and the
216-sample decisions from recorded samples (mm_NOISE_25_7.bit from fsk_build.sh), then the
link through the PC's UART (ms_NOISE.bit).  Results: data/tb_fsk_sync.npz.

    python3 fsk_sync_run.py MM_DIR MS_DIR

MS_DIR/ms_NOISE.bit is modem_sync.v built with that NOISE, from this folder:
    yosys -p "chparam -set NOISE 87 modem_sync; synth_ecp5 -top modem_sync -json ms_87.json" modem_sync.v
    nextpnr-ecp5 --25k --package CABGA256 --speed 6 --json ms_87.json --lpf ../../../src/verilog/icepi_adda.lpf --textcfg ms_87.config
    ecppack --compress ms_87.config ms_87.bit
"""
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import boards
from fsk_sync_ber import link

WM, WS = 2 * np.pi / 4, 2 * np.pi / 8


def analyse(records, win):
    n = np.arange(records.shape[1])
    M = np.column_stack([np.cos(WM * n), np.sin(WM * n), np.ones(len(n))])
    snrs, errs, tot = [], 0, 0
    for codes in records.astype(float):
        co = np.linalg.lstsq(M, codes, rcond=None)[0]
        res = codes - M @ co
        snrs.append(np.hypot(co[0], co[1]) ** 2 / 2 / res.var())
        x = codes - 128
        c1 = np.cumsum(np.concatenate([[0], x * np.exp(-1j * WM * n)]))
        c2 = np.cumsum(np.concatenate([[0], x * np.exp(-1j * WS * n)]))
        em, es = np.abs(c1[win:] - c1[:-win]) ** 2, np.abs(c2[win:] - c2[:-win]) ** 2
        errs += np.sum(es > em)
        tot += len(em)
    return np.mean(snrs), errs, tot


mm, ms = sys.argv[1], sys.argv[2]
rows = []
for m in (55, 61, 69, 77, 87, 97, 109, 122):
    boards.load("JLC3", "%s/mm_%d_25_7.bit" % (mm, m))
    time.sleep(0.3)
    rec = np.array([boards.capture("JLC3")[1] for _ in range(24)])
    snr, derr, dtot = analyse(rec, 216)
    boards.load("JLC3", "%s/ms_%d.bit" % (ms, m))
    time.sleep(0.5)
    bits, extra, nb, anchor = link()
    rows.append((m, snr, derr, dtot, bits, extra, nb))
    print("NOISE %3d: SNR/sample %5.1f dB; 216-sample decisions wrong %d of %d (%.2e), theory %.2e; "
          "link %d of %d (BER %.2e), bytes %+d, anchor %d" %
          (m, 10 * np.log10(snr), derr, dtot, derr / dtot, 0.5 * np.exp(-54 * snr), bits, nb, bits / nb, extra, anchor),
          flush=True)
np.savez(os.path.join(HERE, "..", "..", "data", "tb_fsk_sync.npz"),
         columns="noise snr_linear decisions_wrong decisions bit_errors bytes_extra bits", rows=np.array(rows))
