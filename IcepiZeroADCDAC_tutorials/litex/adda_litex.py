"""LiteX peripherals for the AD9280 ADC + AD9708 DAC module on an Icepi Zero.

Each peripheral is a hand-written Verilog core (the *_core.v files) wrapped in a
few lines of Python that give it registers ("CSRs") the CPU can read and write.

    from adda_litex import add_adda
    add_adda(soc)          # inside your SoC's __init__, after SoCCore.__init__

adds, in the CPU's address space:

    funcgen_tw, funcgen_amplitude, funcgen_waveform      the function generator
    capture_control/config/status + capture_buf (16 kB)  the ADC capture
    lockin_control/n_log2/status/x/y                     the lock-in
"""
import os

from migen import *
from litex.gen import LiteXModule
from litex.build.generic_platform import Pins, Subsignal, IOStandard, Misc
from litex.soc.interconnect.csr import CSRStorage, CSRStatus, CSRField
from litex.soc.interconnect import wishbone
from litex.soc.integration.soc import SoCRegion

HERE = os.path.dirname(os.path.abspath(__file__))

# The pins -- the same balls as icepi_adda.lpf in the bare-Verilog tutorials.
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
        self.x = CSRStatus(64, description="Sum of (adc-128)*sin, signed.")
        self.y = CSRStatus(64, description="Sum of (adc-128)*cos, signed.")

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


def add_adda(soc):
    """Add the converter pins and all three peripherals to a LiteX SoC."""
    platform = soc.platform
    platform.add_extension(adda_pins)
    for f in ["adda_io.v", "funcgen_core.v", "adc_capture_core.v", "lockin_core.v"]:
        platform.add_source(os.path.join(HERE, f))

    pads = platform.request("adda")
    adc_sample = Signal(8)
    adc_valid  = Signal()

    soc.funcgen = FuncGen()
    soc.capture = AdcCapture(adc_sample, adc_valid)
    soc.lockin  = LockIn(adc_sample, adc_valid, soc.funcgen.phase)

    soc.specials += Instance("adda_io",
        i_clk        = ClockSignal("sys"),
        i_adc_d      = pads.adc_d,
        o_adc_clk    = pads.adc_clk,
        o_dac_d      = pads.dac_d,
        o_dac_clk    = pads.dac_clk,
        i_dac_value  = soc.funcgen.dac_value,
        o_adc_sample = adc_sample,
        o_adc_valid  = adc_valid,
    )

    # Put the capture buffer on the CPU's bus, in the uncached I/O area.
    soc.bus.add_slave("capture_buf", soc.capture.bus,
        SoCRegion(size=0x4000, cached=False))
