<!-- nav -->
[← 1.01 A counter on the LEDs](1_01_led_counter.md) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)** &emsp;&emsp;&emsp; [1.03 A sine: direct digital synthesis →](1_03_dac_sine.md)

# 1.02 A sawtooth from the DAC

![sawtooth.sv measured with a scope: one ramp every 256 × 20 ns = 5.12 µs](img/sawtooth_top.png)

Now the converter module goes on. Unplug the board, push the adapter onto
the Icepi Zero's 40-pin header and the module onto the adapter, the right
way round ([0.00](0_00_the_hardware.md#the-converters-for-when-you-get-to-them)
has the two warnings and the picture), and plug the USB cable back into
the **Flash** port. Then put a scope on the DAC's output connector for
this one: DAC OUT, the right-hand SMA with the USB connectors toward you.

<img src="img/stack_scope.png" alt="Seen from above: an oscilloscope on DAC OUT, the right SMA" width="400">


## The converters

* ADC **[AD9280](https://www.analog.com/en/products/ad9280.html)** --- 8 bits at up to 32 MS/s
* DAC **[AD9708](https://www.analog.com/en/products/ad9708.html)** ---
 8 bits at up to 125 MS/s

Each has an op-amp front end and a
potentiometer that you can leave alone. The adapter board's silkscreen names every
pin: the Icepi Zero's 40-pin header plugs into its bottom, the module into
its top.

> [!WARNING]
> **Plug the module in the right way round.** The adapter is the same shape as
> the Icepi Zero, and their mounting holes line up. The wrong way round puts
> 5 V on FPGA pins, which they do not survive. The
> [adapter's page](../adapter_board/) shows how the module goes in.

<img src="img/photo_stack.png" alt="The Icepi Zero, the adapter and the ADC/DAC module, stacked, with a short coax cable from the DAC to the ADC" width="320">

> [!WARNING]
> **Keep the ADC's input between −5 V and +5 V.**

### Which SMA is which?

The module's SMA connectors aren't labelled. Hold the stack with its USB
connectors toward you: 
* **ADC IN is on the left**
* **DAC OUT on the right.**

Sometimes you'll use a loopback cable like this:

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

## DAC Output

The AD9708 DAC takes an 8-bit number on eight pins, `dac_d[7:0]`, and on each
rising edge of its clock pin, `dac_clk`, turns it into an output current. The
module's op-amp turns that into a voltage. So what happens if you wire the
counter of [1.01](1_01_led_counter.md#101-a-counter-on-the-leds) to the DAC?

<!-- file: src/verilog/sawtooth.sv -->
```systemverilog
// sawtooth.sv -- a counter wired to the DAC is a ramp generator.
//
// Every 20 ns the 8-bit count goes up by one and the DAC turns it into a
// voltage.  After 255 it wraps to 0, so the output is a sawtooth that repeats
// every 256 x 20 ns = 5.12 us (195.3 kHz).

module sawtooth (
    input  logic       clk,         // 50 MHz
    output logic [7:0] dac_d = 0,   // DAC data; dac_d[7] is the most significant bit (MSB)
    output logic       dac_clk      // the DAC grabs dac_d on the RISING edge of this
);
    always_ff @(posedge clk)
        // ######################################################################
        // ##  KEY LINE: the DAC's number goes up by one every clock (20 ns).
        // ##  8 bits wrap from 255 back to 0 by themselves: that's the sawtooth.
        // ######################################################################
        dac_d <= dac_d + 1;

    // dac_d changes just after each rising edge of clk.  Inverting clk puts
    // the DAC's rising edge halfway between those changes, 10 ns after one
    // and 10 ns before the next -- when the data is steady.
    assign dac_clk = ~clk;
endmodule
```

The counter is now 8 bits wide, the width of the DAC, and runs at full
speed: 255 + 1 wraps around to 0 by itself, so the output is a ramp that
starts over every 256 clocks.

The only new idea is the DAC's clock. The AD9708 needs its data steady for
2.0 ns before and 1.5 ns after its clock's rising edge (the *setup* and
*hold* times, from its datasheet). Our data changes just after each rising
edge of `clk`, so we give the DAC the inverted clock. Its rising edge then
falls in the middle of each 20 ns period, 10 ns from any change.

`make load-sawtooth`, and on the scope:

![sawtooth.sv measured with an ADALM2000 at 100 MS/s](img/sawtooth.png)

The ramp repeats every 5.12 µs (195.3 kHz) and runs from −3.95 V at code 0
to +3.88 V at code 255: 30.7 mV per code. The scope took a sample every
10 ns, two for each 20 ns step of the DAC, and the line joins them up. Look
at the lower panel: there's no visible staircase, even though the value
steps every 20 ns. The DAC's output amplifier and the scope's own ~25 MHz
bandwidth both low-pass filter the steps. The one big step, 255 → 0, shows
that filtering as a ~20 ns edge with some ringing.

**Try this:**

- Make the ramp go down instead of up.
- Make a triangle: up, then down.
- Slow it down by a factor of a million: feed `dac_d` from `count[27:20]` of
  a 28-bit counter, as [`adc_leds.sv`](../src/verilog/adc_leds.sv) does in
  [1.04](1_04_adc_on_the_leds.md#104-the-adc-on-the-leds), and watch it with a
  multimeter instead. How long is one ramp now?

<!-- nav -->
[← 1.01 A counter on the LEDs](1_01_led_counter.md) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)** &emsp;&emsp;&emsp; [1.03 A sine: direct digital synthesis →](1_03_dac_sine.md)

<!-- author -->
<sub>Jason Gallicchio, jason@hmc.edu, Harvey Mudd College</sub>
