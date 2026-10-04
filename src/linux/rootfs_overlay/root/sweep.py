# sweep.py START_HZ STOP_HZ POINTS -- sweep.sh, in MicroPython.
#   micropython sweep.py 10000 10000000 31 > thru.txt
# Prints: frequency (Hz), amplitude at the ADC (V), phase (degrees).
import math
import os
import sys

D = "/sys/bus/platform/devices/"
A = D + [d for d in os.listdir(D) if d.endswith(".adda")][0]   # f0002000.adda


def put(name, value):
    with open(A + "/" + name, "w") as f:
        f.write(str(value))


def get(name):
    with open(A + "/" + name) as f:
        return f.read().split()


a, b, n = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
for i in range(n):
    f = round(a * math.exp(math.log(b / a) * i / (n - 1)))
    put("funcgen/frequency", f)
    x, y = [float(v) for v in get("lockin/result")]
    volts = 2 * math.sqrt(x * x + y * y) / 127 / 25.35        # as in 1.08
    print("%10d %8.4f %8.2f" % (f, volts, math.degrees(math.atan2(y, x))))
