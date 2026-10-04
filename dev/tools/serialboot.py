"""Instructor's helper: serial-boot a LiteX SoC without an interactive terminal.

Uses litex_term's own upload code, minus its keyboard console (which needs a
real TTY).  Assumes the BIOS is sitting at its litex> prompt.

    python3 serialboot.py --kernel ../litex/firmware/firmware.bin
    python3 serialboot.py --images $ADDA/tools/linux-on-litex-vexriscv/images/boot.json --baud 460800
    python3 serialboot.py --load soc.bit --port /dev/ttyUSB1 --images ...   # load the SoC first,
                          # and answer the BIOS's own serial-boot request (before it tries the SD card)
"""
import argparse
import glob
import os
import subprocess
import sys
import time

from litex.tools import litex_term as lt


class _NoConsole:
    def configure(self): pass
    def unconfigure(self): pass


lt.Console = _NoConsole


def usb_serial(port):
    """The FTDI chip's serial number, from /dev/serial/by-id, for openFPGALoader."""
    for link in glob.glob("/dev/serial/by-id/*"):
        if os.path.realpath(link) == os.path.realpath(port):
            return link.split("_")[-1].split("-")[0]


def serialboot(port="/dev/ttyUSB0", baud=115200, kernel=None, images=None,
               kernel_adr="0x40000000", echo=True, read_after=0, load=None):
    term = lt.LiteXTerm(False, kernel, kernel_adr if kernel else None, images, False)
    if load:
        # openFPGALoader takes the FTDI chip from the serial driver, so open the port after it
        subprocess.check_call(["openFPGALoader", "-b", "icepi-zero", "--usb-serial-num", usb_serial(port), load])
        for _ in range(50):
            try:
                term.open(port, baud)
                break
            except Exception:
                time.sleep(0.05)
        term.port.timeout = 0.2
    else:
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
    ap.add_argument("--load", help="first load this bitstream into the board on --port")
    a = ap.parse_args()
    serialboot(a.port, a.baud, a.kernel, a.images, a.kernel_adr, read_after=a.read, load=a.load)
