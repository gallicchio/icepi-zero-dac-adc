"""Instructor's test of make_modem_linux.py's SoC: Linux's /dev/ttyLXU1 through the cable.

    python3 linux_modem_test.py PORT_TX [PORT_RX]     (one port: a board looped back to itself)
"""
import sys, time, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, ".."))
from linux_shell import Shell

ptx = sys.argv[1]; prx = sys.argv[2] if len(sys.argv) > 2 else ptx
tx = Shell(port=ptx, baud=460800, boot_timeout=400)
rx = tx if prx == ptx else Shell(port=prx, baud=460800, boot_timeout=400)
def show(sh, cmd, t=30):
    out = sh.run(cmd, t); print("[%s] # %s" % ("A" if sh is tx else "B", cmd)); print(out) if out else None; sys.stdout.flush(); return out
for sh in {id(tx): tx, id(rx): rx}.values():
    show(sh, "dmesg | grep -i -E 'ttyLXU|liteuart'")
    show(sh, "stty -F /dev/ttyLXU1 raw -echo -icrnl -onlcr; echo set")
show(rx, "cat /dev/ttyLXU1 > /tmp/rx.txt & sleep 1; echo started")
show(tx, "echo 'Hello from Linux on one FPGA, through a DAC, a cable and an ADC.' > /dev/ttyLXU1; echo sent")
time.sleep(2)
show(rx, "cat /tmp/rx.txt")
show(rx, "kill %1 2>/dev/null; killall cat 2>/dev/null; cat /dev/ttyLXU1 > /tmp/rx.bin & sleep 1; echo started")
show(tx, "dd if=/dev/urandom of=/tmp/tx.bin bs=1024 count=32 2>/dev/null; md5sum /tmp/tx.bin", 60)
show(tx, "time cat /tmp/tx.bin > /dev/ttyLXU1", 60)
time.sleep(8)        # 32 kB at 115200 baud takes 2.8 s on the wire
show(rx, "killall cat; sleep 1; ls -l /tmp/rx.bin; md5sum /tmp/rx.bin", 60)
