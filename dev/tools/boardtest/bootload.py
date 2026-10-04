#!/usr/bin/env python3
"""Serial-boot a LiteX SoC by answering the BIOS's request as the FPGA starts.

serialboot.py types `serialboot` at the litex> prompt.  The Linux SoC of Part 8
never shows that prompt when its micro-SD slot is empty (its BIOS spends ~17
minutes trying to wake a card), so this one listens from the start instead.
Start it, *then* load the bitstream (or `openFPGALoader -r`):

    python3 bootload.py images_adda/boot.json boot.log --read 120 &
    openFPGALoader -b icepi-zero build/icepi_zero_adda/gateware/icepi_zero_adda.bit

It reopens /dev/ttyUSB0 whenever it vanishes (loading a bitstream takes the
port away), closing the old handle first: a handle left open makes the port
come back as /dev/ttyUSB1.  Everything received goes to the log file with
timestamps (seconds since start).
"""
import argparse
import time

import serial
from litex.tools import litex_term as lt


class _NoConsole:
    def configure(self): pass
    def unconfigure(self): pass


lt.Console = _NoConsole

ap = argparse.ArgumentParser()
ap.add_argument("images", help="boot.json")
ap.add_argument("log")
ap.add_argument("--baud", type=int, default=460800)
ap.add_argument("--port", default="/dev/ttyUSB0")
ap.add_argument("--read", type=float, default=0, help="keep logging this many seconds after the upload")
ap.add_argument("--wait", type=float, default=60, help="give up if no request comes in this long")
a = ap.parse_args()

term = lt.LiteXTerm(False, None, None, a.images, False)
logf = open(a.log, "wb")
t0 = time.time()


def log(b):
    logf.write(b)
    logf.flush()


found = False
while not found:
    if time.time() - t0 > a.wait:
        raise SystemExit("no serial-boot request in %g s" % a.wait)
    try:
        term.port = serial.Serial(a.port, a.baud, timeout=0.05)
    except serial.SerialException:
        time.sleep(0.005)
        continue
    log(b"\n[%.3f port open]\n" % (time.time() - t0))
    try:
        while time.time() - t0 < a.wait and not found:
            for c in term.port.read(4096):
                log(bytes([c]))
                if term.detect_magic(bytes([c])):
                    found = True
                    break
    except serial.SerialException:
        term.port.close()
        log(b"\n[%.3f port lost]\n" % (time.time() - t0))
log(b"\n[%.3f request seen, uploading]\n" % (time.time() - t0))
term.port.timeout = None
term.answer_magic()
log(b"\n[%.3f upload done]\n" % (time.time() - t0))
term.port.timeout = 0.2
t1 = time.time()
while time.time() - t1 < a.read:
    d = term.port.read(4096)
    if d:
        log(b"[%.3f]" % (time.time() - t0) + d)
term.port.close()
