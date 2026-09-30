"""Instructor's check of Part 8 on a booted board: /dev/mem, then the driver.
Prints a transcript (commands and output) for the tutorial."""
import sys, time, re
import numpy as np
import m2k
from linux_shell import Shell

sh = Shell(baud=460800, boot_timeout=240)
m = m2k.M2k()


def show(cmd, timeout=30):
    out = sh.run(cmd, timeout)
    print("# " + cmd)
    if out:
        print(out)
    return out


def dac():
    t, v = m.ch1(1e8, 16384)
    f, A, ph, c, r = m2k.fit_sine(t, v)
    return f, A


if "--driver-only" not in sys.argv:
    show("uname -a")
    show("cat /proc/cpuinfo | head -8")
    show("free")

    # ---- the quick way: /dev/mem ----
    fg = int(re.search(r"adda@([0-9a-f]+)", show("ls /sys/firmware/devicetree/base/soc | grep adda")).group(1), 16)
    show("devmem 0x%08x 32" % fg)
    show("devmem 0x%08x 32 0x051eb852" % fg)          # 1 MHz
    time.sleep(0.2)
    print("  M2k: DAC at %.1f Hz, %.3f V" % dac())
    show("devmem 0x%08x 32 0x0a3d70a4" % fg)          # 2 MHz
    time.sleep(0.2)
    print("  M2k: DAC at %.1f Hz, %.3f V" % dac())

    if "--devmem-only" in sys.argv:
        cap = int(re.search(r"reg = <0x[0-9a-f]+ 0x100 0x([0-9a-f]+)", open(sys.argv[-1]).read()).group(1), 16) \
            if sys.argv[-1].endswith(".dts") else None
        m.close()
        sh.close()
        sys.exit(0)

# ---- the driver ----
show("lsmod | grep -q adda || insmod /root/adda.ko")
show("dmesg | tail -2")
A = show("echo /sys/bus/platform/devices/*.adda")
show("ls %s/funcgen %s/capture %s/lockin" % (A, A, A))
show("echo 123456 > %s/funcgen/frequency" % A)
show("cat %s/funcgen/frequency" % A)
show("echo triangle > %s/funcgen/waveform; echo 128 > %s/funcgen/amplitude" % (A, A))
time.sleep(0.2)
t, v = m.ch1(1e8, 16384)
print("  M2k: DAC min %.2f max %.2f V" % (v.min(), v.max()))
show("echo sine > %s/funcgen/waveform; echo 255 > %s/funcgen/amplitude" % (A, A))
show("cat %s/funcgen/waveform %s/funcgen/amplitude" % (A, A))

fw = m.w1_sine(137e3, 3.0)
time.sleep(0.3)
show("echo 2 > %s/capture/decimation; echo 128 > %s/capture/trigger" % (A, A))
show("cat %s/capture/sample_rate %s/capture/trigger" % (A, A))
show("time cat %s/capture/data > /tmp/samples.bin; ls -l /tmp/samples.bin" % A)
out = show("od -An -tu1 -N48 /tmp/samples.bin")

# lock-in at the W1 frequency
show("echo 100000 > %s/funcgen/frequency" % A)
m.w1_wave_exact(100e3 * (1 - 2.8e-6), lambda c: 2.0 * np.sin(2 * np.pi * c))
time.sleep(0.3)
show("cat %s/lockin/n_log2" % A)
for _ in range(3):
    show("time cat %s/lockin/result" % A)
show("cd /root && ./sweep.sh 90000 110000 5", timeout=60)
show("time ./dump.sh | wc -l; ./dump.sh | head -2 | cut -c 1-64")
m.w1_dc(0.0)
m.close()
sh.close()
