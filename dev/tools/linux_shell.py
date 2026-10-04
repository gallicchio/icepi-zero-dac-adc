"""Instructor's helper: log in to the board's Linux serial console and run
shell commands from Python.

    sh = Shell(baud=460800)          # waits for the login prompt if needed
    print(sh.run("uname -a"))
"""
import re
import time

import serial

PROMPT = b"# "


class Shell:
    def type(self, text):
        """Send text the way a person types: in small pieces.  The board's UART
        receive FIFO is small, and the 2021 kernel only polls it, so a burst of
        more than ~16 characters at 460800 baud loses some."""
        data = text.encode()
        for i in range(0, len(data), 8):
            self.ser.write(data[i:i + 8])
            self.ser.flush()
            time.sleep(0.01)

    def __init__(self, port="/dev/ttyUSB0", baud=460800, boot_timeout=180):
        self.ser = serial.Serial(port, baud, timeout=0.2)
        self.log = b""
        self._login(boot_timeout)

    def _read_until(self, marks, timeout):
        buf = b""
        t0 = time.time()
        while time.time() - t0 < timeout:
            buf += self.ser.read(4096)
            for m in marks:
                if m in buf[-200:]:
                    self.log += buf
                    return buf, m
        self.log += buf
        return buf, None

    def _login(self, timeout):
        self.ser.write(b"\x03")          # Ctrl-C: abandon any half-typed command
        time.sleep(0.1)
        self.ser.write(b"\r")
        buf, m = self._read_until([b"login: ", PROMPT], timeout)
        if m == b"login: ":
            self.type("root\r")
            buf, m = self._read_until([PROMPT], 20)
        if m is None:
            raise RuntimeError("no shell prompt; last output: %r" % buf[-300:])
        # quieter, predictable prompt.  (Its own echo contains "# ", so wait for a marker.)
        self.type("stty -echo; PS1='# '; echo READY$((6*7))\r")
        self._read_until([b"READY42"], 10)
        self._read_until([PROMPT], 5)
        self.n = 0

    def run(self, cmd, timeout=30):
        # End with a marker of our own, so that a "# " in the output can't end the wait early
        self.n += 1
        end = "@@END%d@@" % self.n
        self.ser.reset_input_buffer()
        self.type(cmd + "; echo @@END''%d@@\r" % self.n)    # typed with '' so its echo can't match
        buf, m = self._read_until([end.encode()], timeout)
        out = buf.decode("utf-8", "replace").replace("\r", "")
        out = out.split(end)[0]
        self._read_until([PROMPT], 5)
        return out.strip("\n")

    def close(self):
        self.ser.close()
