#!/usr/bin/env python3
"""When the carrier is too far off for the Costas loop: find it coarsely first.

    python3 fll.py --cfo 100000             # one board looped back, its carrier 100 kHz high
    python3 fll.py --sim --cfo 100000       # no board: the channel model of channel.py
    python3 fll.py --sim --cfo 24000 --ebn0 6
    python3 fll.py --sim --pullin           # the Costas loop alone, --cfo stepped up: where it gives up
    python3 fll.py --bpsk ...               # BPSK: square instead of raising to the 4th power
    python3 fll.py --tau 1000               # the FLL's time constant, symbols (default 100)
    python3 fll.py -o fll.npz --no-plot

psk.py's Costas loop learns the carrier's frequency as well as its phase, but only if it
starts close enough: its PULL-IN range.  With the default loop (noise bandwidth 2% of
the symbol rate, 31 kHz) that is about 27 kHz on a clean signal and 12 kHz at
Eb/N0 = 6 dB (--pullin measures it, in --sim).  Real links start further off than that:
two crystals 20 ppm apart put a 915 MHz carrier 18 kHz off, and a cheap synthesizer can
miss by 100 kHz.  So a receiver first finds the frequency coarsely, knowing neither the
symbols nor their timing, in one of two classic ways:

  x^4   raise the matched-filter output to the 4th power.  QPSK's four phases 45, 135,
        225, 315 deg become 180, 540, 900, 1260 = all the same: the data vanish, and
        a spectral LINE is left at 4 x the offset.  One FFT finds it.  (BPSK: square,
        the line is at 2 x.)  Open loop: one estimate from one record.
  band edge   two narrow filters at the signal's two edges, where its spectrum rolls
        off.  A signal that sits too high puts more power through the upper filter
        than the lower; the difference is a frequency error, and a loop drives it to
        zero (fred harris; GNU Radio's fll_band_edge; learnSDR lesson 17).  Closed
        loop: it keeps following.

Either gives the offset to a few hundred hertz.  The record is then shifted by that
much, as a mixer with a corrected local oscillator would do, and handed to psk.py's
receiver, whose Costas loop takes it from there.

The FLL here is a first-order loop on frequency, w += k e: the frequency estimate
w moves towards the truth with a time constant of `tau` symbols.  GNU Radio's wraps
the same detector in its generic second-order loop with "loop bandwidth" theta per
sample, whose frequency gain is 4 theta^2, so its time constant is 1 / (4 theta^2)
samples: lesson 17's 2 pi / sps / 100 is 1000 symbols; the /1000 in its flowgraph
is 100 times longer.
"""
import argparse
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import psk                                                  # noqa: E402
from psk import N, FS_ADC, F_LOOP, F_C, NSYM, ALPHA, SPAN, make_link    # noqa: E402

SPS = 16                        # ADC samples per symbol
R = NSYM * F_LOOP               # symbol rate, 1.5625 Msymbol/s


# ---- the record, in frequency ------------------------------------------------------
def mixdown(rec):
    """The lock-in's first step, as psk.matched: multiply by e^(-jwt) at 6.25 MHz."""
    r = rec - np.mean(rec)
    return 2 * r * np.exp(-2j * np.pi * F_C * np.arange(len(r)) / FS_ADC)


def shift(rec, df):
    """The real record moved up by df Hz, as a mixer with a corrected local oscillator
    would: through its analytic signal (positive frequencies only)."""
    r = np.asarray(rec, float)
    X = np.fft.fft(r - r.mean())
    n = len(r)
    X[n // 2 + 1:] = 0; X[1:n // 2] *= 2                   # keep f > 0, double it
    xa = np.fft.ifft(X)
    return np.real(xa * np.exp(2j * np.pi * df * np.arange(n) / FS_ADC)) + r.mean()


# ---- 1. the x^4 line ----------------------------------------------------------------
def fourth_power(rec, M):
    """Raise the matched-filter output to the Mth power (M = 2 or 4), FFT, find the
    line.  Returns the carrier offset in Hz, and the spectrum (f in Hz, |Y| in dB)."""
    y = psk.matched(rec)
    n = len(y)
    # ##########################################################################
    # ##  KEY LINE: y^4.  Each symbol's phase (45 + 90 q) deg becomes 180 + 360 q:
    # ##  the data are gone, and what is left spins at 4 x the carrier offset.
    # ##########################################################################
    Y = np.abs(np.fft.fft(y**M * np.hanning(n)))
    f = np.fft.fftfreq(n, 1 / FS_ADC)
    inband = np.abs(f) < FS_ADC / (2 * M)                   # 4 x offset must not alias
    i = int(np.argmax(np.where(inband, Y, 0)))
    # the line's centre to a fraction of a bin: a parabola through the peak's log
    a, b, c = np.log(Y[i - 1]), np.log(Y[i]), np.log(Y[i + 1])
    frac = 0.5 * (a - c) / (a - 2 * b + c)
    f_line = (f[i] + frac * FS_ADC / n)
    db = 20 * np.log10(Y / Y[i])
    return f_line / M, np.fft.fftshift(f), np.fft.fftshift(db)


# ---- 2. the band-edge FLL -----------------------------------------------------------
def band_edge_filters(sps=SPS, ntaps=2 * SPAN * SPS + 1):
    """Two filters, each a half-cosine bump as wide as the pulse's roll-off region
    (alpha x the symbol rate), centred on the band edges +R/2 and -R/2: the slope of
    the signal's own spectrum.  Returns (upper taps, lower taps)."""
    m = np.arange(ntaps) - (ntaps - 1) / 2                  # samples from the centre
    # ##########################################################################
    # ##  KEY LINE: two sincs half a cycle apart add up to a half-cosine bump
    # ##  in frequency, alpha R wide; spinning it by e^(+-j 2 pi (R/2) t) puts
    # ##  one copy on each band edge.
    # ##########################################################################
    bump = np.sinc(ALPHA * m / sps + 0.5) + np.sinc(ALPHA * m / sps - 0.5)
    hu = bump * np.exp(2j * np.pi * m / (2 * sps)) * np.hanning(ntaps + 2)[1:-1]
    hu = hu / np.sqrt(np.sum(np.abs(hu)**2))
    return hu, np.conj(hu)


def rc_spectrum(f, sps=SPS, alpha=ALPHA):
    """The signal's power spectrum before the matched filter: a raised cosine in f
    (cycles per sample), 1 in the middle, rolling off over (1 +- alpha) R / 2."""
    nu = np.abs(f) * sps                                    # in units of the symbol rate
    S = np.where(nu < (1 - alpha) / 2, 1.0,
                 0.5 * (1 + np.cos(np.pi * (nu - (1 - alpha) / 2) / alpha)))
    return np.where(nu > (1 + alpha) / 2, 0.0, S)


def s_curve(hu, hl, offsets_hz, sps=SPS, nfft=8192):
    """What the detector should say for a signal `offset` Hz too high: the power the
    upper filter passes minus the lower's, over their sum."""
    f = np.fft.fftfreq(nfft)
    Hu2 = np.abs(np.fft.fft(hu, nfft))**2
    Hl2 = np.abs(np.fft.fft(hl, nfft))**2
    out = []
    for d in np.atleast_1d(offsets_hz):
        S = rc_spectrum(f - d / FS_ADC, sps)
        pu, pl = np.sum(S * Hu2), np.sum(S * Hl2)
        out.append((pu - pl) / (pu + pl + 1e-12))
    return np.array(out)


def band_edge_error(z, hu, hl):
    """The detector, open loop, over a whole record: one number."""
    pu = np.sum(np.abs(np.convolve(z, hu, "valid"))**2)
    pl = np.sum(np.abs(np.convolve(z, hl, "valid"))**2)
    return (pu - pl) / (pu + pl)


def fll(z, tau=100, sps=SPS, ntaps=2 * SPAN * SPS + 1):
    """The frequency-locked loop, sample by sample on the mixed-down signal z.
    Returns the frequency it believes (rad per sample) at every sample, the error
    signal, and its final estimate of the offset in Hz."""
    hu, hl = band_edge_filters(sps, ntaps)
    kd = float(np.diff(s_curve(hu, hl, [-100.0, 100.0], sps))) / (2 * 100.0 * 2 * np.pi / FS_ADC)
    k = 1 / (kd * tau * sps)                                # KEY: one time constant = tau symbols
    P = np.mean(np.abs(np.convolve(z, hu, "valid"))**2 + np.abs(np.convolve(z, hl, "valid"))**2)
    hu_r, hl_r = hu[::-1], hl[::-1]                         # convolution = dot with reversed taps
    v = np.zeros(len(z) + ntaps - 1, complex)               # the derotated signal, with history
    phi = w = 0.0
    ws, es = np.empty(len(z)), np.empty(len(z))
    for n in range(len(z)):
        v[n + ntaps - 1] = z[n] * np.exp(-1j * phi)         # turn back by what we believe so far
        win = v[n:n + ntaps]
        u, l = hu_r @ win, hl_r @ win                       # the two band-edge filters
        # ######################################################################
        # ##  KEY LINE: the frequency error.  Too high, and the upper band edge
        # ##  carries more power than the lower one.  No symbols, no timing.
        # ######################################################################
        e = (abs(u)**2 - abs(l)**2) / P
        # ######################################################################
        # ##  KEY LINE: a first-order loop on FREQUENCY.  w is radians per
        # ##  sample; it creeps towards the offset with time constant tau.
        # ######################################################################
        w += k * e
        phi += w
        ws[n], es[n] = w, e
    # The data make the band edges' power flicker, so w jitters by several kHz even
    # once it has settled (its "self-noise", as Gardner's detector has): the estimate
    # is w averaged over the second half of the record.
    return dict(w=ws, e=es, df=float(np.mean(ws[len(z) // 2:])) * FS_ADC / (2 * np.pi), kd=kd, taps=(hu, hl))


# ---- running it -----------------------------------------------------------------------
def found_by_costas(r):
    """The carrier offset psk.py's Costas loop ended up believing, Hz."""
    return float(np.mean(r["w"][-200:]) * R / (2 * np.pi))


def one_record(args, M, play, record, cfo_bins, ebn0=None, rng=None):
    """Play one frame `cfo_bins` steps of 3052 Hz high; receive it three ways: the
    Costas loop alone, after the x^4 estimate, after the FLL."""
    q, data = psk.make_frame(M)
    play(psk.transmit(q, M, cfo_bins, ebn0=ebn0, rng=rng))
    rec = record()
    out = dict(rec=rec, q=q, cfo=cfo_bins * F_LOOP)
    r = psk.receive(rec, M, NSYM, q, bnt_carrier=args.bnt_carrier)
    out["costas"] = dict(errs=r["errs"], nbits=r["nbits"], mer=r["mer"], found=found_by_costas(r), z=r["zc"][400:])
    df4, f4, spec4 = fourth_power(rec, M)
    r = psk.receive(shift(rec, -df4), M, NSYM, q, bnt_carrier=args.bnt_carrier)
    out["x4"] = dict(df=df4, f=f4, spec=spec4, errs=r["errs"], nbits=r["nbits"], mer=r["mer"],
                     found=df4 + found_by_costas(r), z=r["zc"][400:] * np.exp(-2j * np.pi * r["rot"][-1] / M))
    loop = fll(mixdown(rec), tau=args.tau)
    r = psk.receive(shift(rec, -loop["df"]), M, NSYM, q, bnt_carrier=args.bnt_carrier)
    out["fll"] = dict(df=loop["df"], w=loop["w"], e=loop["e"], kd=loop["kd"], errs=r["errs"], nbits=r["nbits"],
                      mer=r["mer"], found=loop["df"] + found_by_costas(r),
                      z=r["zc"][400:] * np.exp(-2j * np.pi * r["rot"][-1] / M))
    return out


def plot(o, M, title):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 3, figsize=(13, 7.5))
    a = ax[0, 0]
    a.plot(o["x4"]["f"] / 1e6, o["x4"]["spec"], lw=0.5)
    a.axvline(M * o["cfo"] / 1e6, color="C1", ls="--", lw=1, label="%d x %.1f kHz" % (M, o["cfo"] / 1e3))
    a.set_xlim(-FS_ADC / 2e6, FS_ADC / 2e6); a.set_ylim(-60, 5)
    a.set_xlabel("frequency (MHz)"); a.set_ylabel("|FFT(y^%d)| (dB re the line)" % M)
    a.set_title("the x^%d line: offset found %.0f Hz" % (M, o["x4"]["df"])); a.legend(); a.grid(True)
    a = ax[0, 1]
    us = np.arange(N) / FS_ADC * 1e6
    a.plot(us, o["fll"]["w"] * FS_ADC / (2 * np.pi) / 1e3, lw=1)
    a.axhline(o["cfo"] / 1e3, color="C1", ls="--", lw=1, label="sent: %.1f kHz" % (o["cfo"] / 1e3))
    a.set_xlabel("time (us)"); a.set_ylabel("the FLL's frequency (kHz)")
    a.set_title("band-edge FLL: offset found %.0f Hz" % o["fll"]["df"]); a.legend(); a.grid(True)
    a = ax[0, 2]
    a.plot(us, o["fll"]["e"], ".", markersize=1)
    a.set_xlabel("time (us)"); a.set_ylabel("band-edge error")
    a.set_title("the FLL's detector, every sample"); a.grid(True)
    for a, key, lab in ((ax[1, 0], "costas", "Costas loop alone"), (ax[1, 1], "x4", "after x^%d" % M),
                        (ax[1, 2], "fll", "after the FLL")):
        z = o[key]["z"]
        a.plot(z.real, z.imag, ".", markersize=2)
        a.set_aspect("equal"); a.set_xlim(-1.8, 1.8); a.set_ylim(-1.8, 1.8)
        a.set_xlabel("I"); a.set_ylabel("Q"); a.grid(True)
        a.set_title("%s: %d errors in %d bits" % (lab, o[key]["errs"], o[key]["nbits"]))
    fig.suptitle(title); fig.tight_layout(); plt.show()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ports", nargs="*", help="one port: looped back; two: A plays, B records")
    ap.add_argument("--sim", action="store_true", help="use channel.py's model, not a board")
    ap.add_argument("--ppm", type=float, default=0.0, help="--sim: pretend to be two boards, A this many ppm fast")
    ap.add_argument("--bpsk", action="store_true", help="BPSK (default QPSK)")
    ap.add_argument("--cfo", type=float, default=100e3, help="transmitter's carrier offset, Hz (3051.76 Hz steps)")
    ap.add_argument("--ebn0", type=float, help="add noise at the transmitter: Eb/N0 in dB")
    ap.add_argument("--pullin", action="store_true", help="step --cfo up to 120 kHz: the Costas loop alone")
    ap.add_argument("--tau", type=float, default=100, help="the FLL's time constant, symbols")
    ap.add_argument("--bnt-carrier", type=float, default=0.02, help="Costas loop bandwidth x symbol time")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("-o", "--out", help="save the results (.npz)")
    ap.add_argument("--no-plot", action="store_true")
    args = ap.parse_args()
    M = 2 if args.bpsk else 4
    play, record = make_link(args)
    args.sro = 0; args.diff = False; args.bnt_timing = 0.01; args.skip = 400     # for psk.run_once

    if args.pullin:
        print("%s, Costas loop alone (bandwidth %.3f x symbol rate), Eb/N0 %s:" % ("BPSK" if M == 2 else "QPSK",
              args.bnt_carrier, "none" if args.ebn0 is None else "%.0f dB" % args.ebn0))
        print("  carrier offset (Hz)  found (Hz)  bit errors / bits  MER (dB)")
        rows = []
        for bins in list(range(0, 12)) + [14, 16, 20, 24, 28, 33, 40]:
            args.cfo = bins * F_LOOP
            r = psk.run_once(args, M, play, record, ebn0=args.ebn0, rng=args.seed)
            rows.append((r["cfo"], found_by_costas(r), r["errs"], r["nbits"], r["mer"]))
            print("  %8.0f  %18.0f  %6d / %4d  %8.1f" % rows[-1], flush=True)
        if args.out:
            np.savez(args.out, rows=np.array(rows), M=M)
    else:
        cfo_bins = int(round(args.cfo / F_LOOP))
        o = one_record(args, M, play, record, cfo_bins, ebn0=args.ebn0, rng=args.seed)
        print("%s, transmitter's carrier %+.0f Hz%s" % ("BPSK" if M == 2 else "QPSK", o["cfo"],
              "" if args.ebn0 is None else ", Eb/N0 %.0f dB" % args.ebn0))
        print("  receiver                      offset found (Hz)  bit errors / bits  MER (dB)")
        for key, lab in (("costas", "Costas loop alone"), ("x4", "x^%d line, then Costas" % M),
                         ("fll", "band-edge FLL, then Costas")):
            x = o[key]
            print("  %-28s  %17.0f  %6d / %4d  %8.1f" % (lab, x["found"], x["errs"], x["nbits"], x["mer"]))
        print("  (x^%d alone said %+.0f Hz; the FLL alone %+.0f Hz, with a time constant of %.0f symbols)"
              % (M, o["x4"]["df"], o["fll"]["df"], args.tau))
        if args.out:
            np.savez(args.out, rec=o["rec"], cfo=o["cfo"], M=M, x4_df=o["x4"]["df"], fll_df=o["fll"]["df"],
                     fll_w=o["fll"]["w"], fll_e=o["fll"]["e"], x4_f=o["x4"]["f"], x4_spec=o["x4"]["spec"],
                     **{"%s_%s" % (k, s): o[k][s] for k in ("costas", "x4", "fll") for s in ("errs", "nbits", "mer", "found", "z")})
        if not args.no_plot:
            plot(o, M, "%s, carrier %+.0f Hz, %s" % ("BPSK" if M == 2 else "QPSK", o["cfo"],
                                                    "simulated" if args.sim else " ".join(args.ports) or "one board"))
