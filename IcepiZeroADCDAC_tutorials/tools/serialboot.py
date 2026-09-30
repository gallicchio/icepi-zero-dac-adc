"""Instructor's helper: serial-boot a LiteX SoC without an interactive terminal.

Uses litex_term's own upload code, minus its keyboard console (which needs a
real TTY).  Assumes the BIOS is sitting at its litex> prompt.

    python3 serialboot.py --kernel ../litex/firmware/firmware.bin
    python3 serialboot.py --images ~/openfpga/linux-on-litex-vexriscv/images/boot.json --baud 460800
"""
import argparse
import sys
import time

from litex.tools import litex_term as lt


class _NoConsole:
    def configure(self): pass
    def unconfigure(self): pass


lt.Console = _NoConsole


def serialboot(port="/dev/ttyUSB0", baud=115200, kernel=None, images=None,
               kernel_adr="0x40000000", echo=True, read_after=0):
    term = lt.LiteXTerm(False, kernel, kernel_adr if kernel else None, images, False)
    term.open(port, baud)
    term.port.timeout = 0.2
    term.port.write(b"\r")
    time.sleep(0.3)
    term.port.reset_input_buffer()
    term.port.write(b"serialboot\r")
    t0 = time.time()
    while time.time() - t0 < 10:
        c = term.port.read(1)
        if echo and c:
            sys.stdout.buffer.write(c)
            sys.stdout.flush()
        if term.detect_magic(c):
            term.port.timeout = None
            term.answer_magic()
            break
    else:
        term.close()
        raise RuntimeError("no serial-boot request from the BIOS")
    # keep listening, e.g. to catch a kernel's boot messages
    term.port.timeout = 0.2
    t0 = time.time()
    while time.time() - t0 < read_after:
        c = term.port.read(4096)
        if c:
            sys.stdout.buffer.write(c)
            sys.stdout.flush()
    term.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyUSB0")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--kernel")
    ap.add_argument("--kernel-adr", default="0x40000000")
    ap.add_argument("--images")
    ap.add_argument("--read", type=float, default=0, help="keep printing output for this many seconds")
    a = ap.parse_args()
    serialboot(a.port, a.baud, a.kernel, a.images, a.kernel_adr, read_after=a.read)
