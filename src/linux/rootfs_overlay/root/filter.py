# filter.py -- 7.04's filter peripheral from MicroPython on the board's own Linux (3.01).
#   micropython filter.py lowpass            7.01's 2 MHz low-pass (the firmware's preset)
#   micropython filter.py edge               [-1 2 -1]
#   micropython filter.py rc 4               7.02's one-pole, time constant 2^4 samples
#   micropython filter.py b 4096 4096        any taps, as integers x 8192 (Q2.13)
#   micropython filter.py a -7680            feedback taps a1 a2 .. (also x 8192)
#   micropython filter.py src 1 | out 0 | tone 1000000 | on | off | show
# Several at once:  micropython filter.py lowpass src 1 on
#
# The addresses come from the build's csr.csv: "csr_base,filter,0xf000f800" (the filter
# is pinned to the last CSR slot, in the Chapter 2 SoC and this Linux one alike), and
# its registers follow in order, 4 bytes each.  Needs root for /dev/mem, as 3.01's
# mem32 did, and mem32 reads come back signed, hence the masking.  No driver: this is
# the quick, address-in-the-script way that 3.02 argued against for an instrument.
import sys
import machine

FILTER = 0xf000f800
B, A, SRC, OUT, TONE, DAC_SOURCE, STATUS = [FILTER + o for o in (0x00, 0x40, 0x50, 0x54, 0x58, 0x5c, 0x60)]

LOWPASS = [-12, 8, 87, 289, 625, 1020, 1344, 1470, 1344, 1020, 625, 289, 87, 8, -12]
EDGE = [-8192, 16384, -8192]
SRC_NAMES = ["ADC", "impulse", "step", "noise", "tone"]


def write(addr, value):
    machine.mem32[addr] = value & 0xffffffff


def read(addr):
    return machine.mem32[addr] & 0xffffffff


def read16(addr):
    v = read(addr) & 0xffff
    return v - 65536 if v >= 32768 else v


def load(base, taps, n):
    # ##########################################################################
    # ##  KEY LINE: a coefficient is a 32-bit store to base + 4k, nothing more.
    # ##########################################################################
    for k in range(n):
        write(base + 4 * k, taps[k] if k < len(taps) else 0)


def show():
    print("filter: b =", " ".join(str(read16(B + 4 * k)) for k in range(16)))
    print("        a =", " ".join(str(read16(A + 4 * k)) for k in range(4)), "  (x 8192)")
    status = read(STATUS)
    print("        src %s, out %s, tone %d Hz; the DAC plays %s%s%s" % (
        SRC_NAMES[read(SRC)] if read(SRC) < 5 else "?",
        "the input" if read(OUT) else "the output",
        (read(TONE) * 25000000 + 2**31) // 2**32,
        "the filter" if read(DAC_SOURCE) else "the function generator ('on' to switch)",
        ", running" if status & 1 else "", ", clipped" if status & 2 else ""))


def numbers(args):
    """Take the leading integers off args."""
    taken = []
    while args and (args[0].lstrip("-").isdigit()):
        taken.append(int(args.pop(0)))
    return taken


args = sys.argv[1:]
if not args:
    print("usage: micropython filter.py lowpass | edge | rc K | b .. | a .. | src N | out N | tone HZ | on | off | show")
while args:
    cmd = args.pop(0)
    if cmd == "lowpass":
        load(B, LOWPASS, 16); load(A, [], 4)
    elif cmd == "edge":
        load(B, EDGE, 16); load(A, [], 4)
    elif cmd == "rc":
        k = numbers(args)[0]                      # y += (x - y) / 2^K
        load(B, [8192 >> k], 16); load(A, [-(8192 - (8192 >> k))], 4)
    elif cmd == "b":
        load(B, numbers(args), 16)
    elif cmd == "a":
        load(A, numbers(args), 4)
    elif cmd == "src":
        write(SRC, numbers(args)[0])
    elif cmd == "out":
        write(OUT, numbers(args)[0])
    elif cmd == "tone":
        write(TONE, numbers(args)[0] * 2**32 // 25000000)
    elif cmd == "on":
        write(DAC_SOURCE, 1)
    elif cmd == "off":
        write(DAC_SOURCE, 0)
    elif cmd != "show":
        print("filter.py: what is '%s'?" % cmd)
show()
