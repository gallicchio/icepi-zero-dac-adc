#!/usr/bin/env python3
"""OFDM over the cable: a board (awgcap.sv) loops an OFDM frame, a board (the same one,
looped back, or a second one) records it, and this script demodulates it.

    python3 ofdm.py --qam 16 [--records 10]       # one board looped back (finds its port)
    python3 ofdm.py PORT_A PORT_B --qam 16        # two boards: A plays, B records
    python3 ofdm.py --sim --qam 64                # no board: channel.py's model
    python3 ofdm.py --sound                       # channel sounding and Shannon capacity

The frame is designed at the ADC's 25 MS/s: 256-point FFT (97.66 kHz per subcarrier),
a 32-sample cyclic prefix, one pilot symbol and 27 data symbols per 8192-sample loop,
on subcarriers 3..115 (0.29-11.2 MHz).  It is played at 50 MS/s (upsampled by 2).
The receiver's record starts at ITS OWN loop start, so the frame is found by
correlation, and with two boards the transmitter's and receiver's clocks differ by
about 1 ppm.
"""
import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "twoboard"))      # awgcap

NFFT, CP, NSYM = 256, 32, 28
L = 8192                         # one loop at 25 MS/s
KS = np.arange(3, 116)           # used subcarriers
FS = 25e6                        # the ADC's rate


def qam_map(bits, M):
    """Gray-coded square QAM, unit average power."""
    m = int(np.sqrt(M)); b = int(np.log2(m))
    def pam(bb):
        g = bb @ (1 << np.arange(b)[::-1])                 # Gray index
        n = g ^ (g >> 1)
        for s in (2, 4, 8):
            n ^= n >> s
        return 2 * n - (m - 1)
    bits = bits.reshape(-1, 2 * b)
    s = pam(bits[:, :b]) + 1j * pam(bits[:, b:])
    return s / np.sqrt(2 * (M - 1) / 3)


def qam_demap(s, M):
    m = int(np.sqrt(M)); b = int(np.log2(m))
    s = s * np.sqrt(2 * (M - 1) / 3)
    def unpam(x):
        n = np.clip(np.round((x + m - 1) / 2), 0, m - 1).astype(int)
        g = n ^ (n >> 1)
        return ((g[:, None] >> np.arange(b)[::-1]) & 1)
    return np.hstack([unpam(s.real), unpam(s.imag)]).ravel()


def frame(M, seed=7, rms=28.0, noise=0.0):
    """Returns (waveform at 50 MS/s as codes, pilot symbols, data bits).  noise: rms of white
    noise added to the data symbols' subcarriers, relative to the signal (0.1 = -20 dB)."""
    rng = np.random.default_rng(seed)
    pilot = np.exp(1j * np.pi / 2 * rng.integers(0, 4, len(KS)))        # QPSK
    nb = int(np.log2(M)) * len(KS) * (NSYM - 1)
    bits = rng.integers(0, 2, nb)
    data = qam_map(bits, M).reshape(NSYM - 1, len(KS))
    x = np.zeros(L)
    for i in range(NSYM):
        X = np.zeros(NFFT // 2 + 1, complex)
        X[KS] = pilot if i == 0 else data[i - 1]
        if i > 0 and noise:                          # in-band noise on the data symbols only
            X[KS] += noise * (rng.normal(size=len(KS)) + 1j * rng.normal(size=len(KS))) / np.sqrt(2)
        s = np.fft.irfft(X, NFFT)
        x[i * (NFFT + CP):(i + 1) * (NFFT + CP)] = np.concatenate([s[-CP:], s])
    x *= rms / x.std()
    # play at 50 MS/s: perfect periodic interpolation by zero-padding the spectrum
    Xf = np.fft.rfft(x); X2 = np.zeros(L + 1, complex); X2[:len(Xf)] = Xf
    x50 = np.fft.irfft(X2, 2 * L) * 2
    return np.clip(np.round(128 + x50), 0, 255), pilot, bits, x


def demod(rec, M, pilot, bits, x_ref):
    """Align, strip prefixes, FFT, equalise with the pilot, slice.  Returns per-loop
    (bit errors, EVM per subcarrier)."""
    out = []
    for half in rec.reshape(2, L):
        r = half - half.mean()
        lag = np.argmax(np.fft.irfft(np.fft.rfft(r) * np.conj(np.fft.rfft(x_ref)), L))
        r = np.roll(r, -lag)
        Y = np.array([np.fft.rfft(r[i * (NFFT + CP) + CP:(i + 1) * (NFFT + CP)], NFFT)[KS] for i in range(NSYM)])
        H = Y[0] / pilot
        Z = Y[1:] / H
        rb = qam_demap(Z.ravel(), M)
        ideal = qam_map(bits, M).reshape(NSYM - 1, len(KS))
        evm = np.sqrt(np.mean(np.abs(Z - ideal)**2, axis=0))           # per subcarrier, rms
        out.append((int((rb != bits).sum()), evm, Z))
    return out


def make_link(ports, sim=False, seed=1):
    """play(wave) and record() for one board looped back, two boards, or the model."""
    if sim:
        import channel
        rng = np.random.default_rng(seed)
        st = {}
        def play(wave):
            st["wave"] = wave
        def record():
            return channel.channel(st["wave"], rng=rng)
        return play, record
    import awgcap
    from psk import find_port
    ports = ports or [find_port()]
    tx, rx = ports[0], ports[-1]
    return (lambda wave: awgcap.upload(tx, wave)), (lambda: awgcap.record(rx))


def sound(play, record, nrec=20):
    """Multitone on every 25 MS/s bin; average records -> H(f), noise -> SNR(f)."""
    rng = np.random.default_rng(11)
    X = np.zeros(L // 2 + 1, complex); band = np.arange(1, L // 2 - 40)
    X[band] = np.exp(2j * np.pi * rng.random(len(band)))
    x = np.fft.irfft(X, L); x *= 28 / x.std()
    Xf = np.fft.rfft(x); X2 = np.zeros(L + 1, complex); X2[:len(Xf)] = Xf
    play(np.clip(np.round(128 + np.fft.irfft(X2, 2 * L) * 2), 0, 255))
    # Signal and noise from inside each record: it holds two loops of the same waveform,
    # 327.68 us apart, so (loop1 + loop2)/2 is signal and (loop1 - loop2)/2 is noise.
    # (Comparing DIFFERENT records would count the slow drift of the two boards' relative
    # sampling phase as noise.)
    f = np.fft.rfftfreq(L, 1 / FS)
    sig = np.zeros(len(f)); noi = np.zeros(len(f)); Hs = []
    for _ in range(nrec):
        A, B = np.fft.rfft(record().reshape(2, L).astype(float), axis=1)
        sig += np.abs((A + B) / 2)**2; noi += 2 * np.abs((A - B) / 2)**2
        Hs.append(np.abs((A + B) / 2))
    with np.errstate(invalid='ignore', divide='ignore'):
        snr_single = sig / noi                    # SNR of ONE loop (8192 samples)
    S = np.mean(Hs, axis=0)
    sel = band
    C = np.sum(np.log2(1 + snr_single[sel])) * FS / L
    return f[sel], S[sel] / np.abs(np.fft.rfft(x)[sel]), snr_single[sel], C


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("ports", nargs="*", help="none: one board looped back; two: A plays, B records")
    ap.add_argument("--sim", action="store_true", help="use channel.py's model, not a board")
    ap.add_argument("--qam", type=int, default=16)
    ap.add_argument("--records", type=int, default=10)
    ap.add_argument("--sound", action="store_true")
    ap.add_argument("-o", "--out", help="save the results (.npz)")
    a = ap.parse_args()
    play, record = make_link(a.ports, a.sim)
    if a.sound:
        f, H, snr, C = sound(play, record)
        for fm in (0.5e6, 2e6, 5e6, 8e6, 11e6, 12e6):
            i = np.argmin(abs(f - fm)); print("%5.1f MHz: |H| %.3f, SNR %.1f dB" % (fm / 1e6, H[i], 10 * np.log10(snr[i])))
        print("Shannon capacity of one record's worth of channel: %.1f Mbit/s" % (C / 1e6))
        if a.out:
            np.savez(a.out, f=f, H=H, snr=snr, C=C)
    else:
        wave, pilot, bits, x = frame(a.qam)
        play(wave)
        rate = np.log2(a.qam) * len(KS) * (NSYM - 1) / (L / FS)
        errs = nbits = 0; evms = []; Zs = []
        for _ in range(a.records):
            for e, evm, Z in demod(record(), a.qam, pilot, bits, x):
                errs += e; nbits += len(bits); evms.append(evm); Zs.append(Z)
        evm = np.sqrt(np.mean(np.array(evms)**2, axis=0))
        print("QAM-%d: %.1f Mbit/s while sending; %d errors in %d bits (BER %.2e); EVM %.1f%% rms (%.1f dB), best %.1f%%, worst %.1f%% at %.2f MHz" %
              (a.qam, rate / 1e6, errs, nbits, errs / nbits, 100 * np.sqrt(np.mean(evm**2)), 20 * np.log10(np.sqrt(np.mean(evm**2))),
               100 * evm.min(), 100 * evm.max(), KS[np.argmax(evm)] * FS / NFFT / 1e6))
        if a.out:
            np.savez(a.out, M=a.qam, Z=np.array(Zs[:4]), evm=evm, fk=KS * FS / NFFT, errs=errs, nbits=nbits, rate=rate)
