import glob, subprocess, sys, time, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..") + "/src/verilog")
from capture import capture
out = sys.argv[1]; pats = sys.argv[2:]
bits = sorted(b for p in pats for b in glob.glob(p))
res = {}
for rep in range(2):
    for bit in bits:                       # interleave configs so drift affects all alike
        subprocess.run(["openFPGALoader", "-b", "icepi-zero", bit], capture_output=True)
        for _ in range(50):
            try:
                time.sleep(0.2); caps = [capture("/dev/ttyUSB0", 0)[1] for _ in range(4)]; break
            except Exception: pass
        res["%s_r%d" % (bit[:-4], rep)] = np.array(caps)
    print("pass", rep, "done", flush=True)
np.savez(out, **res)
