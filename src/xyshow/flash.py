#!/usr/bin/env python3
"""Load build/x.bit and build/y.bit into the two Icepi Zeros on this computer, the same way round every time.

    python3 flash.py                 write them into the boards' flash: the show starts at every power-up
    python3 flash.py --sram          load them into the FPGAs' RAM only: quicker, and gone at power-off
    python3 flash.py --list          only show the boards, and which one would be X
    python3 flash.py --x DK0GFLAW --y DP051TLX      choose for yourself

The boards are told apart by their FT231X serial numbers, as in 5.00.  Sorted, the first is X and the second is Y,
so with the same two boards on the same computer the same board is always X, whichever USB port each is in and in
whatever order they were plugged in.  (If the picture comes out turned or mirrored, swap the two cables at the scope:
with both boards cabled to each other, either board can be X.)
"""
import argparse, re, subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
FT231X = (0x0403, 0x6015)                    # the Icepi Zero's USB-UART


def serials():
    """the FT231X serial numbers on USB, sorted"""
    try:
        from serial.tools import list_ports
        found = {p.serial_number for p in list_ports.comports() if (p.vid, p.pid) == FT231X and p.serial_number}
    except ImportError:                      # no pyserial: ask openFPGALoader
        out = subprocess.run(["openFPGALoader", "--scan-usb"], capture_output=True, text=True).stdout
        found = set(re.findall(r"0x0403:0x6015\s+\S+\s+\S+\s+(\S+)", out))
    return sorted(found)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sram", action="store_true", help="load into RAM (gone at power-off) instead of the flash")
    ap.add_argument("--list", action="store_true", help="only list the boards")
    ap.add_argument("--x", help="the X board's FT231X serial number"); ap.add_argument("--y", help="the Y board's")
    a = ap.parse_args()
    sn = serials()
    print("Icepi Zeros (FT231X serial numbers):", " ".join(sn) if sn else "none")
    if a.x or a.y:
        if not (a.x and a.y): sys.exit("give both --x and --y")
        x, y = a.x, a.y
    elif len(sn) == 2:
        x, y = sn
    else:
        sys.exit("found %d boards: plug in exactly two, or choose with --x SERIAL --y SERIAL" % len(sn))
    print("X (role 0, the scope's X input) = %s, Y (role 1) = %s" % (x, y))
    if a.list: return
    for role, s in (("x", x), ("y", y)):
        bit = os.path.join(HERE, "build", role + ".bit")
        if not os.path.exists(bit): sys.exit("%s is missing: run make first" % bit)
        cmd = ["openFPGALoader", "-b", "icepi-zero", "--usb-serial-num", s] + ([] if a.sram else ["-f"]) + [bit]
        print("$", " ".join(cmd), flush=True)
        if subprocess.run(cmd).returncode: sys.exit("openFPGALoader failed on %s" % s)
    print("done: X is %s, Y is %s" % (x, y))


if __name__ == "__main__":
    main()
