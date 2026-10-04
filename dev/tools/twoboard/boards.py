"""Instructor's helper for several Icepi Zeros on one PC: each board is addressed by
its FT231X serial number, never by /dev/ttyUSBn (those numbers move whenever a board
re-enumerates).

    import boards
    boards.load("JLC1", "probe_0.7.bit")
    t, codes = boards.capture("JLC1")
"""
import os
import subprocess
import time

import numpy as np
import serial

SERIAL = {"JLC1": "DP0525BU", "JLC2": "DP051TLX", "JLC3": "DP0525LR", "JLC4": "DP0524FJ"}
N = 16384


def port(name):
    return "/dev/serial/by-id/usb-FTDI_FT231X_USB_UART_%s-if00-port0" % SERIAL.get(name, name)


def _wait_port(name, timeout=15):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if os.path.exists(port(name)):
            try:
                serial.Serial(port(name), 115200).close()
                return
            except serial.SerialException:
                pass
        time.sleep(0.05)
    raise RuntimeError("port of %s did not come back" % name)


def load(name, bit, flash=False):
    """Load a bitstream into one board (SRAM, or the SPI flash with flash=True)."""
    cmd = ["openFPGALoader", "-b", "icepi-zero", "--usb-serial-num", SERIAL.get(name, name)]
    r = subprocess.run(cmd + (["-f"] if flash else []) + [bit], capture_output=True, text=True)
    if "DONE" not in r.stdout + r.stderr:
        raise RuntimeError("load of %s into %s failed:\n%s" % (bit, name, r.stdout + r.stderr))
    time.sleep(0.3)
    _wait_port(name)


def reset(name):
    """Make one board reload its configuration from flash, as at power-up."""
    subprocess.run(["openFPGALoader", "-b", "icepi-zero", "--usb-serial-num", SERIAL.get(name, name), "-r"],
                   capture_output=True)
    time.sleep(0.3)
    _wait_port(name)


def capture(name, d=0, retries=20):
    """capture.sv's protocol: one hex digit D, then 16384 ADC samples at 25 MS/s / 2^D."""
    for _ in range(retries):
        try:
            with serial.Serial(port(name), 1_000_000, timeout=2) as s:
                time.sleep(0.05)
                s.reset_input_buffer()
                s.write(b"%x" % d)
                raw = s.read(N)
            if len(raw) == N:
                return np.arange(N) / (25e6 / 2**d), np.frombuffer(raw, np.uint8).astype(int)
        except serial.SerialException:
            pass
        time.sleep(0.2)
    raise RuntimeError("no capture from %s" % name)
