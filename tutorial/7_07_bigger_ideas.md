<!-- nav -->
[← 7.06 Control at the speed of the cable](7_06_control.md#706-control-at-the-speed-of-the-cable) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)** &emsp;&emsp;&emsp; [Appendix A. Why this hardware? →](A_why_this_hardware.md#appendix-a-why-this-hardware)

# 7.07 Bigger ideas: NMR, MRI and qubits

![The TeachSpin PS2 pulsed NMR spectrometer's signal path with this board jacked in: the FPGA's pins replace the pulse programmer's I and Q gates into the synthesizer, the ADC digitizes the receiver's I, Q and envelope outputs or its 21 MHz RF output by aliasing, and the gradient coils' current monitors are read for imaging](img/dsp_d_nmr.png)

[7.06](7_06_control.md#706-control-at-the-speed-of-the-cable) made the case
that a loop with sub-microsecond latency is the thing a laser lock and a
qubit have in common. This page asks the author's next question: what is
the simplest experiment that is *actually* quantum control, what is the
cheapest MRI that returns a picture of a real object, and does either
need more bandwidth, a higher carrier, or a different board? None of it
has been built. All of it has been priced.

## The quantum control demo you already own

A pulsed NMR spectrometer is a quantum control instrument. The protons in
a drop of mineral oil are spin-½ systems; a resonant RF pulse rotates
their state on the Bloch sphere by an angle set by the pulse's length
(Rabi); two π/2 pulses separated by a delay interfere (Ramsey); a π pulse
in between refocuses the dephasing (Hahn's echo, 1950, the first
dynamical decoupling); a train of them (CPMG) is the first error-mitigation
sequence. Every pulse sequence a superconducting-qubit lab runs on a
transmon at 5 GHz was run on protons at 20 MHz first, and the physics is
the same two-level system in a rotating frame. The TeachSpin PS2-A on the
author's shelf does all of this at 21 MHz in a 0.49 T permanent magnet,
with a pulse programmer whose A and B pulses are 0.2 to 20 µs long and up
to 100 of them in a train.

What it does not do is let you *shape* a pulse, phase-cycle a sequence
freely, or digitize the raw signal, and that is exactly what this board
adds. Read the PS2 manual's connector list ([the manual is online](https://www.physics.rutgers.edu/~eandrei/389/PS2-1%20Manual%201.41.pdf))
with the board in mind:

| PS2 connector | what it is | what this board does with it |
| --- | --- | --- |
| Pulse Programmer → Synthesizer **Pulse In I** and **Pulse In Q** | TTL gates that turn the 21 MHz RF on with 0° and 90° phase | two FPGA pins replace the pulse programmer: any sequence, 20 ns resolution, phase cycling by choosing I or Q |
| Synthesizer **REF Out** → Receiver **REF In** | the CW reference for the phase-sensitive detectors | leave it |
| Receiver **I Out**, **Q Out**, **Env. Out** | the detected NMR signal at baseband, time constant 1 µs to 3.3 ms | straight into ADC IN (±4 V is plenty): the FID and echoes, digitized |
| Receiver **RF Out** | the amplified, filtered 21 MHz NMR signal itself | into ADC IN: at 25 MS/s, 21 MHz aliases to 4 MHz, and [1.08](1_08_lockin.md#108-a-lock-in-amplifier)'s lock-in at 4 MHz is a digital phase-sensitive detector with no analog mixer at all |
| Synthesizer **Pulsed RF Out** | the high-power pulse, ±25 V | **never** to this board; it goes to the probe through the receiver's diodes as designed |
| Synthesizer **CW In** (−10 to −65 dBm) | the CW resonance path | the DAC, attenuated to −10 dBm, could inject a *shaped* 21 MHz pulse here, but the PS2's pulse amplifier is gated by the TTL pulses; the honest first version keeps the PS2's RF and controls only the gates |
| Pulse Programmer **External Start** (TTL 4 V, 1 µs), **Sync** out | triggers | the FPGA triggers the PS2, or is triggered by it, so the capture starts with the pulse |
| Gradient supply **current monitors** (2.5 Ω and 1.25 Ω sense resistors) | the x, y, z and z<sup>2</sup> gradient currents | into the ADC, for imaging (below) |

So the minimal quantum-control hardware is: the PS2 you own, this board,
four BNC cables and two jumper wires from FPGA pins to the Pulse In
jacks (3.3 V logic is TTL enough). The board's DC-to-50 MHz is exactly
the right range: 21 MHz is in the DAC's first Nyquist zone and the ADC's
second, and nothing about NMR at this field wants a Pluto SDR (its
70 MHz floor is *above* the PS2's band) or an RFSoC. What you would build,
in order: the gateware pulse programmer (a table of (I/Q gate, length,
delay) entries played from the [UART](https://en.wikipedia.org/wiki/Universal_asynchronous_receiver-transmitter), with the ADC capture triggered by
it); a Rabi curve (signal against pulse length); Ramsey fringes against
the delay with the synthesizer detuned; a Hahn echo and *T*<sub>2</sub>; CPMG and
the difference it makes; then the thing the PS2 cannot do, a composite
pulse (BB1 or CORPSE) that rotates by exactly π even when the pulse
amplitude is 10% wrong, which is the first idea of fault-tolerant
control, demonstrated on a vial of oil.

<details>
<summary><b>Detail:</b> the numbers that make it work</summary>

Protons precess at 42.58 MHz per tesla, so 0.49 T is 21 MHz. The PS2's
synthesizer runs 1 to 30 MHz in 10 Hz steps with ±50 ppm stability; the
receiver's [low-noise amplifier](https://en.wikipedia.org/wiki/Low-noise_amplifier) has 20 dB of gain and a 2.5 dB noise
figure, followed by 0 to 80 dB of variable gain and a narrow-band filter,
and the manual says a careful student gets a *T*<sub>2</sub>\* of 5 ms in light
mineral oil, which is a 60 Hz linewidth. A π/2 pulse is a few microseconds,
so the Rabi frequency is about 100 kHz: the board's 20 ns timing is 0.2%
of a pulse, and its 25 MS/s is 250 samples per Rabi cycle. The receiver's
recovery after a pulse was "improved by a factor of five" in this
revision; whatever it is, it is the dead time that sets the shortest
Ramsey delay, and measuring it is the first experiment.

</details>

## The cheapest MRI that shows you a thing

An MRI is NMR plus a magnetic field gradient: make the field vary
linearly across the sample and the precession frequency becomes a
position, so the spectrum of the echo is a *projection* of the proton
density along the gradient. Rotate the gradient and take another
projection; a dozen projections and the filtered back-projection of the
CT scanner give a picture. The PS2-A ships with gradient coils on all
three axes (7.1 µT/mm per ampere on *x* and *y*, 6.6 on *z*, with a *z*<sup>2</sup>
shim), a regulated supply with a current monitor under each knob, and a
one-dimensional imaging kit, because TeachSpin uses the *x* gradient to
show a 1-D image of a shaped sample. Nobody said you may only use one
knob at a time.

- **1-D, as TeachSpin intends:** one gradient on, a spin echo, the FFT of
  the echo is the profile of the sample along that axis. At 1 A the
  gradient is 7 µT/mm, which is 300 Hz/mm for protons; against a 60 Hz
  linewidth that resolves 0.2 mm across a 10 mm vial. This board records
  the echo from **I Out** and **Q Out** and does the FFT; the PS2 alone shows it
  on an oscilloscope.
- **2-D, by hand:** set *G*<sub>x</sub> = *G* cos θ and *G*<sub>y</sub> = *G* sin θ with the
  two knobs (the current monitors tell you what you set), take a
  projection, turn θ by 10°, repeat eighteen times, and run the
  back-projection in numpy. The object is whatever fits a 10 mm vial and
  has protons in some places and not others: two capillaries of oil in
  air, a plastic letter in mineral oil, a drinking straw full of water
  beside an empty one. That is a recognizable picture of an actual thing
  you put in the coil, and the only purchase is the board.
- **2-D, properly:** the gradient currents switched by the FPGA. The
  coils are low impedance (the monitors are 2.5 Ω and 1.25 Ω sense
  resistors in series with them), so a cheap class-D audio amplifier
  driven by the DAC through the sense resistor can play the gradient
  waveform, and *then* you can do what a real scanner does: a frequency-
  encoding gradient during the echo and a phase-encoding gradient pulse
  before it, 32 phase-encoding steps, a 2-D FFT, and an image in a
  minute. This is where the second DAC of the board in
  [Appendix A](A_why_this_hardware.md#coming-soon-hopefully) earns its keep.
  Do not drive the PS2's coils from anything until you have read its
  gradient supply's limits and put a fuse in.

If you want a scanner rather than a demonstration, the open-source
low-field community has done the work: [MaRCoS](https://arxiv.org/abs/2203.11314)
is an open MRI console on a Red Pitaya (two ADCs, two DACs, 125 MS/s,
14 bits, about $600: the board in Appendix A is the same idea), and it
runs the 0.36 T tabletop scanner MIT built for teaching and the 50 mT
Halbach scanners of the [Open Source Imaging Initiative](https://www.opensourceimaging.org/),
whose magnet is 2948 neodymium cubes glued into a cylinder; a
[2025 workshop](https://arxiv.org/abs/2511.20979) built one in three days.
The console-plus-magnet systems come in under $10,000. For the price of
one TeachSpin module, then, a student could have a Halbach magnet and a
console that this tutorial has already taught them to understand. The
author's own answer to "do I need more channels": yes, two, which is why
Appendix A's board has two of each.

## Qubits that are not nuclei

The other room-temperature quantum system a teaching lab can afford is
the nitrogen-vacancy centre in diamond: an electron spin-1 read out with
a green laser and controlled with microwaves at 2.87 GHz. UNSW's
teaching lab ([Sewani et al., 2020](https://arxiv.org/abs/2004.02643), with
its sequel on [hyperfine structure](https://arxiv.org/abs/2110.07835))
does optically detected magnetic resonance, Rabi oscillations, Ramsey
fringes and Hahn echoes with a 520 nm laser diode, a microscope
objective, a [photodiode](https://en.wikipedia.org/wiki/Photodiode), a microwave generator and amplifier at +24 dBm
into a printed loop antenna, and a [lock-in amplifier](https://en.wikipedia.org/wiki/Lock-in_amplifier), for under
US$20,000 in their version; a German group has the same experiments in
[3-D-printed optical cubes for under €500](https://www.dpg-physik.de/vereinigungen/fachuebergreifend/ak/akhaw/publikationen-akhaw/akhaw-workshop-quantentechnologien-von-der-lehre-zur-anwendung/akhaw-steinfurt-2025-modular-optical-cubes-for-education-in-quantumtechnologies_pror-dr-markus-gregor.pdf),
without the oscilloscope. This is where the carrier frequency finally
outruns the board: 2.87 GHz needs the ADF4351 synthesizer of
[6.00](6_00_digital_communications.md#600-digital-communications-hardware-defined-radio)'s
parts list ($27) and a microwave amplifier, with the FPGA gating them.
Everything else, the laser pulses, the microwave pulse timing at 20 ns,
the photodiode's digitization and the lock-in, is what this board does
already, and [1.08](1_08_lockin.md#108-a-lock-in-amplifier)'s lock-in in
gateware replaces the $5,000 instrument on UNSW's bench.

Rubidium, the other classic, is a step further: Ramsey fringes on a Rb
vapour cell need a narrow-linewidth 795 nm laser and its lock
([7.06](7_06_control.md#706-control-at-the-speed-of-the-cable)'s loop, with
a real plant), which is a few thousand dollars of laser before the
physics starts. It is the right second experiment, not the first.

## What to buy, in order

| for | buy | about |
| --- | --- | --- |
| quantum control on protons | nothing: the PS2, this board, four BNC cables, two jumpers | $0 |
| 2-D MRI by hand | a 10 mm vial with two capillaries of oil, patience | $5 |
| 2-D MRI with switched gradients | a 20 W class-D amplifier board, a fuse, a current-sense resistor | $30 |
| NV centres | a 520 nm laser diode and driver, a 20× objective, a dichroic and a long-pass filter, a photodiode, an NV-rich diamond plate, an ADF4351 board, a 2.4–3 GHz amplifier module, a loop antenna | $1,500–3,000, by the UNSW and Steinfurt parts lists |
| a real low-field scanner | a MaRCoS-class console (or Appendix A's board) and a Halbach magnet | under $10,000 |

**Try this:** none of this is a "try this"; it is a semester. The order
above is the order of cost, and the first row is free.
