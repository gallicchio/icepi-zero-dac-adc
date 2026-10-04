<!-- nav -->
[← 6.12 On the air: whispers, and how far they carry](6_12_on_the_air.md#612-on-the-air-whispers-and-how-far-they-carry) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)** &emsp;&emsp;&emsp; [7.00 Signal processing in gateware →](7_00_signal_processing_in_gateware.md#700-signal-processing-in-gateware)

# 6.13 More ideas, and a radar chapter

![Computed: a chirp from 2 to 20 kHz, a noisy microphone record, and the cross-correlation, where the direct sound and the echo from a wall 1.5 m away become two sharp peaks](img/chirp_sonar.png)

This chapter went further than most courses do, but a modem is a deep well.
None of these has been built yet. Each starts from something that works
here, and each comes with the question it answers.

## Communications

| idea | what you'd learn | start from |
| --- | --- | --- |
| **Two boards, for real** | everything in this chapter was tested on one board looped back, where the transmitter and the receiver share a crystal. With two boards, the offsets that [6.02](6_02_psk_and_qpsk.md#602-psk-and-qpsk-finding-the-clock-and-the-carrier)'s loops exist for are real (0.76 ppm, [5.01](5_01_two_clocks.md#501-two-clocks)), the carrier phase drifts during a record, and [6.11](6_11_the_modem_in_the_fpga.md#611-the-modem-in-the-fpga)'s modem talks to someone who isn't itself. Every script takes two ports already | [5.00](5_00_two_boards.md#500-two-boards-on-one-laptop) |
| **An echo you can touch** | an SMA T with an open stub puts a real reflection in the channel; [6.05](6_05_the_channel.md#605-the-channel-sounding-it-and-equalizing-it) says which lengths put it where. Then the equalizer, the [cyclic prefix](https://en.wikipedia.org/wiki/Cyclic_prefix) and the radar of [6.10](6_10_chirps_and_lora.md#610-chirps-zadoffchu-and-lora-ranging-and-radar-on-a-cable) all have something to undo, and you can change it with your hands | [6.05](6_05_the_channel.md#605-the-channel-sounding-it-and-equalizing-it), [4.05](4_05_quarter_wave_stub.md#405-a-quarter-wave-stub) |
| **The code in the FPGA** | [6.11](6_11_the_modem_in_the_fpga.md#611-the-modem-in-the-fpga) sends raw bits. Add [6.09](6_09_error_correcting_codes.md#609-error-correcting-codes)'s convolutional encoder (a shift register and two XORs: trivial) and a Viterbi decoder (64 states, add-compare-select: a classic FPGA exercise) and measure the coding gain on the real link | [6.09](6_09_error_correcting_codes.md#609-error-correcting-codes), [6.11](6_11_the_modem_in_the_fpga.md#611-the-modem-in-the-fpga) |
| **OFDM in the FPGA** | [1.09](1_09_spectrum_analyzer.md#109-a-spectrum-analyzer)'s FFT already runs in logic. An inverse FFT, a cyclic prefix and a pilot make a streaming OFDM transmitter; the FFT and one complex divide per subcarrier make the receiver | [1.09](1_09_spectrum_analyzer.md#109-a-spectrum-analyzer), [6.07](6_07_ofdm.md#607-ofdm-the-triumph-of-physics-over-math) |
| **MIMO, with two boards** | two transmit antennas and two receive antennas, over the air at 915 MHz, and the channel is a 2 × 2 matrix per subcarrier: invert it and two streams share one frequency. Wi-Fi 4 and every phone since do this; it's the other reason OFDM won, since the matrix is only diagonal-per-subcarrier in the Fourier basis | [6.07](6_07_ofdm.md#607-ofdm-the-triumph-of-physics-over-math), [5.03](5_03_time_transfer.md#503-what-time-is-it-over-there)'s synchronization |
| **OTFS** | the proposal for channels that change during a symbol (trains, satellites): modulate in the delay–Doppler domain, which a second Fourier transform reaches from OFDM's time–frequency grid. Simulate a channel with Doppler and compare | [6.07](6_07_ofdm.md#607-ofdm-the-triumph-of-physics-over-math) |
| **An FM broadcast transmitter** | the sound card in, a frequency-modulated carrier out of the DAC at 12 MHz, and [1.10](1_10_am_radio.md#110-an-am-radio)'s receiver with a phase-difference detector instead of an [envelope detector](https://en.wikipedia.org/wiki/Envelope_detector). (Into a cable or a dummy load: 88–108 MHz needs a mixer, [6.00](6_00_digital_communications.md#600-digital-communications-hardware-defined-radio), and a licence) | [1.10](1_10_am_radio.md#110-an-am-radio), [6.04](6_04_msk_and_gmsk.md#604-msk-and-gmsk-constant-envelope)'s discriminator |
| **Carrier-phase ranging** | [6.10](6_10_chirps_and_lora.md#610-chirps-zadoffchu-and-lora-ranging-and-radar-on-a-cable) measures a delay to a fraction of a chip. The carrier's phase does a hundred times better, as RTK GPS does, with an integer ambiguity to resolve. A metre of RG-316 is 5 ns of delay, and PTFE's phase changes by a few hundred ppm across room temperature, so warming the cable 10 °C in your hand moves its delay by tens of picoseconds: visible, since [5.03](5_03_time_transfer.md#503-what-time-is-it-over-there) resolved 5 ps, but only with its averaging | [6.10](6_10_chirps_and_lora.md#610-chirps-zadoffchu-and-lora-ranging-and-radar-on-a-cable), [5.02](5_02_warming_a_crystal.md#502-warming-a-crystal) |
| **A real LoRa packet** | scale [6.10](6_10_chirps_and_lora.md#610-chirps-zadoffchu-and-lora-ranging-and-radar-on-a-cable)'s chirps to LoRa's 125 kHz bandwidth, add its header, whitening and code, mix to 915 MHz ([6.00](6_00_digital_communications.md#600-digital-communications-hardware-defined-radio)), and see whether a $5 LoRa module receives it | [6.10](6_10_chirps_and_lora.md#610-chirps-zadoffchu-and-lora-ranging-and-radar-on-a-cable) |

## Chapter 8, perhaps: radar

A radar is a transmitter and a receiver that share a clock, so it can
measure *when* an echo comes back (range) and how its phase turns
(velocity). One board, or two synchronized as in [5.03](5_03_time_transfer.md#503-what-time-is-it-over-there), has all of that, and
[6.10](6_10_chirps_and_lora.md#610-chirps-zadoffchu-and-lora-ranging-and-radar-on-a-cable) already built the waveforms radar people use and ran a radar on a
cable. The sections below would make it a chapter. Sound is the place to
start: [4.06](4_06_speed_of_sound.md#406-the-speed-of-sound-at-40-khz)'s 40 kHz ultrasound has a wavelength of 8.6 mm, the same as a
35 GHz radar's, so a tabletop behaves like a radar range, and a pair of
transducers costs [about $6](https://www.robotshop.com/products/devantech-400sr-st160-transducer).

| section | what you'd learn | start from |
| --- | --- | --- |
| **8.01 Radar on a cable** | done: [6.10](6_10_chirps_and_lora.md#610-chirps-zadoffchu-and-lora-ranging-and-radar-on-a-cable)'s pulse, [chirp](https://en.wikipedia.org/wiki/Chirp) and Zadoff–Chu echoes from a T and a stub, range resolution *c*/2*B*, [pulse compression](https://en.wikipedia.org/wiki/Pulse_compression) | [6.10](6_10_chirps_and_lora.md#610-chirps-zadoffchu-and-lora-ranging-and-radar-on-a-cable) |
| **8.02 Doppler** | a steady 40 kHz tone, and the echo's frequency shift, 2*v*/λ: a fan's blades, a pendulum, your hand. Offset the tone first (learnSDR's [lesson 8b](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson08b.md) does, at 915 MHz with a Pluto) so that coming and going have opposite signs | [4.06](4_06_speed_of_sound.md#406-the-speed-of-sound-at-40-khz), [1.08](1_08_lockin.md#108-a-lock-in-amplifier) |
| **8.03 FMCW** | a continuous chirp, mixed with its own echo: the difference frequency is the range. It's how car radars and the cheap 24 GHz modules work | [6.10](6_10_chirps_and_lora.md#610-chirps-zadoffchu-and-lora-ranging-and-radar-on-a-cable), [4.06](4_06_speed_of_sound.md#406-the-speed-of-sound-at-40-khz) |
| **8.04 Range and Doppler together** | many chirps in a row, and a two-dimensional FFT: range one way, velocity the other, the picture every automotive radar makes | 8.03 |
| **8.05 Angle of arrival** | two receivers a few millimetres apart, and the phase difference between them: two boards, synchronized as in [5.03](5_03_time_transfer.md#503-what-time-is-it-over-there), or one board's ADC switched between two microphones | [5.03](5_03_time_transfer.md#503-what-time-is-it-over-there) |
| **8.06 Synthetic-aperture radar** | step one transducer along a rail, record an echo at each stop, and add them back up with the right delays: a picture of the targets, sharper than the transducer could ever see alone. The same arithmetic maps the Earth from orbit | everything above |
| **8.07 Real microwaves** | an HB100 module ([$4–8](https://www.digikey.com/en/products/detail/st-engineering-urban-solutions/HB100/24762149)) is a 10.525 GHz Doppler radar on a 4 cm board whose output is the beat between what it sent and what came back: a few hertz for a walking person. Amplify it (it's microvolts) into ADC IN and [1.09](1_09_spectrum_analyzer.md#109-a-spectrum-analyzer)'s [spectrum analyzer](https://en.wikipedia.org/wiki/Spectrum_analyzer) is a speed trap | 8.02, [1.09](1_09_spectrum_analyzer.md#109-a-spectrum-analyzer) |

MIT's [*Build a Small Radar System Capable of Sensing Range, Doppler, and
Synthetic Aperture Radar Imaging*](https://ocw.mit.edu/courses/res-ll-003-build-a-small-radar-system-capable-of-sensing-range-doppler-and-synthetic-aperture-radar-imaging-january-iap-2011/)
(the "coffee-can radar") does 8.02–8.06 at 2.4 GHz with six Mini-Circuits
parts, two coffee cans and a laptop's sound card as the digitizer. This
board would replace the sound card with a 25 MS/s one and the laptop's
MATLAB with the FFT in logic, and the RF parts of [6.00](6_00_digital_communications.md#600-digital-communications-hardware-defined-radio) are most of its
bill of materials.
