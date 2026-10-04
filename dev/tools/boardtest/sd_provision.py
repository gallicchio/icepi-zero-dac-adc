#!/usr/bin/env python3
"""Instructor's tool: give one Icepi Zero's micro-SD card Part 8's Linux, and test it.

    python3 sd_provision.py SERIAL LOGDIR [--boots 3] [--skip-install]
    (run from $ADDA/tools/linux-on-litex-vexriscv, after make_sd_installer.sh)

The board must have Part 8's SoC (icepi_zero_adda.bit) in its flash, and be at the BIOS
prompt (litex>), as it is after power-up with a card that has no boot.json, or be running
Linux on its console.  Nothing here uses openFPGALoader, so several boards can run this at
once (a bitstream load on one board has stalled another's serial-boot upload).

  1. "reboot", and answer the BIOS's serial-boot request with images_install/ (8.7's
     installer: the RAM-disk system plus /boot/sd and /root/install-sd.sh)
  2. log in, run install-sd.sh (it ERASES the card), then do 8.7's tuning on the card's
     root file system: five start-up services moved to /etc/init.d/off, and S90adda added
  3. BOOTS times: boot from the card, time reset -> login, log in, and check the root
     device, the driver, and the serial link both ways (random data, compared by md5).
     --reset reboot: type "reboot"; flash: openFPGALoader -r, which reloads the FPGA from
     its flash as at power-up (one board at a time, under a lock); mix: the first boot by
     "reboot", the rest from flash.

Everything received goes to LOGDIR/SERIAL.log with timestamps; a summary to LOGDIR/SERIAL.json.
"""
import argparse
import base64
import fcntl
import subprocess
import hashlib
import json
import os
import re
import sys
import threading
import time

import serial
from litex.tools import litex_term as lt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from linux_shell import Shell, PROMPT


class _NoConsole:
    def configure(self): pass
    def unconfigure(self): pass


lt.Console = _NoConsole

ap = argparse.ArgumentParser()
ap.add_argument("serial")
ap.add_argument("logdir")
ap.add_argument("--baud", type=int, default=460800)
ap.add_argument("--boots", type=int, default=3)
ap.add_argument("--skip-install", action="store_true", help="the card is done: just test")
ap.add_argument("--skip-upload", action="store_true", help="the installer system is already running")
ap.add_argument("--reset", choices=("reboot", "flash", "mix"), default="mix")
a = ap.parse_args()

os.makedirs(a.logdir, exist_ok=True)
PORT = "/dev/serial/by-id/usb-FTDI_FT231X_USB_UART_%s-if00-port0" % a.serial
logf = open(os.path.join(a.logdir, a.serial + ".log"), "ab")
T0 = time.time()
summary = {"serial": a.serial, "start": time.strftime("%H:%M:%S"), "boots": []}


def note(msg):
    line = "[%8.2f] %s" % (time.time() - T0, msg)
    logf.write(b"\n" + line.encode() + b"\n")
    logf.flush()
    print("%s %s" % (a.serial, line), flush=True)


def save():
    json.dump(summary, open(os.path.join(a.logdir, a.serial + ".json"), "w"), indent=1)


def fail(msg):
    note("FAILED: " + msg)
    summary["result"] = "FAILED: " + msg
    save()
    os._exit(2)


ser = serial.Serial(PORT, a.baud, timeout=0.1)


def read_until(marks, timeout):
    """Read, logging everything, until one of marks appears; return (text, mark)."""
    buf = b""
    t1 = time.time()
    while time.time() - t1 < timeout:
        d = ser.read(4096)
        if d:
            logf.write(d)
            logf.flush()
            new = buf[-64:] + d                 # all that arrived, plus a mark's length before it
            buf += d
            for m in marks:
                if m in new:
                    return buf, m
    return buf, None


def shell(busy_timeout=60):
    """A linux_shell.Shell on our own (already open) port.  After logging in, wait for a
    marker that only the board can print ("SY""NC" typed, SYNC echoed back): the shell
    is slow to start, and a command typed before its stty -echo has run is echoed, and
    then cut short by the next prompt.  A command still running delays the marker."""
    sh = Shell.__new__(Shell)
    sh.ser, sh.log = ser, b""
    sh._login(30)
    for _ in range(2):
        sh.type('echo "SY""NC"\r')
        buf, m = read_until([b"SYNC"], busy_timeout)
        if m is None:
            fail("no answer from the shell: %r" % buf[-200:])
        read_until([PROMPT], 5)
    time.sleep(0.3)
    ser.reset_input_buffer()
    return sh


def run(sh, cmd, timeout=60):
    out = sh.run(cmd, timeout)
    logf.write(("\n$ %s\n%s\n" % (cmd, out)).encode())
    logf.flush()
    return out


def get_to_reboot():
    """Send 'reboot' from whatever the console is showing: the BIOS or Linux."""
    ser.reset_input_buffer()
    ser.write(b"\x03\r")
    buf, m = read_until([b"litex", b"login: ", PROMPT], 5)
    if m == b"litex":
        ser.write(b"reboot\r")
    elif m in (b"login: ", PROMPT):
        sh = shell()
        sh.type("reboot\r")
    else:
        fail("no BIOS or Linux prompt on the console: %r" % buf[-200:])


# ---- 1. serial boot of the installer -------------------------------------------------
if not a.skip_install and not a.skip_upload:
    note("rebooting into a serial boot of images_install/")
    term = lt.LiteXTerm(False, None, None, "images_install/boot.json", False)
    term.port = ser
    get_to_reboot()
    found, t1 = False, time.time()
    while not found and time.time() - t1 < 60:
        for c in ser.read(4096):
            logf.write(bytes([c]))
            if term.detect_magic(bytes([c])):
                found = True
                break
    if not found:
        fail("no serial-boot request within 60 s of reboot")
    note("serial-boot request seen; uploading")
    done = threading.Event()
    threading.Thread(target=lambda: (done.wait(900) or fail("upload stalled (15 min)")), daemon=True).start()
    ser.timeout = None
    t_up = time.time()
    term.answer_magic()
    done.set()
    ser.timeout = 0.1
    summary["upload_s"] = round(time.time() - t_up, 1)
    note("upload done in %.0f s" % summary["upload_s"])
    buf, m = read_until([b"login: "], 300)
    if m is None:
        fail("installer system did not reach login: %r" % buf[-300:])
    note("installer system up")

if not a.skip_install:
    # ---- 2. write the card -------------------------------------------------------------
    sh = shell(busy_timeout=900)
    if "/boot/sd" not in run(sh, "ls -d /boot/sd"):
        fail("not the installer system (no /boot/sd)")
    run(sh, "umount /mnt/boot /mnt/root 2>/dev/null; sync; true")       # after an interrupted run
    t_in = time.time()
    out = run(sh, "/root/install-sd.sh 2>&1; echo EXIT=$?", 1200)
    summary["install_s"] = round(time.time() - t_in, 1)
    if "EXIT=0" not in out or "Done." not in out:
        fail("install-sd.sh: %r" % out[-400:])
    note("install-sd.sh done in %.0f s" % summary["install_s"])
    out = run(sh, "mount -t ext2 /dev/mmcblk0p2 /mnt/root && cd /mnt/root/etc/init.d && mkdir -p off && "
                  "mv S01syslogd S02klogd S02sysctl S40network S50crond off/ && "
                  "printf '#!/bin/sh\\n# load the ADC/DAC driver at boot\\n[ \"$1\" = start ] && insmod /root/adda.ko\\n' > S90adda && "
                  "chmod +x S90adda && ls; cd /; umount /mnt/root && sync; echo EXIT=$?", 120)
    if "EXIT=0" not in out or "S90adda" not in out:
        fail("tuning: %r" % out[-400:])
    note("tuning done: %s" % " ".join(out.split()[:-1]))
    summary["installed"] = time.strftime("%H:%M:%S")
    save()

def reload_from_flash():
    """openFPGALoader -r: the FPGA reloads itself from flash, as at power-up.  The port
    vanishes meanwhile; reopen it as soon as it is back."""
    global ser
    ser.close()
    with open("/tmp/sd_provision.lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        t = time.time()
        subprocess.run(["openFPGALoader", "-b", "icepi-zero", "--usb-serial-num", a.serial, "-r"],
                       capture_output=True)
    while True:
        try:
            ser = serial.Serial(PORT, a.baud, timeout=0.1)
            return t
        except (serial.SerialException, OSError):
            if time.time() - t > 30:
                fail("port did not come back after openFPGALoader -r")
            time.sleep(0.02)


# ---- 3. boot from the card, and test ---------------------------------------------------------
for k in range(a.boots):
    how = "flash" if a.reset == "flash" or (a.reset == "mix" and k > 0) else "reboot"
    note("boot %d from the card (%s)" % (k + 1, how))
    if how == "reboot":
        get_to_reboot()
        buf0, m = read_until([b"BIOS CRC passed"], 120)
        if m is None:
            fail("no BIOS banner after reboot")
        t_reset = time.time()
    else:
        t_reset = reload_from_flash()
        buf0 = b""
    buf, m = read_until([b"login: "], 300)
    if m is None:
        fail("boot %d: no login prompt within 300 s; last: %r" % (k + 1, buf[-300:]))
    boot = {"how": how, "reset_to_login_s": round(time.time() - t_reset, 1)}
    text = (buf0 + buf).decode("utf-8", "replace")
    boot["from_sd_seen"] = "Booting from SDCard" in text and "Copying Image" in text
    boot["adda_ready"] = "ADC/DAC peripherals ready" in text
    sh = shell()
    boot["cmdline_root"] = "root=/dev/mmcblk0p2" in run(sh, "cat /proc/cmdline")
    boot["root_mounted"] = "/dev/root" in run(sh, "mount | grep ' / '") or "mmcblk0p2" in run(sh, "mount")
    boot["services"] = run(sh, "ls /etc/init.d | tr '\\n' ' '")
    boot["adda_sysfs"] = "funcgen" in run(sh, "ls /sys/bus/platform/devices/f0002000.adda/")
    boot["uname"] = run(sh, "uname -r")
    # board -> PC: 32 kB of random bytes as base64, checked against the board's md5
    run(sh, "dd if=/dev/urandom of=/tmp/r bs=1024 count=32 2>/dev/null")
    want = run(sh, "md5sum /tmp/r").split()[0]
    b64 = run(sh, "base64 /tmp/r", 60)
    try:
        got = hashlib.md5(base64.b64decode(re.sub(r"\s", "", b64))).hexdigest()
    except Exception as e:
        got = "undecodable: %s" % e
    boot["board_to_pc_32k_ok"] = (got == want)
    # PC -> board: 4 kB typed in as a base64 here-document, checked by the board's md5
    data = os.urandom(4096)
    lines = base64.encodebytes(data).decode().splitlines()
    sh.type("base64 -d > /tmp/w << 'END'\r")
    for ln in lines:
        sh.type(ln + "\r")
    sh.type("END\r")
    read_until([PROMPT], 20)
    boot["pc_to_board_4k_ok"] = run(sh, "md5sum /tmp/w").split()[0] == hashlib.md5(data).hexdigest()
    boot["uptime"] = run(sh, "cat /proc/uptime")
    ok = all(boot[x] for x in ("adda_ready", "cmdline_root", "root_mounted", "adda_sysfs",
                               "board_to_pc_32k_ok", "pc_to_board_4k_ok"))
    boot["ok"] = ok
    summary["boots"].append(boot)
    save()
    note("boot %d: %s, %.1f s reset -> login; %s" % (k + 1, "OK" if ok else "PROBLEM", boot["reset_to_login_s"],
                                                     {x: y for x, y in boot.items() if y is False}))
summary["result"] = "OK" if all(b["ok"] for b in summary["boots"]) else "PROBLEMS"
summary["end"] = time.strftime("%H:%M:%S")
save()
note("result: " + summary["result"])
