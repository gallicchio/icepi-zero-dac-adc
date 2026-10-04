// am_radio.sv -- an AM radio station on the DAC and an AM radio receiver on the ADC.
//
// TRANSMITTER (the DAC).  A carrier at frequency f_tx (default 1.000 MHz, in the
// AM broadcast band; anything from 0.1 to 20 MHz works), made by a DDS as in
// sine.sv, whose amplitude follows a sound a(t) between -1 and +1:
//
//     DAC = 128 + 70 (1 + m a(t)) cos(2 pi f_tx t)       (codes; m = 0.8)
//
// (times 127/128, as the sine table's peak is 127).  m < 1 keeps 1 + m a(t)
// above 0, so the carrier never vanishes and its amplitude -- its "envelope" --
// is a copy of the sound.  At the loudest, 70 x 1.8 = 126 codes still fits.
// The sound comes from inside the FPGA: a music box playing Beethoven's "Ode to
// Joy" (13.6 s, over and over; each note is plucked and dies away), or a
// steady 1 kHz test tone.
//
// RECEIVER (the ADC).  A "digital down-converter" and an AM detector:
//   1. Mix: multiply each ADC sample (minus 128) by cos and -sin of a second DDS
//      at the receive frequency f_rx, as lockin.sv does.  A station at f_rx
//      lands at 0 Hz (plus and minus its sound's frequencies); a station 10 kHz
//      away lands at 10 kHz.  The two products are I and Q, the lock-in's X, Y.
//   2. A CIC filter: three running sums at 25 MS/s, then three differences at
//      25 kS/s.  It averages away everything far from 0 Hz and keeps 1 sample in
//      R = 1000: 25 MS/s -> 25 kS/s.
//   3. A FIR filter at 25 kS/s: 127 numbers ("taps") that pass 0..4 kHz and
//      block 5 kHz and beyond.  This is what separates neighbouring stations.
//   4. The envelope, sqrt(I^2 + Q^2): the amplitude of whatever is left near f_rx.
//      It doesn't care about the station's phase, so f_rx needn't match f_tx
//      exactly, nor be locked to it.
//   5. Send it to the laptop, 25,000 samples a second.  (am_radio.py plays it.)
//
// Serial port, 1,000,000 baud:
//   laptop -> FPGA:  a letter, hex digits, Enter ("\n" or "\r"):
//       t<TW>   transmit frequency  f_tx = TW x 50 MHz / 2^32   ("t51eb852": 1 MHz)
//       r<TW>   receive frequency   f_rx = TW x 50 MHz / 2^32   ("r51eb852": 1 MHz)
//       m<n>    what to transmit: 0 nothing (DAC at 128), 1 the bare carrier,
//               2 the melody (from its first note), 3 the 1 kHz tone
//       g<n>    output = envelope / 2^n, n = 0..f (default 2)
//     Lowercase hex.  Anything else is ignored, as are m > 3 and g > f.
//   FPGA -> laptop:  each envelope sample, 0..16383 (14 bits), as two bytes:
//       0hhhhhhh = its low 7 bits, then 1hhhhhhh = its high 7 bits.
//     The top bit says which byte is which, so the laptop can join in anywhere.
//     Envelopes bigger than 16383 after the shift are sent as 16383.
//     25,000 samples/s x 2 bytes = 50 kB/s: half of what 1 Mbaud carries.
// At power-up it transmits the melody at 1.000 MHz and receives at 1.000 MHz,
// with g = 2: a cable from the DAC to the ADC plays Ode to Joy, no commands.
//
// Numbers (all checked by am_check.py):
//   - The envelope is 473.1 A for a carrier of amplitude A ADC codes at f_rx:
//     the mixer gives 127 A / 2, the CIC multiplies by R^3 = 10^9 and divides
//     by 2^27, the FIR's gain is 1.  So a full-scale carrier (A = 127) gives
//     60,084, and a cable from the DAC (A = 0.776 x 69.5 = 54 codes) about
//     25,500: 6,375 after g = 2.  The modulation then swings it from 0.2 to 1.8
//     times that.  A 14-bit output holds up to 16,383.
//   - The sound is flat to 1.1 dB from 0 to 4 kHz, 3 dB down at 4.33 kHz.
//   - Anything 6 to 19 kHz from f_rx (a station 10 kHz away, say) comes
//     through at least 93 dB weaker (from 5.5 kHz: 81 dB), if the arithmetic
//     were perfect.  In practice the 8-bit ADC's own rounding noise, about
//     80 dB below a full-scale carrier, is what's left.
//   - The weak spot: the CIC keeps 1 sample in 1000, so frequencies 25 kHz
//     from f_rx fold onto 0 Hz, and some 20.3 to 29.6 kHz away get through
//     only 43 dB weaker (the worst: 20.8 kHz).  So a station 20 kHz away is
//     stopped 101 dB, but its sound's sidebands at 21 kHz only 44 dB.  (See
//     the CIC section.)
//   - Tuned 10 kHz away from its own transmitter, it still hears the melody,
//     60 dB down: the DAC rounds the modulated carrier to 8 bits, and the
//     rounding errors make faint copies of the sound tens of kHz wide.
//
// LEDs: the left four are a signal-strength meter (each needs 10 dB more than
// the one to its right: a carrier of 1.5, 5, 15, 50 ADC codes); the rightmost
// lights while the transmitter plays a note.

module am_radio #(
    parameter integer EIGHTH = 10_000_000   // clocks per eighth note: 0.2 s (at most 2^24)
) (
    input  logic       clk,         // 50 MHz
    input  logic [7:0] adc_d,
    output logic       adc_clk,
    output logic [7:0] dac_d = 128,
    output logic       dac_clk,
    input  logic       uart_rx,
    output logic       uart_tx,
    output logic [4:0] led
);
    localparam logic [31:0] TW_1MHZ = 32'h051eb852;  // 1.000000 MHz = 85899346 x 50 MHz / 2^32
    localparam logic [31:0] TW_1KHZ = 32'd85899;     // 999.996 Hz, the test tone

    // ---- tables, computed by Yosys (as in lockin.sv and fft.sv) ---------------
    // sine_table: one cycle of a sine, height 127: the carrier, and the
    //   receiver's references (the table at the phase is cos, 64 entries on is
    //   -sin, as in lockin.sv).
    // tone_table: the same, height 56 = 0.8 x 70: the 1 kHz tone, at m = 0.8.
    // box_table:  the music box's note, sin x + 0.5 sin 2x (the note plus, half
    //   as loud, the note an octave up, so even a laptop speaker that can't
    //   play 262 Hz plays something), scaled to the same height, 56.  The
    //   peak of sin x + 0.5 sin 2x is 3 sqrt(3) / 4 = 1.299, at x = 60 degrees.
    logic signed [7:0] sine_table [0:255], tone_table [0:255], box_table [0:255];
    initial
        for (int i = 0; i < 256; i++) begin
            sine_table[i] = $rtoi($floor(127.0 * $sin(6.283185307179586 * i / 256) + 0.5));
            tone_table[i] = $rtoi($floor(56.0 * $sin(6.283185307179586 * i / 256) + 0.5));
            box_table[i]  = $rtoi($floor(56.0 / 1.299038105676658 * ($sin(6.283185307179586 * i / 256)
                                         + 0.5 * $sin(12.566370614359172 * i / 256)) + 0.5));
        end

    // ---- the serial port, both directions (see uart.sv) -------------------------
    logic [7:0] rx_data;
    logic       rx_valid;
    logic [7:0] tx_data  = 0;
    logic       tx_start = 0;
    logic       tx_busy;
    uart_rx #(.CLKS_PER_BIT(50)) rx (.clk(clk), .rx(uart_rx),
                                     .data(rx_data), .valid(rx_valid));
    uart_tx #(.CLKS_PER_BIT(50)) tx (.clk(clk), .data(tx_data), .start(tx_start),
                                     .busy(tx_busy), .tx(uart_tx));

    // ---- commands: a letter, hex digits, Enter -----------------------------------
    // The letter is remembered, the digits shift into `entry` (as in lockin.sv),
    // and Enter carries out the command.
    localparam logic [1:0] OFF = 0, CARRIER = 1, MELODY = 2, TONE = 3;
    logic [31:0] tx_tw   = TW_1MHZ;  // transmit frequency
    logic [31:0] rx_tw   = TW_1MHZ;  // receive frequency
    logic [1:0]  source  = MELODY;   // what the transmitter sends
    logic [3:0]  shift   = 2;        // output = envelope / 2^shift
    logic        restart = 0;        // high for one clock: play the tune from the top
    logic [7:0]  command = 0;        // the letter of the command being typed, or 0
    logic [31:0] entry   = 0;
    logic        is_digit, is_letter;
    logic [3:0]  nibble;
    assign is_digit  = rx_data >= "0" && rx_data <= "9";
    assign is_letter = rx_data >= "a" && rx_data <= "f";
    assign nibble    = is_digit ? rx_data - "0" : rx_data - "a" + 10;
    always_ff @(posedge clk) begin
        restart <= 0;
        if (rx_valid) begin
            if (rx_data == "t" || rx_data == "r" || rx_data == "m" || rx_data == "g") begin
                command <= rx_data;
                entry   <= 0;
            end else if (is_digit || is_letter)
                entry <= {entry[27:0], nibble};
            else if (rx_data == "\n" || rx_data == "\r") begin
                case (command)
                    "t": tx_tw <= entry;
                    "r": rx_tw <= entry;
                    "m": if (entry <= 3) begin
                        source  <= entry[1:0];
                        restart <= 1;
                    end
                    "g": if (entry <= 15) shift <= entry[3:0];
                    default: ;
                endcase
                command <= 0;
            end
        end
    end

    // =============================================================================
    //  THE TRANSMITTER
    // =============================================================================

    // ---- the tune --------------------------------------------------------------
    // Written as text: each note is a letter, the pitch (C to B: C4 to B4, the
    // octave from middle C; R is a rest), then a digit, its length in eighth
    // notes (1 = an eighth, 2 = a quarter, 3 = a dotted quarter, 4 = a half).
    // Write your own tune here.  (A Verilog string is a vector of 8-bit
    // characters, with the first character in the top 8 bits.)
    localparam integer N_NOTES = 31;
    localparam logic [8*2*N_NOTES-1:0] TUNE =
        {"E2E2F2G2", "G2F2E2D2", "C2C2D2E2", "E3D1D4",       // one bar per string:
         "E2E2F2G2", "G2F2E2D2", "C2C2D2E2", "D3C1C4",       //   4 quarter notes each
         "R4"};
    localparam integer GAP = EIGHTH / 5;  // the last 40 ms of each note fades out

    logic [5:0]  note   = 0;         // which note of the tune: 0 .. N_NOTES-1
    logic [2:0]  eighth = 0;         // eighths of it already played
    logic [23:0] timer  = 0;         // clocks into the current eighth
    logic [7:0]  letter, digit;
    logic [31:0] note_tw;            // the note's tuning word, or 0 for a rest
    logic        last_eighth, in_gap, note_over;
    assign letter      = TUNE[8 * (2 * N_NOTES - 1 - 2 * note) +: 8];
    assign digit       = TUNE[8 * (2 * N_NOTES - 2 - 2 * note) +: 8];
    assign last_eighth = (eighth == digit - "1");
    assign in_gap      = last_eighth && (timer >= EIGHTH - GAP);
    assign note_over   = last_eighth && (timer == EIGHTH - 1);

    // The pitch: f = 440 Hz x 2^(s/12), s = semitones from A4 (equal temperament),
    // as a tuning word for a DDS clocked at 50 MHz: f x 2^32 / 50 MHz.
    always_comb
        case (letter)
            "C": note_tw = 32'd22473;    // C4, 261.63 Hz
            "D": note_tw = 32'd25226;    // D4, 293.66 Hz
            "E": note_tw = 32'd28315;    // E4, 329.63 Hz
            "F": note_tw = 32'd29998;    // F4, 349.23 Hz
            "G": note_tw = 32'd33672;    // G4, 392.00 Hz
            "A": note_tw = 32'd37796;    // A4, 440.00 Hz
            "B": note_tw = 32'd42424;    // B4, 493.88 Hz
            default: note_tw = 0;        // R: a rest
        endcase

    // ---- the music box: each note starts loud and dies away ---------------------
    // Every 2^16 clocks (1.31 ms) the loudness loses 1/256 of itself: an
    // exponential decay with a time constant of 256 x 1.31 ms = 0.34 s.  In the
    // gap at the end of a note it loses 1/8 each time (10 ms), so the next
    // pluck, even of the same note, is heard as a new note.
    logic        pluck       = 0;        // high for one clock: a new note begins
    logic [15:0] loudness    = 16'hffff; // 0 .. 65535 = silent .. full
    logic [15:0] tick        = 0;        // counts 2^16 clocks
    logic [31:0] note_phase  = 0;        // the note's DDS: starts at 0 with each pluck
    logic [31:0] tone_phase  = 0;        // the 1 kHz tone's DDS
    always_ff @(posedge clk) begin
        timer <= (timer == EIGHTH - 1) ? 24'd0 : timer + 1;
        if (timer == EIGHTH - 1)
            eighth <= eighth + 1;
        pluck <= 0;
        if (note_over || restart) begin            // on to the next note
            note   <= (restart || note == N_NOTES - 1) ? 6'd0 : note + 1;
            eighth <= 0;
            timer  <= 0;
            pluck  <= 1;                            // (next clock: note_tw is the new note's)
        end
        tick <= tick + 1;
        if (pluck) begin
            loudness   <= (note_tw != 0) ? 16'hffff : 16'd0;
            note_phase <= 0;                        // so the sound starts smoothly from 0
        end else begin
            if (tick == 0)
                loudness <= loudness - (loudness >> (in_gap ? 3 : 8));
            note_phase <= note_phase + note_tw;
        end
        tone_phase <= tone_phase + TW_1KHZ;
    end

    // ---- the sound a(t), and the carrier's amplitude 70 (1 + 0.8 a(t)) -------------
    // Everything here is in DAC codes x 256, so that the slowly changing
    // amplitude has 8 bits after the binary point.
    logic signed [7:0]  wave      = 0;   // the table: -56 .. 56
    logic        [8:0]  level     = 0;   // its loudness: 0 .. 256
    logic signed [16:0] audio     = 0;   // wave x level = 56 a(t) x 256
    logic        [15:0] amplitude = 0;   // 70 x 256 + audio = 70 (1 + 0.8 a(t)) x 256
    always_ff @(posedge clk) begin
        wave  <= (source == TONE) ? tone_table[tone_phase[31:24]] : box_table[note_phase[31:24]];
        level <= (source == TONE) ? 9'd256 : {1'b0, loudness[15:8]};
        audio <= wave * $signed({1'b0, level});
        case (source)
            OFF:     amplitude <= 0;
            CARRIER: amplitude <= 70 * 256;
            default: amplitude <= 70 * 256 + audio;
        endcase
    end

    // ---- the carrier, and the DAC -----------------------------------------------
    logic [31:0]        tx_phase = 0;
    logic signed [7:0]  carrier  = 0;    // cos(2 pi f_tx t): -127 .. 127
    logic signed [24:0] rf       = 0;    // carrier x amplitude
    always_ff @(posedge clk) begin
        tx_phase <= tx_phase + tx_tw;
        carrier  <= sine_table[tx_phase[31:24]];
        // ######################################################################
        // ##  KEY LINE: amplitude modulation.  The carrier times its amplitude;
        // ##  then / 2^15 (rounded) undoes the x 256 and the table's x 128:
        // ##  DAC = 128 + 70 (1 + 0.8 a(t)) x 127/128 x cos(2 pi f_tx t).
        // ######################################################################
        rf    <= carrier * $signed({1'b0, amplitude});
        dac_d <= 128 + ((rf + 25'sd16384) >>> 15);
    end
    assign dac_clk = ~clk;

    // =============================================================================
    //  THE RECEIVER
    // =============================================================================

    // ---- the ADC at 25 MS/s, and the receiver's own DDS, as in lockin.sv -------------
    // The receiver's phase steps every clock, like the transmitter's, so both
    // use f = TW x 50 MHz / 2^32.  Each sample keeps the phase it was taken at.
    logic [31:0] rx_phase     = 0;
    logic        adc_clk_r    = 0;
    logic        new_sample   = 0;
    logic [7:0]  sample       = 128;
    logic [7:0]  sample_phase = 0;
    always_ff @(posedge clk) begin
        rx_phase   <= rx_phase + rx_tw;
        adc_clk_r  <= ~adc_clk_r;
        new_sample <= 0;
        if (adc_clk_r == 0) begin            // adc_clk is about to rise
            sample       <= adc_d;
            sample_phase <= rx_phase[31:24];
            new_sample   <= 1;
        end
    end
    assign adc_clk = adc_clk_r;

    // ---- 1. mix down to 0 Hz -----------------------------------------------------
    // x cos and x (-sin), exactly the lock-in's products.  If the ADC sees
    // A cos(2 pi f t + phi), then I + jQ = (127 A / 2) e^(j (2 pi (f - f_rx) t + phi)),
    // plus terms at f + f_rx that the filters remove: the lock-in's X + jY, but
    // turning at the difference frequency f - f_rx.  The filters keep it only
    // if that's less than about 4.5 kHz.  Each step takes one clock; v1 and v2
    // say "the step before me had a new sample".
    logic               v1 = 0, v2 = 0;
    logic signed [8:0]  x     = 0;           // sample - 128: -128 .. 127
    logic signed [7:0]  ref_c = 0, ref_s = 0;
    logic signed [15:0] mix_i = 0, mix_q = 0;  // -16256 .. 16256
    always_ff @(posedge clk) begin
        v1    <= new_sample;
        x     <= $signed({1'b0, sample}) - 9'sd128;
        ref_c <= sine_table[sample_phase];            // cos
        ref_s <= sine_table[sample_phase + 8'd64];    // a quarter turn on: -sin
        v2    <= v1;
        // ######################################################################
        // ##  KEY LINE: multiply the signal by both references, cos and -sin.
        // ######################################################################
        mix_i <= x * ref_c;
        mix_q <= x * ref_s;
    end

    // ---- 2. the CIC filter: 25 MS/s -> 25 kS/s ----------------------------------------
    // The lock-in's average is a low-pass filter.  So is a moving average of the
    // last R = 1000 samples: it lets through about +-11 kHz around 0 Hz (3 dB
    // down there), and nothing at 25 kHz (= 25 MS/s / 1000), 50 kHz, ...
    // The trick: keep a running sum S[n] = x[0] + ... + x[n] (an "integrator");
    // then the sum of the last R samples is S[n] - S[n - R] (a "comb").  And
    // since we keep only every R-th output, the comb runs at 25 kS/s: each
    // output is S now minus S at the previous output.  No multiplies, no
    // memory of 1000 samples, just adders.
    //
    // One moving average leaks badly (frequencies between its nulls get through
    // only 13 dB down), so the CIC ("cascaded integrator-comb") does three in a
    // row: three integrators, then three combs.  Its response is
    //     H(f) = [ sin(pi f R / 25 MHz) / (R sin(pi f / 25 MHz)) ]^3,
    // zero at multiples of 25 kHz, and 1.1 dB down at 4 kHz, 1.7 dB at 5 kHz
    // ("droop"), 7.3 dB at 10 kHz, 38 dB at 20 kHz.  The FIR does the rest.
    //
    // The catch: after keeping 1 sample in 1000, f and f + 25 kHz look alike
    // ("aliasing", as the ADC itself folds 15 MHz onto 10 MHz).  The CIC's
    // nulls at 25 kHz, 50 kHz, ... are where things fold onto 0 Hz, which is
    // why it works -- but a station 21 kHz away folds onto 4 kHz, which the
    // FIR passes, and the CIC alone stops it only 44 dB.
    //
    // Bit growth: each sum of R numbers can be R times bigger than one of them,
    // so three in a row grow by R^3 = 10^9: log2(10^9) = 3 log2(1000) = 29.9 bits.
    // In: 15 bits (|mix| <= 16256 < 2^14, and a sign).  Out: 15 + 30 = 45 bits.
    // The integrators overflow and wrap around, over and over -- and that is
    // fine: two's complement is arithmetic modulo 2^45, and the combs'
    // differences come out right as long as the final answer fits in 45 bits.
    localparam integer R = 1000;
    localparam integer W = 45;
    logic signed [W-1:0] int_i1 = 0, int_i2 = 0, int_i3 = 0;
    logic signed [W-1:0] int_q1 = 0, int_q2 = 0, int_q3 = 0;
    logic [9:0]          count  = 0;     // 0 .. R-1
    logic                dec    = 0;     // high for one clock after every R-th sample
    always_ff @(posedge clk) begin
        dec <= 0;
        if (v2) begin
            // ##################################################################
            // ##  KEY LINES: three integrators in a row, at 25 MS/s.  Each adds
            // ##  up the one before it.
            // ##################################################################
            int_i1 <= int_i1 + mix_i;
            int_i2 <= int_i2 + int_i1;
            int_i3 <= int_i3 + int_i2;
            int_q1 <= int_q1 + mix_q;
            int_q2 <= int_q2 + int_q1;
            int_q3 <= int_q3 + int_q2;
            count  <= (count == R - 1) ? 10'd0 : count + 1;
            if (count == R - 1)
                dec <= 1;
        end
    end

    // The three combs, once per output, one per clock: each takes the
    // difference between its input now and its input at the previous output.
    logic signed [W-1:0] comb_i1 = 0, comb_i2 = 0, comb_i3 = 0, last_i1 = 0, last_i2 = 0, last_i3 = 0;
    logic signed [W-1:0] comb_q1 = 0, comb_q2 = 0, comb_q3 = 0, last_q1 = 0, last_q2 = 0, last_q3 = 0;
    logic [2:0]          dec_d = 0;      // dec, delayed by 1, 2, 3 clocks
    always_ff @(posedge clk) begin
        dec_d <= {dec_d[1:0], dec};
        if (dec) begin
            // ##################################################################
            // ##  KEY LINES: the first comb, at 25 kS/s: the running sum now,
            // ##  minus the running sum 1000 samples ago.
            // ##################################################################
            comb_i1 <= int_i3 - last_i1;
            last_i1 <= int_i3;
            comb_q1 <= int_q3 - last_q1;
            last_q1 <= int_q3;
        end
        if (dec_d[0]) begin
            comb_i2 <= comb_i1 - last_i2;
            last_i2 <= comb_i1;
            comb_q2 <= comb_q1 - last_q2;
            last_q2 <= comb_q1;
        end
        if (dec_d[1]) begin
            comb_i3 <= comb_i2 - last_i3;
            last_i3 <= comb_i2;
            comb_q3 <= comb_q2 - last_q3;
            last_q3 <= comb_q2;
        end
    end

    // Keep the top 18 bits, the width of the multipliers: / 2^27, rounded.
    // At most 16256 x 10^9 / 2^27 = 121,117, so it fits (18 bits: +-131,071).
    logic signed [W-1:0] cic_i_full, cic_q_full;
    logic signed [17:0]  cic_i, cic_q;
    assign cic_i_full = (comb_i3 + (45'sd1 <<< 26)) >>> 27;
    assign cic_q_full = (comb_q3 + (45'sd1 <<< 26)) >>> 27;
    assign cic_i      = cic_i_full[17:0];
    assign cic_q      = cic_q_full[17:0];

    // ---- 3. the FIR filter at 25 kS/s -----------------------------------------------
    // A FIR ("finite impulse response") filter: each output is a weighted sum of
    // the last 127 inputs,  y[n] = h[0] x[n] + h[1] x[n-1] + ... + h[126] x[n-126].
    // Its response to a sine of frequency f is sum_k h[k] e^(-2 pi i f k / 25 kHz)
    // (a Fourier transform of the h's), so to pass 0..4.5 kHz and block the
    // rest, choose h = the Fourier transform of that: the "sinc" function
    //     sin(2 pi fc k / fs) / (pi k),   fc = 4.5 kHz, fs = 25 kHz,
    // counting k from the middle tap.  It goes on forever, so cut it to 127
    // taps, and fade it out towards the ends with a window (as fft.sv does to
    // its frames), here a Blackman window, so the cut doesn't leak.  Result:
    // flat (+-0.001 dB) to 3.5 kHz, -6 dB at 4.5 kHz, -63 dB at 5 kHz, and
    // below -78 dB from 5.5 kHz up.  The h's add up to 2^18 (almost: 262,140),
    // so dividing the sum by 2^18 gives a gain of 1 at 0 Hz.
    //
    // 127 multiplies for I and 127 for Q, 4 clocks each: 1016 of the 2000
    // clocks between outputs, all on one multiplier.
    localparam integer TAPS = 127;
    localparam real    FS = 25000.0, FC = 4500.0;
    logic signed [17:0] coef [0:TAPS-1];
    initial
        for (int i = 0; i < TAPS; i++)
            coef[i] = (i == TAPS / 2) ? $rtoi($floor(262144.0 * 2.0 * FC / FS + 0.5))
                    : $rtoi($floor(262144.0
                        * $sin(6.283185307179586 * FC / FS * (i - TAPS / 2))     // the sinc,
                        / (3.141592653589793 * (i - TAPS / 2))
                        * (0.42 + 0.5 * $cos(6.283185307179586 * (i - TAPS / 2) / 128.0)   // the window
                           + 0.08 * $cos(12.566370614359172 * (i - TAPS / 2) / 128.0)) + 0.5));

    // The last 128 inputs of each, in block RAM, as a ring: `newest` is where
    // the newest is, and x[n-k] is k places back (the 7-bit address wraps).
    (* no_rw_check *) logic signed [17:0] hist_i [0:127], hist_q [0:127];
    initial
        for (int i = 0; i < 128; i++) begin
            hist_i[i] = 0;
            hist_q[i] = 0;
        end
    logic [6:0]         newest = 0;
    logic [6:0]         tap    = 0;      // k
    logic               ch     = 0;      // 0: filtering I; 1: Q
    logic [6:0]         raddr;
    logic signed [17:0] rd_i, rd_q, coef_rd;
    assign raddr = newest - tap;
    always_ff @(posedge clk) begin
        if (dec_d[2]) begin                  // the combs are done: a new input
            hist_i[newest + 7'd1] <= cic_i;
            hist_q[newest + 7'd1] <= cic_q;
        end
        rd_i    <= hist_i[raddr];
        rd_q    <= hist_q[raddr];
        coef_rd <= coef[tap];
    end

    // ---- 4. the envelope, and 5. out to the laptop ------------------------------------
    // v / 2^18, rounded, kept within 18 bits.  (Only a strange signal, bigger
    // than any sine, could need more: the h's add up to 2^18, but their sizes
    // to 2.05 x 2^18.)
    function automatic logic signed [17:0] scale(input logic signed [39:0] v);
        logic signed [39:0] r;
        r = (v + 40'sd131072) >>> 18;
        if (r > 131071)       scale = 131071;
        else if (r < -131071) scale = -131071;
        else                  scale = r[17:0];
    endfunction

    typedef enum logic [2:0] {WAIT, FILTER, ROUND, SQUARE, ROOT, OUTPUT} state_t;
    state_t             state = WAIT;
    logic [1:0]         step  = 0;       // FILTER: the step within one tap
    logic signed [17:0] d = 0, c = 0;    // x[n-k] and h[k], into the multiplier
    logic signed [35:0] prod  = 0;
    logic signed [39:0] acc   = 0, acc_i = 0;
    logic signed [17:0] fir_i = 0, fir_q = 0;
    logic        [35:0] power = 0;       // I^2 + Q^2 < 2^35
    logic        [17:0] root  = 0, bit_ = 0, envelope = 0;
    logic        [17:0] trial;
    logic        [35:0] trial_sq;
    logic               out_ready = 0;   // high for one clock: `envelope` is new
    assign trial    = root | bit_;
    assign trial_sq = trial * trial;
    always_ff @(posedge clk) begin
        out_ready <= 0;
        case (state)
            WAIT:
                if (dec_d[2]) begin              // a new input is being written
                    newest <= newest + 1;
                    tap    <= 0;
                    ch     <= 0;
                    step   <= 0;
                    acc    <= 0;
                    state  <= FILTER;
                end
            FILTER: begin
                step <= step + 1;
                case (step)
                    0: ;                                    // the RAMs read x[n-k], h[k]
                    1: begin                                // into registers (fft.sv explains)
                        d <= ch ? rd_q : rd_i;
                        c <= coef_rd;
                    end
                    2: prod <= d * c;
                    3: begin
                        // ##########################################################
                        // ##  KEY LINE: multiply-accumulate: add h[k] x[n-k].
                        // ##########################################################
                        acc <= acc + prod;
                        tap <= tap + 1;
                        if (tap == TAPS - 1) begin          // that was the last tap
                            tap <= 0;
                            if (ch == 0) begin              // I is done; now Q
                                acc_i <= acc + prod;
                                acc   <= 0;
                                ch    <= 1;
                            end else
                                state <= ROUND;
                        end
                    end
                endcase
            end
            ROUND: begin
                fir_i <= scale(acc_i);
                fir_q <= scale(acc);
                state <= SQUARE;
            end
            SQUARE: begin
                power <= fir_i * fir_i + fir_q * fir_q;
                root  <= 0;
                bit_  <= 18'h20000;                         // 2^17, the top bit of the root
                state <= ROOT;
            end
            ROOT: begin
                // ##############################################################
                // ##  KEY LINE: the square root, one bit per clock, from the
                // ##  top: set the next bit, and keep it if the square of the
                // ##  root so far is still no more than I^2 + Q^2.  After 18
                // ##  clocks, root = floor(sqrt(I^2 + Q^2)).
                // ##############################################################
                if (trial_sq <= power)
                    root <= trial;
                bit_ <= bit_ >> 1;
                if (bit_ == 1)
                    state <= OUTPUT;
            end
            OUTPUT: begin
                envelope  <= root;
                out_ready <= 1;
                state     <= WAIT;
            end
            default: state <= WAIT;
        endcase
    end

    // Send envelope / 2^shift (at most 16383) as two bytes: 0 + the low 7 bits,
    // then 1 + the high 7 bits.  They take 1000 of the 2000 clocks to the next.
    logic [17:0] shifted;
    logic [13:0] out14   = 0;
    logic [1:0]  to_send = 0;            // bytes still to send
    assign shifted = envelope >> shift;
    always_ff @(posedge clk) begin
        tx_start <= 0;
        if (out_ready) begin
            out14   <= (shifted > 16383) ? 14'd16383 : shifted[13:0];
            to_send <= 2;
        end else if (to_send != 0 && !tx_busy && !tx_start) begin
            tx_data  <= (to_send == 2) ? {1'b0, out14[6:0]} : {1'b1, out14[13:7]};
            tx_start <= 1;
            to_send  <= to_send - 1;
        end
    end

    // ---- LEDs: signal strength (473 per ADC code), and the notes -----------------------
    logic playing;
    assign playing = (source == TONE) || (source == MELODY && note_tw != 0 && !in_gap);
    assign led = {envelope >= 18'd23655, envelope >= 18'd7097, envelope >= 18'd2366,
                  envelope >= 18'd710, playing};
endmodule
