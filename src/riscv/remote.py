"""2.06, the laptop side: the SoC's registers from Python, by name, with no firmware.

Needs the SoC built with LiteX's UART bridge, and litex_server between it and Python:

    python3 icepi_adda_soc.py --build --uart-name=crossover+uartbone --output-dir build/bone
    openFPGALoader -b icepi-zero build/bone/gateware/icepi_zero.bit
    litex_server --uart --uart-port /dev/ttyUSB0 &
    python3 remote.py

It sets the LEDs and the function generator, runs a lock-in sweep, and takes a capture,
all by reading and writing the registers that the firmware of 2.03-2.05 uses.
"""
import math
import time

import numpy as np
from litex import RemoteClient

F_SYS = 50e6                 # the SoC's clock
ADC_CODES_PER_VOLT = 25.35   # measured in 0.00

wb = RemoteClient(csr_csv="build/bone/csr.csv")      # every register's name and address
wb.open()

# ##########################################################################################
# ##  KEY LINES: a register is an attribute; read() and write() go over the serial port,
# ##  through the UART bridge, onto the SoC's bus, just like the CPU's loads and stores.
# ##########################################################################################
print("ctrl_scratch = 0x%08x" % wb.regs.ctrl_scratch.read())
wb.regs.leds_out.write(0b10101)


def funcgen(hz, amplitude=255, waveform=0):
    """2.03's function generator: waveform 0 sine, 1 square, 2 triangle, 3 sawtooth."""
    wb.regs.funcgen_tw.write(round(hz * 2**32 / F_SYS))
    wb.regs.funcgen_amplitude.write(amplitude)
    wb.regs.funcgen_waveform.write(waveform)


def signed64(v):
    return v - (1 << 64) if v >> 63 else v


def lockin(n_log2=20):
    """2.05's lock-in: the amplitude (V) and phase (degrees) at the function generator's
    frequency, averaged over 2^n_log2 samples."""
    wb.regs.lockin_n_log2.write(n_log2)
    wb.regs.lockin_control.write(1)                        # start
    while not wb.regs.lockin_status.read() & 2:            # done?
        time.sleep(0.001)
    x = signed64(wb.regs.lockin_x.read()) / 2**n_log2      # the 64-bit sums, read as two words
    y = signed64(wb.regs.lockin_y.read()) / 2**n_log2
    return 2 * math.hypot(x, y) / 127 / ADC_CODES_PER_VOLT, math.degrees(math.atan2(y, x))


print("    f (Hz)   volts   degrees")
t0 = time.time()
for f in [100e3, 300e3, 1e6, 3e6, 10e6]:
    funcgen(f)
    v, deg = lockin()
    print("%10.0f  %6.3f  %8.2f" % (f, v, deg))
print("(%.2f s for 5 points)" % (time.time() - t0))

# 2.04's capture: start it, wait until it's done, then read the 16 kB buffer straight off the bus
funcgen(1e6)
wb.regs.capture_config.write(0)                            # every sample, no trigger
wb.regs.capture_control.write(1)                           # start
while not wb.regs.capture_status.read() & 2:
    time.sleep(0.001)
t0 = time.time()
buf = wb.mems.capture_buf
words = wb.read(buf.base, buf.size // 4)                   # 4096 32-bit words
samples = np.array(words, dtype="<u4").view(np.uint8)     # 4 samples per word, first one lowest
print("capture: %d samples in %.1f s, codes %d to %d, first ones %s"
      % (len(samples), time.time() - t0, samples.min(), samples.max(), list(samples[:8])))
wb.close()
