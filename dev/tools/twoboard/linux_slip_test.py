"""Instructor's test: IP between two FPGA Linux computers, over SLIP on /dev/ttyLXU1 and the modem.

    python3 linux_slip_test.py PORT_A PORT_B
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from linux_shell import Shell

A = Shell(port=sys.argv[1], baud=460800, boot_timeout=400)
B = Shell(port=sys.argv[2], baud=460800, boot_timeout=400)


def show(sh, cmd, t=60):
    out = sh.run(cmd, t)
    print("%s# %s" % ("A" if sh is A else "B", cmd))
    if out:
        print(out)
    sys.stdout.flush()
    return out


for sh, me, peer in ((A, "10.0.0.1", "10.0.0.2"), (B, "10.0.0.2", "10.0.0.1")):
    show(sh, "slattach -p slip -s 115200 /dev/ttyLXU1 & sleep 2; "
             "ifconfig sl0 %s pointopoint %s up; ifconfig sl0 | head -3" % (me, peer))
show(A, "ping -c 5 10.0.0.2", 60)
show(B, "ping -c 3 10.0.0.1", 60)
show(B, "nc -l -p 5000 > /tmp/rx.bin & sleep 1; echo listening")
show(A, "dd if=/dev/urandom of=/tmp/tx.bin bs=1024 count=32 2>/dev/null; md5sum /tmp/tx.bin; "
        "nc 10.0.0.2 5000 < /tmp/tx.bin & sleep 20; killall nc", 120)      # BusyBox's nc has no -w
show(B, "ls -l /tmp/rx.bin; md5sum /tmp/rx.bin", 60)
show(A, "ping -c 20 -s 1000 10.0.0.2 | tail -2", 120)
show(A, "ifconfig sl0 | grep -E 'RX packets|TX packets|errors'")
