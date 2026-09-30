"""Part 9 figures: circuit diagrams for the suggested experiments (schemdraw).

    pip install --user schemdraw
    python3 fig_experiments.py          # writes img/exp_*.png

Every circuit starts at the DAC, drawn as a source behind the ~50 ohm the
module appears to have in series with its output, and ends at the ADC's
high-impedance input.
"""
import os
import matplotlib
matplotlib.use("Agg")
import schemdraw
import schemdraw.elements as e

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, "..", "img")
SURFACE = "#fcfcfb"
schemdraw.config(fontsize=11, bgcolor=SURFACE, lw=1.4)


def dac(d):
    """DAC source + its 50 ohm; returns with the drawing at the DAC connector."""
    src = d.add(e.SourceSin().up())
    d.add(e.Label().at((src.center[0] - 1.0, src.center[1])).label("DAC"))
    d.add(e.Ground().at(src.start))
    d.add(e.Resistor().right().at(src.end).label("50 Ω\n(in module)", fontsize=9))
    d.add(e.Dot(open=True).label("DAC\nSMA", loc="top", fontsize=9))
    d.add(e.Line().right(0.8))


def adc(d):
    """The ADC input: an open dot and its high-impedance input to ground."""
    d.add(e.Dot(open=True).label("ADC\nSMA", loc="top", fontsize=9))
    here = d.here
    d.add(e.Line().right(0.8))
    d.add(e.Resistor().down().label("ADC input\n(high Z)", loc="bottom", fontsize=9))
    d.add(e.Ground())
    d.here = here


def save(d, name):
    """An opaque background, so the black lines show on dark themes too."""
    path = os.path.join(IMG, name)
    d.save(path, dpi=130, transparent=False)
    from PIL import Image, ImageOps
    im = Image.open(path).convert("RGBA")
    bg = Image.new("RGBA", im.size, SURFACE)
    flat = Image.alpha_composite(bg, im).convert("RGB")
    ImageOps.expand(flat, border=16, fill=SURFACE).save(path)
    print("wrote", name)


# E1: the ADC's input impedance and the cable's capacitance
with schemdraw.Drawing(show=False) as d:
    dac(d)
    d.add(e.Resistor().right().label("R = 10 kΩ"))
    d.add(e.Line().right(0.6))
    d.add(e.Coax(length=3).right().label("RG-316: 16.5 cm or 101.5 cm", loc="bottom", fontsize=9))
    d.add(e.Line().right(0.8))
    adc(d)
    save(d, "exp_cable_c.png")

# E2a: RC low-pass
with schemdraw.Drawing(show=False) as d:
    dac(d)
    d.add(e.Resistor().right().label("R = 1.0 kΩ"))
    d.add(e.Dot())
    n = d.here
    d.add(e.Capacitor().down().label("C = 1.0 nF", loc="bottom"))
    d.add(e.Ground())
    d.here = n
    d.add(e.Line().right(1.5))
    adc(d)
    save(d, "exp_rc_low.png")

# E2b: RC high-pass
with schemdraw.Drawing(show=False) as d:
    dac(d)
    d.add(e.Capacitor().right().label("C = 1.0 nF"))
    d.add(e.Dot())
    n = d.here
    d.add(e.Resistor().down().label("R = 1.0 kΩ", loc="bottom"))
    d.add(e.Ground())
    d.here = n
    d.add(e.Line().right(1.5))
    adc(d)
    save(d, "exp_rc_high.png")

# E3: series LC band-pass
with schemdraw.Drawing(show=False) as d:
    dac(d)
    d.add(e.Inductor().right().label("L = 100 µH"))
    d.add(e.Capacitor().right().label("C = 100 pF"))
    d.add(e.Dot())
    n = d.here
    d.add(e.Resistor().down().label("R = 100 Ω", loc="bottom"))
    d.add(e.Ground())
    d.here = n
    d.add(e.Line().right(1.5))
    adc(d)
    save(d, "exp_lc.png")

# E4: quartz crystal
with schemdraw.Drawing(show=False) as d:
    dac(d)
    d.add(e.Crystal().right().label("4.000 MHz"))
    d.add(e.Dot())
    n = d.here
    d.add(e.Resistor().down().label("R = 50 Ω", loc="bottom"))
    d.add(e.Ground())
    d.here = n
    d.add(e.Line().right(1.5))
    adc(d)
    save(d, "exp_crystal.png")

# E5: diode clipper (two anti-parallel 1N4148)
with schemdraw.Drawing(show=False) as d:
    dac(d)
    d.add(e.Resistor().right().label("R = 1.0 kΩ"))
    d.add(e.Dot())
    n1 = d.here
    d.add(e.Line().right(1.6))
    d.add(e.Dot())
    n2 = d.here
    d.add(e.Line().right(1.6))
    adc(d)
    d.add(e.Diode().down().at(n1).label("D1", loc="bottom"))
    d.add(e.Ground())
    d.add(e.Diode().down().reverse().at(n2).label("D2", loc="bottom"))
    d.add(e.Ground())
    save(d, "exp_diodes.png")

# E6: open-ended stub on a T
with schemdraw.Drawing(show=False) as d:
    dac(d)
    d.add(e.Line().right(1.6))
    d.add(e.Dot().label("SMA T", loc="top", fontsize=9))
    t = d.here
    d.add(e.Coax(length=2.2).right().label("short cable"))
    adc(d)
    d.here = t
    d.add(e.Coax(length=3).down().label("stub: 5.0 m RG-58,\nfar end open", loc="bottom", fontsize=9))
    d.add(e.Dot(open=True))
    save(d, "exp_stub.png")

# E7: ultrasonic speed of sound (piezo transducers, drawn as crystals)
with schemdraw.Drawing(show=False) as d:
    dac(d)
    d.add(e.Line().right(1.2))
    t = d.here
    d.add(e.Crystal().down().label("40 kHz\ntransmitter", loc="bottom", fontsize=9))
    d.add(e.Ground())
    rx = (t[0] + 5.0, t[1])
    d.add(e.Label().at((t[0] + 2.6, t[1] - 0.4)).label("))) air )))  10–50 cm", fontsize=10))
    d.add(e.Crystal().down().at(rx).label("40 kHz\nreceiver", loc="bottom", fontsize=9))
    d.add(e.Ground())
    d.here = rx
    d.add(e.Line().right(1.2))
    adc(d)
    save(d, "exp_ultrasound.png")

# E8: optical link: an LED transmitter and a photodiode receiver
with schemdraw.Drawing(show=False) as d:
    dac(d)
    d.add(e.Resistor().right().label("100 Ω"))
    d.add(e.Dot())
    n1 = d.here
    d.add(e.Line().right(2.4))
    n2 = d.here
    d.add(e.LED().down().at(n1).label("red\nLED", loc="bottom", fontsize=9))
    d.add(e.Ground())
    d.add(e.Diode().down().reverse().at(n2).label("1N4148", loc="bottom", fontsize=9))
    d.add(e.Ground())
    # the receiver, drawn separately to the right
    x0, y0 = n2[0] + 3.5, n2[1]
    d.add(e.BatteryCell().up().at((x0, y0 - 3)).label("9 V", loc="bottom", fontsize=9))
    d.add(e.Ground().at((x0, y0 - 3)))
    d.add(e.Line().right(1.8).at((x0, y0)))
    d.add(e.Photodiode().down().reverse().label("BPW34", loc="bottom", fontsize=9))
    d.add(e.Dot())
    n3 = d.here
    d.add(e.Resistor().down().label("R_L = 10 kΩ\n(or 1 kΩ)", loc="bottom", fontsize=9))
    d.add(e.Ground())
    d.here = n3
    d.add(e.Line().right(1.6))
    adc(d)
    save(d, "exp_optical.png")

# E10: clock comparison against a 10 MHz reference
with schemdraw.Drawing(show=False) as d:
    src = d.add(e.SourceSin().up())
    d.add(e.Label().at((src.center[0] - 1.5, src.center[1])).label("10 MHz\nreference\n(GPSDO)", fontsize=10))
    d.add(e.Ground().at(src.start))
    d.add(e.Line().right(0.6).at(src.end))
    d.add(e.RBox().right().label("10 dB\nattenuator", fontsize=9))
    d.add(e.Dot().label("SMA T", loc="top", fontsize=9))
    n = d.here
    d.add(e.Resistor().down().label("50 Ω\ntermination", loc="bottom", fontsize=9))
    d.add(e.Ground())
    d.here = n
    d.add(e.Line().right(1.5))
    adc(d)
    save(d, "exp_reference.png")
