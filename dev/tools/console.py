"""Instructor's helper: drive a LiteX serial console (BIOS or the firmware's
shell) from Python.

    c = Console()                     # /dev/ttyUSB0, 115200
    print(c.cmd("mem_read 0xf0001000 4"))
"""
import re
import time

import serial

PROMPT = re.compile(rb"(litex|adda)\S*> ")
ANSI = re.compile(rb"\x1b\[[0-9;]*m")


class Console:
    def __init__(self, port="/dev/ttyUSB0", baud=115200):
        self.ser = serial.Serial(port, baud, timeout=0.1)
        time.sleep(0.05)
        self.ser.reset_input_buffer()

    def read_until_prompt(self, timeout=5.0):
        buf = b""
        t0 = time.time()
        while time.time() - t0 < timeout:
            buf += self.ser.read(4096)
            if PROMPT.search(ANSI.sub(b"", buf)[-40:]):
                break
        return ANSI.sub(b"", buf).decode("ascii", "replace")

    def sync(self, tries=5):
        for _ in range(tries):
            self.ser.write(b"\r")
            out = self.read_until_prompt(1.0)
            if PROMPT.search(out.encode()):
                return out
        raise RuntimeError("no prompt; got %r" % out[-200:])

    def cmd(self, line, timeout=5.0):
        self.ser.reset_input_buffer()
        self.ser.write(line.encode() + b"\r")
        out = self.read_until_prompt(timeout)
        # drop the echoed command and the trailing prompt
        lines = out.replace("\r", "").split("\n")
        return "\n".join(lines[1:-1])

    def close(self):
        self.ser.close()
