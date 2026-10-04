import glob, subprocess, sys, time, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..") + "/src/verilog")
from capture import capture
res = {}
for bit in sorted(glob.glob("dac*.bit")):
    name = bit[:-4]
    subprocess.run(["openFPGALoader", "-b", "icepi-zero", bit], capture_output=True)
    for _ in range(50):
        try:
            time.sleep(0.2); caps = [capture("/dev/ttyUSB0", 0) for _ in range(4)]; break
        except Exception as e:
            err = e
    else:
        print(name, "capture failed:", err); continue
    res[name] = np.array(caps)
    print(name, "ok", res[name].min(), res[name].max(), flush=True)
np.savez("drive_caps.npz", **res)
