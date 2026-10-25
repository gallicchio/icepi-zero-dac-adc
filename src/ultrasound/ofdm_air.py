#!/usr/bin/env python3
"""4.06: OFDM through the air, with each subcarrier loaded to what it can carry.

    python3 ofdm_air.py --probe                  # QPSK everywhere: the SNR of each subcarrier
    python3 ofdm_air.py --loops 20               # probe, load the bits, send, count errors
    python3 ofdm_air.py --loops 20 --gap 12      # a more cautious loading (SNR gap, dB)

awgcap_slow.bit must be loaded (make load-awgcap_slow).  Its DAC plays a 16384-sample
loop at 195 kS/s (83.9 ms) and its ADC records the mean of each pair of DAC periods,
97.7 kS/s, from the start of a loop, so transmitter and receiver share one clock and
the record is already lined up: no timing or frequency recovery is needed.

The frame, in record samples (97,656.25 a second):
  each symbol  = a 1024-point FFT (10.49 ms; subcarriers 95.37 Hz apart)
               + a 256-sample cyclic prefix (2.62 ms), longer than the pair rings
  six symbols  = 7680 samples; the loop's last 512 samples are silent
  symbol 0     = known QPSK on every subcarrier: the first channel estimate
  symbols 1-5  = data
The DAC plays at twice the record rate, so the transmitter builds each symbol from a
2048-point inverse FFT (same subcarrier spacing) and a 512-sample prefix.  The
receiver's FFT window starts OFFSET samples into the prefix: late, because the sound
takes 0.36 ms to arrive and the pair rings for 2 ms more.

Bit loading: subcarrier k carries b_k bits (0, 1, 2, 4, 6, 8 or 10: none, BPSK, QPSK,
16-, 64-, 256-, 1024-QAM), the largest b with 2^b - 1 <= SNR_k / gap.  With gap = 0 dB
that would be Shannon's limit; real QAM needs about 8 to 10 dB more for few errors (6.08).
"""
import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awgcap_slow as awg                       # noqa: E402

NFFT, CP = 1024, 256                            # record samples
SYM = NFFT + CP
NSYM = 6
OFFSET = 240                                    # where the FFT window starts in the prefix
DF = awg.FS_ADC / NFFT                          # 95.37 Hz
T_SYM = SYM / awg.FS_ADC                        # 13.11 ms
BAND = (36000.0, 45000.0)                       # Hz: the subcarriers to probe
KS = np.arange(int(np.ceil(BAND[0] / DF)), int(BAND[1] / DF) + 1)
RMS = 32.0                                      # DAC codes rms; OFDM's peaks are ~4x that
MAX_BITS = 10                                   # 1024-QAM


# ---- QAM: Gray-coded square constellations, unit average power -----------------------
def qam_points(b):
    if b == 1:
        return np.array([-1, 1], complex)
    m = 2 ** (b // 2)
    gray = np.arange(m) ^ (np.arange(m) >> 1)
    axis = np.empty(m)
    axis[gray] = np.arange(m) * 2 - (m - 1)     # Gray code -> level
    pts = (axis[:, None] + 1j * axis[None, :]).ravel()   # index = (i_bits << b/2) | q_bits
    return pts / np.sqrt(np.mean(abs(pts) ** 2))


def bits_to_symbols(bits, b):
    """bits: (n, sum(b)) -> (n, len(b)) complex, b_k bits on subcarrier k."""
    out = np.zeros((len(bits), len(b)), complex)
    pos = 0
    for k, bk in enumerate(b):
        if bk:
            idx = bits[:, pos:pos + bk] @ (2 ** np.arange(bk)[::-1])
            out[:, k] = qam_points(bk)[idx]
            pos += bk
    return out


def symbols_to_bits(Z, b):
    """The nearest constellation point on each subcarrier, back to bits."""
    cols = []
    for k, bk in enumerate(b):
        if bk:
            idx = np.argmin(abs(Z[:, k, None] - qam_points(bk)[None, :]), axis=1)
            cols.append((idx[:, None] >> np.arange(bk)[::-1]) & 1)
    return np.hstack(cols)


def nearest(Z, b):
    """Each value moved to the nearest point of its subcarrier's constellation."""
    out = np.zeros_like(Z)
    for k, bk in enumerate(b):
        if bk:
            pts = qam_points(bk)
            out[..., k] = pts[np.argmin(abs(Z[..., k, None] - pts), axis=-1)]
    return out


# ---- the transmitter -------------------------------------------------------------------
def training(seed=7):
    rng = np.random.default_rng(seed)
    return np.exp(1j * np.pi / 2 * (rng.integers(0, 4, len(KS)) + 0.5))


def waveform(symbols):
    """symbols: (NSYM, len(KS)) complex values on subcarriers KS.  Returns the loop
    (16384 DAC samples), not yet scaled."""
    nd, cpd = 2 * NFFT, 2 * CP                  # the DAC's samples per symbol
    out = np.zeros(awg.N)
    for s, X in enumerate(symbols):
        spec = np.zeros(nd, complex)
        spec[KS] = X
        # ######################################################################
        # ##  KEY LINE: one OFDM symbol is an inverse FFT; a real signal needs
        # ##  only the positive frequencies, so take twice the real part.
        # ######################################################################
        x = 2 * np.real(np.fft.ifft(spec)) * nd
        out[s * (nd + cpd):(s + 1) * (nd + cpd)] = np.concatenate([x[-cpd:], x])
    return out


def scale(x, rms=RMS):
    """To DAC codes: rms codes rms about mid-scale, the rare peaks clipped."""
    on = x[:NSYM * 2 * SYM]
    return np.clip(128 + x * rms / np.sqrt(np.mean(on ** 2)), 0, 255)


def run_loop(ser, symbols, rms=RMS, settle=2):
    awg.upload(ser, scale(waveform(symbols), rms))
    time.sleep(settle * awg.LOOP)               # the old loop dies away, the new one rings up
    return awg.record(ser)


# ---- the receiver ----------------------------------------------------------------------
def demux(rec, offset=OFFSET):
    """The record's two loops as (2, NSYM, len(KS)) subcarrier values."""
    half = awg.N // 2
    out = np.zeros((2, NSYM, len(KS)), complex)
    for L in range(2):
        r = rec[L * half:(L + 1) * half] - np.mean(rec)
        for s in range(NSYM):
            a = s * SYM + offset
            # ##################################################################
            # ##  KEY LINE: one FFT per symbol, past the prefix's echoes: each
            # ##  subcarrier comes out multiplied by the channel, H(f), and
            # ##  nothing else.
            # ##################################################################
            out[L, s] = np.fft.fft(r[a:a + NFFT])[KS]
    return out


def receive(Y, known, b):
    """One loop's symbols Y (NSYM, K): equalize by the training symbol, decide, then
    re-estimate the channel from every symbol's decisions and decide again."""
    H = Y[0] / known
    X = nearest(Y[1:] / H, b)                   # first decisions
    used = b > 0
    sent_guess = np.vstack([known, X])
    H2 = H.copy()
    H2[used] = np.mean(Y[:, used] / sent_guess[:, used], axis=0)   # decision-directed
    return Y[1:] / H2, H2


def probe(ser, rng, rms=RMS, offset=OFFSET, loops=2):
    """QPSK on every subcarrier.  Returns the SNR of each, and the channel H."""
    errs, Hs = [], []
    for _ in range(loops):
        sent = np.exp(1j * np.pi / 2 * (rng.integers(0, 4, (NSYM, len(KS))) + 0.5))
        Y = demux(run_loop(ser, sent, rms), offset)
        for L in range(2):
            H = np.mean(Y[L] / sent, axis=0)    # the channel, from all six known symbols
            errs.append(np.mean(abs(Y[L] / H - sent) ** 2, axis=0))
            Hs.append(H)
    return 1.0 / np.mean(errs, axis=0), np.mean(Hs, axis=0)


def loading(snr, gap_db):
    b = np.floor(np.log2(1 + snr / 10 ** (gap_db / 10))).astype(int)
    b = np.minimum(b, MAX_BITS)
    b[(b % 2 == 1) & (b > 1)] -= 1              # square QAM only: 3 -> 2, 5 -> 4, ...
    return b


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port")
    ap.add_argument("--probe", action="store_true", help="QPSK on every subcarrier only")
    ap.add_argument("--loops", type=int, default=10, help="data loops to send")
    ap.add_argument("--gap", type=float, default=10.0, help="SNR gap for the loading, dB")
    ap.add_argument("--offset", type=int, default=OFFSET, help="FFT window start in the prefix")
    ap.add_argument("--rms", type=float, default=RMS, help="DAC codes rms (default %g)" % RMS)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("-o", "--out", help="save everything as .npz")
    a = ap.parse_args()
    ser = awg.open_port(a.port)
    rng = np.random.default_rng(a.seed)
    known = training()

    snr, H = probe(ser, rng, a.rms, a.offset)
    cap = np.sum(DF * np.log2(1 + snr)) * NFFT / SYM
    print(f"probe: {len(KS)} subcarriers, {KS[0] * DF:.0f}..{KS[-1] * DF:.0f} Hz; "
          f"best SNR {10 * np.log10(snr.max()):.1f} dB at {KS[np.argmax(snr)] * DF:.0f} Hz")
    print(f"Shannon: sum of df log2(1 + SNR), less the prefix = {cap / 1e3:.1f} kbit/s")
    if a.probe:
        for k, s in zip(KS, snr):
            print(f"{k * DF:8.0f} Hz  SNR {10 * np.log10(s):5.1f} dB")
        return

    b = loading(snr, a.gap)
    nb = int(b.sum())
    counts = [int(np.sum(b == x)) for x in (1, 2, 4, 6, 8, 10)]
    print(f"loading (gap {a.gap:g} dB): {nb} bits a symbol on {np.sum(b > 0)} subcarriers = "
          f"{nb / T_SYM / 1e3:.1f} kbit/s; BPSK/4/16/64/256/1024-QAM on {counts} subcarriers")
    errors = total = 0
    err_k = np.zeros(len(KS))
    Zs, sents = [], []
    for L in range(a.loops):
        bits = rng.integers(0, 2, (NSYM - 1, nb))
        data = bits_to_symbols(bits, b)
        Y = demux(run_loop(ser, np.vstack([known, data]), a.rms), a.offset)
        for half in range(2):
            Z, _ = receive(Y[half], known, b)
            got = symbols_to_bits(Z, b)
            errors += int(np.sum(got != bits))
            total += bits.size
            err_k[b > 0] += np.sum(nearest(Z, b)[:, b > 0] != data[:, b > 0], axis=0)
            Zs.append(Z)
            sents.append(data)
        print(f"loop {L + 1:3d}: {errors} bit errors in {total} so far")
    print(f"BER {errors}/{total} = {errors / max(total, 1):.1e} at {nb / T_SYM / 1e3:.1f} kbit/s "
          f"({NSYM - 1} data symbols a loop: {(NSYM - 1) * nb / awg.LOOP / 1e3:.1f} kbit/s net)")
    if a.out:
        np.savez(a.out, ks=KS, df=DF, snr=snr, H=H, b=b, Z=np.array(Zs), sent=np.array(sents),
                 err_k=err_k, errors=errors, total=total, t_sym=T_SYM, gap=a.gap, cap=cap,
                 rms=a.rms, offset=a.offset)


if __name__ == "__main__":
    main()
