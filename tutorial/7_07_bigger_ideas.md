<!-- nav -->
[← 7.06 Control at the speed of the cable](7_06_control.md) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)** &emsp;&emsp;&emsp; [Appendix A. Why this hardware? →](A_why_this_hardware.md)

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

The same pulse programmer, moved from 21 MHz protons to 2.87 GHz
electrons, runs Rabi, Ramsey and echoes on NV centres in diamond, read out
with light: [Appendix D](D_coming_soon.md#pulsed-odmr-rabi-oscillations-of-nv-centres-in-diamond) works it out for the next board, with the
rubidium clock that coherent population trapping makes of an optical
pumping cell.

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
  [Appendix D](D_coming_soon.md#the-next-board) earns its keep.
  Do not drive the PS2's coils from anything until you have read its
  gradient supply's limits and put a fuse in.

If you want a scanner rather than a demonstration, the open-source
low-field community has done the work: [MaRCoS](https://arxiv.org/abs/2203.11314)
is an open MRI console on a Red Pitaya (two ADCs, two DACs, 125 MS/s,
14 bits, about $600: the board in [Appendix D](D_coming_soon.md#the-next-board) is the same idea). It runs the
[tabletop scanner](https://tabletop.martinos.org) that MGH and MIT built for
teaching (0.19 T at first, 0.36 T later; twenty built, about $10,000
each, more than 800 students), and Leiden's 50 mT
[Halbach scanner](https://doi.org/10.1002/mrm.28396), whose magnet is 23 rings
of neodymium cubes and whose hardware cost under €10,000. The
[Open Source Imaging Initiative](https://www.opensourceimaging.org/)'s
50 mT OSI<sup>2</sup> ONE is a 150 kg scanner at €25,000–60,000.

Building one is now
a workshop's work: a 2024 hackathon built a 35–38 mT Halbach scanner in three days
([ezyMRI](https://arxiv.org/abs/2411.11365)), and a
[2025 workshop](https://arxiv.org/abs/2511.20979) a 0.27 T one in three days.
For the price of one TeachSpin module, then, a student could have a
tabletop magnet and a console that this tutorial has already taught them
to understand. The
author's own answer to "do I need more channels": yes, two, which is why
[Appendix D](D_coming_soon.md#the-next-board)'s board has two of each.

## Earth's field: NMR with no magnet at all

Is Earth's-field NMR worth doing with this board? Yes. It is cheap, and it
is the purest quantum-control demonstration on this page, at audio
frequencies you can watch on a scope. The field in Claremont is 46 µT,
so protons precess at 1960 Hz, between the 32nd and 33rd harmonics of the
mains.

A coil of about a thousand turns round a bottle of water first
*polarizes* the protons. A few amperes for 3 s (about *T*<sub>1</sub>) gives 10–50 mT,
hundreds of times Earth's field. A MOSFET switches the current off
faster than one precession period, the clamp diode takes the coil's
flyback, and the protons are left precessing about Earth's field. The same
coil, through a relay, picks up a few microvolts that ring for a second or
two.

TeachSpin sells it as a
[product](https://www.teachspin.com/earths-field-nmr), about $9,400; open
designs cost about $130–230, among them
[Carl Michal's](https://doi.org/10.1088/0957-0233/21/10/105902) with a
microcontroller as pulse programmer and digitizer, Worley's
[PyPPM](https://github.com/geekysuavo/pyppm) and
[Viciana et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC11398021/), 2024.

What the FPGA adds over a sound card is not lower noise. The
preamplifier sets the noise (1 nV/√Hz, an INA849), and a 24-bit sound card
digitizes as well as anything.

What it adds is *control*: the polarizing
switch, the clamp, the relay and the receiver on one clock, so that
records average coherently; a 1.96 kHz B<sub>1</sub> burst from the DAC through a
class-D amplifier into a small spin-flip coil, for Rabi, Ramsey, Hahn echo,
CPMG and composite pulses on a qubit that precesses slowly enough to hear;
and a digital lock-in that tracks Earth's field as it drifts by a few
hertz a day.

Two warnings. The microvolts need about 100 dB of gain to
reach the ADC's 39 mV code, with the mains' harmonics notched out first,
and the coil's flyback (hundreds of volts) must never reach the ADC.
[7.05](7_05_trading_speed_for_bits.md#705-trading-speed-for-bits)'s
oversampling gains about 9 bits between 25 MS/s and a 33 Hz bandwidth,
but only with at least a code of dither, which the DAC can inject. Work
outdoors, on a battery, with the coil's axis horizontal and east–west.

Imaging is possible but slow: gradients of 50–100 µT/m from FPGA pins
through op-amp current drivers, a fresh polarization for every line, and a
32 × 32 picture in a few minutes (Magritek's
[Terranova](https://www.bmmr.ovgu.de/en/Research/Resources/Terranova.html)
does exactly this). Beyond the board it costs about $250–400.

## A neodymium magnet and printed coils

How easy is permanent-magnet MRI with PCB coils? The signal is easy, the
magnet is hard, and the coils are a mixed bag. A Halbach ring of
32 neodymium cubes (12.7 mm, N52, about $190) makes about 0.12 T, protons
at 5.1 MHz, in the middle of this board's band. A tenth of a millilitre of
water in a hand-wound coil there gives a single-shot signal-to-noise
ratio of about 150 in a 10 kHz band (computed). The
hard part is everything else:

- **Homogeneity.** Ideal cubes give about 600 ppm over 5 mm, and real ones
  are worse, so an FID dies in a tenth of a millisecond. Echoes and CPMG
  relaxometry do not care: they work even in
  [two disc magnets at 15,700 ppm](https://pmc.ncbi.nlm.nih.gov/articles/PMC12302856/).
  A picture needs gradients that beat the inhomogeneity: about 70 mT/m for
  1 mm pixels at 600 ppm. Chemical shifts need 0.5 ppm, and are out of reach.
- **Temperature.** Neodymium loses 0.12% of its field per kelvin, which is
  6 kHz per kelvin at 0.12 T. Put the magnet in a foam box, measure the
  frequency from every FID, and retune the NCO before the next shot. That
  per-shot lock is natural in an FPGA.
- **Printed coils.** For the RF coil, a printed spiral gives about half a
  solenoid's field per ampere, and an uneven flip angle; six hand-wound
  turns and a trimmer are better for a vial. For *gradients*, printed coils
  are the proven answer. The MGH tabletop scanner uses 8-layer
  [PCB gradient coils](https://cds.ismrm.org/protected/14MProceedings/PDFfiles/4819.pdf)
  of 10–14 mT/m per ampere, driven by power op-amps.
- **The front end.** A transmit/receive switch (crossed diodes and a
  λ/4 network) and a low-noise amplifier are a day's work, and they are on
  [Appendix D](D_coming_soon.md#an-amod-a-board-of-analog-blocks)'s list
  of tiles. The new board's +10 dBm is enough for 50 µs pulses on a small
  sample; this board's DAC wants a small amplifier.

So an FID or a CPMG decay from a homemade magnet is a weekend and
$100–400, and a 2-D image is a semester and $800–2,000. The shortcut is
the magnet you already own: the PS2-A's 0.49 T, temperature-controlled,
with gradient coils, is the "homemade" magnet and gradient set done right.

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
| Earth's-field NMR, with pulses | a 1000-turn coil, a battery or 36 V supply, a MOSFET and clamp, an INA849 preamplifier, a class-D amplifier and spin-flip coil | $250–400 |
| NMR in a magnet you built | 32 N52 cubes in a printed former, a solenoid, a T/R switch, a low-noise amplifier, a foam box | $100–400 |
| NV centres | a 520 nm laser diode and driver, a 20× objective, a dichroic and a long-pass filter, a photodiode, an NV-rich diamond plate, an ADF4351 board, a 2.4–3 GHz amplifier module, a loop antenna | $1,500–3,000, by the UNSW and Steinfurt parts lists |
| a real low-field scanner | a MaRCoS-class console (or [Appendix D](D_coming_soon.md#the-next-board)'s board) and a Halbach magnet | $1,000–10,000 for a tabletop one |

**Try this:** none of this is a "try this"; it is a semester. The order
above is the order of cost, and the first row is free.

<!-- nav -->
[← 7.06 Control at the speed of the cable](7_06_control.md) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)** &emsp;&emsp;&emsp; [Appendix A. Why this hardware? →](A_why_this_hardware.md)

<!-- author -->
<sub>Jason Gallicchio, jason@hmc.edu, Harvey Mudd College</sub>
