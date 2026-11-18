<!-- nav -->
[← 1.10 An AM radio](1_10_am_radio.md) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)** &emsp;&emsp;&emsp; [2.00 A processor on the FPGA →](2_00_a_processor_on_the_fpga.md)

# 1.11 A slow ramp: four LEDs and the energy of a photon

![ledramp.sv, worked out from the code. Top: the DAC's voltage climbs in 128 steps from 0 to +3.88 V in 43 s and drops back to 0 V, crossing dashed lines at the photon energies of the four LEDs, hc/λe: red 630 nm 1.97 V, yellow 596 nm 2.08 V, green 525 nm 2.36 V, blue 469 nm 2.64 V. Bottom: when each of the five LEDs is on; led[4], the leftmost, worth 1.97 V, comes on halfway up, and led[0], worth 0.12 V, changes every 1.3 s](img/ledramp_code.png)

An LED makes light when an electron crosses its junction and gives up its
energy as a photon. An electron that crosses *V* volts gains *eV* of energy;
a photon of wavelength λ carries *E* = *hc*/λ. So an LED should start to glow
near *V* = *hc*/(*e*λ): a red LED a little under 2 V, a blue one well over
2.5 V. Measure the voltage at which each colour first glows, plot it against
1/λ, and the slope is *hc*/*e*: one of the classic ways to
[Planck's constant](https://en.wikipedia.org/wiki/Planck_constant).

That needs a voltage that rises slowly enough to watch, and a way to see
where it has got to. `ledramp.sv` is
[1.02](1_02_dac_sawtooth.md#102-a-sawtooth-from-the-dac)'s sawtooth, slowed
down 2<sup>24</sup> times and kept to the DAC's positive half: it climbs from
0 to +3.88 V in 43 s, and the five LEDs show the ramp's top five bits, so the
number on them is the voltage. The button stops the ramp where it is.

## The circuit: AMOD-P's tile p12

[AMOD-P](https://github.com/gallicchio/AMOD-and-RFMOD/blob/main/docs/HANDBOOK_amod_p.md#p12)'s
tile **p12** is four LEDs behind one 100 Ω resistor, chosen by a four-way DIP
switch:

| DIP way | colour | wavelength | made of | *hc*/(*e*λ) |
| --- | --- | --- | --- | --- |
| 1 | red | 630 nm | AlGaInP | 1.97 V |
| 2 | yellow | 596 nm | AlGaInP | 2.08 V |
| 3 | green | 525 nm | InGaN | 2.36 V |
| 4 | blue | 469 nm | InGaN | 2.64 V |

(*hc*/*e* = 1239.8 V nm.) The colours aren't printed on the board: light
them to see which is which.

- **DAC OUT** (with the USB connectors toward you, the right-hand SMA) to
  p12's **IN**, its only jack. Nothing goes to ADC IN.
- An LED that is just starting to glow draws a few microamps, so almost
  nothing is lost in the resistors: the LED sees the DAC's own voltage. At the
  top of the ramp the red LED, well on, draws about 13 mA through the 100 Ω
  and the DAC module's own output resistor: bright, and inside its rating.
- The handbook asks for **one way at a time**. All four LEDs sit after the
  same 100 Ω, in parallel: with several ways on, the red, which needs the
  least voltage, takes the current and holds the voltage near its own, and
  the others stay dark.

## The design

<!-- file: src/verilog/ledramp.sv -->
```systemverilog
// ledramp.sv -- a slow DC ramp on the DAC, and where it has got to on the five LEDs.
//
// For AMOD-P's tile p12: four LEDs (red, yellow, green, blue) behind 100 ohm, one at a time on its DIP switch.
// The DAC rises from 0 V to +3.9 V in 43 s, one DAC step (30.7 mV) every 0.34 s, drops back to 0 V and rises
// again.  The LEDs show the ramp's top five bits: led[4], the leftmost, is worth 1.97 V, then 0.98, 0.49, 0.25 and
// 0.12 V, so the voltage is the sum of the lit LEDs' weights (to within the 0.12 V of one LED step).
// The button nearest the USB connectors stops the ramp where it is; press it again and it goes on.

module ledramp (
    input  logic       clk,         // 50 MHz
    input  logic       btn,         // 0 while pressed
    output logic [7:0] dac_d,       // code 128 is 0 V (-0.02 V), 255 is +3.88 V: 1.02's V = 0.0307 x code - 3.95
    output logic       dac_clk,
    output logic [4:0] led          // led[4] (the MSB) is the leftmost; 1 = on
);
    // ---- the button starts and stops the ramp.  Its contacts bounce for a few milliseconds, so look at it only
    //      once every 2^20 clocks (21 ms): a press is a 1 at one look and a 0 at the next.  `last` starts at 0, so a
    //      press has to be a 1 first: the button's pull-up is inside the FPGA, and at the first clock after loading the
    //      pin can still read 0.  (Starting at 1 counted that as a press: the ramp stopped at 0 V before it began.)
    logic [19:0] tick = 0;
    logic        last = 0, running = 1;
    always_ff @(posedge clk) begin
        tick <= tick + 1;
        if (tick == 0) begin
            last <= btn;
            if (last && !btn)
                running <= !running;
        end
    end

    // ---- the ramp: a 31-bit counter whose top 7 bits are the DAC's steps above 0 V
    logic [30:0] t = 0;
    always_ff @(posedge clk)
        if (running)
            // ######################################################################
            // ##  KEY LINE: up by one every 20 ns.  The top 7 bits go up by one
            // ##  every 2^24 clocks (0.34 s): 0 to 127 in 43 s, then wrap to 0.
            // ######################################################################
            t <= t + 1;

    wire [6:0] v = t[30:24];        // 0 .. 127
    assign dac_d   = 8'd128 + v;    // 0 V .. +3.88 V
    assign led     = v[6:2];        // the top five bits: one LED step is 4 DAC steps, 0.12 V
    assign dac_clk = ~clk;          // as in sawtooth.sv
endmodule
```

- `t` is [1.01](1_01_led_counter.md#101-a-counter-on-the-leds)'s counter
  with 24 more bits under the ones that reach the DAC. The top seven bits,
  `v = t[30:24]`, go up by one every 2<sup>24</sup> × 20 ns = 0.34 s: 0 to
  127 in 43 s.
- The DAC gets `128 + v`: by [1.02](1_02_dac_sawtooth.md#102-a-sawtooth-from-the-dac)'s
  measured line, *V* = 0.0307 × code − 3.95, that is −0.02 V at code 128 and
  +3.88 V at code 255, 30.7 mV a step. After 127, `v` wraps to 0 and the DAC
  drops back to 0 V.
- `led = v[6:2]` is the top five of those seven bits. One step of the LEDs is
  four steps of the DAC, 0.12 V; the leftmost, `led[4]`, is worth 1.97 V.
- **The button stops and starts the ramp.** A button's contacts bounce: for a
  few milliseconds after a press they open and close many times. Looking at
  the button only once every 2<sup>20</sup> clocks (21 ms) steps over the
  bounce, and a press is a 1 at one look and a 0 at the next: one press, one
  toggle of `running`.
- **Why `last` starts at 0.** The button's pull-up is inside the FPGA
  (`PULLMODE=UP` in the `.lpf`), with no resistor on the board, and at the
  first clock after the design loads the pin can still read 0. The first
  version started `last` at 1, counted that 0 as a press, and stopped the
  ramp at 0 V before it began: the LEDs and p12 stayed dark. With `last` at 0
  a press has to be a 1 first.

## Run it

```console
$ cd $ADDA/src/verilog
$ make load-ledramp
```

**What you should see:** the five LEDs count up in binary for 43 s, all off
again, and again. Add up the weights of the ones that are lit:

| LED | `led[4]` (left) | `led[3]` | `led[2]` | `led[1]` | `led[0]` (right) |
| --- | --- | --- | --- | --- | --- |
| worth | 1.97 V | 0.98 V | 0.49 V | 0.25 V | 0.12 V |

`10001`, for instance, is 2.07 to 2.16 V: the LEDs show the ramp to within
one LED step, 0.12 V, since the two bits under them are hidden. Press the
button the moment a colour starts to glow, and read the LEDs.

## What it showed

On 2026-11-18, with the Icepi Zero DK0GFLAW driving AMOD-P's p12, by eye:
**red, yellow, green and blue each came on at the right point of the ramp,
in that order, and the blue was bright near the top.** The thresholds
themselves were not read off; that is the first item under Try this.

The same experiment on the ECP5-2ADC-2DAC board, whose finer DAC stops at
+2 V, lit the red, a little of the yellow and perhaps a hint of green at the
very top (all four ways on), and never the blue: an electron that falls
through 2 V brings 2 eV, and a blue photon needs 2.64 eV. Here the DAC
reaches +3.88 V, enough for all four.

## Try this

- **One way at a time.** For each colour, watch for the first glow, press the
  button, and read the LEDs. A dark room helps, and so does looking at the
  LED from the side. Do the colours come in the order of their photon
  energies?
- **Planck's constant.** Plot each threshold voltage against 1/λ: the slope is
  *hc*/*e*. The red and yellow are the same kind of LED (AlGaInP); the green
  and blue (InGaN) are a different material, and their thresholds sit above
  the red and yellow's line. With 0.12 V steps on the LEDs, how well can four
  points pin down the slope? (Showing the low bits too, or stepping the ramp
  by hand, would help: try it.)
- **The current.** A meter on p12's LED loop reads the LED's own voltage; the
  DAC's voltage less that, over the 100 Ω and the DAC's output resistance, is
  the current. Stop the ramp at a dozen points and plot the current on a log
  scale against the LED's voltage: the diode equation of
  [4.04](4_04_harmonics.md#404-harmonics-a-diode-clipper), once for each
  colour.
- **All four at once.** AMOD-P's next revision may give each LED its own
  resistor, so that all four can be on together and the colours come up one
  after another as the ramp rises. Work out how large the resistors would
  have to be for the DAC to light all four at once without drawing more than
  about 10 mA.

<!-- nav -->
[← 1.10 An AM radio](1_10_am_radio.md) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)** &emsp;&emsp;&emsp; [2.00 A processor on the FPGA →](2_00_a_processor_on_the_fpga.md)

<!-- author -->
<sub>Jason Gallicchio, jason@hmc.edu, Harvey Mudd College</sub>
