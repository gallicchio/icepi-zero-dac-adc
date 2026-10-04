<!-- nav -->
[← 7.03 A filter you can load](7_03_a_filter_you_can_load.md#703-a-filter-you-can-load) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)** &emsp;&emsp;&emsp; [7.05 Trading speed for bits →](7_05_trading_speed_for_bits.md#705-trading-speed-for-bits)

# 7.04 The filter as a LiteX peripheral

![The same filter three ways: the C firmware's filter command at the adda prompt, MicroPython on the board's Linux writing the registers with machine.mem32, and the laptop's filter_remote.py through LiteX's bridge, all addressing the same twenty-five control registers of filter_core.sv](img/dsp_d_litex_filter.png)

[7.03](7_03_a_filter_you_can_load.md#703-a-filter-you-can-load)'s filter
has a byte protocol that the laptop and the gateware both had to get
right by hand. Chapter 2 built a processor on the FPGA so that this kind
of thing becomes a register: the processor, or the laptop through LiteX's
bridge, or MicroPython on the board's own Linux, writes a number to an
address and the gateware uses it 40 ns later. This page makes the filter
a *peripheral* of [2.03](2_03_function_generator_peripheral.md#203-a-function-generator-peripheral)'s
SoC, and the point is that nothing about the filter changes: the datapath
of `filter.sv` becomes `filter_core.sv` with its settings as input ports,
and the twenty-five control registers are the contract.

## The contract

```console
$ cd src/riscv
$ python3 icepi_adda_soc.py --build --libc-mode full         # as 2.03; several minutes
$ litex_cli --csr-csv build/bone/csr.csv --regs --filter filter
```

| offset from `0xf000f800` | register | meaning |
| --- | --- | --- |
| +0x00 … +0x3c | `filter_b0` … `filter_b15` | the feed-forward taps, signed 16-bit, Q2.13; *b*<sub>0</sub> resets to 8192 (1.0) |
| +0x40 … +0x4c | `filter_a1` … `filter_a4` | the feedback taps |
| +0x50 | `filter_src` | 0 the ADC, 1 impulse, 2 step, 3 noise, 4 tone |
| +0x54 | `filter_out` | 0 the output, 1 the input, same delay |
| +0x58 | `filter_tone` | the tone's tuning word, *f* / 25 MHz × 2<sup>32</sup> |
| +0x5c | `filter_dac_source` | 0 the DAC plays the function generator (Chapter 2 unchanged), 1 the filter; 0 also clears the state |
| +0x60 | `filter_status` | bit 0 running, bit 1 clipped |

Two things in that table are the lessons of the page. The DAC has one pin
and two sources, so there is a multiplexer, and its reset value is why
Chapter 2 did not notice a new peripheral had been added. And the status
bits are what the gateware knows and software doesn't: `clipped` replaces
[7.03](7_03_a_filter_you_can_load.md#703-a-filter-you-can-load)'s LED, and
turning `dac_source` off and on clears an IIR that has latched into
saturation, which is how you recover from loading a pole outside the
unit circle.

<details>
<summary><b>Detail:</b> why the bank is pinned to the last slot</summary>

LiteX allocates its CSR banks alphabetically, and "filter" sorts between
"ctrl" and "funcgen". Left to itself it would have moved the function
generator, the LEDs and the lock-in, and every address quoted in
[2.06](2_06_registers_from_the_laptop.md#206-the-registers-from-the-laptop) and
[3.01](3_01_booting_linux.md#301-booting-linux) would have been wrong.
One line in `adda_litex.py` pins the new bank to slot 31, nothing moves,
and the moral of [2.06](2_06_registers_from_the_laptop.md#206-the-registers-from-the-laptop), use names from `csr.csv`, is shown biting.

</details>

<details>
<summary>The whole file: <code>filter_core.sv</code></summary>

<!-- file: src/riscv/filter_core.sv -->
```systemverilog
// filter_core.sv -- 7.03's filter.sv with the serial port replaced by registers (7.04).
//
// The same filter: direct form I, 16 feed-forward and 4 feedback taps in Q2.13 (the
// value x 8192), the same built-in stimuli and the same output select, line for line
// (the arithmetic, the pipeline and the 18-bit state are explained in filter.sv).
// What changed is where the settings come from: the coefficients, the source, the
// output select and the tone's tuning word are inputs, wired to CSRs by adda_litex.py,
// and the ADC's samples arrive from adda_io instead of the pins.
//
//   y[n] = ( b_0 x[n] + ... + b_15 x[n-15]  -  a_1 y[n-1] - ... - a_4 y[n-4] ) / 8192
//
// New, because a CPU wants to switch it on and off and ask how it is:
//   enable   low holds the filter's state at zero, so dac_value sits at 128.  Switching
//            a filter off and on clears it: an unstable set of a's saturates for ever
//            (7.02), and this is the way out.  The stimuli keep running.
//   running  high three samples after enable: the pipeline has filled, and dac_value is
//            the filter's answer to real input (filter.sv's latency, 120 ns).
//   clipped  the output saturated within the last 2^22 clocks (84 ms): filter.sv's led[4].
//
// One difference from filter.sv's stimuli: the noise re-seeds at every period start
// (every 2^14 samples) instead of only when a capture asks it to, so that the noise is
// periodic and a capture taken at any moment (2.04's peripheral, which knows nothing of
// this filter) holds exactly one period of it, which the laptop can line up by
// correlation.  The impulse and the step were periodic already.
module filter_core (
    input  logic             clk,           // 50 MHz
    input  logic [7:0]       sample,        // the ADC's code, from adda_io
    input  logic             sample_valid,  // one clock per sample: 25 MS/s
    // the settings, from CSRs
    input  logic [16*16-1:0] b_all,         // b_0..b_15, 16 bits each, b_0 lowest; Q2.13
    input  logic [16*4-1:0]  a_all,         // a_1..a_4, a_1 lowest
    input  logic [2:0]       src,           // 0 ADC; 1 impulse; 2 step; 3 noise; 4 tone
    input  logic             out_in,        // 1: the DAC plays the input, delayed to match
    input  logic [31:0]      tone_word,     // the tone: f / 25e6 x 2^32
    input  logic             enable,
    output logic             running,
    output logic             clipped,
    output logic [7:0]       dac_value = 128
);
    localparam integer NB = 16, NA = 4;             // feed-forward and feedback taps

    // ---- the settings, unpacked ------------------------------------------------------
    logic signed [15:0] b [0:NB-1];                 // Q2.13
    logic signed [15:0] a [1:NA];
    always_comb begin
        for (int k = 0; k < NB; k++) b[k] = b_all[16*k +: 16];
        for (int k = 1; k <= NA; k++) a[k] = a_all[16*(k-1) +: 16];
    end

    // ---- the ADC's samples, as filter.sv sees them ------------------------------------
    logic new_sample;
    logic signed [8:0] x;                           // the sample, -128..127
    assign new_sample = sample_valid;
    assign x = $signed({1'b0, sample}) - 9'sd128;
    logic step = 0;                                 // the clock after new_sample
    always_ff @(posedge clk) step <= new_sample;

    // ---- the built-in stimuli, one value per sample (filter.sv) ------------------------
    logic [14:0] cnt = 0;                           // counts samples; the period is 2^14
    logic        period_start;                      // the next sample is cnt 0
    assign period_start = (cnt[13:0] == 14'h3fff);
    logic signed [8:0] impulse, stp, noise, tone = 0;
    assign impulse = (cnt[13:0] == 0) ? 9'sd64 : 9'sd0;
    assign stp     = cnt[14] ? 9'sd64 : -9'sd64;
    localparam logic [31:0] SEED = 32'h2545_f491;
    logic [31:0] r = SEED, r1, r2, r3;
    assign r1 = r ^ (r << 13);
    assign r2 = r1 ^ (r1 >> 17);
    assign r3 = r2 ^ (r2 << 5);
    logic signed [10:0] gsum;
    assign gsum  = $signed({3'b0, r[7:0]}) + $signed({3'b0, r[15:8]}) + $signed({3'b0, r[23:16]})
                 + $signed({3'b0, r[31:24]}) - 11'sd510;
    assign noise = 9'(gsum >>> 4);
    logic signed [7:0] sin64 [0:255];
    initial for (int i = 0; i < 256; i++)
        sin64[i] = $rtoi($floor(64.0 * $sin(6.283185307179586 * i / 256) + 0.5));
    logic [31:0] phase = 0;
    always_ff @(posedge clk)
        if (new_sample) begin
            cnt   <= cnt + 1;
            r     <= period_start ? SEED : r3;      // periodic: see the header
            phase <= phase + tone_word;
            tone  <= sin64[phase[31:24]];
        end
    logic signed [8:0] u;                           // the filter's input, this sample
    always_comb case (src)
        3'd1:    u = impulse;
        3'd2:    u = stp;
        3'd3:    u = noise;
        3'd4:    u = tone;
        default: u = x;
    endcase

    // ---- the filter: filter.sv's, with `enable` low clearing every register -----------
    logic signed [8:0]  xd [0:NB-1];                // x[n-k]: the delay line
    logic signed [24:0] pb [0:NB-1];                // b_k x[n-k], 9 x 16 bits
    logic signed [26:0] q  [0:3];                   // sums of four products
    logic signed [28:0] F = 0;                      // the sum of all sixteen
    initial for (int k = 0; k < NB; k++) begin xd[k] = 0; pb[k] = 0; end
    initial for (int j = 0; j < 4; j++) q[j] = 0;
    always_ff @(posedge clk)
        if (!enable) begin
            for (int k = 0; k < NB; k++) begin xd[k] <= 0; pb[k] <= 0; end
            for (int j = 0; j < 4; j++) q[j] <= 0;
            F <= 0;
        end else begin
            if (new_sample) begin
                // ##################################################################
                // ##  KEY LINE 1: the delay line.  Each new input pushes the rest along.
                // ##################################################################
                xd[0] <= u;
                for (int k = 1; k < NB; k++) xd[k] <= xd[k-1];
                for (int j = 0; j < 4; j++) q[j] <= pb[4*j] + pb[4*j+1] + pb[4*j+2] + pb[4*j+3];
            end
            if (step) begin
                // ##################################################################
                // ##  KEY LINE 2: sixteen multiplies at once, one hardware multiplier
                // ##  each; b[k] is a wire from a register the CPU writes.
                // ##################################################################
                for (int k = 0; k < NB; k++) pb[k] <= b[k] * xd[k];
                F <= q[0] + q[1] + q[2] + q[3];
            end
        end

    localparam logic signed [17:0] YMAX = 18'sd131071, YMIN = -YMAX - 18'sd1;
    logic signed [17:0] yd [1:NA];                  // y[n-1..n-4], Q10.8
    logic signed [33:0] pa1 = 0, pa2 = 0, pa3 = 0, pa4 = 0;    // 16 x 18 bits
    logic signed [39:0] G = 0, acc, shifted;
    logic               clip_y;
    initial for (int k = 1; k <= NA; k++) yd[k] = 0;
    always_ff @(posedge clk)
        if (!enable) begin
            pa1 <= 0; pa2 <= 0; pa3 <= 0; pa4 <= 0;
        end else if (step) begin
            pa1 <= a[1] * yd[1];
            pa2 <= a[2] * yd[1];
            pa3 <= a[3] * yd[2];
            pa4 <= a[4] * yd[3];
        end
    assign acc     = G - pa1;                       // Q.21: 13 from the coefficients, 8 from y
    assign shifted = acc >>> 13;                    // Q10.8
    assign clip_y  = (shifted > YMAX) || (shifted < YMIN);
    always_ff @(posedge clk)
        if (!enable) begin
            G <= 0;
            for (int k = 1; k <= NA; k++) yd[k] <= 0;
        end else if (new_sample) begin
            G <= (F <<< 8) - pa2 - pa3 - pa4;
            // ######################################################################
            // ##  KEY LINE 3: the output, which is also the next sample's y[n-1].
            // ######################################################################
            yd[1] <= (shifted > YMAX) ? YMAX : (shifted < YMIN) ? YMIN : 18'(shifted);
            for (int k = 2; k <= NA; k++) yd[k] <= yd[k-1];
        end

    // ---- the output: y rounded to codes, or the input with the same delay -------------
    logic signed [18:0] y_round;
    logic signed [10:0] y, mon = 0;
    assign y_round = yd[1] + 19'sd128;
    assign y       = 11'(y_round >>> 8);
    always_ff @(posedge clk) begin
        if (new_sample) mon <= xd[2];               // the input that yd[1] answers to
        if (out_in) dac_value <= 8'(mon + 128);
        else        dac_value <= (y > 127) ? 8'd255 : (y < -128) ? 8'd0 : 8'(y + 128);
    end

    // ---- status ----------------------------------------------------------------------
    logic [1:0]  primed = 0;                        // samples since enable, up to 3
    logic [21:0] clip_timer = 0;                    // holds `clipped` for 2^22 clocks
    always_ff @(posedge clk) begin
        if (!enable)                                 primed <= 0;
        else if (new_sample && primed != 2'd3)       primed <= primed + 1;
        if (new_sample && (clip_y || y > 127 || y < -128)) clip_timer <= '1;
        else if (clip_timer != 0)                    clip_timer <= clip_timer - 1;
    end
    assign running = (primed == 2'd3);
    assign clipped = (clip_timer != 0);
endmodule
```

</details>

`filter_core.sv` is `filter.sv` with the [UART](https://en.wikipedia.org/wiki/Universal_asynchronous_receiver-transmitter) parser, the capture and the
LEDs removed and the settings brought in as ports (`b_all`, `a_all`, `src`,
`out_in`, `tone_word`, `enable`), plus `running` and `clipped` going out.
The key line is unchanged: `pb[k] <= b[k] * xd[k]`, where *b*[*k*] is now a
wire from a register that any processor can write. The seven-check
testbench feeds it [7.03](7_03_a_filter_you_can_load.md#703-a-filter-you-can-load)'s
own noise sequence and compares every output sample with `filter.py`'s
bit-exact model: 2996 of 2996 identical, so the two pages' filters are
the same filter by construction, not by intention.

## Three ways to load it

**From the firmware**, at the `adda>` prompt, the way a student with
nothing but a terminal sees a filter work ([2.05](2_05_lockin_peripheral.md#205-a-lock-in-peripheral)'s
shell, with a `filter` command):

```console
$ litex_term --kernel=firmware/firmware.bin /dev/ttyUSB0
adda> filter lowpass           # the 15-tap 2 MHz low-pass of 7.01, built in
adda> filter src 4             # the 1 MHz tone, 64 codes, into the filter
adda> filter on                # the DAC now plays the filter
adda> filter tone 5000000
adda> filter rc 4              # 7.02's one-pole, K = 4
adda> filter b 0 8192          # one coefficient at a time
adda> filter a 1 -9000         # a pole outside the circle: "clipped"; off, on clears it
adda> filter off               # back to the function generator
```

Every command prints the whole state back. The firmware has three
presets (`lowpass`, `edge`, `rc K`) because the CPU has no scipy; the
numbers are the same integers `filter.py` prints.

**From the laptop over the bridge**, with no firmware at all
([2.06](2_06_registers_from_the_laptop.md#206-the-registers-from-the-laptop)'s
`litex_server` and RemoteClient). `filter_remote.py` imports
`filter.py`'s design functions, so every flag of [7.03](7_03_a_filter_you_can_load.md#703-a-filter-you-can-load) works and the
quantization is literally the same code. Measured on the bench, with the
M2k's scope on DAC OUT and the filter's own tone as the input:

```console
$ openFPGALoader -b icepi-zero build/bone/gateware/icepi_zero.bit
$ litex_server --uart --uart-port /dev/ttyUSB0 &
$ python3 filter_remote.py --lowpass 2e6 --src 4 --tone 1e6 --on
    as designed:        -0.1    -0.3    -1.2    -5.0   -12.1   -24.6   -54.2 ...
loaded
$ python3 filter_remote.py --tone 3e6
$ python3 filter_remote.py --tone 5e6
$ python3 filter_remote.py --edge --tone 1e6
$ python3 filter_remote.py --rc 250e3 --tone 1e6
$ python3 filter_remote.py --show
filter: b = 499 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
        a = -7693 0 0 0   (x 8192)
        src tone, out the output, tone 1000000 Hz; the DAC plays the filter, running
```

| filter, tone | scope, DAC OUT | re the 64-code tone | design |
| --- | ---: | ---: | ---: |
| low-pass 2 MHz, 1 MHz | 1.698 V = 55 codes | −1.3 dB | −1.2 dB |
| low-pass, 3 MHz | 0.469 V = 15 codes | −12.4 dB | −12.1 dB |
| low-pass, 5 MHz | 0.000 V | below the noise | −54 dB |
| the input (`--out 1`), 5 MHz | 1.812 V = 59 codes | −0.7 dB | 0 |
| edge detector, 1 MHz | 0.120 V = 4 codes | −24.3 dB | −24.0 dB |
| edge detector, 4 MHz | 1.723 V = 56 codes | −1.1 dB | −0.6 dB |
| one-pole 250 kHz, 1 MHz | 0.468 V = 15 codes | −12.5 dB | −12.3 dB |

Twenty register writes take a few tens of milliseconds over the bridge;
a new design is one edited line and a rerun. This is the way to iterate.

**From MicroPython on the board's Linux**, with `machine.mem32`
([3.02](3_02_a_driver.md#302-a-driver)'s way to a register
without a driver): `micropython /root/filter.py lowpass src 4 on`, `show`,
`rc 4 tone 5000000`, several per line, no laptop and no scipy. The
honest footnote: the filter is **not in the prebuilt Linux bitstream**,
which was built before this page; `make_linux.py` calls the same
`add_adda()`, so the next rebuild puts it at the same address with
nothing else moving, and the script is in the root overlay waiting for
it.

## The price of the bus, and the price of the chip

| way | per register | per new design | needs |
| --- | --- | --- | --- |
| C in the firmware | tens of nanoseconds | a compile and an upload | the terminal |
| the laptop over the bridge | a few milliseconds | nothing: rerun the script | `litex_server`, numpy and scipy |
| MicroPython on the board | microseconds | nothing | Linux booted, no scipy |

And the chip: the SoC used 7 of the 28 multipliers (four in VexRiscv's
multiplier, one in the function generator, two in the lock-in); the
filter uses 20; **27 of 28**. A seventeenth tap, or a second filter, means
time-sharing multipliers or building them from logic, which is the
conversation every FPGA designer eventually has with the resource report.
The firmware SoC fits at 69 MHz, the bridge SoC at 74, both with the
filter.

**Try this:**

- A third DAC source: a 2-bit `dac_source` and your own module. The mux is
  one line; the registers are three.
- A sample counter in `filter_status` so that software can measure the
  25 MS/s itself (and notice when the clock is wrong).
- Wire `filter_core`'s period start to the capture core's trigger, so the
  bridge capture is aligned to the stimulus as [7.03](7_03_a_filter_you_can_load.md#703-a-filter-you-can-load)'s was (six lines), and
  then `filter_remote.py --src 1 --capture` gives the [impulse response](https://en.wikipedia.org/wiki/Impulse_response)
  through the loopback cable.
- Rebuild the Linux SoC with the filter ([3.03](3_03_building_linux.md#303-building-linux-yourself)) and add `filter/` to the
  [sysfs](https://en.wikipedia.org/wiki/Sysfs) driver of [3.02](3_02_a_driver.md#302-a-driver), so `echo 8192 > /sys/.../b0` works.
