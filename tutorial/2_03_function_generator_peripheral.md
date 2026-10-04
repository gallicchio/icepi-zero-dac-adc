<!-- nav -->
[← 2.02 C on the CPU](2_02_c_on_the_cpu.md#202-c-on-the-cpu) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)** &emsp;&emsp;&emsp; [2.04 A capture peripheral →](2_04_capture_peripheral.md#204-a-capture-peripheral)

# 2.03 A function-generator peripheral

![The four waveforms of the LiteX function generator](img/funcgen.png)

Now put Chapter 1's circuits into the SoC, where the CPU can reach them. This
section adds a function generator; [2.04](2_04_capture_peripheral.md#204-a-capture-peripheral) and [2.05](2_05_lockin_peripheral.md#205-a-lock-in-peripheral) add a capture unit and a
lock-in. All three share the converters, so they're built from four small
SystemVerilog *cores* in [`src/riscv/`](../src/riscv/), plus one Python file
that connects them to the CPU.

## The cores

The first core owns the converter pins. It's the clocking of [1.02](1_02_dac_sawtooth.md#102-a-sawtooth-from-the-dac) and [1.04](1_04_adc_on_the_leds.md#104-the-adc-on-the-leds),
unchanged. (Its name, like `icepi_adda.lpf`'s, uses *adda* for *analog to
digital and digital to analog*: the ADC and the DAC.)

<!-- file: src/riscv/adda_io.sv -->
```systemverilog
// adda_io.sv -- the converter pins, and nothing else.
//
// The same clocking as Chapter 1: the DAC takes a new value every clock
// (50 MS/s) on the rising edge of the inverted clock, and the ADC is clocked
// at clk/2 = 25 MS/s and read just before each rising edge of its clock.
// Every peripheral that wants the converters goes through here.

module adda_io (
    input  logic       clk,             // the SoC's 50 MHz system clock
    // the pins
    input  logic [7:0] adc_d,
    output logic       adc_clk,
    output logic [7:0] dac_d = 128,
    output logic       dac_clk,
    // the peripherals' side
    input  logic [7:0] dac_value,       // what the DAC should output (0..255)
    output logic [7:0] adc_sample = 128,
    output logic       adc_valid  = 0   // high for one clock when adc_sample is new
);
    always_ff @(posedge clk)
        dac_d <= dac_value;
    assign dac_clk = ~clk;

    logic adc_clk_r = 0;
    always_ff @(posedge clk) begin
        adc_clk_r <= ~adc_clk_r;
        adc_valid <= 0;
        if (adc_clk_r == 0) begin
            adc_sample <= adc_d;
            adc_valid  <= 1;
        end
    end
    assign adc_clk = adc_clk_r;
endmodule
```

The function generator is the DDS of [1.03](1_03_dac_sine.md#103-a-sine-direct-digital-synthesis), with the tuning
word, amplitude and waveform turned into *inputs*, so the CPU can change them
while it runs:

<!-- file: src/riscv/funcgen_core.sv -->
```systemverilog
// funcgen_core.sv -- a DDS function generator: sine, square, triangle, sawtooth.
//
// The phase accumulator of sine.sv, with the waveform and amplitude now
// inputs, so a CPU can change them while it runs.  The phase is also an
// output: the lock-in uses it as its reference.
//
//   f = tw * f_clk / 2^32        amplitude: 255 = full scale (+-3.9 V)

module funcgen_core (
    input  logic        clk,
    input  logic [31:0] tw,             // tuning word: from a CPU register
    input  logic [7:0]  amplitude,      // 0..255: from a CPU register
    input  logic [1:0]  waveform,       // 0 sine, 1 square, 2 triangle, 3 sawtooth
    output logic [31:0] phase = 0,
    output logic [7:0]  dac_value = 128
);
    logic signed [7:0] sine_table [0:255];
    initial
        for (int i = 0; i < 256; i++)
            sine_table[i] = $rtoi($floor(127.0 * $sin(6.283185307179586 * i / 256) + 0.5));

    // ##########################################################################
    // ##  KEY LINE: the same phase accumulator as sine.sv, but now `tw` is a
    // ##  wire from a register that the CPU writes.
    // ##########################################################################
    always_ff @(posedge clk)
        phase <= phase + tw;

    // step 1: the waveform, as a signed number -128..127
    logic [8:0] p;
    assign p = phase[31:23];                    // 9 bits of phase, for the triangle
    logic signed [7:0] w = 0;
    always_ff @(posedge clk)
        case (waveform)
            2'd0: w <= sine_table[phase[31:24]];
            2'd1: w <= phase[31] ? -8'sd127 : 8'sd127;
            2'd2: w <= (p < 256) ? p - 128 : 383 - p;   // up for half a cycle, then down
            2'd3: w <= phase[31:24] - 128;
        endcase

    // step 2: scale by amplitude/256.  step 3: back to offset binary for the DAC
    logic signed [16:0] scaled = 0;
    always_ff @(posedge clk) begin
        scaled    <= w * $signed({1'b0, amplitude});
        dac_value <= (scaled >>> 8) + 128;
    end
endmodule
```

## Registers: the Python glue

`adda_litex.py` is the only new kind of code. For each core it declares the
registers (CSRs), wires them to the core's ports with `Instance(...)`, and
tells LiteX where the SystemVerilog files are. The function generator's
wrapper is the whole idea in sixteen lines:

```python
class FuncGen(LiteXModule):
    def __init__(self):
        self.tw        = CSRStorage(32, description="Tuning word: f = tw * f_sys / 2^32.")
        self.amplitude = CSRStorage(8, reset=255, description="0..255; 255 = full scale.")
        self.waveform  = CSRStorage(2, description="0 sine, 1 square, 2 triangle, 3 sawtooth.")

        self.phase     = Signal(32)   # to the lock-in
        self.dac_value = Signal(8)    # to the DAC
        self.specials += Instance("funcgen_core",
            i_clk       = ClockSignal("sys"),
            i_tw        = self.tw.storage,
            i_amplitude = self.amplitude.storage,
            i_waveform  = self.waveform.storage,
            o_phase     = self.phase,
            o_dac_value = self.dac_value,
        )
```

`Instance("funcgen_core", i_tw=self.tw.storage, ...)` is a SystemVerilog
module instance written in Python: `i_` marks an input port and `o_` an
output. `self.tw.storage` is the register's value, which the CPU sets. LiteX
also writes the C side for you: a function per register, like
`funcgen_tw_write()`, in a header file. The capture and lock-in wrappers are
the same pattern, for [2.04](2_04_capture_peripheral.md#204-a-capture-peripheral) and [2.05](2_05_lockin_peripheral.md#205-a-lock-in-peripheral), and
`add_adda()` adds all three to an SoC, with the converter pins and the four
SystemVerilog files:

<details>
<summary>The whole file: <code>adda_litex.py</code></summary>

<!-- file: src/riscv/adda_litex.py -->
```python
"""LiteX peripherals for the AD9280 ADC + AD9708 DAC module on an Icepi Zero.

Each peripheral is a hand-written SystemVerilog core (the *_core.sv files) wrapped in a
few lines of Python that give it registers ("CSRs") the CPU can read and write.

    from adda_litex import add_adda
    add_adda(soc)          # inside your SoC's __init__, after SoCCore.__init__

adds, in the CPU's address space:

    funcgen_tw, funcgen_amplitude, funcgen_waveform      the function generator
    capture_control/config/status + capture_buf (16 kB)  the ADC capture
    lockin_control/n_log2/status/x/y                     the lock-in
    filter_b0..b15, a1..a4, src, out, tone, dac_source,  the loadable filter (7.04)
    filter_status
"""
import os

from migen import *
from litex.gen import LiteXModule
from litex.build.generic_platform import Pins, Subsignal, IOStandard, Misc
from litex.soc.interconnect.csr import CSRStorage, CSRStatus, CSRField
from litex.soc.interconnect import wishbone
from litex.soc.integration.soc import SoCRegion

HERE = os.path.dirname(os.path.abspath(__file__))

# The pins -- the same balls as ../verilog/icepi_adda.lpf in Chapter 1.
# In Pins("..."), the first ball is bit 0.
adda_pins = [
    ("adda", 0,
        Subsignal("adc_d",   Pins("R1 R3 N4 P3 P2 M2 L1 L2")),
        Subsignal("adc_clk", Pins("J1"), Misc("DRIVE=4 SLEWRATE=SLOW")),
        Subsignal("dac_d",   Pins("D4 E4 E3 J3 F3 E1 G1 H2"), Misc("DRIVE=4 SLEWRATE=SLOW")),
        Subsignal("dac_clk", Pins("G2"), Misc("DRIVE=4 SLEWRATE=SLOW")),
        IOStandard("LVCMOS33"),
    ),
]


class FuncGen(LiteXModule):
    def __init__(self):
        self.tw        = CSRStorage(32, description="Tuning word: f = tw * f_sys / 2^32.")
        self.amplitude = CSRStorage(8, reset=255, description="0..255; 255 = full scale.")
        self.waveform  = CSRStorage(2, description="0 sine, 1 square, 2 triangle, 3 sawtooth.")

        self.phase     = Signal(32)   # to the lock-in
        self.dac_value = Signal(8)    # to the DAC
        self.specials += Instance("funcgen_core",
            i_clk       = ClockSignal("sys"),
            i_tw        = self.tw.storage,
            i_amplitude = self.amplitude.storage,
            i_waveform  = self.waveform.storage,
            o_phase     = self.phase,
            o_dac_value = self.dac_value,
        )


class AdcCapture(LiteXModule):
    def __init__(self, sample, sample_valid):
        self.control = CSRStorage(fields=[
            CSRField("start", pulse=True, description="Write 1 to start a capture."),
        ])
        self.config = CSRStorage(fields=[
            CSRField("decimation",  size=4, offset=0,  description="Keep 1 sample in 2^decimation."),
            CSRField("trig_enable", size=1, offset=8,  description="Wait for an upward crossing of trig_level."),
            CSRField("trig_level",  size=8, offset=16, reset=128, description="Trigger level, in ADC codes."),
        ])
        self.status = CSRStatus(fields=[
            CSRField("busy", description="Waiting for the trigger, or recording."),
            CSRField("done", description="The buffer holds a complete capture."),
        ])

        # The buffer: a 32-bit Wishbone bus slave, read-only in effect.
        self.bus = wishbone.Interface(data_width=32, adr_width=30)
        rd_addr = Signal(12)
        rd_data = Signal(32)
        self.comb += [
            rd_addr.eq(self.bus.adr[:12]),
            self.bus.dat_r.eq(rd_data),
        ]
        # The core's memory answers one clock after it is asked: acknowledge then.
        self.sync += self.bus.ack.eq(self.bus.cyc & self.bus.stb & ~self.bus.ack)

        self.specials += Instance("adc_capture_core",
            i_clk          = ClockSignal("sys"),
            i_sample       = sample,
            i_sample_valid = sample_valid,
            i_start        = self.control.fields.start,
            i_decimation   = self.config.fields.decimation,
            i_trig_enable  = self.config.fields.trig_enable,
            i_trig_level   = self.config.fields.trig_level,
            o_busy         = self.status.fields.busy,
            o_done         = self.status.fields.done,
            i_rd_addr      = rd_addr,
            o_rd_data      = rd_data,
        )


class LockIn(LiteXModule):
    def __init__(self, sample, sample_valid, phase):
        self.control = CSRStorage(fields=[
            CSRField("start", pulse=True, description="Write 1 to start a measurement."),
        ])
        self.n_log2 = CSRStorage(5, reset=20, description="Average 2^n_log2 samples (max 24).")
        self.status = CSRStatus(fields=[
            CSRField("busy", description="Measuring."),
            CSRField("done", description="x and y hold a finished measurement."),
        ])
        self.x = CSRStatus(64, description="Sum of (adc-128)*cos, signed.")
        self.y = CSRStatus(64, description="Sum of (adc-128)*(-sin), signed.")

        x_sum = Signal((48, True))
        y_sum = Signal((48, True))
        self.comb += [self.x.status.eq(x_sum), self.y.status.eq(y_sum)]   # sign-extends
        self.specials += Instance("lockin_core",
            i_clk          = ClockSignal("sys"),
            i_sample       = sample,
            i_sample_valid = sample_valid,
            i_phase        = phase,
            i_start        = self.control.fields.start,
            i_n_log2       = self.n_log2.storage,
            o_busy         = self.status.fields.busy,
            o_done         = self.status.fields.done,
            o_x_sum        = x_sum,
            o_y_sum        = y_sum,
        )


class Filter(LiteXModule):
    """7.03's loadable filter (filter_core.sv) with its settings in registers.  The 16 b
    and 4 a registers are made in order, so b_k is at b0's address + 4k and a_k at
    a1's + 4(k-1): software can index them instead of naming all twenty."""
    def __init__(self, sample, sample_valid, bypass):
        for k in range(16):
            setattr(self, "b%d" % k, CSRStorage(16, name="b%d" % k, reset=8192 if k == 0 else 0,
                description="b_%d, signed, Q2.13 (8192 = 1.0).  At power-up a wire: b_0 = 1." % k))
        for k in range(1, 5):
            setattr(self, "a%d" % k, CSRStorage(16, name="a%d" % k,
                description="a_%d, signed, Q2.13; 0 = an FIR." % k))
        self.src  = CSRStorage(3, description="Input: 0 the ADC; 1 an impulse (+64, every 2^14 samples); "
                                              "2 a step (-64/+64, every 2^14); 3 white noise; 4 a tone.")
        self.out  = CSRStorage(1, description="What the filter outputs: 0 its output, 1 its input, with the same delay.")
        self.tone = CSRStorage(32, reset=0x0a3d70a4, description="The tone's tuning word: f / 25e6 x 2^32 (reset: 1 MHz).")
        self.dac_source = CSRStorage(1, description="What the DAC plays: 0 the function generator (as in Chapter 2), "
                                                    "1 the filter.  0 also clears the filter's state.")
        self.status = CSRStatus(fields=[
            CSRField("running", description="The filter drives the DAC and its pipeline is full."),
            CSRField("clipped", description="The output saturated within the last 84 ms."),
        ])

        # The twenty 16-bit registers, side by side, as one wide input to the core.
        b_all = Cat(*[getattr(self, "b%d" % k).storage for k in range(16)])
        a_all = Cat(*[getattr(self, "a%d" % k).storage for k in range(1, 5)])
        y = Signal(8)
        self.specials += Instance("filter_core",
            i_clk          = ClockSignal("sys"),
            i_sample       = sample,
            i_sample_valid = sample_valid,
            i_b_all        = b_all,
            i_a_all        = a_all,
            i_src          = self.src.storage,
            i_out_in       = self.out.storage,
            i_tone_word    = self.tone.storage,
            i_enable       = self.dac_source.storage,
            o_running      = self.status.fields.running,
            o_clipped      = self.status.fields.clipped,
            o_dac_value    = y,
        )
        # ######################################################################
        # ##  KEY LINE: the DAC's source is a register bit.  0 (the reset value)
        # ##  leaves everything of Chapter 2 exactly as it was.
        # ######################################################################
        self.dac_value = Signal(8)
        self.comb += self.dac_value.eq(Mux(self.dac_source.storage, y, bypass))


def add_adda(soc):
    """Add the converter pins and all four peripherals to a LiteX SoC."""
    platform = soc.platform
    platform.add_extension(adda_pins)
    for f in ["adda_io.sv", "funcgen_core.sv", "adc_capture_core.sv", "lockin_core.sv", "filter_core.sv"]:
        platform.add_source(os.path.join(HERE, f))

    pads = platform.request("adda")
    adc_sample = Signal(8)
    adc_valid  = Signal()

    soc.funcgen = FuncGen()
    soc.capture = AdcCapture(adc_sample, adc_valid)
    soc.lockin  = LockIn(adc_sample, adc_valid, soc.funcgen.phase)
    # LiteX hands out register addresses in alphabetical order, and "filter" would land
    # between "ctrl" and "funcgen" and move every address in Chapters 2 and 3.  Pin it to
    # the last of the 32 slots instead (0xf000f800), and nothing else moves.
    soc.csr.add("filter", n=soc.csr.n_locs - 1)
    soc.filter  = Filter(adc_sample, adc_valid, soc.funcgen.dac_value)

    soc.specials += Instance("adda_io",
        i_clk        = ClockSignal("sys"),
        i_adc_d      = pads.adc_d,
        o_adc_clk    = pads.adc_clk,
        o_dac_d      = pads.dac_d,
        o_dac_clk    = pads.dac_clk,
        i_dac_value  = soc.filter.dac_value,      # the function generator, or the filter
        o_adc_sample = adc_sample,
        o_adc_valid  = adc_valid,
    )

    # Put the capture buffer on the CPU's bus, in the uncached I/O area.
    soc.bus.add_slave("capture_buf", soc.capture.bus,
        SoCRegion(size=0x4000, cached=False))
```

</details>

And the SoC itself: LiteX-Boards' stock Icepi Zero SoC of [2.01](2_01_a_cpu_and_its_bios.md#201-a-cpu-and-its-bios), plus
`add_adda()`:

<!-- file: src/riscv/icepi_adda_soc.py -->
```python
#!/usr/bin/env python3
"""A LiteX SoC for the Icepi Zero with the ADC/DAC peripherals added.

    python3 icepi_adda_soc.py --build          # about 1.5 minutes
    python3 icepi_adda_soc.py --load           # into the FPGA's SRAM

Everything the stock LiteX Icepi Zero target has (VexRiscv CPU, 32 MB SDRAM,
serial port, BIOS, LED chaser) plus add_adda()'s peripherals: the function
generator, the capture, the lock-in (2.03-2.05) and the loadable filter (7.04).
"""
from litex.build.parser import LiteXArgumentParser
from litex.soc.integration.builder import Builder
from litex_boards.platforms import icepi_zero as icepi_zero_platform
from litex_boards.targets import icepi_zero

from adda_litex import add_adda


class BaseSoC(icepi_zero.BaseSoC):
    def __init__(self, **kwargs):
        icepi_zero.BaseSoC.__init__(self, **kwargs)   # the stock SoC...
        add_adda(self)                                # ...plus our peripherals


def main():
    parser = LiteXArgumentParser(platform=icepi_zero_platform.Platform,
                                 description="Icepi Zero + ADC/DAC SoC.")
    parser.add_target_argument("--sys-clk-freq", default=50e6, type=float, help="System clock.")
    args = parser.parse_args()

    soc = BaseSoC(sys_clk_freq=args.sys_clk_freq, **parser.soc_argdict)
    builder = Builder(soc, **parser.builder_argdict)
    if args.build:
        builder.build(**parser.toolchain_argdict)
    if args.load:
        soc.platform.create_programmer().load_bitstream(builder.get_bitstream_filename(mode="sram"))


if __name__ == "__main__":
    main()
```

## Build it

```bash
cd src/riscv
python3 icepi_adda_soc.py --build --libc-mode full     # about 1.5 minutes
```

(`--libc-mode full` gives C programs the whole standard library, including
`atoi()` and `sqrtf()`, instead of LiteX's default minimal one.) The CPU and
SoC take about a third of the FPGA's logic and most of its block RAM.
Everything lands in `build/icepi_zero/`. Look at its `csr.csv`, the new SoC's
map:

```text
csr_base,capture,0xf0000000,,
csr_base,ctrl,0xf0000800,,
csr_base,funcgen,0xf0001000,,
...
csr_base,leds,0xf0002000,,
csr_base,lockin,0xf0002800,,
...
csr_register,funcgen_tw,0xf0001000,1,rw
csr_register,funcgen_amplitude,0xf0001004,1,rw
csr_register,funcgen_waveform,0xf0001008,1,rw
...
memory_region,capture_buf,0x80000000,16384,io
```

Notice that the LEDs moved, from 0xf0001000 in the stock SoC to 0xf0002000.
LiteX hands out addresses as it builds, so always look them up in `csr.csv`
(or let the generated C functions do it) rather than remembering them.

## Drive it from the BIOS

Load it, and connect a terminal (and a scope to the DAC output):

```bash
python3 icepi_adda_soc.py --load
litex_term /dev/ttyUSB0            # press Enter for the litex> prompt
```

1 MHz is a tuning word of 0x051eb852:

```
litex> mem_write 0xf0001000 0x051eb852
litex> mem_write 0xf0001004 64
litex> mem_read 0xf0001000 12
Memory dump:
0xf0001000  52 b8 1e 05 40 00 00 00 00 00 00 00              R...@.......
```

The first write sets 1 MHz; the second sets the amplitude to 64/255, and the
scope shows the sine shrink to a quarter of full scale (measured amplitude:
0.956 V against 3.82 V at full scale). A store to an address, and the DDS in
the FPGA changes frequency.

## A C program

[`src/riscv/firmware/`](../src/riscv/firmware/) holds a small command shell,
one command per instrument. The function-generator part is this:

```c
static void funcgen_set(uint32_t hz, int amplitude, int wave)
{
	uint32_t tw = ((uint64_t)hz << 32) / F_SYS;     /* f = tw * F_SYS / 2^32 */
	funcgen_tw_write(tw);
	funcgen_amplitude_write(amplitude);
	funcgen_waveform_write(wave);
}
```

The whole program is printed at the end of [2.05](2_05_lockin_peripheral.md#205-a-lock-in-peripheral).
Build it and send it to the board as in [2.02](2_02_c_on_the_cpu.md#202-c-on-the-cpu):

```bash
cd firmware && make && cd ..            # -> firmware/firmware.bin, about 17 kB
litex_term --kernel=firmware/firmware.bin /dev/ttyUSB0
```

then `serialboot` at the `litex>` prompt. The firmware takes over the same
terminal with a prompt of its own, `adda>`; from here on, `adda>` means the
board's C program is listening:

```
ADC/DAC peripherals on LiteX.  Type 'help'.
adda> fg 250000 191 triangle
funcgen: 249999.994 Hz, amplitude 191/255, triangle
```

The figure at the top of this page shows all four waveforms, measured with a
scope on DAC OUT (the right-hand SMA, as in [1.02](1_02_dac_sawtooth.md#102-a-sawtooth-from-the-dac)).

**Try this:**

- Add an `offset` register: a signed number added to the waveform before it
  goes to the DAC. You need a `CSRStorage` in `FuncGen`, a port on
  `funcgen_core`, and a few lines of C.
- Add a frequency *sweep* command to the firmware: step `funcgen_tw` in a loop
  with `busy_wait()` between steps. How fast can the CPU change the frequency?
  (Look at the DAC output with the scope's persistence on.)
- Show the waveform number on the LEDs with `leds_out_write()`.

<!-- nav -->
[← 2.02 C on the CPU](2_02_c_on_the_cpu.md#202-c-on-the-cpu) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)** &emsp;&emsp;&emsp; [2.04 A capture peripheral →](2_04_capture_peripheral.md#204-a-capture-peripheral)

<!-- author -->
<sub>Jason Gallicchio, jason@hmc.edu, Harvey Mudd College</sub>
