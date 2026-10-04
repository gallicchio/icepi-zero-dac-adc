#!/usr/bin/env python3
"""FT8, forty thousand times faster: a weak-signal text message in 79 tones through the
cable, and the same frame at six symbols a second through 6.78 MHz for the air.

    python3 ft8.py "CQ HMC JASON"           # one board looped back: encode, play, record, decode
    python3 ft8.py --sim "HELLO WORLD"      # no board: channel.py's model
    python3 ft8.py --esn0 3                 # noise at the transmitter: energy per symbol / N0, dB
    python3 ft8.py --cfo 40                 # the transmitter 40 steps (122 kHz, half a tone) high
    python3 ft8.py --rate=-2:10             # decodes and symbol errors against Es/N0, 10 frames each
    python3 ft8.py --slow PORT --send "CQ HMC JASON"   # ddc.sv loaded: 5.96 baud at 6.78 MHz
    python3 ft8.py --slow PORT --listen --seconds 30   # ... the receiving end, same or another board
    python3 ft8.py -o ft8.npz --no-plot

FT8 (Franke, Somerville and Taylor, 2017: WSJT-X) sends 77 bits in 12.64 seconds as 79
symbols of 8-FSK, tones 6.25 Hz apart, and decodes them 21 dB under the noise in a
2.5 kHz channel.  Its frame is three 7-symbol COSTAS ARRAYS, for finding the signal in
time and frequency at once, around two blocks of 29 data symbols.  This is the same
frame with the same tones, the same Gray map, FT8's 14-bit CRC polynomial and FT8's
free-text alphabet, with two honest simplifications: 6.09's K = 7 convolutional code
(soft Viterbi) in place of FT8's LDPC(174,91), which costs one of the 13 characters
(12 fit), and no Gaussian smoothing of the tone switches (they are phase-continuous).

FAST: on awgcap.sv (6.00) the symbol is 200 DAC samples = 4 us (FT8: 160 ms), the tones
250 kHz apart (6.25 Hz) around 6.25 MHz, and the 79 symbols take 316 us of the 327.68 us
loop.  Es/N0 is the honest axis; FT8's "SNR in 2.5 kHz" is Es/N0 - 26 dB (2.5 kHz is
400 tone spacings), so FT8's -21 dB is Es/N0 = +5 dB.

SLOW: ddc.sv (6.12) plays the same 79 tones one every 2^23 clocks (167.8 ms) from a table
of 8 tuning words, 25e6/2^22 = 5.96 Hz apart at 6.78 MHz, and its down-converter streams
I/Q at 3052 S/s to the laptop; the same receiver code runs on that stream with 512
samples per symbol instead of 100.

RECEIVER (both): mix to baseband; for each of the 8 tones, correlate every symbol-long
window with that tone (a sliding DFT, by FFT); search the 21 Costas positions over
every start time and a grid of frequency offsets for the biggest sum; read the 8
magnitudes at each of the 58 data symbols; turn them into three soft bits each (the
best tone with the bit 0 against the best with the bit 1); Viterbi; CRC; text.
"""
import argparse
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import channel                                      # noqa: E402
from psk import find_port                          # noqa: E402
from ecc import CONV                               # noqa: E402

N, L = 16384, 8192                  # DAC samples per loop; ADC samples per loop
FS_DAC, FS_ADC = 50e6, 25e6
F_LOOP = FS_DAC / N                 # 3051.76 Hz: one cycle per loop
F_C = 6.25e6
AMP = 100
NSYM = 79
COSTAS = [3, 1, 4, 0, 6, 5, 2]      # FT8's 7 x 7 Costas array
COSTAS_AT = [0, 36, 72]
DATA_AT = list(range(7, 36)) + list(range(43, 72))
GRAY = [0, 1, 3, 2, 5, 6, 4, 7]     # FT8's gray map: 3 bits (MSB first) -> tone
UNGRAY = [GRAY.index(t) for t in range(8)]
ALPHA = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ+-./?"      # FT8's free-text alphabet, 42
NCHAR, NTEXT = 12, 65               # 42^12 < 2^65
CRC_POLY, CRC_BITS = 0x2757, 14     # FT8's CRC-14
NINFO = NTEXT + CRC_BITS            # 79 information bits
NCODE = 174                         # 58 symbols x 3 bits
TONE_OFF = -3.5                     # tone k sits (k - 3.5) tone spacings from the carrier

# the fast frame
SPS_DAC, SPS = 200, 100             # samples per symbol at the DAC and the ADC
DF = FS_ADC / SPS                   # 250 kHz: one cycle per symbol
# the slow frame
SLOW_F0 = 6.78e6
SLOW_LOG2 = 22                      # ADC samples per symbol = 2^22: 167.77 ms
SLOW_DF = FS_ADC / 2**SLOW_LOG2     # 5.96 Hz
SLOW_DECIM = 13                     # ddc.sv sums 2^13 samples: 3051.76 I/Q per second
SLOW_SPS = 2**(SLOW_LOG2 - SLOW_DECIM)   # 512 I/Q samples per symbol


# ---- the message ------------------------------------------------------------------
def pack_text(text):
    """12 characters of FT8's alphabet -> 65 bits (a base-42 integer, MSB first)."""
    text = text.upper()[:NCHAR].ljust(NCHAR)
    v = 0
    for ch in text:
        if ch not in ALPHA:
            ch = "?"
        v = v * len(ALPHA) + ALPHA.index(ch)
    return np.array([(v >> (NTEXT - 1 - i)) & 1 for i in range(NTEXT)])


def unpack_text(bits):
    v = 0
    for b in bits[:NTEXT]:
        v = (v << 1) | int(b)
    out = []
    for _ in range(NCHAR):
        out.append(ALPHA[v % len(ALPHA)])
        v //= len(ALPHA)
    return "".join(reversed(out))


def crc(bits, poly=CRC_POLY, nbits=CRC_BITS):
    """A cyclic redundancy check: the remainder of the message (times x^14) divided by
    the polynomial, in GF(2).  14 bits catch all bursts up to 14 long and 1 in 16384 of
    anything else: the receiver's way to know that the decoder's answer is right."""
    r = 0
    for b in list(bits) + [0] * nbits:
        r = (r << 1) | int(b)
        if r & (1 << nbits):
            r ^= (1 << nbits) | poly
    return np.array([(r >> (nbits - 1 - i)) & 1 for i in range(nbits)])


def encode(text):
    """Text -> 79 tones.  The code bits go three at a time through the Gray map."""
    info = np.concatenate([pack_text(text), crc(pack_text(text))])         # 79 bits
    code = CONV.encode(info)                                              # 170 (6 tail bits)
    code = np.concatenate([code, np.zeros(NCODE - len(code), int)])       # 174
    syms = code.reshape(-1, 3) @ [4, 2, 1]
    data_tones = [GRAY[s] for s in syms]
    tones = np.zeros(NSYM, int)
    for p in COSTAS_AT:
        tones[p:p + 7] = COSTAS
    tones[DATA_AT] = data_tones
    return tones


def decode(values):
    """174 soft code bits (+ for a 0, - for a 1) -> (text, crc ok) by soft Viterbi."""
    info = CONV.viterbi(values[:2 * (NINFO + CONV.K - 1)])
    ok = bool(np.all(crc(info[:NTEXT]) == info[NTEXT:NINFO]))
    return unpack_text(info[:NTEXT]), ok


# ---- the fast frame on awgcap.sv ---------------------------------------------------
def waveform(tones, cfo_steps=0):
    """DAC codes for one loop: 79 phase-continuous tones, then silence."""
    f = F_C + cfo_steps * F_LOOP + (np.repeat(tones, SPS_DAC) + TONE_OFF) * DF
    phase = 2 * np.pi * np.cumsum(f) / FS_DAC
    s = np.zeros(N)
    s[:len(phase)] = np.cos(phase)
    return s


def transmit(tones, esn0=None, cfo_steps=0, rng=None):
    """The waveform with white noise over the ADC's band for the given Es/N0 (energy per
    symbol over the noise density), as the other scripts add it: at the transmitter."""
    s = waveform(tones, cfo_steps)
    if esn0 is not None:
        es = 0.5 * SPS_DAC / FS_DAC                     # a unit-amplitude tone, one symbol
        n0 = es / 10**(esn0 / 10)
        k = np.arange(N // 2 + 1)
        band = (k > 0) & (k * F_LOOP <= FS_ADC / 2)
        X = np.zeros(N // 2 + 1, complex)
        X[band] = np.random.default_rng(rng).standard_normal((band.sum(), 2)) @ [1, 1j]
        x = np.fft.irfft(X, N)
        s = s + x * np.sqrt(n0 * band.sum() * F_LOOP) / x.std()
    return 128 + AMP * s / np.abs(s).max()


def baseband(rec):
    """Two loops of the record, mixed down from 6.25 MHz and low-passed to +-1.5 MHz."""
    r = np.asarray(rec, float)[:L] - np.mean(rec)
    r = np.tile(r, 2)
    n = np.arange(len(r))
    z = 2 * r * np.exp(-2j * np.pi * F_C * n / FS_ADC)
    f = np.fft.fftfreq(len(r), 1 / FS_ADC)
    return np.fft.ifft(np.fft.fft(z) * (np.abs(f) <= 6 * DF))


# ---- the receiver, for either frame ------------------------------------------------
def tone_corr(z, sps, nu=0.0):
    """Correlate every symbol-long window of z with each of the 8 tones, the whole
    record at once by FFT.  C[k, t0] = sum_n z[t0 + n] exp(-2 pi j (k + off + nu) n / sps).
    nu: a frequency offset in tone spacings (cycles per symbol) to take out first."""
    n = np.arange(len(z))
    Z = np.fft.fft(z * np.exp(-2j * np.pi * nu * n / sps))
    C = np.empty((8, len(z)), complex)
    for k in range(8):
        e = np.zeros(len(z), complex)
        e[:sps] = np.exp(2j * np.pi * (k + TONE_OFF) * np.arange(sps) / sps)
        # ##############################################################################
        # ##  KEY LINE: a sliding matched filter for tone k, at every start time, in
        # ##  one FFT: this is 6.06's acquisition with a tone instead of a code.
        # ##############################################################################
        C[k] = np.fft.ifft(Z * np.conj(np.fft.fft(e)))
    return C


def sync(z, sps, nu_max=1.0, nu_step=0.125):
    """Find the frame: the start time and frequency offset where the 21 Costas symbols
    add up best.  Returns (t0, nu, C at that nu, the search surface)."""
    nus = np.arange(-nu_max, nu_max + nu_step / 2, nu_step)
    best, surface = None, []
    for nu in nus:
        C = tone_corr(z, sps, nu)
        S = np.zeros(len(z))
        for p in COSTAS_AT:
            for j, tone in enumerate(COSTAS):
                # ######################################################################
                # ##  KEY LINE: the Costas sum.  Each of the 21 known symbols votes for
                # ##  the start time that puts its tone where it should be.
                # ######################################################################
                S += np.abs(np.roll(C[tone], -(p + j) * sps))
        surface.append(S)
        if best is None or S.max() > best[0]:
            best = (S.max(), int(np.argmax(S)), nu, C)
    _, t0, nu, C = best
    return t0, nu, C, np.array(surface), nus


def magnitudes(C, t0, sps):
    """The 8 tone magnitudes at each of the 79 symbols: (79, 8)."""
    idx = (t0 + np.arange(NSYM) * sps) % C.shape[1]
    return np.abs(C[:, idx]).T


def soft_bits(M):
    """(58, 8) magnitudes -> 174 soft code bits.  For each bit: the best tone that has
    it 0, minus the best that has it 1, in units of a clean symbol's peak."""
    scale = np.median(M.max(axis=1)) + 1e-12
    bits_of_tone = np.array([[(UNGRAY[t] >> (2 - b)) & 1 for b in range(3)] for t in range(8)])
    v = np.empty((len(M), 3))
    for b in range(3):
        zero = bits_of_tone[:, b] == 0
        # ##############################################################################
        # ##  KEY LINE: a soft bit from eight magnitudes.  A near miss between two tones
        # ##  that agree on this bit leaves it confident; a miss across it leaves it ~0.
        # ##############################################################################
        v[:, b] = (M[:, zero].max(axis=1) - M[:, ~zero].max(axis=1)) / scale
    return v.ravel()


def receive(z, sps, nu_max=1.0, period=None):
    """Baseband in; dict out: text, crc ok, the tones heard, the sync, the magnitudes.
    period: the record repeats every this many samples (the fast frame: one loop), so
    the start is reported modulo it; without one, a start past the middle is reported
    as negative (the frame began before the record did)."""
    t0, nu, C, surface, nus = sync(z, sps, nu_max)
    M = magnitudes(C, t0, sps)
    if period:
        t0 %= period
    elif t0 > C.shape[1] // 2:
        t0 -= C.shape[1]
    heard = np.argmax(M, axis=1)
    text, ok = decode(soft_bits(M[DATA_AT]))
    return dict(text=text, ok=ok, t0=t0, nu=nu, M=M, heard=heard, surface=surface, nus=nus)


def report(r, tones, esn0=None, sps=SPS, df=DF):
    serr = int(np.sum(r["heard"][DATA_AT] != tones[DATA_AT]))
    cerr = int(np.sum(r["heard"][[p + j for p in COSTAS_AT for j in range(7)]]
                      != np.tile(COSTAS, 3)))
    snr = "" if esn0 is None else " at Es/N0 %.1f dB (FT8's scale: %.0f dB in 2.5 kHz)" % (esn0, esn0 - 10 * np.log10(400))
    print("sync: frame starts at sample %d, carrier off by %+.3f tone spacings (%+.1f Hz)%s"
          % (r["t0"], r["nu"], r["nu"] * df, snr))
    print("tones heard: %d of 58 data symbols wrong, %d of 21 Costas symbols wrong" % (serr, cerr))
    print("decoded: %r  CRC %s" % (r["text"], "ok" if r["ok"] else "FAILED"))
    return serr


# ---- the link ----------------------------------------------------------------------
def make_link(args):
    if args.sim:
        rng = np.random.default_rng(args.seed)
        st = {}
        def play(wave):
            st["wave"] = wave
        def record():
            return channel.channel(st["wave"], rng=rng)
        return play, record
    sys.path.insert(0, os.path.join(HERE, "..", "twoboard"))
    import awgcap
    ports = args.ports or [find_port()]
    return (lambda w: awgcap.upload(ports[0], w)), (lambda: awgcap.record(ports[-1]))


def rate_run(play, record, esn0s, frames=10, seed=1, out=None):
    """Decodes and data-symbol errors against Es/N0."""
    rng = np.random.default_rng(seed)
    rows = []
    print("%8s  %8s  %12s  %s" % ("Es/N0", "decoded", "symbols wrong", "FT8 scale"))
    for e in esn0s:
        ok, serr, nsym = 0, 0, 0
        for i in range(frames):
            text = "TEST %04d %s" % (rng.integers(10000), ALPHA[rng.integers(1, 11)])
            tones = encode(text)
            play(transmit(tones, e, rng=rng))
            r = receive(baseband(record()), SPS, period=L)
            ok += int(r["ok"] and r["text"].strip() == text.strip())
            serr += int(np.sum(r["heard"][DATA_AT] != tones[DATA_AT]))
            nsym += 58
        rows.append((e, ok / frames, serr / nsym))
        print("%6.1f dB  %3d of %2d   %5d of %4d  %+.0f dB" % (e, ok, frames, serr, nsym, e - 10 * np.log10(400)))
    rows = np.array(rows)
    if out:
        np.savez(out, esn0=rows[:, 0], decoded=rows[:, 1], ser=rows[:, 2], frames=frames)
    return rows


def ser_theory_8fsk(esn0_db):
    """Symbol error rate of non-coherent 8-FSK (Proakis), for the uncoded reference."""
    from math import comb
    g = 10**(np.asarray(esn0_db, float) / 10)
    p = np.zeros_like(g)
    for n in range(1, 8):
        p += (-1)**(n + 1) * comb(7, n) / (n + 1) * np.exp(-n * g / (n + 1))
    return p


# ---- the slow frame on ddc.sv ------------------------------------------------------
def slow_tones_hz():
    return [SLOW_F0 + (k + TONE_OFF) * SLOW_DF for k in range(8)]


def slow_send(port, text, amp=100):
    sys.path.insert(0, os.path.join(HERE, "..", "twoboard"))
    import ddc
    ser = ddc.open_port(port)
    for k, f in enumerate(slow_tones_hz()):
        ddc.set_tone(ser, k, f)
    ddc.set_amp(ser, amp)
    ddc.set_symbol(ser, 2**(SLOW_LOG2 + 1))
    tones = encode(text)
    ddc.queue(ser, [int(t) for t in tones])
    print("sending %r: 79 tones, %.2f s, %.2f Hz apart at %.4f MHz" % (text, NSYM * 2**SLOW_LOG2 / FS_ADC, SLOW_DF, SLOW_F0 / 1e6))
    return tones


def slow_listen(port, seconds=30.0, nu_max=3.0):
    sys.path.insert(0, os.path.join(HERE, "..", "twoboard"))
    import ddc
    ser = ddc.open_port(port)
    ddc.set_rx(ser, SLOW_F0)
    ddc.set_decim(ser, SLOW_DECIM)
    ddc.stream(ser, True)
    n = int(seconds * FS_ADC / 2**SLOW_DECIM)
    print("listening at %.4f MHz for %.0f s (%d I/Q samples)..." % (SLOW_F0 / 1e6, seconds, n))
    z = ddc.read_iq(ser, n, SLOW_DECIM)
    ddc.stream(ser, False)
    rms = np.sqrt(np.mean(np.abs(z)**2))
    z = np.concatenate([z, np.zeros(SLOW_SPS * NSYM, complex)])      # room for a linear search
    r = receive(z, SLOW_SPS, nu_max)
    print("signal: %.2f codes rms over the record; the frame's tones peak at %.1f codes"
          % (rms, r["M"].max() / SLOW_SPS))
    return r, z


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("text", nargs="?", default="CQ HMC JASON", help="up to 12 characters of ' 0-9 A-Z + - . / ?'")
    ap.add_argument("ports", nargs="*", help="one port: looped back; two: A plays, B records")
    ap.add_argument("--sim", action="store_true", help="use channel.py's model, not a board")
    ap.add_argument("--esn0", type=float, help="noise at the transmitter: energy per symbol / N0, dB")
    ap.add_argument("--cfo", type=int, default=0, help="transmitter's carrier offset, steps of 3051.76 Hz")
    ap.add_argument("--rate", help="decode rate against Es/N0 = LO:HI dB (1 dB steps)")
    ap.add_argument("--frames", type=int, default=10, help="--rate: frames per point")
    ap.add_argument("--slow", action="store_true", help="the real-speed frame through ddc.sv (6.12)")
    ap.add_argument("--send", help="--slow: transmit this text")
    ap.add_argument("--listen", action="store_true", help="--slow: receive for --seconds and decode")
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--amp", type=int, default=100, help="--slow: the tone's amplitude in DAC codes")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("-o", "--out", help="save the results (.npz)")
    ap.add_argument("--no-plot", action="store_true")
    args = ap.parse_args()
    if args.text and args.text.startswith("/dev/"):
        args.ports.insert(0, args.text)
        args.text = "CQ HMC JASON"

    if args.slow:
        port = args.ports[0] if args.ports else find_port()
        if args.send:
            slow_send(port, args.send, args.amp)
        if args.listen:
            r, z = slow_listen(port, args.seconds)
            report(r, encode(args.send or ""), sps=SLOW_SPS, df=SLOW_DF)
            if args.out:
                np.savez(args.out, z=z, M=r["M"], heard=r["heard"], t0=r["t0"], nu=r["nu"], text=r["text"], ok=r["ok"])
        return

    play, record = make_link(args)
    if args.rate:
        lo, hi = map(float, args.rate.split(":"))
        rate_run(play, record, np.arange(lo, hi + 0.5, 1.0), args.frames, args.seed, args.out)
        return

    tones = encode(args.text)
    print("sending %r: %d information bits (65 text + 14 CRC) -> 174 code bits -> 58 data symbols + 21 Costas"
          % (args.text, NINFO))
    play(transmit(tones, args.esn0, args.cfo, rng=np.random.default_rng(args.seed)))
    rec = record()
    r = receive(baseband(rec), SPS, period=L)
    report(r, tones, args.esn0)
    if args.out:
        np.savez(args.out, rec=rec, tones=tones, M=r["M"], heard=r["heard"], t0=r["t0"], nu=r["nu"],
                 surface=r["surface"], nus=r["nus"], text=r["text"], ok=r["ok"], esn0=np.nan if args.esn0 is None else args.esn0)
    if not args.no_plot:
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(2, 1, figsize=(10, 7))
        ax[0].imshow(r["M"].T, aspect="auto", origin="lower", cmap="Blues",
                     extent=(-0.5, NSYM - 0.5, -0.5, 7.5))
        ax[0].plot(np.arange(NSYM), tones, "o", color="C1", ms=3, label="sent")
        ax[0].set_ylabel("tone"); ax[0].set_xlabel("symbol"); ax[0].legend(loc="upper right")
        ax[0].set_title("the 8 tone magnitudes at every symbol; %r, CRC %s" % (r["text"], "ok" if r["ok"] else "failed"))
        ax[1].imshow(r["surface"], aspect="auto", origin="lower", cmap="Blues",
                     extent=(0, r["surface"].shape[1], r["nus"][0], r["nus"][-1]))
        ax[1].plot(r["t0"], r["nu"], "x", color="C1", ms=10)
        ax[1].set_xlabel("start sample"); ax[1].set_ylabel("frequency offset (tone spacings)")
        ax[1].set_title("the Costas search")
        fig.tight_layout(); plt.show()


if __name__ == "__main__":
    main()
