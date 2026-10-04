import glob, subprocess, time, serial, numpy as np
res = {}
for load in range(2):
    for bit in sorted(glob.glob("eye_*.bit")):
        subprocess.run(["openFPGALoader", "-b", "icepi-zero", bit], capture_output=True)
        caps = []
        for attempt in range(5):
            try:
                time.sleep(0.3)
                with serial.Serial("/dev/ttyUSB0", 1_000_000, timeout=3) as s:
                    time.sleep(0.05); s.reset_input_buffer()
                    for _ in range(3):
                        s.write(b"g"); raw = s.read(16384)
                        assert len(raw) == 16384, len(raw)
                        caps.append(np.frombuffer(raw, np.uint8).copy())
                break
            except Exception as e:
                caps = []; err = e
        else:
            print(bit, "failed", err); continue
        res["%s_L%d" % (bit[:-4], load)] = np.array(caps)
        print(bit, load, caps[0][:12], flush=True)
np.savez("eye_caps.npz", **res)
