"""Build the drive-strength experiment: DAC sine from a PLL at F MS/s, ADC capture at 25 MS/s.
One bitstream per (F, drive config, tone).  Builds run in parallel; nothing touches the FPGA."""
import itertools, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
T = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..") + "/src/verilog"
RATES = [50, 100, 125, 150, 200]
CONFIGS = {"4S-4S": ("DRIVE=4 SLEWRATE=SLOW", "DRIVE=4 SLEWRATE=SLOW"),     # (data, clock): the tutorial's
           "8S-8S": ("DRIVE=8 SLEWRATE=SLOW", "DRIVE=8 SLEWRATE=SLOW"),     # Lattice's defaults
           "4S-8F": ("DRIVE=4 SLEWRATE=SLOW", "DRIVE=8 SLEWRATE=FAST"),     # weak data, faster clock
           "16F-16F": ("DRIVE=16 SLEWRATE=FAST", "DRIVE=16 SLEWRATE=FAST")} # strongest, fastest
TONES = {"1M": 721, "10M": 6619}      # f0 = k * 25 MHz / 16384 (coherent with the capture)
lpf0 = open(os.path.join(T, "icepi_adda.lpf")).read()

def pll(F):
    out = subprocess.run(["ecppll", "-n", "pllF", "--clkout0_name", "clkF", "-i", "50", "-o", str(F), "-f", "pll%d.v" % F],
                         capture_output=True, text=True).stdout
    return re.search(r"clkout0 frequency: ([\d.]+)", out).group(1)

def lpf(cfg):
    d, c = CONFIGS[cfg]; s = lpf0
    s = re.sub(r'(IOBUF  PORT "dac_d\[\d\]"\s+IO_TYPE=LVCMOS33) DRIVE=4 SLEWRATE=SLOW', r"\1 " + d, s)
    s = re.sub(r'(IOBUF  PORT "dac_clk"\s+IO_TYPE=LVCMOS33) DRIVE=4 SLEWRATE=SLOW', r"\1 " + c, s)
    assert s.count(d) >= 8 and c in s
    open("%s.lpf" % cfg, "w").write(s)

def top(F, tone):
    TW = round(TONES[tone] * 25e6 / 16384 / (F * 1e6) * 2**32)
    name = "dac%d_%s" % (F, tone)
    open(name + ".v", "w").write("""
module %(n)s (input wire clk, output reg [7:0] dac_d, output wire dac_clk,
              input wire [7:0] adc_d, output wire adc_clk, input wire uart_rx, output wire uart_tx, output wire [4:0] led);
    wire clkF, locked;
    pllF pll (.clkin(clk), .clkF(clkF), .locked(locked));
    reg signed [7:0] sine_table [0:255];
    integer i;
    initial for (i = 0; i < 256; i = i + 1)
        sine_table[i] = $rtoi($floor(127.0 * $sin(6.283185307179586 * i / 256) + 0.5));
    reg [31:0] phase = 0;
    always @(posedge clkF) if (locked) begin
        phase <= phase + 32'd%(tw)d;
        dac_d <= sine_table[phase[31:24]] + 128;
    end
    assign dac_clk = ~clkF;
    capture cap (.clk(clk), .adc_d(adc_d), .adc_clk(adc_clk), .uart_rx(uart_rx), .uart_tx(uart_tx), .led(led));
endmodule
""" % dict(n=name, tw=TW))
    return name, TW

def build(job):
    F, cfg, tone = job
    name, TW = top(F, tone)
    out = "%s_%s" % (name, cfg)
    if os.path.exists(out + ".bit"): return out, "cached"
    r = subprocess.run("yosys -q -p 'synth_ecp5 -top %s -json %s.json' %s.v pll%d.v %s/capture.sv %s/uart.sv && "
                       "nextpnr-ecp5 --25k --package CABGA256 --speed 6 --json %s.json --lpf %s.lpf --textcfg %s.config 2> %s.pnr.log && "
                       "ecppack --compress %s.config %s.bit" % (name, out, name, F, T, T, out, cfg, out, out, out, out),
                       shell=True, capture_output=True, text=True)
    fm = re.findall(r"Max frequency for clock +'([^']+)': ([\d.]+) MHz \((PASS|FAIL)", open(out + ".pnr.log").read())
    return out, ("ok" if r.returncode == 0 else "BUILD FAILED") + " " + " ".join("%s=%s %s" % (c.split("$")[-1], f, p) for c, f, p in fm[-2:])

if __name__ == "__main__":
    for F in RATES: print("PLL for %d MHz -> %s MHz" % (F, pll(F)))
    for cfg in CONFIGS: lpf(cfg)
    jobs = list(itertools.product(RATES, CONFIGS, TONES))
    with ThreadPoolExecutor(6) as ex:
        for out, msg in ex.map(build, jobs): print(out, msg, flush=True)
