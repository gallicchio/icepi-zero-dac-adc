#!/usr/bin/env python3
"""Sounding the channel: its impulse response and its frequency response, three ways.

    python3 sound.py                    # one board looped back (finds its port)
    python3 sound.py PORT_A PORT_B      # board A plays, board B records
    python3 sound.py --sim              # no board: channel.py's model
    python3 sound.py --sim --stub 25    # ... with a 25 m open stub on a T (echo.py)
    python3 sound.py --records 4        # average 4 records per probe (the default)
    python3 sound.py -o sound.npz --no-plot

The board runs awgcap.sv (5.01).  The cable, the converters and the T with its stub are
one linear, time-invariant system: whatever goes in comes out convolved with its impulse
response h[n], or, the same thing, with each frequency multiplied by H(f).  Three probes,
each one loop long, measure it:

  mseq       1.07's m-sequence (GPS's G1, 1023 chips), one chip per ADC sample, played
             8 times with 8 chips of padding to fill the loop.  Cross-correlating the
             record with the sequence gives h[n] directly, because the sequence's
             autocorrelation is a delta (1.07).  25 Mchip/s: h at 40 ns resolution.
  step       a square wave, 8 periods per loop: h[n] is the difference between
             successive samples of the (averaged) step response.
  multitone  every bin of the loop from 3 kHz to 12.3 MHz at the same amplitude with
             random phases (6.04's sounding).  The loop repeats, so its spectrum sits
             exactly on the FFT's bins, and H(f) = Y(f) / X(f): one divide per bin.
             Its inverse FFT is h[n] again.
  psk        psk.py's QPSK frame itself, the same divide, but only where the signal has
             power, 5.2-7.3 MHz.  Any transmission a receiver knows can sound the channel:
             6.07's OFDM does it with one known symbol, every frame.

One system, so all the answers should agree.  (Through the long cable they almost do:
1.07 found it slightly non-linear, 0.74 against 0.79 at the main tap.)

h[n] is in ADC codes per DAC code: about 0.74 at a delay of 6 samples (240 ns) through
1 m of cable, 1.07's number, and nearly nothing elsewhere.  |H(f)| is the same gain
against frequency; its phase slopes down at 2 pi f x 240 ns; the group delay,
-dphase/d(2 pi f), is that 240 ns, flat, until something (a stub) makes it wobble.
"""
import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import channel                                      # noqa: E402
import echo                                         # noqa: E402
import psk                                          # noqa: E402
from psk import g1, find_port                      # noqa: E402

N, L = 16384, 8192                  # DAC samples per loop; ADC samples per loop
FS_DAC, FS_ADC = 50e6, 25e6
HI, LO = 224, 32                    # the m-sequence's and the step's two levels (1.07)
MSEQ = 1023
PROBES = ("mseq", "step", "multitone", "psk")


# ---- the probes: each returns (the DAC waveform, what the ADC should see at 25 MS/s) ----
def probe_mseq():
    chips = 2 * g1(MSEQ) - 1                                  # +1 for a 1, as loopback.sv
    x = np.zeros(L)
    x[:8 * MSEQ] = np.tile(chips, 8)                          # 8 periods, then 8 chips of 0
    return 128 + (HI - LO) / 2 * np.repeat(x, 2), (HI - LO) / 2 * x


def probe_step():
    x = np.where((np.arange(L) // 512) % 2 == 1, HI, LO).astype(float)
    return np.repeat(x, 2), x - (HI + LO) / 2


def probe_multitone(rms=28.0, seed=11):
    rng = np.random.default_rng(seed)
    X = np.zeros(L // 2 + 1, complex)
    band = np.arange(1, L // 2 - 40)                          # 3 kHz to 12.3 MHz
    X[band] = np.exp(2j * np.pi * rng.random(len(band)))
    x = np.fft.irfft(X, L)
    x *= rms / x.std()
    X2 = np.zeros(L + 1, complex)
    X2[:L // 2 + 1] = np.fft.rfft(x)                          # to 50 MS/s: pad the spectrum
    return np.clip(np.round(128 + 2 * np.fft.irfft(X2, N)), 0, 255), x


def probe_psk():
    q, _ = psk.make_frame(4)
    wave = psk.transmit(q, 4)
    return wave, wave[::2] - 128                              # band-limited: every 2nd sample is exact


# ---- the three methods --------------------------------------------------------------
def by_mseq(rec):
    """h[n] by cross-correlation, averaged over the 14 clean periods of the two loops
    (the period right after the padding is skipped)."""
    chips = 2 * g1(MSEQ) - 1
    periods = [rec[lp + k * MSEQ:lp + (k + 1) * MSEQ] for lp in (0, L) for k in range(1, 8)]
    y = np.mean(periods, axis=0)
    # ##########################################################################
    # ##  KEY LINE: cross-correlate what came back with what was sent (1.07).
    # ##  The m-sequence's autocorrelation is a delta, so this IS h[n].
    # ##########################################################################
    r = np.real(np.fft.ifft(np.fft.fft(y - y.mean()) * np.conj(np.fft.fft(chips)))) / (MSEQ + 1)
    return r / ((HI - LO) / 2)                                # ADC codes per DAC code


def by_step(rec, n=64):
    """h[n] from the 16 rising edges (at ADC samples 512, 1536, ...), averaged."""
    edges = 512 + 1024 * np.arange(16)
    s = np.mean([rec[e - 8:e + n] for e in edges], axis=0)
    h = np.diff(s) / (HI - LO)
    return h[7:]                                               # h[0] is the sample of the step


def by_divide(rec, x):
    """H(f) = Y(f) / X(f) on the loop's bins, from the two loops averaged, where the probe
    has power; NaN elsewhere.  Also h[n] = its inverse FFT (multitone only)."""
    y = rec.reshape(2, L).mean(axis=0)
    X = np.fft.rfft(x)
    Y = np.fft.rfft(y - y.mean())
    ok = np.abs(X) > 0.05 * np.abs(X).max()
    H = np.full(len(X), np.nan, complex)
    # ##########################################################################
    # ##  KEY LINE: one complex divide per frequency bin.  (The loop repeats,
    # ##  so the convolution is circular and the FFT turns it into a product.)
    # ##########################################################################
    H[ok] = Y[ok] / X[ok]
    return H


def group_delay(f, H, smooth=64):
    """-d(phase)/d(2 pi f), in seconds, from the unwrapped phase, smoothed over `smooth`
    bins (NaN where H is unknown, and within smooth/2 bins of there)."""
    ok = np.isfinite(H)
    ph = np.unwrap(np.angle(H[ok]))
    gd = -np.gradient(ph, f[ok]) / (2 * np.pi)
    gd = np.convolve(gd, np.ones(smooth) / smooth, mode="valid")
    out = np.full(len(f), np.nan)
    out[np.flatnonzero(ok)[smooth // 2:smooth // 2 + len(gd)]] = gd
    return out


def delay_in_band(f, H, lo=5.3e6, hi=7.2e6):
    """The mean group delay between lo and hi: a straight line fitted to the phase."""
    sel = np.isfinite(H) & (f > lo) & (f < hi)
    return -np.polyfit(f[sel], np.unwrap(np.angle(H[sel])), 1)[0] / (2 * np.pi)


def sound(play, record, probes=PROBES, records=4, align=False):
    """Play each probe, record it `records` times, and measure.  Returns a dict:
    h_mseq, h_step (impulse responses, ADC codes per DAC code, one per 40 ns sample),
    f and H_mseq, H_multitone, H_psk (frequency responses on the loop's bins)."""
    out = {"f": np.fft.rfftfreq(L, 1 / FS_ADC)}
    for name in probes:
        wave, x = globals()["probe_" + name]()
        play(wave)
        rec = np.mean([record() for _ in range(records)], axis=0).astype(float)
        if align:                                                # two boards: find the loop's start
            c = np.fft.irfft(np.fft.rfft(rec[:L] - rec.mean()) * np.conj(np.fft.rfft(x)), L)
            rec = np.roll(rec, -int(np.argmax(c)))
        out["rec_" + name] = rec
        if name == "mseq":
            out["h_mseq"] = by_mseq(rec)
            out["H_mseq"] = np.fft.rfft(out["h_mseq"], L)         # h[n] -> H(f), 1.07's caution applies
        elif name == "step":
            out["h_step"] = by_step(rec)
        else:
            out["H_" + name] = by_divide(rec, x)
            if name == "multitone":
                out["h_multitone"] = np.fft.irfft(np.nan_to_num(out["H_multitone"]), L)
    return out


def summary(out):
    f = out["f"]
    lines = []
    for name in ("mseq", "step", "multitone"):
        if "h_" + name in out:
            h = out["h_" + name]
            lines.append("h[n] by %-9s delay %2d samples, main tap %.3f; h[0..11] = %s"
                         % (name + ":", np.argmax(h[:64]), h[:64].max(), np.round(h[:12], 3)))
    for name in ("mseq", "multitone", "psk"):
        if "H_" + name in out:
            H = out["H_" + name]
            gains = []
            for fm in (1e6, 6.25e6, 11e6):
                near = np.abs(H[np.abs(f - fm) < 50e3])
                gains.append("%.3f" % np.nanmean(near) if np.isfinite(near).any() else "  -  ")
            lines.append("H(f) by %-9s |H| %s at 1 MHz, %s at 6.25 MHz, %s at 11 MHz; delay %.0f ns across 5.3-7.2 MHz"
                         % (name + ":", *gains, delay_in_band(f, H) * 1e9))
    return "\n".join(lines)


def make_link(args):
    """play(wave) and record() for the board(s) or the model, with the simulated stub
    (--stub) added to every record."""
    if args.sim:
        rng = np.random.default_rng(args.seed)
        st = {}
        def play(wave):
            st["wave"] = wave
        def record():
            return channel.channel(st["wave"], rng=rng)
    else:
        sys.path.insert(0, os.path.join(HERE, "..", "twoboard"))
        import awgcap
        ports = args.ports or [find_port()]
        play = lambda wave: awgcap.upload(ports[0], wave)
        record = lambda: awgcap.record(ports[-1])
    if args.stub:
        rec0 = record
        record = lambda: echo.add_stub(rec0(), args.stub, vf=args.vf, loss=args.loss)
    return play, record


def plot(out, title):
    import matplotlib.pyplot as plt
    f = out["f"] / 1e6
    fig, ax = plt.subplots(2, 2, figsize=(12, 7))
    n = np.arange(40)
    for name, m in (("mseq", "o"), ("step", "s"), ("multitone", "^")):
        if "h_" + name in out:
            ax[0, 0].plot(n, out["h_" + name][:40], m + "-", ms=4, lw=0.8, label=name)
    ax[0, 0].set_xlabel("delay (ADC samples of 40 ns)"); ax[0, 0].set_ylabel("h (ADC codes per DAC code)")
    ax[0, 0].set_title("impulse response"); ax[0, 0].legend(); ax[0, 0].grid(True)
    for name in ("mseq", "multitone", "psk"):
        if "H_" + name in out:
            H = out["H_" + name]
            ax[0, 1].plot(f, np.abs(H), lw=0.7, label=name)
            ax[1, 0].plot(f, np.degrees(np.unwrap(np.angle(np.nan_to_num(H, nan=1)))), lw=0.7, label=name)
            ax[1, 1].plot(f, group_delay(out["f"], H) * 1e9, lw=0.7, label=name)
    ax[0, 1].set_ylabel("|H| (ADC codes per DAC code)"); ax[0, 1].set_title("gain")
    ax[1, 0].set_ylabel("phase (degrees, unwrapped)"); ax[1, 0].set_title("phase")
    ax[1, 1].set_ylabel("group delay (ns)"); ax[1, 1].set_title("group delay"); ax[1, 1].set_ylim(0, 600)
    for a in (ax[0, 1], ax[1, 0], ax[1, 1]):
        a.set_xlabel("frequency (MHz)"); a.set_xlim(0, 12.5); a.grid(True); a.legend()
    fig.suptitle(title); fig.tight_layout(); plt.show()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ports", nargs="*", help="one port: looped back; two: A plays, B records")
    ap.add_argument("--sim", action="store_true", help="use channel.py's model, not a board")
    ap.add_argument("--stub", type=float, default=0.0, help="add a simulated open stub of this many metres (echo.py)")
    ap.add_argument("--vf", type=float, default=echo.VF, help="--stub: the stub's velocity factor")
    ap.add_argument("--loss", type=float, default=echo.LOSS, help="--stub: the stub's loss, dB/m at 10 MHz")
    ap.add_argument("--probe", choices=PROBES, help="just one probe (default: all four)")
    ap.add_argument("--records", type=int, default=4, help="records averaged per probe")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("-o", "--out", help="save the results (.npz)")
    ap.add_argument("--no-plot", action="store_true")
    args = ap.parse_args()
    play, record = make_link(args)
    out = sound(play, record, (args.probe,) if args.probe else PROBES, args.records,
                align=len(args.ports) == 2)
    print(summary(out))
    if args.out:
        np.savez(args.out, **out)
    if not args.no_plot:
        plot(out, "channel sounding, %s%s" % ("simulated" if args.sim else "measured",
                                              ", %g m stub" % args.stub if args.stub else ""))
