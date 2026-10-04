"""Record adc_stream.sv's stream (DAC cabled to ADC) and draw the 1.05 figure.
Run with adc_stream.bit loaded.  --replot redraws from the saved data."""
import os
import sys

import numpy as np
from plotstyle import plt, save, dots, C1, INK2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src", "verilog"))
DATA = os.path.join(HERE, "..", "data", "stream.npz")
IMG = os.path.join(HERE, "..", "..", "tutorial", "img", "stream.png")

if "--replot" not in sys.argv:
    import serial
    import stream
    with serial.Serial(stream.find_port(), 1_000_000, timeout=2) as ser:
        ser.reset_input_buffer()
        raw = ser.read(5000)
    np.savez(DATA, code=np.frombuffer(raw, dtype=np.uint8))
code = np.load(DATA)["code"].astype(int)
v = (code - 126.7) / 25.35
t = np.arange(len(v)) / 50e3

fig, (a, b) = plt.subplots(2, 1, figsize=(8, 5.6))
a.plot(t * 1e3, v, color=C1, lw=0.8)
a.set_xlabel("time (ms)")
a.set_ylabel("ADC input (V)")
a.set_title("stream.py: 0.1 s of the DAC's 763 Hz sawtooth, 50,000 samples a second")
sel = t < 2.0e-3
a.axvspan(0, 2.0, color="#eb6834", alpha=0.10, lw=0)
b.plot(t[sel] * 1e3, v[sel], color=C1, lw=0.8, alpha=0.5)
dots(b, t[sel] * 1e3, v[sel], C1, label="ADC samples, one every 20 µs")
b.set_xlabel("time (ms)")
b.set_ylabel("ADC input (V)")
b.set_title("The first 2 ms (shaded above): 65.5 samples per ramp")
b.legend(loc="lower right")
save(fig, IMG)
print("wrote", IMG, "codes", code.min(), code.max())
