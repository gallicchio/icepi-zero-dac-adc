#!/usr/bin/env python3
"""Check am_radio.sv against numpy, in simulation: no hardware needed.

    python3 am_check.py            # all the tests: about 2 minutes (the first run also
                                   #   builds the Verilator model: add a minute)
    python3 am_check.py --plot     # ...and plot the results (--plot FILE.png: save them)
    python3 am_check.py --quick    # skip the 14 s melody and the fake serial port: 10 s

Icarus Verilog runs am_radio.sv at about 60,000 clocks a second: 1 ms of the radio's
time per second.  Hearing anything takes seconds of radio time, so this uses
Verilator, which turns the design into a C++ program (as dev/tools/anim_leds.py
does): over 100 times faster.  The C++ "harness" below plays the analog world and
the laptop: the ADC sees either a test signal from a file or the DAC through a
cable (code = 0.776 x DAC + 27.5, as measured with a real cable); bytes go in on
uart_rx and come out of uart_tx, bit by bit, as on the real wires.

The tests:
  1. Receiver, bit for bit: test signals (a bare carrier; AM with a 1 kHz tone; the
     same 10 and 20 kHz off frequency; two stations 10 kHz apart) go into the ADC,
     and every envelope sample the FPGA sends must equal model(): a copy of
     am_radio.sv's arithmetic in numpy (mixer, CIC, FIR, square root).
  2. Selectivity: a carrier from 0 to 100 kHz away from the receive frequency;
     the envelope it gives, against the theory, |CIC x FIR| at that offset
     (folded into +-12.5 kHz, as keeping 1 sample in 1000 does).
  3. Audio frequency response: AM with tones from 100 Hz to 12 kHz.
  4. Transmitter: the DAC's spectrum near the carrier, with the 1 kHz tone and with
     the melody's first note (sidebands at +-1 kHz, +-329.63 Hz and +-659.26 Hz);
     the receiver at the other end of the cable, on tune and 10 kHz off.
  5. The whole loop: the melody through the cable, all 13.6 s; each note's pitch.
     (It also writes ../../tools/am_sim/ode_to_joy_sim.wav: what the laptop should hear.)
  6. am_radio.py itself, talking to the simulation through a fake serial port.
"""
import argparse
import contextlib
import hashlib
import io
import os
import select
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

import numpy as np

import am_radio                     # am_radio.py: the laptop side

HERE = os.path.dirname(os.path.abspath(__file__))
SIMDIR = os.path.join(HERE, "..", "..", "tools", "am_sim")     # build folder (git-ignored)
F_CLK, FS_ADC, R, FS = 50e6, 25e6, 1000, 25e3
TW_1MHZ = 0x051EB852

# ---- am_radio.sv's tables, computed exactly as its `initial` blocks do ---------
i256 = np.arange(256)
SINE = np.floor(127.0 * np.sin(6.283185307179586 * i256 / 256) + 0.5).astype(np.int64)
TAPS, FC = 127, 4500.0


def coefficients():
    """The FIR's h[k], as the Verilog's `initial` block computes them."""
    h = np.zeros(TAPS, dtype=np.int64)
    for i in range(TAPS):
        k = i - TAPS // 2
        if k == 0:
            h[i] = np.floor(262144.0 * 2.0 * FC / 25000.0 + 0.5)
        else:                       # the same operations, in the same order, as the Verilog
            h[i] = np.floor(262144.0 * np.sin(6.283185307179586 * FC / 25000.0 * k)
                            / (3.141592653589793 * k)
                            * (0.42 + 0.5 * np.cos(6.283185307179586 * k / 128.0)
                               + 0.08 * np.cos(12.566370614359172 * k / 128.0)) + 0.5)
    return h


COEF = coefficients()


def model(codes, tw=TW_1MHZ, g=0):
    """am_radio.sv's receiver, step for step, on ADC codes (sample n taken at clock 2n,
    with the receive DDS at phase 2n x TW).  Returns (envelope, the 14-bit samples sent)."""
    n = np.arange(len(codes) // R * R, dtype=np.int64)      # whole outputs only
    x = codes[:len(n)].astype(np.int64) - 128
    phase = ((2 * n * tw) % 2**32) >> 24
    # ##########################################################################
    # ##  KEY LINES: the mixer, the CIC and the FIR, in integers.  int64
    # ##  wraps around like the FPGA's 45-bit sums, and like them, the combs'
    # ##  differences still come out exactly right.
    # ##########################################################################
    mix = (x * SINE[phase], x * SINE[(phase + 64) % 256])
    out = []
    for p in mix:
        i1 = np.cumsum(p)                                    # int1 after sample n
        i2 = np.concatenate(([0], np.cumsum(i1)[:-1]))       # int2 adds int1 *before* the update
        i3 = np.concatenate(([0], np.cumsum(i2)[:-1]))
        y = i3[R - 1::R]                                     # after every R-th sample
        for _ in range(3):                                   # the three combs
            y = np.diff(y, prepend=0)
        cic = (y + 2**26) >> 27
        acc = np.convolve(cic, COEF)[:len(cic)]              # the FIR
        out.append(np.clip((acc + 2**17) >> 18, -131071, 131071))
    power = out[0]**2 + out[1]**2
    env = np.floor(np.sqrt(power.astype(float))).astype(np.int64)
    env += (env + 1)**2 <= power                             # an exact integer square root
    env -= env**2 > power
    return env, np.minimum(env >> g, am_radio.FULL)


def cic_response(f):
    """|H| of the CIC at f Hz (from the receive frequency)."""
    x = np.pi * np.asarray(f, float) / FS_ADC
    with np.errstate(invalid="ignore", divide="ignore"):
        h = np.where(x == 0, 1.0, np.sin(R * x) / (R * np.sin(x)))
    return np.abs(h)**3


def fir_response(f):
    k = np.arange(TAPS)
    return np.abs(np.exp(-2j * np.pi * np.outer(np.atleast_1d(f), k) / FS) @ COEF) / 2**18


def response(f):
    """CIC x FIR at an offset f, with f folded into -12.5..12.5 kHz as decimation does."""
    f = np.atleast_1d(np.asarray(f, float))
    folded = (f + FS / 2) % FS - FS / 2
    return cic_response(f) * fir_response(folded)


GAIN = 127 / 2 * R**3 / 2**27 * COEF.sum() / 2**18        # envelope per ADC code: 473.1


# ---- the Verilator model and its harness ---------------------------------------
HARNESS = r'''
// am_radio.sv in Verilator, with a fake analog world and a fake laptop.
// Arguments (key=value):
//   clocks=N        how many 50 MHz clocks to run (live mode: until stdin closes)
//   adc=FILE        ADC codes, one byte per sample at 25 MS/s (then the last one, held)
//   adc=loop        ...or the DAC through a cable: code = round(0.776 DAC + 27.5), 10 clocks late
//   adc_out=FILE    write the code the ADC gave at each sample
//   dac=FILE dac_from=N dac_n=N   write dac_d for N clocks from clock N, one byte each
//   cmd=CLOCK:HEX   at that clock, start sending these bytes (hex) to uart_rx
//   out=FILE        write the bytes received from uart_tx
//   live=1          also send what arrives on stdin; write what's received to stdout
#include "Vam_radio.h"
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <cmath>
#include <string>
#include <vector>
#include <deque>
#include <poll.h>
#include <unistd.h>

int main(int argc, char **argv) {
    uint64_t clocks = 0, dac_from = 0, dac_n = 0;
    std::string adc = "loop", adc_out, dac, out;
    bool live = false;
    std::vector<std::pair<uint64_t, std::string>> cmds;
    for (int i = 1; i < argc; i++) {
        std::string a = argv[i], k = a.substr(0, a.find('=')), v = a.substr(a.find('=') + 1);
        if (k == "clocks") clocks = strtoull(v.c_str(), 0, 10);
        else if (k == "adc") adc = v;
        else if (k == "adc_out") adc_out = v;
        else if (k == "dac") dac = v;
        else if (k == "dac_from") dac_from = strtoull(v.c_str(), 0, 10);
        else if (k == "dac_n") dac_n = strtoull(v.c_str(), 0, 10);
        else if (k == "out") out = v;
        else if (k == "live") live = true;
        else if (k == "cmd") {
            std::string hex = v.substr(v.find(':') + 1), bytes;
            for (size_t j = 0; j + 1 < hex.size(); j += 2) bytes += (char)strtol(hex.substr(j, 2).c_str(), 0, 16);
            cmds.push_back({strtoull(v.c_str(), 0, 10), bytes});
        } else { fprintf(stderr, "unknown argument %s\n", argv[i]); return 1; }
    }
    std::vector<uint8_t> codes;
    if (adc != "loop") {
        FILE *f = fopen(adc.c_str(), "rb");
        if (!f) { fprintf(stderr, "can't open %s\n", adc.c_str()); return 1; }
        int ch;
        while ((ch = fgetc(f)) != EOF) codes.push_back(ch);
        fclose(f);
    }
    FILE *fa = adc_out.empty() ? 0 : fopen(adc_out.c_str(), "wb");
    FILE *fd = dac.empty() ? 0 : fopen(dac.c_str(), "wb");
    FILE *fo = live ? stdout : (out.empty() ? 0 : fopen(out.c_str(), "wb"));
    std::vector<uint8_t> obuf;

    Vam_radio t;
    t.clk = 0; t.adc_d = 128; t.uart_rx = 1; t.eval();
    uint8_t pipe[16] = {128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128};
    size_t n_adc = 0;
    std::deque<uint8_t> sendq;                  // bytes waiting to go to uart_rx
    int send_bit = -1; uint64_t send_t0 = 0; uint8_t send_byte = 0;
    int rx_bit = -1; uint64_t rx_t0 = 0; uint8_t rx_byte = 0; int last_tx = 1;
    size_t next_cmd = 0;
    for (uint64_t c = 0; live || c < clocks; c++) {
        // ---- inputs, before the rising edge ----
        if (!t.adc_clk) {                       // the design takes adc_d at this edge
            uint8_t code;
            if (adc == "loop") code = (uint8_t)lround(0.776 * pipe[9] + 27.5);
            else code = codes.empty() ? 128 : codes[n_adc < codes.size() ? n_adc : codes.size() - 1];
            t.adc_d = code;
            n_adc++;
            if (fa) fputc(code, fa);
        }
        while (next_cmd < cmds.size() && cmds[next_cmd].first <= c) {
            for (char ch : cmds[next_cmd].second) sendq.push_back((uint8_t)ch);
            next_cmd++;
        }
        if (live && (c & 4095) == 0) {          // anything from the laptop?
            struct pollfd p = {0, POLLIN, 0};
            if (poll(&p, 1, 0) > 0) {
                uint8_t buf[256];
                ssize_t k = read(0, buf, sizeof buf);
                if (k <= 0) break;              // stdin closed: the laptop has gone
                for (ssize_t j = 0; j < k; j++) sendq.push_back(buf[j]);
            }
        }
        if (send_bit < 0 && !sendq.empty()) {   // start a byte: 1 start bit, 8 data, 1 stop
            send_byte = sendq.front(); sendq.pop_front(); send_bit = 0; send_t0 = c;
        }
        if (send_bit >= 0) {
            int b = (int)((c - send_t0) / 50);  // 50 clocks per bit
            t.uart_rx = b == 0 ? 0 : b <= 8 ? (send_byte >> (b - 1)) & 1 : 1;
            if (b == 10) { send_bit = -1; t.uart_rx = 1; }
        }
        t.clk = 1; t.eval();
        // ---- outputs, after the rising edge ----
        for (int k = 15; k > 0; k--) pipe[k] = pipe[k - 1];
        pipe[0] = t.dac_d;
        if (fd && c >= dac_from && c < dac_from + dac_n) fputc(t.dac_d, fd);
        if (rx_bit < 0 && last_tx && !t.uart_tx) { rx_bit = 0; rx_t0 = c; }   // a start bit
        if (rx_bit >= 0 && c - rx_t0 == (uint64_t)(75 + 50 * rx_bit)) {      // the middle of a bit
            if (rx_bit < 8) rx_byte |= t.uart_tx << rx_bit, rx_bit++;
            else {
                if (!t.uart_tx) fprintf(stderr, "framing error at clock %llu\n", (unsigned long long)c);
                obuf.push_back(rx_byte);
                rx_byte = 0; rx_bit = -1;
                if (fo && obuf.size() >= (live ? 64 : 65536)) {
                    fwrite(obuf.data(), 1, obuf.size(), fo); fflush(fo); obuf.clear();
                }
            }
        }
        last_tx = t.uart_tx;
        t.clk = 0; t.eval();
    }
    if (fo) { fwrite(obuf.data(), 1, obuf.size(), fo); fflush(fo); }
    if (fa) fclose(fa);
    if (fd) fclose(fd);
    if (fo && !live) fclose(fo);
    return 0;
}
'''


VERILATOR_FLAGS = ["--cc", "--exe", "--build", "-O3", "--x-assign", "fast", "--x-initial", "fast",
                   "-CFLAGS", "-O3", "-j", "8", "-Wno-fatal", "-Wno-lint", "-Wno-style",
                   "--top-module", "am_radio"]


def build():
    """Verilate am_radio.sv + uart.sv + the harness, unless that's already been done."""
    srcs = [os.path.join(HERE, f) for f in ("am_radio.sv", "uart.sv")]
    stamp = hashlib.sha1(" ".join(VERILATOR_FLAGS).encode() + HARNESS.encode()
                         + b"".join(open(f, "rb").read() for f in srcs)).hexdigest()
    exe = os.path.join(SIMDIR, "obj", "am_sim")
    stamp_file = os.path.join(SIMDIR, "stamp")
    if os.path.exists(exe) and os.path.exists(stamp_file) and open(stamp_file).read() == stamp:
        return exe
    os.makedirs(SIMDIR, exist_ok=True)
    open(os.path.join(SIMDIR, "harness.cpp"), "w").write(HARNESS)
    print("building the Verilator model (about a minute)...", flush=True)
    subprocess.run(["verilator", *VERILATOR_FLAGS, "-Mdir", os.path.join(SIMDIR, "obj"), *srcs,
                    os.path.join(SIMDIR, "harness.cpp"), "-o", "am_sim"],
                   check=True, stdout=subprocess.DEVNULL)
    open(stamp_file, "w").write(stamp)
    return exe




def run(exe, tmp, name, clocks, adc="loop", cmds=(), adc_out=False, dac=None):
    """One simulation.  adc: "loop" (the cable from the DAC) or an array of ADC codes.
    cmds: (clock, text) pairs to send to the FPGA.  dac: (first clock, how many) of
    dac_d to keep.  Returns the envelope samples it sent, and the ADC and DAC codes."""
    f = {x: os.path.join(tmp, f"{name}.{x}") for x in ("adc", "out", "adc_out", "dac")}
    args = [exe, f"clocks={clocks}", f"out={f['out']}"]
    if isinstance(adc, str):
        args.append("adc=loop")
    else:
        adc.tofile(f["adc"])
        args.append(f"adc={f['adc']}")
    if adc_out:
        args.append(f"adc_out={f['adc_out']}")
    if dac:
        args += [f"dac={f['dac']}", f"dac_from={dac[0]}", f"dac_n={dac[1]}"]
    args += [f"cmd={c}:{text.encode().hex()}" for c, text in cmds]
    p = subprocess.run(args, capture_output=True, text=True)
    if p.returncode or p.stderr:
        raise SystemExit(f"{name}: simulation failed: {p.stderr}")
    out = {"env": am_radio.decode(open(f["out"], "rb").read())}
    if adc_out:
        out["adc"] = np.fromfile(f["adc_out"], np.uint8)
    if dac:
        out["dac"] = np.fromfile(f["dac"], np.uint8)
    for x in f.values():
        if os.path.exists(x):
            os.remove(x)
    return out


# ---- test signals: ADC codes at 25 MS/s ------------------------------------------
def station(A, m=0.0, fm=1000.0, df=0.0, phase=0.3):
    """An AM station: a carrier of A codes at 1 MHz + df, modulated at depth m by a tone fm."""
    return lambda t: A * (1 + m * np.cos(2 * np.pi * fm * t)) * np.cos(2 * np.pi * (1e6 + df) * t + phase)


def codes_of(parts, seconds):
    t = np.arange(int(seconds * FS_ADC)) / FS_ADC
    return np.clip(np.round(128 + sum(p(t) for p in parts)), 0, 255).astype(np.uint8)


def tones(env, freqs, start=300):
    """Fit the average plus a sine at each of freqs to env[start:] (least squares, all
    at once, so they don't leak into each other).  Returns (average, amplitudes).
    The first 300 samples (12 ms) are the filters filling up."""
    y = env[start:].astype(float)
    t = np.arange(len(y)) / FS
    cols = [np.ones_like(t)]
    for f in freqs:
        cols += [np.cos(2 * np.pi * f * t), np.sin(2 * np.pi * f * t)]
    c = np.linalg.lstsq(np.column_stack(cols), y, rcond=None)[0]
    return c[0], np.hypot(c[1::2], c[2::2])


def db(x):
    return 20 * np.log10(np.maximum(np.abs(x), 1e-12))


def show_db(x, zero):
    """x in dB for a table, or `zero` if x is 0 (or 0 but for floating-point rounding)."""
    return f"{db(x):9.1f} dB" if abs(x) > 1e-9 else f"{zero:>12s}"


RX_TESTS = [   # name, the signal, g (the output shift)
    ("bare carrier, 80 codes", [station(80)], 2),
    ("AM: 1 kHz tone, m = 0.5", [station(80, 0.5)], 2),
    ("the same, 10 kHz higher", [station(80, 0.5, df=10e3)], 0),
    ("the same, 10 kHz lower", [station(80, 0.5, df=-10e3)], 0),
    ("the same, 20 kHz higher", [station(80, 0.5, df=20e3)], 0),
    ("the same, 20 kHz lower", [station(80, 0.5, df=-20e3)], 0),
    ("two: 1 kHz here + 400 Hz at +10 kHz", [station(40, 0.5), station(40, 0.5, 400, 10e3, 1.1)], 2),
    ("nothing (the ADC reads 128)", [lambda t: 0 * t], 0),
]
OFFSETS = [0, 1e3, 2e3, 3e3, 4e3, 4.5e3, 5e3, 6e3, 8e3, 10e3, 12.5e3, 15e3, 20e3, 21e3, 22e3, 23e3,
           24e3, 24.9e3, 26e3, 28e3, 29e3, 30e3, 35e3, 40e3, 50e3, 100e3, -10e3, -20e3, -21e3]
AUDIO = [100, 300, 1000, 2000, 3000, 4000, 4300, 4500, 4700, 5000, 6000, 8000, 12000]
SEL_A = 127                           # the selectivity sweep's carrier: full scale


def check_receiver(results):
    """Tests 1-3: the receiver on test signals, bit for bit, and what it measures."""
    ok = True
    print("\n1. THE RECEIVER, BIT FOR BIT (40 ms of each signal; averages from 12 ms on)")
    print(f"   {'test signal':38s} g  bit-exact  average envelope   re on-tune   1 kHz tone (as m)")
    rx = results["rx"]
    for (name, parts, g), r in zip(RX_TESTS, rx):
        avg, (amp,) = tones(r["env"], [1000.0])
        r["avg"], r["amp"] = avg * 2**g, amp * 2**g          # in units of the envelope itself
        rel = f"{db(r['avg'] / rx[0]['avg']):7.1f} dB" if avg > 0 else "      -"
        m = f"{amp / avg:.4f}" if avg > 0 and not name.startswith("the same") else "-"
        print(f"   {name:38s} {g}  {'yes' if r['same'] else 'NO':9s} {avg:9.1f} x 2^{g}    {rel}   {m}")
        ok &= r["same"]
    want = GAIN * 80
    print(f"   bare carrier: {rx[0]['avg']:.0f}, expected 473.1 x 80 = {want:.0f} ({(rx[0]['avg'] / want - 1) * 100:+.2f}%)")
    ok &= abs(rx[0]["avg"] / want - 1) < 0.003
    m = rx[1]["amp"] / rx[1]["avg"]
    m_want = 0.5 * response(1000.0)[0]
    print(f"   AM at f_rx: m = {m:.4f}, expected 0.5 x |H(1 kHz)| = {m_want:.4f}")
    ok &= abs(m / m_want - 1) < 0.01
    print("   off tune: the station is a carrier at df and sidebands at df +- 1 kHz (each m/2 = 0.25\n"
          "   of it); the filters let through the most of whichever lands nearest 0 Hz once folded:")
    for r, (name, parts, g) in zip(rx[2:6], RX_TESTS[2:6]):
        df = float(name.split()[2]) * 1e3 * (1 if "higher" in name else -1)
        parts = {"carrier": response(df)[0], "a sideband": 0.25 * max(response(df - 1e3)[0], response(df + 1e3)[0])}
        which = max(parts, key=parts.get)
        meas, theory = db(r["avg"] / rx[1]["avg"]), db(parts[which])
        print(f"   {name}: {meas:6.1f} dB; theory {theory:6.1f} dB (from {which})"
              + ("; below about -75 dB, the test signal's own 8-bit rounding noise is what's left" if theory < -75 else ""))
        ok &= abs(meas - theory) < 1.5 if theory > -70 else meas < -70
    avg, (a1k, a400, a10k) = tones(rx[6]["env"], [1000.0, 400.0, 10000.0])
    print(f"   two stations: the 1 kHz tone {a1k * 4 / (0.5 * GAIN * 40 * response(1000.0)[0]) * 100:.2f}% of "
          f"what it is alone; the other's 400 Hz {db(a400 / a1k):.1f} dB and the 10 kHz whistle "
          f"{db(a10k / a1k):.1f} dB below it")
    ok &= db(a400 / a1k) < -70 and db(a10k / a1k) < -70
    ok &= not np.any(rx[7]["env"])
    print(f"   nothing: all {len(rx[7]['env'])} samples are 0: {'yes' if not np.any(rx[7]['env']) else 'NO'}")

    print("\n2. SELECTIVITY: a full-scale carrier (127 codes) away from f_rx, envelope re on-tune")
    print("   offset (kHz)    measured   CIC x FIR (theory)  bit-exact")
    base = results["sel"][0]["avg"]
    sel = []
    for df, r in zip(OFFSETS, results["sel"]):
        meas, theory = db(r["avg"] / base), db(response(df)[0])
        sel.append((df, meas, theory))
        note = "  (what's left: the test signal's 8-bit rounding)" if theory < -75 else ""
        print(f"   {df / 1e3:9.1f}  {show_db(r['avg'] / base, 'all 0')}  {show_db(response(df)[0], 'a null')}"
              f"   {'yes' if r['same'] else 'NO':>9s}{note}")
        ok &= r["same"]
        if theory > -60:
            ok &= abs(meas - theory) < 0.5
        else:
            ok &= meas < -60
    print(f"   on tune: {base:.0f} = {base / SEL_A:.2f} per code (expected {GAIN:.2f})")

    print("\n3. AUDIO FREQUENCY RESPONSE: AM, m = 0.5, the tone's size re m x the average")
    print("   tone (Hz)       measured   CIC x FIR (theory)  bit-exact")
    aud = []
    for fm, r in zip(AUDIO, results["aud"]):
        avg, (amp,) = tones(r["env"], [fm])
        meas, theory = db(amp / (0.5 * avg)), db(response(fm)[0])
        aud.append((fm, meas, theory))
        print(f"   {fm:9.0f}  {show_db(amp / (0.5 * avg), 'none')}  {show_db(response(fm)[0], 'a null')}"
              f"   {'yes' if r['same'] else 'NO':>9s}")
        ok &= r["same"]
        if theory > -40:
            ok &= abs(meas - theory) < 0.1
    f = np.arange(0, 12500, 1.0)
    h = db(response(f))
    print(f"   -> 0 to 4 kHz within {-h[:4001].min():.2f} dB; -3 dB at {f[np.argmax(h < -3)]:.0f} Hz; "
          f"-6 dB at {f[np.argmax(h < -6)]:.0f} Hz")
    return ok, sel, aud


def spectrum(dac):
    """The DAC's spectrum (Hann window), in dB re its biggest line, and the frequencies."""
    x = dac.astype(float) - 128
    s = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    return np.fft.rfftfreq(len(x), 1 / F_CLK), db(s / s.max())


def line(f, s, at, width=20):
    """The strongest point of spectrum s within `width` Hz of `at`: (its frequency, level)."""
    near = np.abs(f - at) <= width
    k = np.argmax(np.where(near, s, -999))
    return f[k], s[k]


def box_fundamental():
    """The music box table's fundamental and 2nd harmonic, in codes (out of 56)."""
    box = np.floor(56.0 / 1.299038105676658 * (np.sin(6.283185307179586 * i256 / 256)
                                               + 0.5 * np.sin(12.566370614359172 * i256 / 256)) + 0.5)
    X = np.fft.fft(box) * 2 / 256
    return abs(X[1]), abs(X[2])


def check_transmitter(results):
    """Test 4: the DAC's spectrum, and the receiver at the other end of the cable."""
    ok = True
    fc = TW_1MHZ * F_CLK / 2**32
    f_tone = 85899 * F_CLK / 2**32
    f_e4 = 28315 * F_CLK / 2**32
    print("\n4. THE TRANSMITTER: the DAC's spectrum near the carrier (0.1 s: 10 Hz resolution),\n"
          "   and what the receiver makes of it through the cable (code = 0.776 DAC + 27.5)")
    for name in ("tone", "melody", "carrier", "off"):
        ok &= results[name]["same"]
    print("   receiver bit-exact on all four: "
          + ("yes" if all(results[n]["same"] for n in ("tone", "melody", "carrier", "off")) else "NO"))

    f, s = spectrum(results["tone"]["dac"])
    fl, _ = line(f, s, fc)
    lo, hi = line(f, s, fc - f_tone), line(f, s, fc + f_tone)
    far = (np.abs(f - fc) > 50) & (np.abs(f - fc) < 5000) & (np.abs(np.abs(f - fc) - f_tone) > 50)
    print(f"   m3, the 1 kHz tone: carrier at {fl:.0f} Hz; sidebands {lo[0] - fl:+.0f} Hz: {lo[1]:.2f} dBc, "
          f"{hi[0] - fl:+.0f} Hz: {hi[1]:.2f} dBc (expected m/2 = 0.4: {db(0.4):.2f} dBc); "
          f"nothing else within 5 kHz above {s[far].max():.0f} dBc")
    ok &= abs(lo[1] - db(0.4)) < 0.2 and abs(hi[1] - db(0.4)) < 0.2 and s[far].max() < -50
    ok &= abs(lo[0] - (fc - f_tone)) <= 10 and abs(hi[0] - (fc + f_tone)) <= 10
    avg, (amp,) = tones(results["tone"]["env"], [f_tone])
    m_want = 0.8 * response(f_tone)[0]
    print(f"     received: carrier {avg * 4:.0f} (expected 473.1 x 0.776 x 69.45 = {GAIN * 0.776 * 70 * 127 / 128:.0f}), "
          f"m = {amp / avg:.4f} (expected 0.8 x |H(1 kHz)| = {m_want:.4f})")
    ok &= abs(amp / avg / m_want - 1) < 0.01 and abs(avg * 4 / (GAIN * 0.776 * 70 * 127 / 128) - 1) < 0.01

    f, s = spectrum(results["melody"]["dac"])
    fl, _ = line(f, s, fc)
    b1, b2 = box_fundamental()
    tau = 2**16 / F_CLK / -np.log(1 - 1 / 256)          # the loudness's time constant: 0.335 s
    t = np.arange(len(results["melody"]["dac"])) / F_CLK
    w = np.hanning(len(t))
    decay = np.sum(w * np.exp(-t / tau)) / np.sum(w)     # what the window sees of the decay
    for k, (b, name) in enumerate(((b1, "E4"), (b2, "E5, its octave")), 1):
        want = db(0.5 * 0.8 * b / 56 * 255 / 256 * decay)
        lo, hi = line(f, s, fc - k * f_e4), line(f, s, fc + k * f_e4)
        print(f"   the melody's first note, {name}: sidebands {lo[0] - fl:+.0f} Hz: {lo[1]:.2f} dBc, "
              f"{hi[0] - fl:+.0f} Hz: {hi[1]:.2f} dBc (expected {want:.2f})")
        ok &= abs(lo[1] - want) < 0.3 and abs(hi[1] - want) < 0.3
        ok &= abs(lo[0] - (fc - k * f_e4)) <= 10 and abs(hi[0] - (fc + k * f_e4)) <= 10

    f, s = spectrum(results["carrier"]["dac"])
    near = (np.abs(f - fc) > 50) & (np.abs(f - fc) < 5000)
    env = results["carrier"]["env"][300:]
    print(f"   m1, the bare carrier: nothing within 5 kHz above {s[near].max():.0f} dBc; received "
          f"{env.mean() * 4:.0f}, steady to {env.std() / env.mean() * 100:.3f}% rms")
    ok &= s[near].max() < -60 and env.std() / env.mean() < 1e-3
    dac, env = results["off"]["dac"], results["off"]["env"]
    print(f"   m0, off: DAC always 128: {'yes' if np.all(dac == 128) else 'NO'}; received envelope "
          f"after the filters empty: {env[300:].max()}")
    ok &= np.all(dac == 128) and env[300:].max() == 0

    print("   the receiver tuned 10 kHz above its own transmitter (r52bd3c3: 1.01 MHz), re on-tune;\n"
          "   and the DAC's biggest line 5.5 to 14.5 kHz from the carrier (which the receiver hears):")
    on = GAIN * 0.776 * 70 * 127 / 128
    for name in ("melody", "tone", "carrier"):
        f, s = spectrum(results[name]["dac"])
        band = (np.abs(f - fc) > 5500) & (np.abs(f - fc) < 14500)
        heard = results[name + "_10k"]["env"][300:].mean() * 4 / on
        print(f"     {name:8s} {show_db(heard, 'all 0')}    DAC: "
              + (f"{s[band].max():6.1f} dBc" if s[band].max() > -200 else "nothing"))
        ok &= heard < 10**(-55 / 20) if name != "carrier" else heard < 10**(-100 / 20)
    print("   -> not the receiver's filters (93 dB): the DAC rounds the modulated carrier to 8 bits,\n"
          "      and with 1 MHz exactly 50 samples per cycle, the rounding errors repeat with the\n"
          "      sound, making faint copies of it tens of kHz wide.  A bare carrier is clean.")
    return ok


def tune():
    """The tune, each note's pitch (Hz) and the length of an eighth note, read from am_radio.sv."""
    import re
    src = open(os.path.join(HERE, "am_radio.sv")).read()
    body = src[src.index("TUNE =") + 6:]
    text = "".join(re.findall(r'"([^"]*)"', body[:body.index(";")]))
    pitch = {k: int(v) * F_CLK / 2**32 for k, v in re.findall(r'"([A-G])": note_tw = 32\'d(\d+);', src)}
    eighth = int(re.search(r"EIGHTH = ([\d_]+)", src).group(1).replace("_", "")) / F_CLK
    return [(text[i], int(text[i + 1])) for i in range(0, len(text), 2)], pitch, eighth


NAMES = {"C": "C4", "D": "D4", "E": "E4", "F": "F4", "G": "G4", "A": "A4", "B": "B4", "R": "rest"}


def check_melody(env, seconds):
    """Test 5: the whole melody through the cable; each note's pitch."""
    ok = True
    notes, pitch, eighth = tune()
    print(f"\n5. THE WHOLE MELODY through the cable ({seconds:g} s): each note's pitch, from the "
          f"peak of its spectrum")
    x = env.astype(float)
    t0, heard, errs, rows = 0.0, [], [], []
    delay = 0.003                                       # the receiver's delay (the FIR: 63 / 25 kHz)
    rest_rms = []
    while True:
        for letter, length in notes:
            t1 = t0 + length * eighth
            if t1 > seconds + 1e-6:
                break
            a, b = int((t0 + 0.02 + delay) * FS), int((t1 - 0.045 + delay) * FS)
            seg = x[a:b] - x[a:b].mean()
            if letter == "R":
                rest_rms.append(seg.std())
                heard.append("rest")
            else:
                n = 2**19
                spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), n))
                fr = np.fft.rfftfreq(n, 1 / FS)
                band = (fr > 200) & (fr < 450)              # C4 .. G4, not their octaves
                k = np.argmax(np.where(band, spec, 0))
                d = 0.5 * (spec[k - 1] - spec[k + 1]) / (spec[k - 1] - 2 * spec[k] + spec[k + 1])
                f_meas = fr[k] + d * FS / n                   # between the bins: fit a parabola
                name = min(pitch, key=lambda p: abs(np.log(f_meas / pitch[p])))
                heard.append(NAMES[name])
                errs.append(1200 * np.log2(f_meas / pitch[letter]))
                rows.append((t0, f_meas, pitch[letter]))
                ok &= name == letter
            t0 = t1
        else:
            continue
        break
    want = [NAMES[letter] for letter, _ in notes] * 2
    print("   heard:    " + " ".join(heard))
    ok &= heard == want[:len(heard)]
    print(f"   the score: {'the same' if heard == want[:len(heard)] else 'DIFFERENT'} ({len(heard)} notes, "
          f"the tune and the start of its repeat); pitch errors {min(errs):+.2f} to {max(errs):+.2f} cents")
    ok &= max(abs(e) for e in errs) < 2
    loud = np.median([x[int(r[0] * FS):int((r[0] + 0.2) * FS)].std() for r in rows])
    print(f"   during the rest: {max(rest_rms):.1f} rms, against {loud:.0f} in the notes")
    ok &= max(rest_rms) < 0.02 * loud
    return ok, rows


class FakeSerial:
    """Stands in for serial.Serial in am_radio.py.  The "board" is am_radio.sv in
    Verilator with a cable from its DAC to its ADC: what am_radio.py writes goes to
    uart_rx, and what comes out of uart_tx is what it reads.  (The simulation runs
    about 7 times slower than the real thing, but am_radio.py can't tell.)"""
    def __init__(self, exe):
        self.sim = subprocess.Popen([exe, "adc=loop", "live=1"], stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, bufsize=0)
        self.timeout = 2
        self.written = b""

    def write(self, data):
        self.written += data
        self.sim.stdin.write(data)

    def read(self, n):
        got = b""
        while len(got) < n:
            chunk = os.read(self.sim.stdout.fileno(), n - len(got))
            if not chunk:
                break
            got += chunk
        return got

    def reset_input_buffer(self):
        fd = self.sim.stdout.fileno()
        while select.select([fd], [], [], 0)[0] and os.read(fd, 65536):
            pass

    def close(self):
        self.sim.kill()
        self.sim.wait()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def check_am_radio_py(exe, tmp):
    """Test 6: am_radio.py, start to finish, on the simulated board."""
    import matplotlib.pyplot as plt
    show, plt.show = plt.show, lambda *a, **k: None    # --plot draws, but doesn't open a window
    ok = True
    print("\n6. am_radio.py through a fake serial port (the simulation, with the cable)")
    # decode() first: the samples 1, 16383, 128, 5, with half a sample before them
    # (a high byte, 0x85) and the 128's high byte lost on the way
    got = am_radio.decode(bytes([0x85, 0x01, 0x80, 0x7F, 0xFF, 0x00, 0x05, 0x80])).tolist()
    print(f"   decode(): half a sample, then 1, 16383, 128 (its high byte lost), 5 -> {got}")
    ok &= got == [1, 16383, 5]
    expected = GAIN * 0.776 * 70 * 127 / 128
    for argv, check in [
            (["--seconds", "1"], "melody"),
            (["--source", "tone", "--tx", "7.2e6", "--rx", "7.2e6", "--gain", "2", "--seconds", "0.5",
              "--plot"], "tone"),
            (["--rx", "1.01e6", "--seconds", "0.5"], "off tune")]:
        ser = FakeSerial(exe)
        wav = os.path.join(tmp, "fake.wav")
        log = io.StringIO()
        with contextlib.redirect_stdout(log):
            env, samples, g = am_radio.main(argv + ["--no-play", "-o", wav], ser=ser)
        print(f"   python3 am_radio.py {' '.join(argv)}")
        print("     " + log.getvalue().strip().replace("\n", "\n     "))
        sent = ser.written.decode()
        print(f"     it sent: {sent!r}")
        n_wav = (os.path.getsize(wav) - 44) // 2
        if check == "melody":
            good = (sent == f"t51eb852\nr51eb852\nm2\ng0\ng4\ng{g}\nm2\n" and g in (2, 3)
                    and abs(env.mean() / expected - 1) < 0.03)
        elif check == "tone":
            k = np.argmax(np.abs(np.fft.rfft(env - env.mean())))
            f_loud = k * FS / len(env)
            good = (sent == "t24dd2f1b\nr24dd2f1b\nm3\ng2\nm3\n" and abs(f_loud - 1000) <= 2
                    and abs(env.mean() / expected - 1) < 0.01)
        else:
            print(f"     the station, 10 kHz away: {db(env.mean() / expected):.1f} dB (the transmitter's own "
                  f"8-bit rounding: see test 4)")
            good = g == 0 and env.mean() < expected * 10**(-50 / 20)
        good &= n_wav == int(len(env) * 48000 / FS)
        print(f"     {'as expected' if good else 'NOT AS EXPECTED'}")
        ok &= good
    plt.close("all")
    plt.show = show
    return ok


def g_for(df):
    """The output shift for the selectivity sweep: 2 if the envelope needs it, else 0."""
    return 2 if response(df)[0] * GAIN * SEL_A * 1.05 >= am_radio.FULL else 0


def plot(sel, aud, results, rows, save):
    import matplotlib
    if save:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 3, figsize=(17, 9))
    a = ax[0, 0]
    f = np.linspace(-50e3, 50e3, 4001)
    a.plot(f / 1e3, db(response(f)), "-", linewidth=0.8, label="CIC x FIR (theory)")
    sel = np.array(sel)
    a.plot(sel[:, 0] / 1e3, sel[:, 1], "o", markersize=4, label="FPGA (simulated), full-scale carrier")
    a.set_xlabel("offset from the receive frequency (kHz)")
    a.set_ylabel("envelope re on-tune (dB)")
    a.set_ylim(-130, 5)
    a.set_title("1. selectivity", fontsize=10)
    a.legend(fontsize=8, loc="lower left")
    a.grid(True)
    a = ax[0, 1]
    f = np.linspace(0, 12500, 2501)
    a.plot(f / 1e3, db(response(f)), "-", linewidth=0.8, label="CIC x FIR (theory)")
    aud = np.array(aud)
    a.plot(aud[:, 0] / 1e3, aud[:, 1], "o", markersize=4, label="FPGA (simulated), AM with m = 0.5")
    a.set_xlabel("audio frequency (kHz)")
    a.set_ylabel("recovered tone re m x carrier (dB)")
    a.set_ylim(-100, 5)
    a.set_title("2. audio frequency response", fontsize=10)
    a.legend(fontsize=8, loc="lower left")
    a.grid(True)
    fc = TW_1MHZ * F_CLK / 2**32
    for a, name, title in ((ax[0, 2], "tone", "3. DAC spectrum, m3: the 1 kHz tone"),
                           (ax[1, 0], "melody", "4. DAC spectrum, the melody's first 0.1 s (E4)")):
        f, s = spectrum(results[name]["dac"])
        near = np.abs(f - fc) < 3000
        a.plot((f[near] - fc), s[near], ".-", markersize=2, linewidth=0.5)
        a.set_xlabel("frequency - 1 MHz (Hz)")
        a.set_ylabel("dB re the carrier (dBc)")
        a.set_ylim(-110, 5)
        a.set_title(title, fontsize=10)
        a.grid(True)
    a = ax[1, 1]
    env = results["melody"]["env"][:600] * 4
    a.plot(np.arange(len(env)) / FS * 1e3, env / GAIN, ".-", markersize=3, linewidth=0.5)
    a.set_xlabel("time since power-up (ms)")
    a.set_ylabel("envelope: carrier amplitude (ADC codes)")
    a.set_title("5. received through the cable: the first note, plucked", fontsize=10)
    a.grid(True)
    a = ax[1, 2]
    if rows:
        rows = np.array(rows)
        a.step(rows[:, 0], rows[:, 2], where="post", color="gray", linewidth=1, label="the score")
        a.plot(rows[:, 0], rows[:, 1], "o", markersize=4, label="heard (simulated)")
        a.legend(fontsize=8)
    a.set_xlabel("time (s)")
    a.set_ylabel("pitch (Hz)")
    a.set_title("6. the whole melody, through the cable", fontsize=10)
    a.grid(True)
    plt.tight_layout()
    if save:
        plt.savefig(save, dpi=110)
        print(f"plot saved to {save}")
    else:
        plt.show()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plot", nargs="?", const="", metavar="FILE",
                    help="plot the results (or save the plot to FILE)")
    ap.add_argument("--quick", action="store_true",
                    help="skip the 14 s melody and the fake serial port (about 30 s)")
    args = ap.parse_args()
    exe = build()
    MELODY_S = 14.0                      # the tune (13.6 s), and the start of its repeat

    with tempfile.TemporaryDirectory() as tmp, ThreadPoolExecutor(os.cpu_count()) as pool:
        def from_file(name, codes, g):
            """Test signal in, envelope out; and the model, on the same codes."""
            r = run(exe, tmp, name, 2 * len(codes) + 4000, codes, [(0, f"g{g:x}\n")])
            r["same"] = compare(r, codes, g)
            r["avg"] = r["env"][300:].mean() * 2**g
            return r

        def through_cable(name, clocks, cmds, dac):
            r = run(exe, tmp, name, clocks, "loop", cmds, adc_out=True, dac=dac)
            r["same"] = compare(r, r["adc"], 2)
            return r

        def compare(r, codes, g):
            # ##################################################################
            # ##  KEY LINE: every sample the FPGA sent, against the model.  (The
            # ##  last one or two may still have been on their way out.)
            # ##################################################################
            want = model(codes, g=g)[1]
            n = min(len(r["env"]), len(want))
            r["env"] = r["env"][:n]
            return n >= len(want) - 2 and np.array_equal(r["env"], want[:n])

        jobs = {}
        if not args.quick:
            jobs["ode"] = pool.submit(run, exe, tmp, "ode", int(MELODY_S * F_CLK))
        jobs["rx"] = [pool.submit(from_file, f"rx{i}", codes_of(parts, 0.04), g)
                      for i, (name, parts, g) in enumerate(RX_TESTS)]
        jobs["sel"] = [pool.submit(from_file, f"sel{i}", codes_of([station(SEL_A, df=df)], 0.024), g_for(df))
                       for i, df in enumerate(OFFSETS)]
        jobs["aud"] = [pool.submit(from_file, f"aud{i}", codes_of([station(80, 0.5, fm)], 0.04), 2)
                       for i, fm in enumerate(AUDIO)]
        late, dump = 2_500_000, (2_500_000, 5_000_000)   # DAC: 0.1 s, from 50 ms after the command
        jobs["tone"] = pool.submit(through_cable, "tone", late + 5_100_000, [(0, "m3\n")], dump)
        jobs["melody"] = pool.submit(through_cable, "melody", 5_100_000, [], (0, 5_000_000))
        jobs["carrier"] = pool.submit(through_cable, "carrier", late + 5_100_000, [(0, "m1\n")], dump)
        jobs["off"] = pool.submit(through_cable, "off", late + 5_100_000, [(0, "m0\n")], dump)
        tune_10k = "r%x\n" % am_radio.tuning_word(1.01e6)
        for name, cmd in (("melody", ""), ("tone", "m3\n"), ("carrier", "m1\n")):
            jobs[name + "_10k"] = pool.submit(run, exe, tmp, name + "_10k", 5_000_000, "loop",
                                              [(0, cmd + tune_10k)])
        ok = True
        log6 = io.StringIO()
        if not args.quick:                   # (while the other simulations run)
            with contextlib.redirect_stdout(log6):
                ok &= check_am_radio_py(exe, tmp)
        results = {k: ([j.result() for j in v] if isinstance(v, list) else v.result())
                   for k, v in jobs.items()}

    good, sel, aud = check_receiver(results)
    ok &= good
    ok &= check_transmitter(results)
    rows = []
    if not args.quick:
        good, rows = check_melody(results["ode"]["env"] * 4, MELODY_S)
        ok &= good
        wav = os.path.join(SIMDIR, "ode_to_joy_sim.wav")
        import stream
        stream.save_wav(results["ode"]["env"] * 4 / GAIN, wav, fs=FS)
        print(f"   (that's what the laptop should hear: listen to {os.path.relpath(wav)})")
        print(log6.getvalue(), end="")
    print("\nPASS" if ok else "\nFAIL")
    if args.plot is not None:
        plot(sel, aud, results, rows, args.plot)
    sys.exit(0 if ok else 1)
