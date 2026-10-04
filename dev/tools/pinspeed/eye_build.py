import re, subprocess, sys, os
from concurrent.futures import ThreadPoolExecutor
T = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..") + "/src/verilog"
K = 145
def job(args):
    fadc, ns = args
    nadc = {31.25: 4096, 25: 3276}[fadc]; nraw = 16384
    f0 = K * fadc * 1e6 / nadc
    TW = round(f0 / 62.5e6 * 2**32)
    deg = ns * 1e-9 * fadc * 1e6 * 360
    name = "eye_%g_%gns" % (fadc, ns)
    out = subprocess.run(["ecppll", "-n", "pll2", "--clkin_name", "clkin", "--clkout0_name", "c125", "--clkout1_name", "cadc",
                          "-i", "50", "-o", "125", "--clkout1", str(fadc), "--phase1", str(deg), "-f", name + "_pll.v"],
                         capture_output=True, text=True).stdout
    sub = subprocess.run("sed -i 's/output locked/output locked/' %s_pll.v; yosys -q -p 'chparam -set TW %d -set NRAW %d adceye; synth_ecp5 -top adceye -json %s.json' adceye.v %s_pll.v %s/uart.sv && "
                         "nextpnr-ecp5 --25k --package CABGA256 --speed 6 --json %s.json --lpf %s/icepi_adda.lpf --textcfg %s.config --seed 2 2> %s.pnr.log && ecppack --compress %s.config %s.bit"
                         % (name, TW, nraw, name, name, T, name, T, name, name, name, name), shell=True, capture_output=True, text=True)
    fm = re.findall(r"Max frequency for clock +'([^']+)': ([\d.]+) MHz \((PASS|FAIL)", open(name + ".pnr.log").read())
    pll = re.findall(r"(Refclk divisor|clkout1 frequency|clkout1 phase|VCO frequency): ([\d.]+)", out)
    return name, sub.returncode, fm[-2:], pll, f0, TW
if __name__ == "__main__":
    jobs = [(f, ns) for f in (31.25, 25) for ns in (0, 2, 4, 6)]
    with ThreadPoolExecutor(6) as ex:
        for r in ex.map(job, jobs): print(r, flush=True)
