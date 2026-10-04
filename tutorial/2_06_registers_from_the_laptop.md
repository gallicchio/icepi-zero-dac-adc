<!-- nav -->
[← 2.05 A lock-in peripheral](2_05_lockin_peripheral.md#205-a-lock-in-peripheral) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)** &emsp;&emsp;&emsp; [3.00 Linux on the FPGA →](3_00_linux_on_the_fpga.md#300-linux-on-the-fpga)

# 2.06 The registers from the laptop

![remote.py and litex_term on the laptop talk to litex_server, which owns the serial port; inside the FPGA, LiteX's UART bridge reads and writes the Wishbone bus, where the CPU and BIOS, a crossover UART for the BIOS's console, and the CSRs of the function generator and lock-in are](img/uartbone.png)

Everything in this chapter so far went through C: write the firmware,
compile it, upload it, then type commands to it. Sometimes you just want to
set a register from Python, with numpy and matplotlib at hand, and no
firmware at all. LiteX can do that. Instead of connecting the serial port to
the CPU's console, it can connect it to a *bridge*: a small circuit on the
bus that obeys two messages from the laptop, "read the word at this address"
and "write this word there". The laptop then reads and writes the SoC's
registers just as the CPU's loads and stores do, and `csr.csv`, which LiteX
writes for every build, gives them their names.

## Build it

It's the SoC of [2.03](2_03_function_generator_peripheral.md#203-a-function-generator-peripheral)–[2.05](2_05_lockin_peripheral.md#205-a-lock-in-peripheral), with one option changed, built into a folder of its own:

```console
$ cd src/riscv
$ python3 icepi_adda_soc.py --build --uart-name=crossover+uartbone --output-dir build/bone   # about a minute
$ openFPGALoader -b icepi-zero build/bone/gateware/icepi_zero.bit
$ litex_server --uart --uart-port /dev/ttyUSB0 &
```

`crossover+uartbone` puts the bridge (LiteX calls it UARTBone) on the
serial port and gives the CPU's console a *crossover* [UART](https://en.wikipedia.org/wiki/Universal_asynchronous_receiver-transmitter) instead: a pair of
registers that the laptop reads and writes through the bridge. `litex_server`
holds the serial port, and any number of programs on the laptop talk to the
bus through it, over a network connection to port 1234 on the laptop itself.
(Stop it, `kill %1`, before you load another bitstream: it keeps the serial
port open.)

## Read and write registers

`litex_cli` is the simplest of those programs:

```console
$ litex_cli --csr-csv build/bone/csr.csv --ident
LiteX SoC on Icepi Zero 2026-10-04 00:27:44
$ litex_cli --csr-csv build/bone/csr.csv --regs --filter funcgen
0xf0001000 : 0x00000000 funcgen_tw
0xf0001004 : 0x000000ff funcgen_amplitude
0xf0001008 : 0x00000000 funcgen_waveform
```

These are [2.03](2_03_function_generator_peripheral.md#203-a-function-generator-peripheral)'s three registers, as they are at power-up. In Python,
LiteX's `RemoteClient` turns every register into an attribute with `read()`
and `write()`:

<details>
<summary>The whole file: <code>remote.py</code></summary>

<!-- file: src/riscv/remote.py -->
```python
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
```

</details>

Through the 101.5 cm cable from DAC OUT to ADC IN:

```console
$ python3 remote.py
ctrl_scratch = 0x12345678
    f (Hz)   volts   degrees
    100000   3.905    -10.92
    300000   3.898    -32.68
   1000000   3.850   -108.40
   3000000   3.691     38.41
  10000000   4.140      4.66
(0.46 s for 5 points)
capture: 16384 samples in 1.5 s, codes 30 to 225, first ones [48, 37, 30, 30, 37, 49, 66, 87]
```

The same 3.85 V at 1 MHz as the firmware's `li` in [2.05](2_05_lockin_peripheral.md#205-a-lock-in-peripheral), from Python, with nothing
compiled. Afterwards the registers still hold what the script left in them:

```console
$ litex_cli --csr-csv build/bone/csr.csv --regs --filter lockin
0xf0002800 : 0x00000001 lockin_control
0xf0002804 : 0x00000014 lockin_n_log2
0xf0002808 : 0x00000002 lockin_status
0xf000280c : 0x19f2ee533 lockin_x
0xf0002814 : 0x21dd96d8 lockin_y
```

`lockin_status` is 2, *done*; `lockin_x` and `lockin_y` are the 64-bit sums of
the last measurement, 2<sup>20</sup> (0x14) samples' worth.

## The BIOS is still there

The CPU runs the [BIOS](https://en.wikipedia.org/wiki/BIOS) as before; only its console has moved. `litex_term`
reaches it through `litex_server`:

```console
$ litex_term crossover --csr-csv build/bone/csr.csv
...
litex> mem_read 0xf0000804
Memory dump:
0xf0000804  78 56 34 12                                      xV4.
```

(`ctrl_scratch` is at 0xf0000804 in this SoC, not 0xf0000004 as in [2.01](2_01_a_cpu_and_its_bios.md#201-a-cpu-and-its-bios):
adding peripherals moved the registers around, which is why scripts should
use names from `csr.csv`, not addresses.)

## How fast?

Each register access is a round trip: a few bytes to the board over the
serial port, and a few bytes back, a few milliseconds in all. That's slow next
to the CPU, which does a load in tens of nanoseconds, but fast enough for an
instrument you drive by hand or sweep point by point: five lock-in points
took 0.46 s, of which 0.21 s was the lock-in itself averaging. A block read
is efficient: the whole 16 kB capture buffer came back in 1.5 s, against
1.4 s for 16384 bytes at 115,200 baud with no overhead at all, and half the
time of the firmware's hex `dump` in [2.04](2_04_capture_peripheral.md#204-a-capture-peripheral).

So there are now three ways to drive the same registers, each with its
place:

| | firmware in C (2.02–2.05) | the bridge (this page) | Linux (Chapter 3) |
| --- | --- | --- | --- |
| a change takes | a compile and an upload | nothing: edit the script, run it | nothing |
| a register access | tens of ns | a few ms | microseconds (a system call) |
| runs without the laptop | yes | no | yes |
| best for | speed, and instruments that stand alone | exploring and testing hardware, plots | a computer that is also an instrument |

LiteX's own tools are built on this bridge: LiteScope, LiteX's logic
analyzer, records signals inside your design and reads them out through the
same `litex_server`.

**Try this:**

- Plot the capture: add matplotlib to `remote.py`, as `cap_plot.py` in [2.04](2_04_capture_peripheral.md#204-a-capture-peripheral)
  does for the firmware's dump.
- How many register writes per second does the bridge manage? Time a loop
  that writes `leds_out` 1000 times, and compare with the round trip you
  expect from the bytes involved.
- The bridge's speed is the serial port's. Rebuild with `--uart-baudrate
  1000000` and start `litex_server` with `--uart-baudrate 1000000` (the
  FT231X goes up to 3 Mbaud). Not tried here: does the capture come back
  8.7 times faster?
- Write the lock-in sweep of [2.05](2_05_lockin_peripheral.md#205-a-lock-in-peripheral) as a Python function and run it inside a
  Jupyter notebook, with the [Bode plot](https://en.wikipedia.org/wiki/Bode_plot) drawn as it goes.

<!-- nav -->
[← 2.05 A lock-in peripheral](2_05_lockin_peripheral.md#205-a-lock-in-peripheral) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)** &emsp;&emsp;&emsp; [3.00 Linux on the FPGA →](3_00_linux_on_the_fpga.md#300-linux-on-the-fpga)

<!-- author -->
<sub>Jason Gallicchio, jason@hmc.edu, Harvey Mudd College</sub>
