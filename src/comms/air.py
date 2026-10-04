#!/usr/bin/env python3
"""The air, rung by rung: how far a whisper from the DAC carries to an ADC with no radio
in between.  COMPUTED, NOT MEASURED: scaling laws and order-of-magnitude numbers, for
the student to beat with a tape measure.

    python3 air.py                     # the ladder at 6.78 MHz, the transmitter at full power
    python3 air.py --amp 25            # turned down to 5.07's legal estimate
    python3 air.py --f 13.56e6         # the RFID band, where US Part 15 allows 500x the field
    python3 air.py --lna 40            # 40 dB of gain in front of the ADC
    python3 air.py --zin 1e3           # the ADC module's input impedance, if you've measured it
    python3 air.py --fa 40             # the site's noise: ITU-R P.372's Fa in dB above kT0

The transmitter is the DAC: 3.07 V peak into 50 ohm at AMP = 100 (5.07).  The receiver is
the ADC: 8 bits of 39 mV, its own noise about 0.1 code rms, so its floor, quantization
and all, is about 0.3 code rms = 12 mV over 12.5 MHz: 3.4 uV per root hertz, 8 uV in a
6 Hz FT8 tone bin.  That floor is what a small passive antenna fights, not the sky.

Three antennas, each as transmitter and receiver:

  wire    a 10 cm lead with a minigrabber on it: an electric dipole of effective
          length 5 cm and about 2 pF.  Near field ~ 1/r^3, far field ~ 1/r.
  loop    5.07's 30 cm one-turn loop, series-tuned to transmit (I = V / 50 ohm),
          parallel-tuned with Q = 30 to receive: a magnetic dipole.
  dipole  a half-wave dipole (22 m at 6.78 MHz, 11 m at 13.56 MHz): V_oc = E lambda / pi
          into the ADC through a 73 ohm source.  Efficient, so the sky's noise matters.

The fields are the exact dipole fields (electric or magnetic), with their 1/r^3, 1/r^2
and 1/r terms, so one formula covers the bench and the far side of campus.  The
receiver's noise is the ADC floor plus the site's radio noise (ITU-R P.372: Fa dB
above kT0, 50 dB at 7 MHz in a suburb) scaled by the antenna's efficiency, both
through an optional low-noise amplifier.  The thresholds: 5.07's modem needs about
20 mV at the ADC (one code, decoded error-free in a 6 kHz bandwidth); 6.12's FT8-style
frame needs Es/N0 of 7 dB in a 6 Hz bin.
"""
import argparse

import numpy as np

C0, MU0, EPS0, ETA0 = 299792458.0, 4e-7 * np.pi, 8.854e-12, 376.73
K_B, T0 = 1.380649e-23, 290.0
V_DAC_FULL = 3.07                   # volts peak into 50 ohm at AMP = 100
ADC_FLOOR = 3.4e-6                  # volts per root hertz at the ADC (0.3 code rms over 12.5 MHz)
BIN = 5.96                          # hertz: one FT8-style tone bin (2^22 samples at 25 MS/s)
MODEM_V = 20e-3                     # volts at the ADC for 5.07's modem
FT8_ESN0_DB = 7.0                   # Es/N0 for 6.12's frame to decode
FCC_UV_M = {6.78e6: 30.0, 13.56e6: 15848.0}      # 15.209 (1.705-30 MHz); 15.225 (13.553-13.567 MHz)


def dipole_field(moment, r, k, electric=True):
    """|E_theta| of an electric dipole p (or |H_theta| of a magnetic dipole m) at
    theta = 90 degrees: the near 1/r^3, induction 1/r^2 and radiation 1/r terms."""
    kr = k * r
    mag = np.sqrt((1 / kr - 1 / kr**3)**2 + 1 / kr**4) * k**3 / (4 * np.pi)
    return mag * moment / EPS0 if electric else mag * moment


class Wire:
    name, l_eff, cap = "10 cm wire", 0.05, 2e-12
    def tx_field(self, v, r, k, f):                 # electric field, V/m
        return dipole_field(self.cap * v * self.l_eff, r, k, True)
    def rx_volts(self, e, h, f, zin):               # from E, into zin
        v_oc = e * self.l_eff
        zs = 1 / (2 * np.pi * f * self.cap)
        return v_oc * zin / np.hypot(zin, zs)
    field = "E"
    efficiency_db = -60.0                           # radiation resistance of milliohms

class Loop:
    name, radius, turns, q = "30 cm loop", 0.15, 1, 30.0
    @property
    def area(self):
        return np.pi * self.radius**2
    def tx_field(self, v, r, k, f):                 # magnetic field, A/m
        return dipole_field((v / 50.0) * self.turns * self.area, r, k, False)
    def rx_volts(self, e, h, f, zin):
        return self.q * 2 * np.pi * f * self.turns * self.area * MU0 * h
    field = "H"
    efficiency_db = -35.0                           # 31171 (A / lambda^2)^2 ohm against ~0.1 ohm of loss

class Dipole:
    name = "half-wave dipole"
    def tx_field(self, v, r, k, f):                 # fed with the DAC's power into 73 ohm
        p = (v**2 / 2) / 73.0
        return np.sqrt(ETA0 * 1.64 * p / (4 * np.pi * r**2))     # far field only
    def rx_volts(self, e, h, f, zin):
        lam = C0 / f
        return e * lam / np.pi * zin / (zin + 73.0)
    field = "E"
    efficiency_db = 0.0


def ladder(f, amp, lna_db, zin, fa_db, rs):
    k = 2 * np.pi * f / C0
    lam = C0 / f
    v = V_DAC_FULL * amp / 100.0
    g = 10**(lna_db / 20)
    print("f = %.2f MHz (lambda = %.1f m, near field within lambda/2pi = %.1f m); AMP = %d (%.2f V peak); "
          "LNA %g dB; ADC input %g ohm; site noise Fa = %g dB" % (f / 1e6, lam, lam / (2 * np.pi), amp, v, lna_db, zin, fa_db))
    print("ADC floor: %.1f uV in a %.2f Hz bin; FT8-style threshold %.0f dB above it = %.0f uV; 5.07's modem: %.0f mV"
          % (ADC_FLOOR * np.sqrt(BIN) * 1e6, BIN, FT8_ESN0_DB, ADC_FLOOR * np.sqrt(BIN) * 10**(FT8_ESN0_DB / 20) * 1e6, MODEM_V * 1e3))
    limit = FCC_UV_M.get(f)
    pairs = [(Wire(), Wire()), (Wire(), Loop()), (Loop(), Loop()), (Loop(), Dipole()), (Dipole(), Dipole())]
    print()
    print("%-18s %-18s %10s %10s %12s %12s %14s" % ("transmit", "receive", "field@30m", "legal?", "V at 1 m", "5.07 modem", "FT8-style"))
    print("%-18s %-18s %10s %10s %12s %12s %14s" % ("", "", "(uV/m)", "", "", "range", "range"))
    for tx, rx in pairs:
        if tx.field == "H" and rx.field == "E" and not isinstance(rx, Dipole):
            continue
        def volts_at(r):
            fld = tx.tx_field(v, r, k, f)
            if tx.field == "H":
                h = fld
                e = ETA0 * h if isinstance(rx, Dipole) else None     # far field only, for a dipole
            else:
                e, h = fld, None
                if rx.field == "H":
                    h = e / ETA0                                      # far-field relation (crude nearer in)
            return rx.rx_volts(e, h, f, zin) * g
        # the noise at the ADC: its floor, plus the site's noise through the antenna and the LNA
        p_ext = K_B * T0 * BIN * 10**(fa_db / 10) * 10**(rx.efficiency_db / 10)
        v_ext = np.sqrt(p_ext * 50.0) * g
        v_noise = np.hypot(ADC_FLOOR * np.sqrt(BIN), v_ext)
        e30 = tx.tx_field(v, 30.0, k, f)
        e30 = e30 if tx.field == "E" else ETA0 * e30
        legal = "" if limit is None else ("yes" if e30 * 1e6 <= limit else "NO, %.0fx over" % (e30 * 1e6 / limit))
        def rng_for(target):
            lo, hi = 0.01, 1e6
            if volts_at(lo) < target:
                return 0.0
            for _ in range(80):
                mid = np.sqrt(lo * hi)
                if volts_at(mid) >= target:
                    lo = mid
                else:
                    hi = mid
            return lo
        r_modem = rng_for(MODEM_V)
        r_ft8 = rng_for(v_noise * 10**(FT8_ESN0_DB / 20))
        def fmt(r):
            if r >= 1e5:
                return "> 100 km"
            return "0 (never)" if r == 0 else ("%.0f cm" % (r * 100) if r < 1 else ("%.0f m" % r if r < 1000 else "%.1f km" % (r / 1000)))
        v1 = "(far field)" if isinstance(tx, Dipole) else "%.3g uV" % (volts_at(1.0) * 1e6)
        print("%-18s %-18s %10.3g %10s %12s %12s %14s" % (tx.name, rx.name, e30 * 1e6, legal, v1, fmt(r_modem), fmt(r_ft8)))
    print()
    print("Read down the last two columns: each rung is an antenna you can make in an afternoon, and the")
    print("FT8-style frame hears what the modem can't, because a 6 Hz bin lets in a thousandth of the noise")
    print("of a 6 kHz one.  With an LNA (--lna) the dipole rungs stop being limited by the ADC and start")
    print("being limited by the sky, which is the best any receiver can do.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--f", type=float, default=6.78e6, help="carrier, Hz (6.78e6 or 13.56e6)")
    ap.add_argument("--amp", type=int, default=100, help="the DAC's amplitude, codes (5.07's AMP)")
    ap.add_argument("--lna", type=float, default=0.0, help="gain before the ADC, dB")
    ap.add_argument("--zin", type=float, default=50.0, help="the ADC module's input impedance, ohm")
    ap.add_argument("--fa", type=float, default=50.0, help="site noise, dB above kT0 (ITU-R P.372: 35 quiet rural .. 62 business)")
    args = ap.parse_args()
    ladder(args.f, args.amp, args.lna, args.zin, args.fa, None)


if __name__ == "__main__":
    main()
