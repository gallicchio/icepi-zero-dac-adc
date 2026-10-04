"""Chapter 6 figure: how close channel.py's pretend board is to the real one.

comms_channel.png
  left:  a DAC step (code 32 to 224) through 101.5 cm of cable: 1.07's measurement
         (loopback.sv mode s, dev/data/loopback_1m.npz, the 8 rising edges averaged)
         and the model
  right: gain against frequency: 6.07's channel sounding (dev/data/tb_sound_loop.npz)
         and the model, one sine at a time

Uses only saved measurements, so it needs no board:  python3 fig_channel.py
"""
import os
import numpy as np
import link
from plotstyle import plt, save, dots, C1, C2
import channel

N = channel.N
meas = np.load(os.path.join(link.TOP, "dev", "data", "loopback_1m.npz"))["s"].astype(float)
step = np.where((np.arange(N) // 1024) % 2 == 1, 224, 32)            # as loopback.sv plays it
model = channel.channel(step, noise=0).astype(float)
edges = 512 + 1024 * np.arange(8)
k = np.arange(-6, 20)
m_avg = np.mean([meas[e + k] for e in edges], axis=0)
s_avg = np.mean([model[e + k] for e in edges], axis=0)

snd = np.load(os.path.join(link.TOP, "dev", "data", "tb_sound_loop.npz"))
cyc = np.arange(100, 4096, 100)                                       # cycles per loop
gain = []
for c in cyc:
    r = channel.channel(128 + 100 * np.cos(2 * np.pi * c * np.arange(N) / N), noise=0)
    z = 2 * np.mean((r - r.mean()) * np.exp(-2j * np.pi * c * np.arange(N) / (N / 2)))
    gain.append(abs(z) / 100)

fig, ax = plt.subplots(1, 2, figsize=(10, 3.8))
dots(ax[0], k, m_avg, C1, label="measured (1.07)")
dots(ax[0], k + 0.15, s_avg, C2, label="channel.py")
ax[0].set_xlabel("ADC samples (40 ns) after the DAC steps"); ax[0].set_ylabel("ADC code")
ax[0].set_title("A step through 1 m of cable: same delay,\nbut the model has no ringing")
ax[0].legend(loc="center right")
ax[1].plot(snd["f"] / 1e6, snd["H"], color=C1, lw=0.6, label="measured (6.07's sounding)")
dots(ax[1], cyc * channel.FS_DAC / N / 1e6, gain, C2, label="channel.py")
ax[1].set_ylim(0.6, 0.95)
ax[1].set_xlabel("frequency (MHz)"); ax[1].set_ylabel("gain (ADC codes per DAC code)")
ax[1].set_title("Gain against frequency: the model is flatter\nthan the cable by ±8%")
ax[1].legend(loc="lower left")
save(fig, link.img_path("channel"))
print("step: measured %s" % np.round(m_avg[4:12], 1))
print("      model    %s" % np.round(s_avg[4:12], 1))
