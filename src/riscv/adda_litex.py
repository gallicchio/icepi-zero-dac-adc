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
