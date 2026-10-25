<!-- nav -->
[← Front page](../README.md) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)** &emsp;&emsp;&emsp; [0.01 How to use this tutorial →](0_01_how_to_use_this_tutorial.md)

# 0.00 The hardware

![Three results from Chapter 1, measured: a 1 MHz sine from the DAC; the extra phase of 85 cm of cable against frequency, a straight line whose slope is 3.89 ns, so light in the cable goes at 0.73 c; and a tune sent as AM at 1 MHz and received, as a spectrogram of its notes](img/hook.png)

By the end of Chapter 1 you will have made all three of these, on
$120 of hardware, out of nothing but logic you describe yourself: a sine
wave ([1.03](1_03_dac_sine.md#103-a-sine-direct-digital-synthesis)), a
[lock-in amplifier](https://en.wikipedia.org/wiki/Lock-in_amplifier) that
times 85 cm of cable to a twentieth of a nanosecond and so measures the
speed of light in it ([1.08](1_08_lockin.md#108-a-lock-in-amplifier)), and
an AM transmitter and receiver that play a tune ([1.10](1_10_am_radio.md#110-an-am-radio)). No processor is involved: just gates, flip-flops and a
50 MHz clock. You start smaller than that, though: the first thing you
build makes five LEDs count. This is the hardware:

<img src="img/photo_stack.png" alt="The Icepi Zero, the adapter and the ADC/DAC module, stacked, with a short coax cable from the DAC to the ADC" width="320">

Three boards, stacked: an [FPGA](https://en.wikipedia.org/wiki/Field-programmable_gate_array) board at the bottom, a converter module on
top (an [ADC](https://en.wikipedia.org/wiki/Analog-to-digital_converter) that turns a voltage into a number and a [DAC](https://en.wikipedia.org/wiki/Digital-to-analog_converter) that turns a
number into a voltage, each behind an SMA connector), and a small passive
adapter between them.

| board | what it is |
| --- | --- |
| **[Icepi Zero](https://github.com/cheyao/icepi-zero)** | A Lattice **ECP5 LFE5U-25F** FPGA on a Raspberry-Pi-Zero-sized board, with 5 white LEDs, 2 buttons and three USB-C ports. |
| **"AD9280 AD9708 Data Acquisition Board"** | An 8-bit ADC and an 8-bit DAC on one module, about $30. Get the version with a **2×12** pin header and SMA connectors, the one in the photo. |
| **[The adapter](../adapter_board/)** | A passive board you order yourself (about $2 for five). The [`adapter_board/`](../adapter_board/) folder has its KiCad files and gerbers, and says how to put it together. |

**Start with the FPGA board alone.** The first page of Chapter 1
([1.01](1_01_led_counter.md#101-a-counter-on-the-leds)) only makes the
LEDs count, and the module sits right over the LEDs. Leave the adapter
and the module in their bags until
[1.02](1_02_dac_sawtooth.md#102-a-sawtooth-from-the-dac), where the DAC
first does something. Plug the USB-C cable into the Icepi Zero's port
marked **Flash**: the left one of its three USB-C ports when they point
down, toward you. That one port loads your designs into the FPGA and is
also a serial port back to your laptop.

## What else you need

| for | what |
| --- | --- |
| everything | a laptop (Linux, macOS or Windows) and a USB-C cable |
| from [1.02](1_02_dac_sawtooth.md#102-a-sawtooth-from-the-dac) on | the adapter and the module, and an oscilloscope helps a lot. A USB instrument such as the ADALM2000 is plenty |
| from [1.04](1_04_adc_on_the_leds.md#104-the-adc-on-the-leds) on | a coax cable from the DAC output to the ADC input, SMA to SMA. The measurements here used RG-316, 16.5 cm and 101.5 cm long. A function generator is useful but not essential |
| [3.04](3_04_booting_from_sd.md#304-booting-from-an-sd-card) | a micro-SD card, 1 GB or more (it will be erased) |
| Chapter 4 | a few resistors, capacitors and other parts, listed in each section |
| Chapter 5 | a second complete set of boards, and a second cable |

## The converters, for when you get to them

Nothing below matters until
[1.02](1_02_dac_sawtooth.md#102-a-sawtooth-from-the-dac); come back
then. The Icepi Zero's **Flash** port is an FT231X chip that does two
jobs: it loads designs into the FPGA, and it is a serial port between the
FPGA and your laptop. (The HDMI socket and the other two USB-C ports go
straight to FPGA pins; [3.04](3_04_booting_from_sd.md#a-computer-of-its-own)
says what they could do.) The module's **[AD9280](https://www.analog.com/en/products/ad9280.html)**
ADC does 8 bits at up to 32 MS/s and its **[AD9708](https://www.analog.com/en/products/ad9708.html)**
DAC 8 bits at up to 125 MS/s, each with an op-amp front end and a
potentiometer you can leave alone. The adapter's silkscreen names every
pin: the Icepi Zero's 40-pin header plugs into its bottom, the module into
its top.

> [!WARNING]
> **Plug the module in the right way round.** The adapter is the same shape as
> the Icepi Zero, and their mounting holes line up. The wrong way round puts
> 5 V on FPGA pins, which they do not survive. The
> [adapter's page](../adapter_board/) shows how the module goes in.

> [!WARNING]
> **Keep the ADC's input between −5 V and +5 V.**

### Which SMA is which

The module's SMA connectors aren't labelled. Hold the stack with its USB
connectors toward you: **ADC IN is on the left, and DAC OUT on the right.**
(The module's `ACLK` and `DCLK` pins, and the adapter's silkscreen, agree.)
Every page that connects anything but the loopback cable has a picture like
this one, drawn the same way:

<img src="img/stack_loopback.png" alt="Seen from above, USB connectors at the bottom: ADC IN is the left SMA, DAC OUT the right one, and the loopback cable joins them" width="400">

### What the converters can do

Measured on these boards ([Appendix C](C_how_it_was_tested.md) says how):

| | DAC (output connector) | ADC (input connector) |
| --- | --- | --- |
| bits | 8 (codes 0–255) | 8 (codes 0–255) |
| sample rate used here | 50 MS/s (100 MS/s in [4.01](4_01_a_faster_dac.md#401-a-faster-dac-plls)) | 25 MS/s |
| range | code 0 → −3.95 V, code 255 → +3.88 V | −5.0 V → code 0, +5.06 V → code 255 |
| one code (LSB) | 30.7 mV | 39.5 mV |
| conversion | V = 0.0307 × code − 3.95 | code = 126.7 + 25.35 × V |
| quality | harmonics at least 46 dB below a 1 MHz tone | 7.1 effective bits at 1–3 MHz |

The DAC was measured into a 1 MΩ oscilloscope input. With a cable straight
from the DAC to the ADC, ADC code = 0.776 × DAC code + 27.5, and a change at
the DAC shows up at the ADC 6 samples (240 ns) later (you'll measure both in
[1.07](1_07_closing_the_loop.md#107-closing-the-loop-the-dac-talks-to-the-adc)). Each module is a little different: the gains
of the three tested here differ by up to 0.7%.

<!-- nav -->
[← Front page](../README.md) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)** &emsp;&emsp;&emsp; [0.01 How to use this tutorial →](0_01_how_to_use_this_tutorial.md)

<!-- author -->
<sub>Jason Gallicchio, jason@hmc.edu, Harvey Mudd College</sub>
