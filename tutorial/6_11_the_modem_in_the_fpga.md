<!-- nav -->
[← 6.10 Chirps, Zadoff–Chu and LoRa: ranging, and radar on a cable](6_10_chirps_and_lora.md#610-chirps-zadoffchu-and-lora-ranging-and-radar-on-a-cable) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)** &emsp;&emsp;&emsp; [6.12 On the air: whispers, and how far they carry →](6_12_on_the_air.md#612-on-the-air-whispers-and-how-far-they-carry)

# 6.11 The modem in the FPGA

![Simulated with channel.py's model: the symbols after the FPGA's loops, in integers; the symbol-rate offset the timing loop finds and the carrier offset the Costas loop finds, the fixed-point model against psk.py on the same samples, with the transmitter 2000 ppm fast and 3 kHz off; the symbol centre sliding between samples; and the two detectors' outputs symbol by symbol](img/comms_modem_fpga.png)

[5.05](5_05_fsk_modem.md#505-a-modem)'s modem carried a *line*: whatever
level the laptop's serial pin had, the DAC played as one of two tones. This
one carries *bytes*, at 3.125 Mbit/s, as the [QPSK](https://en.wikipedia.org/wiki/Phase-shift_keying#Quadrature_phase-shift_keying_(QPSK)) of
[6.02](6_02_psk_and_qpsk.md#602-psk-and-qpsk-finding-the-clock-and-the-carrier):
root-raised-cosine pulses, a matched filter, Gardner's timing loop, a Costas
loop, frames. Everything `psk.py` did on the laptop with numpy and floating
point now happens inside the FPGA, one clock at a time, in integers and
shifts, in one file. Type into the board's serial port and the characters
come back through the cable 30 µs later. This is the page where "software
defined radio" meets the hardware, and the honest story is which parts
were easy (the arithmetic) and which were not (the bookkeeping).

Everything on this page runs *in the FPGA*. The laptop types (`screen`),
counts errors (`qpsk_modem_test.py`), and runs the Python twin of the
design (`modem_fpga_model.py`) for the figures; no numpy touches a sample
on the live link.

![The blocks of qpsk_modem.sv: the transmitter from the serial port through frames, differential coding, the multiplier-free pulse shaper and the carrier to the DAC; the receiver from the ADC through the mixer, the half-band filter, the decimator, the matched filter, the interpolator and timing loop, the Costas loop, the differential decoder and the frame lock to the serial port, with the clock budget under each row](img/comms_d_modem_fpga.png)

<details>
<summary>The whole file: <code>qpsk_modem.sv</code></summary>

<!-- file: src/twoboard/qpsk_modem.sv -->
```systemverilog
// qpsk_modem.sv -- a QPSK modem inside the FPGA: text typed into this board's serial port
// leaves the DAC as 3.125 Mbit/s of differential QPSK on a 6.25 MHz carrier, and QPSK
// arriving at the ADC comes out of the serial port as text.  Everything psk.py (6.02)
// does on the laptop, one clock at a time, in integers and shifts.  modem_fpga_model.py
// is the same arithmetic in Python; qpsk_modem_check.py shows they agree bit for bit.
//
// TRANSMITTER (one DAC sample per 50 MHz clock)
//   frame    16 bits = 8 symbols: a 7-bit sync word (Barker's 1110010), a "valid" bit,
//            and the byte from the serial port, or 8 bits of a shift register when there
//            is none.  195,312 frames a second: more than 1 Mbaud can supply.
//   symbols  2 bits each, Gray-coded, as a CHANGE of phase (differential QPSK): 00, 01,
//            11, 10 turn the carrier by 0, 90, 180, 270 degrees from the previous symbol,
//            so the receiver needn't know which way is up.
//   pulses   root-raised-cosine, roll-off 0.35, 32 DAC samples per symbol (1.5625
//            Msymbol/s), cut off 6 symbols each side.  The symbols are +-1 +-j, so the
//            pulse shaper is 13 table look-ups and an adder tree: no multipliers.
//   carrier  6.25 MHz = 50 MS/s / 8: cos and sin take the values 0, +-1 and +-0.707, so
//            I cos - Q sin is one of I, Q, 0.707 (I +- Q), and 0.707 = 181/256.
//
// RECEIVER (an ADC sample every 2 clocks; from the decimator on, 8 clocks per sample)
//   1. mix down by 6.25 MHz = 25 MS/s / 4: multiply by 1, -j, -1, j (free).  That leaves
//      I on the even samples and Q on the odd ones, with a hole between each pair.
//   2. a half-band filter, [-1 0 9 16 9 0 -1] / 32, fills Q's holes at the even samples
//      (I's own samples go through it untouched) and keeps the even ones: 12.5 MS/s.
//      Then [1 2 1], keeping 1 in 2: 6.25 MS/s, 4 samples per symbol.
//   3. a 3-tap filter (shifts only) that undoes [1 2 1]'s droop across the band.
//   4. the matched filter: the same root-raised-cosine, 49 taps, symmetric, so 25
//      multiplies per I and Q, shared between 4 multipliers each over 7 of the 8 clocks.
//   5. the timing loop: a counter (the "NCO") says when the next symbol centre falls
//      between two samples, and a cubic interpolator (Catmull-Rom's: its coefficients are
//      halves, 3 multiplies per axis) computes the signal there and, from a second strobe
//      half a period earlier, half-way between symbols.  Gardner's detector; a PI loop
//      filter whose gains are shifts.
//   6. the Costas loop: turn each symbol by the phase so far (a 1024-entry sine table, 4
//      multiplies), find the nearest of the four points, Im(z d*) is +-Q -+ I: no
//      multiplies; a PI loop filter with shift gains learns the carrier's frequency.
//   7. the symbol's quadrant minus the previous one's is the 2 bits; 8 of those make a
//      frame; the sync word in the right place three times running is "locked", and from
//      then on each frame's byte, if valid, goes to the serial port.
//
// Serial port, 1,000,000 baud, both ways: bytes in are sent, bytes received come out.
// (Out, the bytes leave with no pause between them and 2 % fast, 49 clocks per bit: a
// repeater with no flow control must send at least as fast as it receives; see below.)
// LEDs: left, frame lock; then a received byte, a typed byte, the ADC clipping.
//
// Numbers.  The pulse table is 384 x rrc, so the DAC swings about 48 codes rms, 108 at
// the very worst: it can't clip.  With 1.07's cable (0.776 codes per code) a symbol comes
// out of the matched filter at about 1190 per axis, in 16 bits (adversarial inputs reach
// 7900); the interpolator keeps 18; the loops' detectors see 17.  The timing counter
// has 16 bits below the sample; phase has 24 bits per turn.

module qpsk_modem #(
    parameter integer FIFO_BITS = 5     // bytes waiting for the serial port: 2^5 = 32
) (
    input  logic       clk,         // 50 MHz
    input  logic       uart_rx,     // from the laptop
    output logic       uart_tx,     // to the laptop
    output logic [7:0] dac_d = 128,
    output logic       dac_clk,
    input  logic [7:0] adc_d,
    output logic       adc_clk,
    output logic [4:0] led
);
    localparam logic [6:0]  SYNC = 7'b1110010;      // Barker 7
    localparam logic signed [23:0] ONE  = 24'sd65536;     // one sample, in the NCO's units
    localparam logic signed [23:0] PNOM = 24'sd262144;    // 4 samples per symbol
    localparam integer S1_T = 7, S2_T = 5;          // timing loop:  tau -= e >> S1_T; integ += e >> S2_T
    localparam integer S1_C = 7, S2_C = 2;          // carrier loop: phi += e << S1_C; freq += e << S2_C

    // Gray code, both ways: 2 bits <-> a turn of 0, 1, 2, 3 quarters (00 01 11 10)
    function automatic logic [1:0] gray(input logic [1:0] v);
        gray = {v[1], v[1] ^ v[0]};
    endfunction

    // ---- the serial port in (see uart.sv); the way out is at the end -----------------
    logic [7:0] rx_data;
    logic       rx_valid;
    uart_rx #(.CLKS_PER_BIT(50)) urx (.clk(clk), .rx(uart_rx), .data(rx_data), .valid(rx_valid));

    // =============================================================================
    //  THE TRANSMITTER
    // =============================================================================

    // ---- frames and symbols --------------------------------------------------------
    logic [4:0]  p    = 0;          // DAC sample within the symbol, 0..31
    logic [2:0]  fs   = 0;          // symbol within the frame, 0..7
    logic [15:0] fw   = 0;          // the frame being sent; this symbol's 2 bits at the top
    logic [15:0] lfsr = 16'hACE1;   // the idle filler: x^16 + x^14 + x^13 + x^11 + 1
    logic [7:0]  byte_in = 0;
    logic        pending = 0;       // a byte from the laptop waits for the next frame
    logic [1:0]  q = 0;             // the symbol being sent: 0..3 = 45, 135, 225, 315 deg
    logic [1:0]  sr [0:12];         // the 13 symbols overlapping at the DAC: sr[0] newest
    logic        frame_load;        // the last DAC sample of a frame: load the next
    logic [15:0] fw_next;
    logic [1:0]  q_next;
    initial for (int i = 0; i < 13; i++) sr[i] = 0;
    assign frame_load = (p == 31) && (fs == 7);
    assign fw_next    = frame_load ? {SYNC, pending, pending ? byte_in : lfsr[7:0]} : {fw[13:0], 2'b00};
    // ##########################################################################
    // ##  KEY LINE: differential coding.  The 2 bits say how far to TURN from
    // ##  the previous symbol, not where to point.
    // ##########################################################################
    assign q_next = q + gray(fw_next[15:14]);
    always_ff @(posedge clk) begin
        p <= p + 1;
        if (p == 31) begin                      // the next symbol starts
            fs   <= fs + 1;
            fw   <= fw_next;
            q    <= q_next;
            sr[0] <= q_next;
            for (int i = 1; i < 13; i++) sr[i] <= sr[i-1];
            lfsr <= {lfsr[14:0], lfsr[15] ^ lfsr[13] ^ lfsr[12] ^ lfsr[10]};
            if (frame_load) pending <= 0;
        end
        if (rx_valid) begin                     // (after the above: a byte that arrives
            byte_in <= rx_data;                 //  as a frame loads waits for the next)
            pending <= 1;
        end
    end

    // ---- the pulse shaper: 13 tables, one per overlapping symbol ----------------------
    // Symbol j (sr[j]) is j symbols older than the newest, and the newest is 6 symbols
    // ahead of the DAC, so at phase p its pulse is at t = (j - 6) + p/32 symbols.
    logic signed [9:0] pulse [0:12];            // 384 x rrc(t) for each, at this phase
    generate
        for (genvar j = 0; j < 13; j++) begin : rom
            rrc_rom #(.J(j)) r (.clk(clk), .p(p), .v(pulse[j]));
        end
    endgenerate
    logic [1:0]         sr1 [0:12];             // sr, a clock later, to match the tables
    logic signed [10:0] ti [0:12], tq [0:12];   // each symbol's +- pulse, for I and Q
    logic signed [12:0] env_i = 0, env_q = 0;   // the sums: the complex envelope
    logic [4:0]         p1 = 0, p2 = 0, p3 = 0; // the phase, pipelined alongside
    initial for (int i = 0; i < 13; i++) begin sr1[i] = 0; ti[i] = 0; tq[i] = 0; end
    always_ff @(posedge clk) begin
        p1 <= p; p2 <= p1; p3 <= p2;
        for (int i = 0; i < 13; i++) sr1[i] <= sr[i];
        // ######################################################################
        // ##  KEY LINE: the pulse shaper.  Each symbol is +-1 +-j, so it adds or
        // ##  subtracts its pulse's table value; the envelope is the sum of 13.
        // ######################################################################
        for (int i = 0; i < 13; i++) begin
            ti[i] <= (sr1[i] == 0 || sr1[i] == 3) ? pulse[i] : -pulse[i];     // I: + for 45 and 315 deg
            tq[i] <= (sr1[i] == 0 || sr1[i] == 1) ? pulse[i] : -pulse[i];     // Q: + for 45 and 135 deg
        end
        env_i <= ti[0] + ti[1] + ti[2] + ti[3] + ti[4] + ti[5] + ti[6] + ti[7] + ti[8] + ti[9] + ti[10] + ti[11] + ti[12];
        env_q <= tq[0] + tq[1] + tq[2] + tq[3] + tq[4] + tq[5] + tq[6] + tq[7] + tq[8] + tq[9] + tq[10] + tq[11] + tq[12];
    end

    // ---- onto the carrier, and the DAC -------------------------------------------------
    // 8 samples per cycle: I cos - Q sin is I, 0.707 (I - Q), -Q, 0.707 (-I - Q), -I,
    // 0.707 (-I + Q), Q, 0.707 (I + Q), and 0.707 = 181/256.  Then / 8, the table's scale.
    // Three more clocks of pipeline: the choice, the x 181, then the rounding.
    logic [2:0]         m8;                     // where in the carrier's cycle
    logic signed [13:0] even = 0, odd = 0;
    logic               is_odd = 0, is_odd2 = 0;
    logic signed [21:0] odd181 = 0, even8 = 0;
    logic signed [10:0] code;
    assign m8 = p3[2:0];
    always_ff @(posedge clk) begin
        // ######################################################################
        // ##  KEY LINE: onto the carrier: a choice of I, Q or 0.707 (I +- Q).
        // ######################################################################
        case (m8)
            0: even <= env_i;  2: even <= -env_q;  4: even <= -env_i;  default: even <= env_q;
        endcase
        case (m8)
            1: odd <= env_i - env_q;  3: odd <= -env_i - env_q;  5: odd <= -env_i + env_q;  default: odd <= env_i + env_q;
        endcase
        is_odd  <= m8[0];
        odd181  <= (odd <<< 7) + (odd <<< 5) + (odd <<< 4) + (odd <<< 2) + odd + 22'sd1024;   // x 181, rounded
        even8   <= (even <<< 8) + 22'sd1024;                                                  // x 256, rounded
        is_odd2 <= is_odd;
    end
    assign code = (is_odd2 ? odd181 : even8) >>> 11;        // / 2048: the table's x 8 and the x 256
    always_ff @(posedge clk)
        dac_d <= (code > 127) ? 8'd255 : (code < -128) ? 8'd0 : 8'(128 + code);     // (it never clips)
    assign dac_clk = ~clk;

    // =============================================================================
    //  THE RECEIVER
    // =============================================================================

    // ---- the ADC at 25 MS/s, as in modem.sv ------------------------------------------
    logic              adc_clk_r = 0, new_sample = 0;
    logic signed [8:0] xs = 0;
    always_ff @(posedge clk) begin
        adc_clk_r  <= ~adc_clk_r;
        new_sample <= 0;
        if (adc_clk_r == 0) begin
            xs <= $signed({1'b0, adc_d}) - 9'sd128;
            new_sample <= 1;
        end
    end
    assign adc_clk = adc_clk_r;

    // ---- 1 and 2: mix by 1, -j, -1, j; the half-band filter; [1 2 1] ----------------------
    // The last 7 samples, and the phase (sample number mod 4) of the newest.  Mixing by
    // 1, -j, -1, j puts +x, 0, -x, 0 on I and 0, -x, 0, +x on Q, so when the newest
    // sample is odd, x[3] is an even one: I is +-16 x[3], and Q is interpolated there
    // from the four odd samples around it, 9 (x[2] + x[4]) - (x[0] + x[6]) with the
    // mixing signs.  (The half-band filter's own taps are -1 0 9 16 9 0 -1, over 32.)
    logic signed [8:0]  x [0:6];
    logic signed [9:0]  hb;                     // x[4] - x[2]: 9 of these go into Q
    logic [1:0]         n4 = 0, ph = 0;         // the phase of the next sample, and of x[0]
    logic               s1 = 0;
    logic signed [13:0] i1 = 0, q1 = 0;         // 12.5 MS/s
    logic               s1v = 0, tog = 0;       // a new i1/q1; its index's parity
    initial for (int i = 0; i < 7; i++) x[i] = 0;
    assign hb = x[4] - x[2];
    always_ff @(posedge clk) begin
        s1  <= new_sample;
        s1v <= 0;
        if (new_sample) begin
            x[0] <= xs;
            for (int i = 1; i < 7; i++) x[i] <= x[i-1];
            n4 <= n4 + 1;
            ph <= n4;
        end
        if (s1 && ph[0]) begin                  // x[3] is an even sample
            // ##################################################################
            // ##  KEY LINE: I is the even sample itself, Q is interpolated from
            // ##  its odd neighbours (a half-band filter), both mixed down.
            // ##################################################################
            if (ph == 3) begin                  // x[3] has phase 0: +x; its neighbours 3, 1, 1, 3
                i1 <= x[3] <<< 4;
                q1 <= (hb <<< 3) + hb + x[6] - x[0];
            end else begin                      // x[3] has phase 2: everything the other way
                i1 <= -(x[3] <<< 4);
                q1 <= -((hb <<< 3) + hb) + x[0] - x[6];
            end
            s1v <= 1;
        end
    end
    // [1 2 1] over three of those, keeping every other one (the even-numbered): 6.25 MS/s
    logic signed [13:0] li [0:2], lq [0:2];
    logic               s2 = 0, s2v = 0;
    logic signed [15:0] i2 = 0, q2 = 0;
    initial for (int i = 0; i < 3; i++) begin li[i] = 0; lq[i] = 0; end
    always_ff @(posedge clk) begin
        s2  <= 0;
        s2v <= 0;
        if (s1v) begin
            li[0] <= i1; li[1] <= li[0]; li[2] <= li[1];
            lq[0] <= q1; lq[1] <= lq[0]; lq[2] <= lq[1];
            tog <= ~tog;
            s2  <= ~tog;                        // the newest is even-numbered
        end
        if (s2) begin
            i2 <= li[2] + (li[1] <<< 1) + li[0];
            q2 <= lq[2] + (lq[1] <<< 1) + lq[0];
            s2v <= 1;
        end
    end

    // ---- 3. the droop equalizer: y = 4 v[m-1] + 9 (2 v[m-1] - v[m] - v[m-2]) / 32 --------
    // [1 2 1] is 0.93 at the edge of the band (1.05 MHz); this lifts it back to 1.00.
    logic signed [15:0] vi [0:2], vq [0:2];
    logic signed [17:0] dv_i, dv_q;             // 2 v[m-1] - v[m] - v[m-2]
    logic               s3 = 0, dec_strobe = 0;
    logic signed [16:0] eq_i = 0, eq_q = 0;
    initial for (int i = 0; i < 3; i++) begin vi[i] = 0; vq[i] = 0; end
    assign dv_i = (vi[1] <<< 1) - vi[0] - vi[2];
    assign dv_q = (vq[1] <<< 1) - vq[0] - vq[2];
    always_ff @(posedge clk) begin
        s3 <= s2v;
        dec_strobe <= 0;
        if (s2v) begin
            vi[0] <= i2; vi[1] <= vi[0]; vi[2] <= vi[1];
            vq[0] <= q2; vq[1] <= vq[0]; vq[2] <= vq[1];
        end
        if (s3) begin
            eq_i <= (vi[1] <<< 2) + (((dv_i <<< 3) + dv_i) >>> 5);
            eq_q <= (vq[1] <<< 2) + (((dv_q <<< 3) + dv_q) >>> 5);
            dec_strobe <= 1;
        end
    end

    // ---- 4. the matched filter: 49 taps, 8 clocks per sample --------------------------------
    // The taps are symmetric, so pair sample i with sample 48 - i: 24 pairs and the
    // middle one.  Multiplier m (0..3) does pairs 7m .. 7m + 6, one per clock, in
    // clocks sc = 0..6 of the 8 between samples (pairs 25..27 have a zero tap).
    // The root-raised-cosine pulse, as psk.py's rrc(): with a = 0.35 and t in symbols,
    //   rrc(t) = [sin(pi t (1 - a)) + 4 a t cos(pi t (1 + a))] / [pi t (1 - (4 a t)^2)],
    // and 1 - a + 4a/pi at t = 0.  Here t = (i - 24) / 4, i = 0..24 (the taps are symmetric).
    logic signed [9:0] mfc [0:31];             // 256 x rrc(k / 4), k = -24 .. 0 (then zeros)
    initial for (int i = 0; i < 32; i++)
        mfc[i] = (i == 24) ? $rtoi($floor(256.0 * (0.65 + 1.4 / 3.141592653589793) + 0.5))
               : (i > 24)  ? 10'sd0
               : $rtoi($floor(256.0 * ($sin(3.141592653589793 * ((i - 24) / 4.0) * 0.65)
                                       + 1.4 * ((i - 24) / 4.0) * $cos(3.141592653589793 * ((i - 24) / 4.0) * 1.35))
                              / (3.141592653589793 * ((i - 24) / 4.0) * (1.0 - 1.96 * ((i - 24) / 4.0) * ((i - 24) / 4.0)))
                              + 0.5));
    logic [48:0][16:0]  di, dq;                 // the last 49 samples (packed: registers)
    logic [2:0]         sc = 0;                 // the clock within the sample, 0..7
    logic signed [16:0] ai [0:3], bi [0:3], aq [0:3], bq [0:3];
    logic signed [9:0]  c1 [0:3], c2 [0:3];
    logic signed [17:0] pi_ [0:3], pq_ [0:3];
    logic signed [27:0] mi [0:3], mq [0:3];
    logic signed [31:0] acc_i [0:3], acc_q [0:3];
    logic signed [15:0] mf_i = 0, mf_q = 0;     // the output: / 2^13
    logic               mf_valid;
    initial begin
        di = 0; dq = 0;
        for (int m = 0; m < 4; m++) begin
            ai[m] = 0; bi[m] = 0; aq[m] = 0; bq[m] = 0; c1[m] = 0; c2[m] = 0;
            pi_[m] = 0; pq_[m] = 0; mi[m] = 0; mq[m] = 0; acc_i[m] = 0; acc_q[m] = 0;
        end
    end
    assign mf_valid = (sc == 3);
    always_ff @(posedge clk) begin
        sc <= dec_strobe ? 3'd0 : sc + 1;
        if (dec_strobe) begin
            di <= {di[47:0], 17'(eq_i)};
            dq <= {dq[47:0], 17'(eq_q)};
        end
        for (int m = 0; m < 4; m++) begin
            // sc: pick the pair.  (With sc = 7 the pair is 7m + 7: a zero tap, and its
            // product is the one that lands at sc = 2, which isn't accumulated.)  Written
            // out for each sc so that every index is a constant: an 8-way choice, not a
            // shifter across the whole delay line.
            for (int s = 0; s < 8; s++)
                if (sc == s) begin
                    ai[m] <= $signed(di[7 * m + s]);
                    aq[m] <= $signed(dq[7 * m + s]);
                    bi[m] <= (7 * m + s == 24) ? 17'sd0 : $signed(di[48 - 7 * m - s]);
                    bq[m] <= (7 * m + s == 24) ? 17'sd0 : $signed(dq[48 - 7 * m - s]);
                    c1[m] <= mfc[7 * m + s];
                end
            // sc + 1: add the pair
            pi_[m] <= ai[m] + bi[m];
            pq_[m] <= aq[m] + bq[m];
            c2[m]  <= c1[m];
            // ##################################################################
            // ##  KEY LINE (sc + 2): multiply the pair's sum by its tap.
            // ##################################################################
            mi[m] <= pi_[m] * c2[m];
            mq[m] <= pq_[m] * c2[m];
            // sc + 3: accumulate: the first product starts the sum, the last lands at sc = 1
            if (sc == 3) begin
                acc_i[m] <= 32'(mi[m]);
                acc_q[m] <= 32'(mq[m]);
            end else if (sc != 2) begin
                acc_i[m] <= acc_i[m] + mi[m];
                acc_q[m] <= acc_q[m] + mq[m];
            end
        end
        if (sc == 2) begin                      // all four sums are in
            mf_i <= 16'((acc_i[0] + acc_i[1] + acc_i[2] + acc_i[3]) >>> 13);
            mf_q <= 16'((acc_q[0] + acc_q[1] + acc_q[2] + acc_q[3]) >>> 13);
        end
    end

    // ---- 5. the timing loop ---------------------------------------------------------------
    // tau counts down to the next symbol centre, in samples (16 bits below the sample).
    // At the end of each sample's 8 clocks: if tau < 1, the centre falls before the
    // next sample: a symbol strobe, mu = tau, and tau gets a period less the loop's
    // correction.  Half a period before, the same test gives a "mid" strobe.  The
    // interpolator works two samples behind (it needs the sample after the one it is
    // interpolating past), so the strobes and their mu are kept for two samples.
    logic signed [15:0] y_i [0:3], y_q [0:3];   // the matched filter's last 4 outputs
    logic [1:0]         n_dec = 0;              // decimated samples so far (saturating at 2)
    logic               live = 0;               // the matched filter has delivered its first sample
    logic signed [23:0] tau = 2 * 24'd65536;
    logic signed [39:0] integ = 0;              // the integral: the period, in 1/2^24 sample
    logic signed [15:0] prop = 0;               // the last symbol's proportional term
    logic signed [23:0] period, half;
    logic signed [15:0] integ8;
    logic               sym_f [0:2], mid_f [0:2];   // strobes for samples k, k-1, k-2 ...
    logic [15:0]        mu_f [0:2];                 // ... and their mu
    initial for (int i = 0; i < 4; i++) begin y_i[i] = 0; y_q[i] = 0; end
    initial for (int i = 0; i < 3; i++) begin sym_f[i] = 0; mid_f[i] = 0; mu_f[i] = 0; end
    assign integ8 = (integ >>> 8 > 32767) ? 16'sd32767 : (integ >>> 8 < -32768) ? -16'sd32768 : 16'(integ >>> 8);
    assign period = PNOM - integ8;
    assign half   = tau - (period >>> 1);
    always_ff @(posedge clk) begin
        if (dec_strobe && n_dec != 2) n_dec <= n_dec + 1;
        if (mf_valid) begin                     // a new sample
            y_i[0] <= mf_i; y_i[1] <= y_i[0]; y_i[2] <= y_i[1]; y_i[3] <= y_i[2];
            y_q[0] <= mf_q; y_q[1] <= y_q[0]; y_q[2] <= y_q[1]; y_q[3] <= y_q[2];
            if (n_dec == 2) live <= 1;          // (from the second one: the filter's latency)
        end
        if (sc == 7 && live) begin              // the NCO decides, last thing in the sample
            sym_f[1] <= sym_f[0]; sym_f[2] <= sym_f[1];
            mid_f[1] <= mid_f[0]; mid_f[2] <= mid_f[1];
            mu_f[1]  <= mu_f[0];  mu_f[2]  <= mu_f[1];
            if (tau < ONE) begin
                // ##############################################################
                // ##  KEY LINE: a symbol centre falls before the next sample.
                // ##  The next one is a period on, less the loop's correction
                // ##  (psk.py's  t += sps - (k1 e + integ)).
                // ##############################################################
                sym_f[0] <= 1; mid_f[0] <= 0; mu_f[0] <= tau[15:0];
                tau <= tau + period - prop - ONE;
            end else begin
                sym_f[0] <= 0; mid_f[0] <= (half >= 0 && half < ONE); mu_f[0] <= half[15:0];
                tau <= tau - ONE;
            end
        end
    end

    // The interpolator, for the sample before last (y_i[2]), with its mu: Catmull-Rom's
    // cubic, c1 = (y1 - ym1)/2, c2 = (2 ym1 - 5 y0 + 4 y1 - y2)/2, c3 = (-ym1 + 3 y0 -
    // 3 y1 + y2)/2, then y0 + mu (c1 + mu (c2 + mu c3)) by Horner: 3 multiplies each.
    logic [11:0]        mu_i = 0;               // mu, 12 bits, for this interpolation
    logic signed [17:0] ci1 = 0, ci2 = 0, ci3 = 0, cq1 = 0, cq2 = 0, cq3 = 0;
    logic signed [30:0] pri = 0, prq = 0;       // mu times something
    logic signed [17:0] ti1 = 0, ti2 = 0, tq1 = 0, tq2 = 0, yi_i = 0, yi_q = 0;
    logic signed [15:0] y0i = 0, y0q = 0;
    always_ff @(posedge clk) begin
        case (sc)
            4: begin
                mu_i <= mu_f[1][15:4];
                y0i  <= y_i[2];                                  y0q <= y_q[2];
                ci1  <= (y_i[1] - y_i[3]) >>> 1;                 cq1 <= (y_q[1] - y_q[3]) >>> 1;
                ci2  <= ((y_i[3] <<< 1) - (y_i[2] <<< 2) - y_i[2] + (y_i[1] <<< 2) - y_i[0]) >>> 1;
                cq2  <= ((y_q[3] <<< 1) - (y_q[2] <<< 2) - y_q[2] + (y_q[1] <<< 2) - y_q[0]) >>> 1;
                ci3  <= (-y_i[3] + (y_i[2] <<< 1) + y_i[2] - (y_i[1] <<< 1) - y_i[1] + y_i[0]) >>> 1;
                cq3  <= (-y_q[3] + (y_q[2] <<< 1) + y_q[2] - (y_q[1] <<< 1) - y_q[1] + y_q[0]) >>> 1;
            end
            5: begin pri <= $signed({1'b0, mu_i}) * ci3;  prq <= $signed({1'b0, mu_i}) * cq3;  end
            6: begin ti1 <= ci2 + (pri >>> 12);           tq1 <= cq2 + (prq >>> 12);           end
            7: begin pri <= $signed({1'b0, mu_i}) * ti1;  prq <= $signed({1'b0, mu_i}) * tq1;  end
            0: begin ti2 <= ci1 + (pri >>> 12);           tq2 <= cq1 + (prq >>> 12);           end
            1: begin pri <= $signed({1'b0, mu_i}) * ti2;  prq <= $signed({1'b0, mu_i}) * tq2;  end
            // ##################################################################
            // ##  KEY LINE: the signal between two samples, mu of the way.
            // ##################################################################
            2: begin yi_i <= y0i + (pri >>> 12);          yi_q <= y0q + (prq >>> 12);          end
            default: ;
        endcase
    end

    // ---- 5 and 6, once per symbol: Gardner, then the Costas loop, then the bits ------------
    // At sc = 3 the interpolated value of the sample before that is in (yi_i, yi_q);
    // the strobes of that sample say whether it's a symbol centre or the half-way point.
    // `go` carries "a symbol" down the pipeline, one clock per stage.
    logic signed [11:0] sine [0:1023];          // 2047 sin(2 pi i / 1024)
    initial for (int i = 0; i < 1024; i++)
        sine[i] = $rtoi($floor(2047.0 * $sin(6.283185307179586 * i / 1024) + 0.5));
    logic [7:0]         go = 0;
    logic signed [16:0] now_i = 0, now_q = 0, mid_i = 0, mid_q = 0, prev_i = 0, prev_q = 0;
    logic [11:0]        mu = 0;                 // the symbol's mu (for looking at)
    logic signed [34:0] g_i = 0, g_q = 0;
    logic signed [35:0] e_g = 0;
    logic [23:0]        phi = 0;                // the carrier phase estimate: 2^24 per turn
    logic signed [31:0] freq = 0;               // ... and its frequency, per symbol
    logic signed [11:0] cos_r = 0, sin_r = 0;
    logic signed [28:0] pic = 0, pqs = 0, pqc = 0, pis = 0;
    logic signed [18:0] zr_i = 0, zr_q = 0;     // the symbol, turned back by phi
    logic [1:0]         q_now = 0, q_prev = 0;
    logic signed [19:0] e_c = 0;
    logic signed [35:0] eg7, eg5;
    assign eg7 = e_g >>> S1_T;
    assign eg5 = e_g >>> S2_T;
    always_ff @(posedge clk) begin
        go <= {go[6:0], 1'b0};
        if (sc == 3) begin
            if (mid_f[2]) begin mid_i <= yi_i >>> 1; mid_q <= yi_q >>> 1; end
            if (sym_f[2]) begin now_i <= yi_i >>> 1; now_q <= yi_q >>> 1; mu <= mu_f[2][15:4]; go[0] <= 1; end
        end
        if (go[0]) begin                        // sc = 4
            // ##################################################################
            // ##  KEY LINE: Gardner's detector, Re(y_mid* (y_now - y_prev)).
            // ##################################################################
            g_i <= mid_i * (now_i - prev_i);
            g_q <= mid_q * (now_q - prev_q);
            prev_i <= now_i; prev_q <= now_q;
            cos_r <= sine[phi[23:14] + 10'd256];
            sin_r <= sine[phi[23:14]];
        end
        if (go[1]) begin                        // sc = 5
            e_g <= g_i + g_q;
            pic <= now_i * cos_r;  pqs <= now_q * sin_r;
            pqc <= now_q * cos_r;  pis <= now_i * sin_r;
        end
        if (go[2]) begin                        // sc = 6: the loop filter, in time for the NCO
            // ##################################################################
            // ##  KEY LINES: the PI loop filter, its gains shifts.  (Saturated,
            // ##  so that junk at the ADC can't send tau anywhere silly.)
            // ##################################################################
            prop  <= (eg7 > 32767) ? 16'sd32767 : (eg7 < -32768) ? -16'sd32768 : 16'(eg7);
            integ <= integ + ((eg5 > 1048575) ? 40'sd1048575 : (eg5 < -1048576) ? -40'sd1048576 : 40'(eg5));
            // ##################################################################
            // ##  KEY LINE: the Costas loop turns the symbol back by -phi.
            // ##################################################################
            zr_i <= (pic + pqs) >>> 11;
            zr_q <= (pqc - pis) >>> 11;
        end
        if (go[3]) begin                        // sc = 7: the decision, and the phase detector
            q_now <= (zr_i >= 0 && zr_q >= 0) ? 2'd0 : (zr_i < 0 && zr_q >= 0) ? 2'd1 : (zr_i < 0) ? 2'd2 : 2'd3;
            // ##################################################################
            // ##  KEY LINE: Im(z d*) for the nearest point d: +-Q -+ I.
            // ##################################################################
            e_c <= (zr_i >= 0 ? zr_q : -zr_q) - (zr_q >= 0 ? zr_i : -zr_i);
        end
        if (go[4]) begin                        // sc = 0: the carrier loop filter
            // ##################################################################
            // ##  KEY LINES: freq integrates e (it learns the carrier offset),
            // ##  phi integrates freq + k1 e.
            // ##################################################################
            freq <= freq + (e_c <<< S2_C);
            phi  <= phi + 24'(freq + (e_c <<< S2_C)) + 24'(e_c <<< S1_C);
        end
    end

    // ---- 7. differential decoding, frames, and the bytes out ---------------------------------
    logic [15:0] fr = 0;                        // the last 16 bits received
    logic [3:0]  cnt = 0;                       // symbols since the frame (or the sync) began
    logic [1:0]  hits = 0;                      // syncs in a row, 8 symbols apart
    logic [3:0]  misses = 0;                    // frames in a row without their sync
    logic        locked = 0;
    logic        hit;
    logic [1:0]  dq_rx;
    logic [7:0]  fifo [0:(1 << FIFO_BITS) - 1]; // bytes waiting for the serial port
    logic [FIFO_BITS:0] wr = 0, rd = 0;
    logic        fifo_full;
    logic        sym_done = 0;                  // the symbol's state is final (for the testbench)
    assign dq_rx = q_now - q_prev;
    assign hit   = (fr[15:9] == SYNC);
    assign fifo_full = (wr - rd) == (1 << FIFO_BITS);
    always_ff @(posedge clk) begin
        sym_done <= 0;
        if (go[4]) begin                        // sc = 0
            // ##################################################################
            // ##  KEY LINE: differential decoding: the turn since the last symbol
            // ##  is the 2 bits.  Any fixed turn of the whole constellation cancels.
            // ##################################################################
            fr     <= {fr[13:0], gray(dq_rx)};
            q_prev <= q_now;
        end
        if (go[5]) begin                        // sc = 1: frame sync
            if (locked) begin
                if (cnt == 7) begin             // a whole frame is in
                    misses <= hit ? 4'd0 : misses + 1;
                    if (!hit && misses == 7) locked <= 0;
                    else if (fr[8] && !fifo_full) begin fifo[wr[FIFO_BITS-1:0]] <= fr[7:0]; wr <= wr + 1; end
                    cnt <= 0;
                end else
                    cnt <= cnt + 1;
            end else if (hit) begin
                hits <= (cnt == 7) ? hits + 1 : 2'd1;
                cnt  <= 0;
                if (cnt == 7 && hits == 2) begin    // the third, 8 symbols apart: locked
                    locked <= 1;
                    misses <= 0;
                    if (fr[8] && !fifo_full) begin fifo[wr[FIFO_BITS-1:0]] <= fr[7:0]; wr <= wr + 1; end
                end
            end else if (cnt != 8)
                cnt <= cnt + 1;
        end
        if (go[6]) sym_done <= 1;               // sc = 2
    end

    // ---- the way out: a serial transmitter that never pauses ---------------------------------
    // The laptop's bytes arrive 10 us apart and nothing here can ask it to wait, so they
    // must leave at least as fast as they come: no gap between one byte's stop bit and the
    // next one's start bit, and 2 % fast, 49 clocks per bit instead of 50 (a UART re-times
    // every byte from its start bit, so the laptop's doesn't mind).  uart.sv's transmitter
    // rests 2 clocks between bytes, 502 against the 500 coming in: the FIFO filled in 8000
    // bytes and then lost one in 251.  (Measured on the board, then in qpsk_modem_tb.sv.)
    localparam integer TX_CLKS_PER_BIT = 49;
    logic [9:0] tx_frame = 10'h3ff;             // {stop, data, start}; bit 0 is on the wire
    logic [3:0] tx_bits  = 0;                   // bits left to send; 0 = idle
    logic [5:0] tx_timer = 0;
    logic       tx_load  = 0;                   // high for one clock: a byte left the FIFO
    assign uart_tx = tx_frame[0];
    always_ff @(posedge clk) begin
        tx_load <= 0;
        if (tx_bits == 0) begin                                 // idle: anything waiting?
            if (wr != rd) begin
                tx_frame <= {1'b1, fifo[rd[FIFO_BITS-1:0]], 1'b0};
                rd <= rd + 1; tx_bits <= 10; tx_timer <= 0; tx_load <= 1;
            end
        end else if (tx_timer != TX_CLKS_PER_BIT - 1)
            tx_timer <= tx_timer + 1;
        else begin                                              // this bit's time is up
            tx_timer <= 0;
            // ##################################################################
            // ##  KEY LINE: the stop bit is over and a byte is waiting: its start
            // ##  bit goes out in the very next clock.
            // ##################################################################
            if (tx_bits == 1 && wr != rd) begin
                tx_frame <= {1'b1, fifo[rd[FIFO_BITS-1:0]], 1'b0};
                rd <= rd + 1; tx_bits <= 10; tx_load <= 1;
            end else begin
                tx_frame <= {1'b1, tx_frame[9:1]};
                tx_bits  <= tx_bits - 1;
            end
        end
    end

    // ---- LEDs: lock; a byte received; a byte typed; the ADC clipping ----------------------
    logic [23:0] rx_led = 0, tx_led = 0, clip_led = 0;   // each stays lit 0.3 s
    always_ff @(posedge clk) begin
        rx_led   <= (tx_load) ? 24'hffffff : (rx_led != 0 ? rx_led - 1 : 24'd0);
        tx_led   <= (rx_valid) ? 24'hffffff : (tx_led != 0 ? tx_led - 1 : 24'd0);
        clip_led <= (new_sample && (adc_d == 0 || adc_d == 255)) ? 24'hffffff : (clip_led != 0 ? clip_led - 1 : 24'd0);
    end
    assign led = {locked, rx_led != 0, tx_led != 0, clip_led != 0, 1'b0};
endmodule


// One symbol's pulse table for the transmitter: 384 x rrc((J - 6) + p/32), p = 0..31,
// read a clock after p is given: the same formula as the matched filter's taps, at
// t = (J - 6) + p/32.  (13 small tables, rather than one big one with 13 read ports.)
module rrc_rom #(
    parameter integer J = 6
) (
    input  logic              clk,
    input  logic [4:0]        p,
    output logic signed [9:0] v = 0
);
    logic signed [9:0] rom [0:31];
    initial for (int i = 0; i < 32; i++)
        rom[i] = (J == 6 && i == 0) ? $rtoi($floor(384.0 * (0.65 + 1.4 / 3.141592653589793) + 0.5))
               : $rtoi($floor(384.0 * ($sin(3.141592653589793 * ((J - 6) + i / 32.0) * 0.65)
                                       + 1.4 * ((J - 6) + i / 32.0) * $cos(3.141592653589793 * ((J - 6) + i / 32.0) * 1.35))
                              / (3.141592653589793 * ((J - 6) + i / 32.0) * (1.0 - 1.96 * ((J - 6) + i / 32.0) * ((J - 6) + i / 32.0)))
                              + 0.5));
    always_ff @(posedge clk) v <= rom[p];
endmodule
```

</details>

## The transmitter

One DAC sample per 50 MHz clock, 32 per symbol, 1.5625 Msymbol/s, as
`psk.py` sends it. Four ideas make it small.

- **Frames.** Sixteen bits make a frame of eight symbols: Barker's 7-bit
  sync word 1110010, a "valid" bit, and the byte from the serial port, or
  eight bits of a shift register when there is none. That is 195,312 frames
  a second, more than a 1 Mbaud serial port can fill, so a byte never
  waits for more than one frame and nothing queues. The filler bits matter:
  the loops need transitions to lock to, and an idle line of all ones
  would starve them.
- **Differential QPSK.** Each pair of bits is Gray-coded and sent as a
  *change* of phase: 00, 01, 11, 10 turn the carrier by 0°, 90°, 180°, 270°
  from the previous symbol. The receiver's [Costas loop](https://en.wikipedia.org/wiki/Costas_loop) can lock a quarter
  turn off ([6.02](6_02_psk_and_qpsk.md#602-psk-and-qpsk-finding-the-clock-and-the-carrier)),
  and in a difference of two phases a constant offset cancels, so no
  unique word is needed to find which way is up. The price is the
  2*p*(1 − *p*) of [6.02](6_02_psk_and_qpsk.md#602-psk-and-qpsk-finding-the-clock-and-the-carrier):
  twice the errors at high SNR, which costs 0.3 dB at 10<sup>−5</sup>, and
  almost nothing extra where *p* is already large.
- **A pulse shaper with no multipliers.** The symbols are ±1 ± *j*, so the
  root-raised-cosine pulse, cut at six symbols each side, is thirteen
  overlapping pulses at any instant, each *added or subtracted*. Thirteen
  small tables (32 phases each) and two adder trees, one for I and one for
  Q. The table is 384 times the pulse, so the DAC swings 48 codes rms (the
  same as `psk.py`'s waveform) and 108 at the very worst, when all
  thirteen line up: it cannot clip.
- **The carrier at *f*<sub>s</sub>/8.** At 6.25 MHz cos and sin of the
  carrier take only the values 0, ±1 and ±0.707, so *I* cos − *Q* sin is
  one of *I*, 0.707(*I* − *Q*), −*Q*, 0.707(−*I* − *Q*), and so on round
  the eight phases, and 0.707 = 181/256 is a shift and an add. The choice
  of 6.25 MHz back in [6.00](6_00_digital_communications.md#600-digital-communications-hardware-defined-radio)
  was made for this page.

```console
$ cd src/twoboard
$ make load-qpsk_modem                   # one board, DAC OUT cabled to ADC IN
$ screen /dev/ttyUSB0 1000000            # type; each character comes back 30 µs later
```

## The receiver

The receiver gets an ADC sample every two clocks, and from the decimator
on, eight clocks per sample and thirty-two per symbol. Those eight clocks
are the budget everything below is spent from.

**The mixer, and the holes.** Mixing down by 6.25 MHz = *f*<sub>s</sub>/4 is
multiplication by 1, −*j*, −1, *j*: free. But look at what it leaves. The
even samples carry only *I* and the odd ones only *Q*, with a hole in each
where the other should be. The first version of this receiver summed four
samples and kept one in four, which "fills" the holes by averaging, and
nothing downstream, not even in floating point, could get past 27 dB of
MER. Two things are wrong with the sum. It centres *I* at one sample and
*Q* at the next, a skew of a sixteenth of a symbol between the two axes.
And it rejects the image at twice the carrier, 12.5 MHz ± 1 MHz, by only
18 dB before the decimation folds it onto the signal. `psk.py`'s 193-tap
filter interpolates the holes properly; that is why it reads 39 dB. The
fix is the classic one for *f*<sub>s</sub>/4: a *half-band* filter, [−1 0 9 16 9
0 −1]/32, which passes the even samples through untouched (its even taps are
0, 16, 0) and interpolates *Q* at each even sample from its four odd
neighbours: two adds and a ×9, 60 dB of image rejection. Keep the even
samples: 12.5 MS/s. Then [1 2 1] and keep one in two: 6.25 MS/s, four
samples per symbol. [1 2 1] droops to 0.93 at the band edge; a three-tap
filter with a coefficient of 9/128 (shifts) lifts it back, and is worth
about 5 dB of MER.

**The matched filter.** The same root-raised cosine, 49 taps at four
samples per symbol, integer taps of 256 times the pulse. It is symmetric,
so 24 pairs of taps and the middle one: 25 multiplies per axis per sample.
Four multipliers for *I* and four for *Q*, each doing seven pairs in seven of
the eight clocks: the work of 98 multiply-accumulates per sample, done as
50 multiplies by symmetry on eight multipliers.
Its output, divided by 2<sup>13</sup>, fits 16 bits: a symbol is about 1190 per axis
with the cable's 0.776, and the worst adversarial input reaches 7900.

**The timing loop, in integers.** A counter `tau`, with 16 bits below the
sample, says how far away the next symbol centre is, and loses one sample
per sample. When it drops below one, the centre falls before the next
sample: a *strobe*, the fraction `mu = tau`, and `tau += period − prop − 1`,
which is `psk.py`'s `t += sps − (k1·e + integ)`. Half a period earlier
the same test gives a *mid* strobe with its own `mu`, for Gardner's
half-way sample. The interpolator works two samples behind, because it
needs the sample after the one it interpolates past, and uses the `mu`
decided for that sample. It is Catmull-Rom's cubic (Keys's kernel with
*a* = −½), whose coefficients are all halves: three multiplies by `mu` per
axis, Horner's way. Gardner's *e* = Re(*y*<sub>mid</sub> (*y*<sub>now</sub> −
*y*<sub>prev</sub>)\*) is two multiplies.

<details>
<summary><b>Detail:</b> why a cubic interpolator, measured</summary>

At four samples per symbol the band edge is at 0.17 of the sample rate,
which is where cheap interpolators fail. Measured on the model's receiver
in isolation, over a sweep of channel delays: the piecewise-parabolic
interpolator (taps [−1 5 5 −1]/8) loses 13 dB of MER when the symbol
centre falls half-way between samples, because its response peaks by
0.7 dB at the band edge; cubic Lagrange loses nothing; Catmull-Rom loses
nothing in integers; a 32-phase polyphase matched filter, with no
interpolator at all, loses nothing and costs eight times the table. The
cubic is the cheapest one that does not care where the centre falls.

</details>

**The Costas loop, in integers.** The phase `phi` has 24 bits per turn. A
1024-entry table of 2047 sin, in one block RAM with two read ports, gives
cos and sin; rotating the symbol is four multiplies. The nearest of the
four points is just the quadrant, and Im(*z* *d*\*) for *d* = ±1 ± *j* is ±*Q*
∓ *I*: no multiplies. Then the quadrant minus the previous quadrant,
un-Grayed, is the two bits; a 16-bit shift register; the sync word in the
right place three times running (24 symbols) is *locked*; eight frames
without it unlocks; while locked, every frame with the valid bit set drops
its byte into a FIFO for the serial port.

## How the loop gains became shifts

`psk.py` set its loops by bandwidth and damping ([6.02](6_02_psk_and_qpsk.md#602-psk-and-qpsk-finding-the-clock-and-the-carrier)'s
Detail): *B*<sub>n</sub>*T* = 0.010 and ζ = 0.71 for timing, 0.020 and 0.71 for
the carrier. In the FPGA the gains are shifts, so the question runs the
other way: *which* shifts give those loops? The detectors' gains have to
be measured first, because in integers they are whatever the integers
make them. `modem_fpga_model.py --gains` does that on the model and
inverts [6.02](6_02_psk_and_qpsk.md#602-psk-and-qpsk-finding-the-clock-and-the-carrier)'s
formulas:

<details>
<summary>The whole file: <code>modem_fpga_model.py</code></summary>

<!-- file: src/comms/modem_fpga_model.py -->
```python
#!/usr/bin/env python3
"""qpsk_modem.sv in Python, integer for integer: the DQPSK modem that runs inside the FPGA.

    python3 modem_fpga_model.py --sim                 # 300 random bytes through the model,
                                                      #   channel.py's cable, loops' states
    python3 modem_fpga_model.py --sim --ppm 2000      # the transmitter's crystal 2000 ppm fast:
                                                      #   carrier +12.5 kHz, symbols +2000 ppm
    python3 modem_fpga_model.py --sim --ppm 2000 --cfo -9500   # ... and the carrier moved back
    python3 modem_fpga_model.py --sim --gains         # ...and the loops' bandwidths and damping
    python3 modem_fpga_model.py --sim --plot

Everything psk.py does in floating point, done again with integers and shifts, exactly as
the Verilog does it: the same tables, the same widths, the same rounding (every shift
rounds towards minus infinity, as Verilog's >>> does).  qpsk_modem_check.py runs the
Verilog on the same samples and checks that the two agree bit for bit.

TRANSMITTER (one DAC sample per 50 MHz clock)
  frame    16 bits = 8 symbols: a 7-bit sync word (Barker's 1110010), a "valid" bit, and
           the byte from the serial port, or 8 bits of a shift register when there's none.
           195,312 frames a second, more than a 1 Mbaud serial port can supply.
  symbols  2 bits each, Gray-coded, as a CHANGE of phase (differential QPSK): 00, 01, 11,
           10 turn the carrier by 0, 90, 180, 270 degrees from the previous symbol.
  pulses   root-raised-cosine, roll-off 0.35, 32 DAC samples per symbol (1.5625 Msymbol/s),
           cut off 6 symbols each side.  The symbols are +-1 +-j, so the pulse shaper is
           13 table look-ups and an adder tree: no multipliers.
  carrier  6.25 MHz = 50 MS/s / 8: cos and sin take the values 0, +-1 and +-0.707, so I on
           cos minus Q on sin is a choice of I, Q, or 0.707 (I +- Q), and 0.707 = 181/256.

RECEIVER (an ADC sample every 2 clocks; everything after the decimator has 8 clocks per sample)
  1. mix down by 6.25 MHz = 25 MS/s / 4: multiply by 1, -j, -1, j (free).  That leaves
     I on the even samples and Q on the odd ones, each with a hole between;
  2. a half-band filter, [-1 0 9 16 9 0 -1] / 32, fills Q's holes at the even samples
     (I's own samples pass through it untouched) and keeps the even ones: 12.5 MS/s.
     Then [1 2 1] and keep 1 in 2: 6.25 MS/s, 4 samples per symbol;
  3. a 3-tap filter (shifts only) that undoes [1 2 1]'s droop across the band;
  4. the matched filter: the same root-raised-cosine, 49 taps, symmetric, so 25 multiplies
     per I and Q, shared between 4 multipliers each over 7 of the 8 clocks;
  5. the timing loop: a counter (the "NCO") says when the next symbol centre falls between
     two samples, and a cubic interpolator (Catmull-Rom's, whose coefficients are halves:
     3 multiplies per axis) computes the signal there and half a symbol earlier.  Gardner's detector
     and a PI loop filter whose gains are shifts;
  6. the Costas loop: turn each symbol by the phase so far (a 1024-entry sine table, 4
     multiplies), find the nearest of the four points, Im(z d*) is +-Q -+ I: no multiplies;
     a PI loop filter with shift gains learns the carrier's frequency;
  7. the symbol's quadrant minus the previous one's is the 2 bits (differential decoding:
     the loop's 90-degree ambiguity cancels out); 8 of those make a frame; a sync word in
     the right place three times running means "locked", and the byte goes to the serial port.
"""
import argparse
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import channel                                              # noqa: E402
import psk                                                  # noqa: E402

F_CLK, FS_DAC, FS_ADC = 50e6, 50e6, 25e6
SPS_DAC, SPS_ADC, SPS = 32, 16, 4        # DAC samples, ADC samples, decimated samples per symbol
R_SYM = FS_DAC / SPS_DAC                 # 1.5625 Msymbol/s
ALPHA = 0.35
SPAN = 6                                 # pulses cut off this many symbols each side
TX_SCALE = 48 * 8                        # pulse table = 384 x rrc: 48 DAC codes per unit symbol, x 8
MF_SCALE = 256                           # matched-filter taps = 256 x rrc
MF_SHIFT = 13                            # matched-filter output = sum of products / 2^13
SYNC = 0b1110010                         # Barker 7
NSYM_FRAME = 8
GRAY = [0b00, 0b01, 0b11, 0b10]          # turn dq (0..3 quarter turns) -> the 2 bits it carries
GRAY_INV = [0, 1, 3, 2]                  # the 2 bits -> dq
ONE = 1 << 16                            # one sample, in the timing NCO's units
PNOM = SPS * ONE                         # 4 samples per symbol
# the loop filters' gains, as shifts (see loop_report())
S1_T, S2_T = 7, 5                        # timing: tau -= e >> S1_T;  integ += e >> S2_T  (integ / 2^8 per sample)
S1_C, S2_C = 7, 2                        # carrier: phi += e << S1_C;  freq += e << S2_C   (phi: 2^24 per turn)

# ---- the tables, as the Verilog's `initial` blocks compute them -------------------
def rrc_table(t):
    """round(rrc(t)) is not what Verilog does: it computes the formula in double precision
    and $rtoi($floor(x + 0.5)); so does this."""
    return np.floor(psk.rrc(t) + 0.5)

PULSE = np.array([[int(np.floor(TX_SCALE * psk.rrc((j - SPAN) + p / SPS_DAC) + 0.5))
                   for p in range(SPS_DAC)] for j in range(2 * SPAN + 1)], np.int64)    # [13][32]
MF = np.array([int(np.floor(MF_SCALE * psk.rrc(k / SPS) + 0.5))
               for k in range(-SPAN * SPS, SPAN * SPS + 1)], np.int64)                  # 49 taps
SINE = np.array([int(np.floor(2047.0 * np.sin(2 * np.pi * i / 1024) + 0.5)) for i in range(1024)], np.int64)


# ---- transmitter ------------------------------------------------------------------
def lfsr_step(s):
    """The idle filler: x^16 + x^14 + x^13 + x^11 + 1, one step (the Verilog steps it once per symbol)."""
    return ((s << 1) & 0xFFFF) | (((s >> 15) ^ (s >> 13) ^ (s >> 12) ^ (s >> 10)) & 1)


def frames_for(data, gap=1, lead=40, trail=40):
    """Frame words for the bytes `data`, one byte every `gap` + 1 frames (a 1 Mbaud serial
    port delivers a byte every 500 clocks, a frame takes 256), with idle frames before (40 =
    200 us: the loops' settling time) and after.  Returns (16-bit words, the frame number of
    each byte)."""
    words, where, s = [], [], 0xACE1
    def idle():
        nonlocal s
        for _ in range(NSYM_FRAME):
            s = lfsr_step(s)
        return (SYNC << 9) | (s & 0xFF)
    for _ in range(lead):
        words.append(idle())
    for b in data:
        where.append(len(words))
        words.append((SYNC << 9) | 0x100 | int(b))
        for _ in range(gap):
            words.append(idle())
    for _ in range(trail):
        words.append(idle())
    return np.array(words, np.int64), np.array(where)


def tx_symbols(words, q0=0):
    """Frame words -> the symbol number q (0..3: 45, 135, 225, 315 degrees) of each symbol."""
    q, out = q0, []
    for w in words:
        for i in range(NSYM_FRAME):
            dibit = (int(w) >> (14 - 2 * i)) & 3
            # ##################################################################
            # ##  KEY LINE: differential coding.  The bits say how far to turn.
            # ##################################################################
            q = (q + GRAY_INV[dibit]) & 3
            out.append(q)
    return np.array(out, np.int64)


def signs(q):
    """The symbol +-1 +-j for q: (sign of I, sign of Q)."""
    q = np.asarray(q)
    return np.where((q == 0) | (q == 3), 1, -1), np.where(q <= 1, 1, -1)


def tx_dac(q):
    """The DAC codes (32 per symbol) for the symbols q, exactly as the FPGA makes them.  The
    FPGA's symbol register starts full of q = 0 (+1 +j), so 6 of those are put in front."""
    q = np.concatenate([np.zeros(SPAN, np.int64), q, np.zeros(SPAN, np.int64)])
    si, sq = signs(q)
    nsym = len(q) - 2 * SPAN                           # DAC samples for these symbols
    m = np.arange(nsym)
    I = np.zeros((nsym, SPS_DAC), np.int64)
    Q = np.zeros((nsym, SPS_DAC), np.int64)
    for j in range(2 * SPAN + 1):
        # ######################################################################
        # ##  KEY LINE: the pulse shaper.  13 symbols overlap at any instant; each
        # ##  adds or subtracts its pulse's table value at this phase of the symbol.
        # ######################################################################
        I += si[m + 2 * SPAN - j][:, None] * PULSE[j][None, :]
        Q += sq[m + 2 * SPAN - j][:, None] * PULSE[j][None, :]
    I, Q = I.ravel(), Q.ravel()
    m8 = np.arange(len(I)) & 7
    # ##########################################################################
    # ##  KEY LINE: onto the carrier, 8 samples per cycle: I cos - Q sin is I, Q
    # ##  or 0.707 (I +- Q); 0.707 = 181/256.  Then / 8 (the table's scale).
    # ##########################################################################
    even = np.select([m8 == 0, m8 == 2, m8 == 4, m8 == 6], [I, -Q, -I, Q], 0)
    odd = np.select([m8 == 1, m8 == 3, m8 == 5, m8 == 7], [I - Q, -I - Q, -I + Q, I + Q], 0)
    s = np.where(m8 & 1, (181 * odd + 1024) >> 11, (even + 4) >> 3)
    return np.clip(128 + s, 0, 255)


# ---- the cable, for a stream of any length ----------------------------------------
def stream_channel(dac, ppm=0.0, cfo=0.0, delay=5.7, noise=0.1, corner=40e6,
                   gain=channel.GAIN, offset=channel.OFFSET, recon=None, rng=None):
    """channel.channel() for a waveform that doesn't loop: DAC codes at 50 MS/s in, ADC
    codes at 25 MS/s out, with the same steps (held codes, a 40 MHz low-pass, a delay of
    5.7 ADC samples, 0.776 x + 27.5, noise, 8 bits).  `ppm`: the transmitter's clock is
    that much fast (its carrier and symbol rate too); `cfo`: move the carrier by this many
    Hz on top (a mixer's error, as channel.py's `shift`).

    `recon`: give the DAC an ideal reconstruction filter (nothing above 25 MHz).  The
    default is to do that when ppm or cfo isn't 0: the bare DAC's image of the signal, at 50 MHz
    minus 6.25 MHz, folds back onto 6.25 MHz, and with one clock it only changes the gain
    a little, but with two clocks it lands 50 MHz x ppm away: 38 Hz at the boards' real
    0.76 ppm, harmless, but 100 kHz at a pretend 2000 ppm, an interferer 21 dB down
    (channel.py).  A mixer error moves the image the other way, 2 x cfo from the signal.
    Either would be a test of the DAC's missing filter, not of the loops."""
    rng = np.random.default_rng(rng)
    UP = channel.UP
    w = np.clip(np.round(np.asarray(dac, float)), 0, 255) - 128
    pad = 64                                                     # silence either side
    held = np.repeat(np.concatenate([np.zeros(pad), w, np.zeros(pad)]), UP)
    f = np.fft.rfftfreq(len(held), 1 / (FS_DAC * UP))
    s = 1j * f / corner
    Y = np.fft.rfft(held) / (1 + np.sqrt(2) * s + s**2)          # two poles at `corner`
    if recon or (recon is None and (ppm != 0 or cfo != 0)):
        Y[f > FS_DAC / 2] = 0
    n_adc = int((len(w) - 2 * delay) / (2 * (1 + ppm * 1e-6)))
    n = np.arange(n_adc)
    # ##########################################################################
    # ##  KEY LINE: ADC sample n sees the DAC's output at the transmitter's time
    # ##  u = 2n(1 + ppm/1e6) - 2 delay, in DAC samples.
    # ##########################################################################
    pos = (2.0 * n * (1 + ppm * 1e-6) - 2.0 * delay + pad) * UP
    if cfo == 0:
        v = channel.cubic(np.fft.irfft(Y, len(held)), pos)
    else:
        Ya = 2 * Y
        Ya[0] = Y[0]
        full = np.zeros(len(held), complex)
        full[:len(Ya)] = Ya
        ya = np.fft.ifft(full)                                   # the analytic signal
        v = np.real(channel.cubic(ya, pos) * np.exp(2j * np.pi * cfo * n / FS_ADC))
    adc = offset + gain * (128 + v) + noise * rng.standard_normal(n_adc)
    return np.clip(np.round(adc), 0, 255).astype(np.int64)


# ---- receiver, front end (numpy: the same integers the FPGA computes) --------------
def rx_frontend(adc, droop_eq=True):
    """ADC codes -> the matched filter's output at 6.25 MS/s, as (I, Q) integer arrays.
    Also returns the half-band stage's output at 12.5 MS/s, for looking at."""
    x = np.asarray(adc, np.int64) - 128
    n = np.arange(len(x))
    # ##########################################################################
    # ##  KEY LINE: mix by 1, -j, -1, j.  I lives on the even samples and Q on
    # ##  the odd ones (the other half of each is zero).
    # ##########################################################################
    zI = np.where(n % 4 == 0, x, np.where(n % 4 == 2, -x, 0))
    zQ = np.where(n % 4 == 3, x, np.where(n % 4 == 1, -x, 0))
    # 1. the half-band interpolator, keeping the even samples: I is the sample itself
    #    (x 16), Q is interpolated from its four odd neighbours (x 16 too, at DC).
    #    (The zeros in front are what the FPGA's empty delay lines hold at power-up.)
    zI, zQ = np.concatenate([np.zeros(6, np.int64), zI]), np.concatenate([np.zeros(6, np.int64), zQ])
    m1 = np.arange(4, len(zI) - 3, 2)
    I1 = 16 * zI[m1]
    Q1 = 9 * (zQ[m1 - 1] + zQ[m1 + 1]) - (zQ[m1 - 3] + zQ[m1 + 3])
    # 2. [1 2 1] and keep 1 in 2: 6.25 MS/s, 4 samples per symbol (x 4)
    I1, Q1 = np.concatenate([np.zeros(2, np.int64), I1]), np.concatenate([np.zeros(2, np.int64), Q1])
    m2 = np.arange(1, len(I1) - 1, 2)
    I2 = I1[m2 - 1] + 2 * I1[m2] + I1[m2 + 1]
    Q2 = Q1[m2 - 1] + 2 * Q1[m2] + Q1[m2 + 1]
    if droop_eq:
        # 3. a little high-pass that lifts the band edge by what [1 2 1] drooped:
        #    y[m] = 4 v[m-1] + 9 (2 v[m-1] - v[m] - v[m-2]) / 32    (x 4 keeps 2 fraction bits)
        def eq(v):
            vp = np.concatenate([np.zeros(2, np.int64), v])
            return 4 * vp[1:-1] + ((2 * vp[1:-1] - vp[2:] - vp[:-2]) * 9 >> 5)
        Ie, Qe = eq(I2), eq(Q2)
    else:
        Ie, Qe = 4 * I2, 4 * Q2
    # ##########################################################################
    # ##  KEY LINE: the matched filter, 49 integer taps, then / 2^13.
    # ##########################################################################
    yI = np.convolve(Ie, MF)[:len(Ie)] >> MF_SHIFT
    yQ = np.convolve(Qe, MF)[:len(Qe)] >> MF_SHIFT
    return yI, yQ, I1, Q1


# ---- receiver, the loops (one symbol at a time, as the FPGA) ------------------------
def farrow(ym1, y0, y1, y2, mu):
    """The value between y0 and y1, mu/4096 of the way, on the cubic through the four
    samples that Keys's a = -1/2 (the Catmull-Rom spline) gives: every coefficient is a
    half, so there's nothing but shifts, adds and three multiplies by mu (Horner)."""
    c1 = (y1 - ym1) >> 1
    c2 = (2 * ym1 - 5 * y0 + 4 * y1 - y2) >> 1
    c3 = (-ym1 + 3 * y0 - 3 * y1 + y2) >> 1
    t1 = c2 + ((mu * c3) >> 12)
    t2 = c1 + ((mu * t1) >> 12)
    return y0 + ((mu * t2) >> 12)


def sat(v, bits):
    """v, kept within a signed number of this many bits (plus the sign)."""
    lo, hi = -(1 << bits), (1 << bits) - 1
    return lo if v < lo else hi if v > hi else v


def quadrant(i, q):
    """The nearest of the four points: q = 0, 1, 2, 3 for 45, 135, 225, 315 degrees."""
    return 0 if (i >= 0 and q >= 0) else 1 if (i < 0 and q >= 0) else 2 if (i < 0) else 3


def rx_loops(yI, yQ, s1_t=S1_T, s2_t=S2_T, s1_c=S1_C, s2_c=S2_C, tau0=2 * ONE):
    """The timing NCO, the interpolator, the Gardner and Costas loops, the decisions and
    the frame sync, sample by sample.  Returns a dict of arrays (one entry per symbol) and
    the bytes received, with the symbol number each arrived at.

    The NCO is a counter tau that says how many samples away the next symbol centre is,
    and loses 1 per sample.  When it drops below 1, the centre falls before the next
    sample: a symbol strobe, and tau is where between the samples (mu); then it gets a
    period, less the loop's correction, added.  Half a period earlier there's a "mid"
    strobe the same way, for Gardner's half-way sample.  The
    interpolator always works two samples behind (it needs the sample after the one it's
    interpolating past), with the mu that was decided for that sample."""
    n = len(yI)
    yI = np.concatenate([np.zeros(3, np.int64), yI]); yQ = np.concatenate([np.zeros(3, np.int64), yQ])
    tau, integ, prop = tau0, 0, 0
    flags = [(False, False, 0)] * 3            # (symbol strobe, mid strobe, mu) at k, k-1, k-2
    yi = [(0, 0)] * 2                          # interpolated values: basepoint k-2 is yi[0]
    mid = prev = (0, 0)
    phi = freq = 0
    q_prev = fr = cnt = hits = misses = 0
    locked = False
    rec = {k: [] for k in ("sym", "mu", "tau", "period", "eg", "zI", "zQ", "phi", "freq", "ec",
                           "q", "locked", "yI", "yQ")}
    out, out_at = [], []
    for k in range(n):
        # 1. basepoint k-3's strobes: its interpolated value was computed last time (yi[0]).
        #    This comes first so that the loop's correction is in before the NCO decides.
        s_k, m_k, mu_k = flags[2]
        if m_k:
            mid = (yi[0][0] >> 1, yi[0][1] >> 1)
        if s_k:
            nI, nQ = yi[0][0] >> 1, yi[0][1] >> 1
            # ##################################################################
            # ##  KEY LINE: Gardner's detector, Re(y_mid* (y_now - y_prev)).
            # ##################################################################
            eg = mid[0] * (nI - prev[0]) + mid[1] * (nQ - prev[1])
            prev = (nI, nQ)
            integ += sat(eg >> s2_t, 20)              # (the saturations only matter for
            prop = sat(eg >> s1_t, 15)                #  junk: they keep tau in 20 bits)
            # the Costas loop: turn by -phi, decide, Im(z d*), update
            idx = (phi >> 14) & 1023
            c, s = SINE[(idx + 256) & 1023], SINE[idx]
            zI = (nI * c + nQ * s) >> 11
            zQ = (nQ * c - nI * s) >> 11
            qd = quadrant(zI, zQ)
            # ##################################################################
            # ##  KEY LINE: the phase detector: +-Q -+ I, the sign from the quadrant.
            # ##################################################################
            ec = (zQ if zI >= 0 else -zQ) - (zI if zQ >= 0 else -zI)
            freq += ec << s2_c
            phi = (phi + freq + (ec << s1_c)) & 0xFFFFFF
            # differential decoding, and the frame
            dq = (qd - q_prev) & 3
            q_prev = qd
            fr = ((fr << 2) | GRAY[dq]) & 0xFFFF
            hit = (fr >> 9) == SYNC
            if locked:
                if cnt == NSYM_FRAME - 1:                  # a whole frame is in
                    misses = 0 if hit else misses + 1
                    if misses >= 8:
                        locked = False
                    elif (fr >> 8) & 1:
                        out.append(fr & 0xFF); out_at.append(len(rec["sym"]))
                    cnt = 0
                else:
                    cnt += 1
            else:
                if hit:
                    hits = hits + 1 if cnt == NSYM_FRAME - 1 else 1
                    cnt = 0
                    if hits >= 3:
                        locked, misses = True, 0
                        if (fr >> 8) & 1:
                            out.append(fr & 0xFF); out_at.append(len(rec["sym"]))
                else:
                    cnt = min(cnt + 1, NSYM_FRAME)
            for key, val in (("sym", k - 3), ("mu", mu_k >> 4), ("tau", tau), ("period", PNOM - sat(integ >> 8, 15)),
                             ("eg", eg), ("zI", zI), ("zQ", zQ), ("phi", phi), ("freq", freq),
                             ("ec", ec), ("q", qd), ("locked", int(locked)), ("yI", nI), ("yQ", nQ)):
                rec[key].append(val)
        # 2. the NCO: does the next symbol centre, or the half-way point before it,
        #    fall before the next sample?
        period = PNOM - sat(integ >> 8, 15)
        if tau < ONE:
            flags = [(True, False, tau)] + flags[:2]
            # ##################################################################
            # ##  KEY LINE: the next centre is one period on, less the loop's
            # ##  correction (the integrator is in `period`, and `prop` is the
            # ##  last symbol's error): psk.py's  t += sps - (k1 e + integ).
            # ##################################################################
            tau = tau + period - prop - ONE
        else:
            half = tau - (period >> 1)
            flags = [(False, 0 <= half < ONE, half & 0xFFFF)] + flags[:2]
            tau = tau - ONE
        # 3. interpolate at basepoint k-2, with the mu decided for it
        mu = flags[2][2] >> 4
        y = (farrow(yI[k], yI[k + 1], yI[k + 2], yI[k + 3], mu),
             farrow(yQ[k], yQ[k + 1], yQ[k + 2], yQ[k + 3], mu))
        yi = [y] + yi[:1]
    r = {k: np.array(v, np.int64) for k, v in rec.items()}
    r["bytes"], r["bytes_at"] = np.array(out, np.int64), np.array(out_at, np.int64)
    r["ppm"] = (PNOM / np.maximum(r["period"], 1) - 1) * 1e6      # symbol rate offset found
    r["hz"] = r["freq"] * R_SYM / 2**24                            # carrier offset found
    return r


def receive(adc, **kw):
    yI, yQ, I, Q = rx_frontend(adc)
    r = rx_loops(yI, yQ, **kw)
    r["mfI"], r["mfQ"], r["hbI"], r["hbQ"] = yI, yQ, I, Q
    return r


# ---- the loops' gains: what the shifts amount to -----------------------------------
def loop_params(K1, K2):
    """Noise bandwidth x symbol time, and damping, of a second-order loop whose
    proportional and integral gains (times the detector's gain) are K1 and K2 per
    update: psk.loop_gains() run backwards."""
    th = math.sqrt(K2 / (4 - 2 * K1 - K2))
    zeta = th * K1 / K2
    return th * (zeta + 1 / (4 * zeta)), zeta


def detector_gains(adc):
    """Measure the detectors' slopes on this signal, with the loops held still: the Gardner
    error per sample of timing error (at 4 samples per symbol), and the Costas error per
    radian, both in the FPGA's integer units."""
    yI, yQ, _, _ = rx_frontend(adc)
    k = np.arange(40 * SPS, len(yI) - 8, SPS)              # nominal symbol centres: every 4th sample
    def at(off):                                             # the symbols at offset `off` samples
        i, mu = int(np.floor(off)), int((off - np.floor(off)) * 4096)
        return (np.array([farrow(yI[j - 1], yI[j], yI[j + 1], yI[j + 2], mu) for j in k + i]) >> 1,
                np.array([farrow(yQ[j - 1], yQ[j], yQ[j + 1], yQ[j + 2], mu) for j in k + i]) >> 1)
    best, kd_t = None, 0
    for off in np.arange(0, 4, 0.25):                        # find the true centre first
        I, Q = at(off)
        p = np.mean(np.abs(I) + np.abs(Q))
        if best is None or p > best[0]:
            best = (p, off)
    off = best[1]
    d = 0.1
    e = []
    for o in (off - d, off + d):
        nI, nQ = at(o)
        mI, mQ = at(o - 2)
        e.append(np.mean(mI[1:] * np.diff(nI) + mQ[1:] * np.diff(nQ)))
    kd_t = (e[1] - e[0]) / (2 * d)
    I, Q = at(off)
    S = np.mean(np.abs(I) + np.abs(Q)) / 2                   # the symbol's size per axis
    return kd_t, 2 * S, S


def loop_report(adc=None, s1_t=S1_T, s2_t=S2_T, s1_c=S1_C, s2_c=S2_C):
    """Print what the shifts mean, measured on `adc`, which must have no rate offset (the
    symbol centres are taken every 4th sample), or by default on a model signal."""
    if adc is None:
        words, _ = frames_for(np.random.default_rng(3).integers(0, 256, 200), gap=1)
        adc = stream_channel(tx_dac(tx_symbols(words)), rng=3)
    kd_t, kd_c, S = detector_gains(adc)
    lines = ["symbol size after the matched filter and interpolator: %.0f per axis" % S,
             "Gardner detector: %.3g per sample of timing error;  Costas: %.0f per radian" % (kd_t, kd_c)]
    K1 = kd_t * 2**-s1_t / ONE
    K2 = kd_t * 2**-s2_t / ONE / 256
    bnt, z = loop_params(K1, K2)
    lines.append("timing loop:  e >> %d and e >> %d:  K1 = %.4f, K2 = %.2e: BnT = %.4f, zeta = %.2f  (psk.py: 0.01, 0.71)"
                 % (s1_t, s2_t, K1, K2, bnt, z))
    K1 = kd_c * 2**s1_c * 2 * np.pi / 2**24
    K2 = kd_c * 2**s2_c * 2 * np.pi / 2**24
    bnt, z = loop_params(K1, K2)
    lines.append("carrier loop: e << %d and e << %d:  K1 = %.4f, K2 = %.2e: BnT = %.4f, zeta = %.2f  (psk.py: 0.02, 0.71)"
                 % (s1_c, s2_c, K1, K2, bnt, z))
    return "\n".join(lines)


# ---- scoring -----------------------------------------------------------------------
def score(sent, got):
    """Bit errors between the bytes sent and the bytes received, lined up with difflib
    (a lost or invented byte counts 8), as modem_ber.py does."""
    import difflib
    sent, got = bytes(int(b) for b in sent), bytes(int(b) for b in got)
    bits = 0
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, sent, got, autojunk=False).get_opcodes():
        if op == "replace":
            n = min(i2 - i1, j2 - j1)
            bits += sum(bin(x ^ y).count("1") for x, y in zip(sent[i1:i1 + n], got[j1:j1 + n]))
            bits += 8 * abs((i2 - i1) - (j2 - j1))
        elif op == "delete" or op == "insert":
            bits += 8 * max(i2 - i1, j2 - j1)
    return bits


def summary(r, sent=None):
    """A few lines about a receive: lock, the offsets found, errors."""
    lines = []
    lk = np.flatnonzero(r["locked"])
    lines.append("symbols: %d; frame lock at symbol %s" % (len(r["sym"]), lk[0] if len(lk) else "never"))
    last = slice(-200, None)
    lines.append("timing loop:  symbol rate offset found %+.0f ppm (mean of the last 200 symbols)" % np.mean(r["ppm"][last]))
    lines.append("Costas loop:  carrier offset found %+.0f Hz" % np.mean(r["hz"][last]))
    if sent is not None:
        got = r["bytes"]
        lines.append("%d bytes sent, %d received, %d bit errors" % (len(sent), len(got), score(sent, got)))
    return "\n".join(lines)


def plot(r, title):
    import matplotlib.pyplot as plt
    k = r["sym"]
    us = k * SPS / 6.25e6 * 1e6
    fig, ax = plt.subplots(2, 3, figsize=(13, 7))
    good = r["locked"] > 0
    ax[0, 0].plot(r["zI"][~good], r["zQ"][~good], ".", color="0.75", markersize=2)
    ax[0, 0].plot(r["zI"][good], r["zQ"][good], ".", markersize=2)
    ax[0, 0].set_aspect("equal"); ax[0, 0].set_title("after the loops (grey: before frame lock)")
    ax[0, 1].plot(us, r["mu"] / 4096, ".", markersize=1.5); ax[0, 1].set_title("mu: where between samples (0..1)")
    ax[0, 2].plot(us, r["ppm"]); ax[0, 2].set_title("symbol rate offset found (ppm)")
    ax[1, 0].plot(us, r["eg"], ".", markersize=1.5); ax[1, 0].set_title("Gardner error")
    ax[1, 1].plot(us, r["hz"] / 1e3); ax[1, 1].set_title("carrier offset found (kHz)")
    ax[1, 2].plot(us, r["ec"], ".", markersize=1.5); ax[1, 2].set_title("Costas error")
    for a in ax.ravel()[1:]:
        a.set_xlabel("time (us)"); a.grid(True)
    fig.suptitle(title); fig.tight_layout(); plt.show()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sim", action="store_true", help="(the only mode: this is the model)")
    ap.add_argument("--bytes", type=int, default=300)
    ap.add_argument("--ppm", type=float, default=0.0, help="transmitter's clock offset, ppm")
    ap.add_argument("--cfo", type=float, default=0.0, help="extra carrier offset, Hz")
    ap.add_argument("--noise", type=float, default=0.1, help="ADC noise, codes rms")
    ap.add_argument("--gains", action="store_true", help="print the loops' bandwidths")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--plot", action="store_true")
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    data = rng.integers(0, 256, args.bytes)
    words, where = frames_for(data, gap=1)
    dac = tx_dac(tx_symbols(words))
    adc = stream_channel(dac, ppm=args.ppm, cfo=args.cfo, noise=args.noise, rng=args.seed)
    print("DAC: %d samples, rms %.1f codes, peak %d; ADC: %d samples" % (len(dac), (dac - 128).std(), np.abs(dac - 128).max(), len(adc)))
    if args.gains:
        print(loop_report())
    r = receive(adc)
    print(summary(r, data))
    if args.plot:
        plot(r, "fixed-point model, ppm %+.0f, cfo %+.0f Hz" % (args.ppm, args.cfo))
```

</details>

```console
$ cd src/comms
$ python3 modem_fpga_model.py --sim --ppm 2000 --cfo -9500 --gains
DAC: 174080 samples, rms 48.0 codes, peak 105; ADC: 86860 samples
symbol size after the matched filter and interpolator: 592 per axis
Gardner detector: 2.4e+05 per sample of timing error;  Costas: 1184 per radian
timing loop:  e >> 7 and e >> 5:  K1 = 0.0286, K2 = 4.47e-04: BnT = 0.0112, zeta = 0.68  (psk.py: 0.01, 0.71)
carrier loop: e << 7 and e << 2:  K1 = 0.0567, K2 = 1.77e-03: BnT = 0.0224, zeta = 0.68  (psk.py: 0.02, 0.71)
symbols: 5438; frame lock at symbol 37
timing loop:  symbol rate offset found +2003 ppm (mean of the last 200 symbols)
Costas loop:  carrier offset found +2994 Hz
300 bytes sent, 300 received, 0 bit errors
```

| loop | proportional | integral | *K*<sub>1</sub>, *K*<sub>2</sub> | *B*<sub>n</sub>*T*, ζ |
| --- | --- | --- | --- | --- |
| timing | `prop = e >> 7` | `integ += e >> 5`, in units of 2<sup>−24</sup> sample | *k*<sub>d</sub> 2<sup>−23</sup>, *k*<sub>d</sub> 2<sup>−29</sup> | 0.011, 0.68 |
| carrier | `phi += e << 7` | `freq += e << 2`, in units of 2π/2<sup>24</sup> | *k*<sub>d</sub> 2<sup>7</sup> · 2π/2<sup>24</sup>, *k*<sub>d</sub> 2<sup>2</sup> · 2π/2<sup>24</sup> | 0.022, 0.68 |

The nearest shifts land within a factor of 1.1 in bandwidth and 0.03 in
damping of the floating-point loops, which is as close as powers of two
get. The integrator keeps eight extra bits below the sample so that small
errors still move it; without them a 1 ppm offset would never accumulate.
One thing the shifts cannot do that `psk.py` could: the detectors' gains
scale with the signal's amplitude (Gardner's with its square, Costas's
linearly), so the loop bandwidths are set for the cable's 0.776 codes per
code, and at half the amplitude the gains are a quarter, which halves the loop's
bandwidth and halves its damping (ζ = 0.34): slow, and ringing.
There is no AGC. Real receivers have one, and the first "Try this" is to
add it.

## Checking it without a board

The model is the same arithmetic in Python, integer for integer, and
`qpsk_modem_check.py` makes the Verilog prove it, with iverilog and no
board: a testbench that plays the laptop (bytes at 1 Mbaud) and the analog
world (the cable, or a file of ADC samples), and dumps every DAC code,
every frame and the loops' state at every symbol.

```console
$ cd src/twoboard
$ python3 qpsk_modem_check.py              # about a minute
1. LOOPED BACK: 200 random bytes at 1 Mbaud, 180000 clocks (3.6 ms)
   200 bytes came back, 0 bit errors; typed-to-echoed delay 28.1 to 36.0 us

2. THE TRANSMITTER, BIT FOR BIT: the DAC codes of test 1 against the model's,
   from the 703 frames the design sent (200 with a byte)
   bit-exact over 179546 codes: yes (the design's DAC is 454 clocks behind the model's symbol clock)
   DAC: rms 48.0 codes, peak 104 (never clips: the worst case is 108)

3. THE RECEIVER, BIT FOR BIT: the same DAC codes through the channel model, with the
   transmitter's clock +2000 ppm fast (carrier +12500 Hz, symbols +2000 ppm), a mixer error of -9500 Hz, noise 0.1 codes rms
   symbols: Verilog 5686, model 5624; loop states identical: yes, all 5624
   frame lock at symbol 68; found +1990 ppm and +2994 Hz (mean of the last 500 symbols)
   200 bytes came back (model: 200), 0 bit errors (0 from the 0 bytes sent before the lock); bytes identical to the model's: yes
   MER over the last 1000 symbols 39.7 dB

PASS
```

"Bit for bit" is the standard. A design that agrees with its model at
every one of 5624 symbols, through a channel 2000 ppm fast and 3 kHz off,
has no arithmetic bug left to find on the board; what the board can still
add is the real cable's ringing, the converters' real distortion, and a
real second clock. The model's own numbers: 40.0 dB of MER at zero offset,
39.7 to 40.5 at ±2000 ppm, ±3 kHz and ±20 kHz; lock in 37 to 85 symbols;
timing jitter 0.021 samples, half a percent of a symbol, at every channel
delay; with ADC noise of 3, 8 and 12 codes rms, 30.0, 21.9 and 18.4 dB and
no errors in 300 bytes each. `psk.py` measured 38 dB on the real cable, so
the fixed point costs nothing measurable.

<details>
<summary><b>Detail:</b> the three bugs in the NCO, and one in Verilog</summary>

Each of these made a link that *worked* and was wrong by 5 to 15 dB, or by
hundreds of ppm in the reported rate, which is the dangerous kind of bug.
(1) The mid-symbol sample needs its own strobe and its own `mu`: whenever
`mu` wraps past zero the strobes are three or five samples apart, not four,
and "the sample two after the symbol" is half a sample off. (2) The
proportional correction must go into the *next period* at the strobe, not
into the running countdown: a nudge towards "earlier" cannot move a strobe
already decided, which clamps the loop on one side and biases it. (3) The
symbol must be processed before the NCO decides, or a three-sample spacing
skips one correction and applies the previous one twice. And in Verilog,
`tau + period − prop − ONE` with an *unsigned* `ONE` zero-extends a negative
`prop`, and the receiver "worked" at 16 dB. Then yosys: an array indexed by
a computed expression became a 61,000-LUT barrel shifter, 253% of the
chip; written as a `case` with constant indices it is 7000. Constant
multiplies by 9, 5 and 3 took hardware multipliers until written as
shift-adds. None of this is in a textbook, and all of it is the job.

</details>

<details>
<summary><b>Detail:</b> the DAC's image, and why the stress tests cheat</summary>

`channel.py`'s model of the DAC holds each code for a sample, which puts
an image of the signal 50 MHz × ppm away, 21 dB down: 100 kHz at the
pretend 2000 ppm, 38 Hz at the real 0.76 ppm of two boards. A mixer error
moves it 2 × *f*<sub>cfo</sub> away. The 2000 ppm tests above therefore give
the model's DAC an ideal reconstruction filter (the model's `recon`,
on by default whenever ppm or cfo is not zero); a real second board at
2000 ppm would show that interferer, and at 0.76 ppm it would not.

</details>

## On the board

The first run on the board, looped back through the cable:

```console
$ cd src/twoboard
$ make load-qpsk_modem
$ python3 qpsk_modem_test.py /dev/ttyUSB0
20000 bytes sent at 1000000 baud, 19936 received; 664 bit errors in 160000 bits: BER 4.2e-03
$ python3 qpsk_modem_test.py /dev/ttyUSB0 --bytes 200000
200000 bytes sent at 1000000 baud, 199232 received; 8016 bit errors in 1600000 bits: BER 5.0e-03
```

Sixty-four bytes of twenty thousand lost, 768 of two hundred thousand:
one in 250, steadily, after the first eight thousand. That is not what
a noisy link does (a noisy link corrupts bytes, it does not lose them),
and it is not what the bit-exact model does. It is what a *repeater with
no flow control* does when its way out is slower than its way in. The
laptop delivers a byte every 500 clocks (ten bits at 1 Mbaud, back to
back); the modem's serial transmitter, a stock `uart_tx` that rests a
clock after each stop bit and a FIFO that started it a clock after that,
sent one every 502. The 32-byte FIFO filled after 32 × 251 ≈ 8000 bytes
and then overwrote itself once every 251: one byte in 250, from byte
8000 on, exactly as measured. The testbench reproduced it to the byte
(19,936 of 20,000) once it was told to send bytes back to back, which the
first testbench, politely, had not.

The fix is the rule every repeater without flow control obeys: send at
least as fast as you receive. The modem now has its own transmitter that
starts the next byte in the clock after the stop bit, with a bit time of
49 clocks instead of 50, two percent fast, because "equal" is not enough
when two crystals are involved and a [UART](https://en.wikipedia.org/wiki/Universal_asynchronous_receiver-transmitter) re-times every byte from its
start bit anyway. Bytes leave 490 clocks apart against 500 arriving, the
FIFO never holds more than one, and the five-test check (which now
includes 1500 bytes landing at every phase of the frame clock, through a
FIFO shrunk to two bytes) passes with zero errors. And on the board,
once the cable was back:

```console
$ python3 qpsk_modem_test.py /dev/ttyUSB0
20000 bytes sent at 1000000 baud, 20000 received; 0 bit errors in 160000 bits: BER 0.0e+00
$ python3 qpsk_modem_test.py /dev/ttyUSB0 --bytes 200000
200000 bytes sent at 1000000 baud, 200000 received; 0 bit errors in 1600000 bits: BER 0.0e+00
```

Two hundred thousand bytes, 1.6 million bits, none wrong, where the
first bitstream lost 768. (A two-million-byte run stalled inside the
laptop's serial driver after the data had gone and was killed; the
position probe on a fresh 20,000 found nothing. Two hundred thousand is
the longest clean run on record.)

<details>
<summary><b>Detail:</b> why a 115,200-baud port half-works</summary>

The modem's ports are 1 Mbaud, full stop, and a run with the laptop's
port at 115,200 should have been garbage. It returned all 20,000 bytes
with 6% of them wrong, which is the more interesting answer. A
115,200-baud start bit lasts 8.68 µs; `uart_rx`, expecting 1 µs bits,
sees a start bit, samples eight "data bits" inside it, delivers a byte,
and takes the still-low line as the next start bit. It is acting as a
1 MS/s *digitizer of the serial line*, eight samples per byte, and the
modem carries those bytes across and replays them: the low stretches of
the original waveform come back with a 1 µs stop-bit gap cut into every
10 µs of them. The laptop's UART samples once per bit, at the centre, and
lands on one of those gaps about one time in nine per low bit: 6%. Like
[5.05](5_05_fsk_modem.md#505-a-modem)'s modem, this one is transparent to
the line at 1 µs resolution, which is why the wrong baud rate half-works,
and `qpsk_modem_test.py` now refuses any baud rate but 1,000,000 and says
so.

</details>

The LEDs: the leftmost is frame lock, on as soon as the cable is in; pull
the cable and it goes out within 41 µs, plug it back and it returns, no
reset needed. The next two blink for 0.3 s on a received and on a typed
byte; the fourth is the ADC clipping, which should stay off. One known
weakness, shared with every modem that has no preamble: the frame sync
locks at symbol 37 to 85, before the Costas loop's frequency has settled
(about 300 symbols), so a byte sent in the first 200 µs after a signal
appears can be wrong. Real modems send a preamble, or make the lock wait
for the loops.

## What it costs

| resource | used | of the ECP5-25 |
| --- | ---: | ---: |
| logic cells | 6809 | 28% |
| flip-flops | 4654 | 19% |
| 18×18 multipliers | 16 | 57% (of 28) |
| block RAM | 1 | the 1024-entry sine table |
| clock | 69.1 MHz | passes at 50 |

Where the sixteen multipliers went: eight in the matched filter, six in
the interpolator, four in the rotation and two in Gardner's detector by
the design's count, of which yosys put four into LUTs. The critical path
is the NCO's adder chain from the integrator through the period to `tau`.
[5.05](5_05_fsk_modem.md#505-a-modem)'s modem used no multipliers at all
and ran 115,200 baud; this one uses 16 and runs 3.125 Mbit/s with every
loop [6.02](6_02_psk_and_qpsk.md#602-psk-and-qpsk-finding-the-clock-and-the-carrier)
had. The ratio of effort is about right for the ratio of speed.

learnSDR builds each of these blocks in GNU Radio: the Costas loop
(lessons [12](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson12.md)
and [13](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson13.md)),
PSK ([16](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson16.md)),
symbol timing ([18](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson18.md)),
frame sync and differential coding ([19](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson19.md),
[20](https://github.com/gallicchio/learnSDR/blob/main/docs/lesson20.md)).
What the blocks hide, and this page shows, is the integer widths, where the
multipliers go, the NCO's bookkeeping, the holes at *f*<sub>s</sub>/4, and that
a real receiver's loop gains depend on the signal level.

**Try this:**

- An AGC by powers of two: shift the matched filter's output by 0 to 3
  places so that the symbol size stays near 1190 whatever the cable does.
  Then put a 20 dB attenuator in the cable and watch the loops without it
  (they slow down, then lose lock) and with it.
- Make the lock wait for the loops: count 64 sync hits, or gate on a small
  Costas error, before delivering bytes. Measure how many bytes the first
  200 µs cost before and after.
- A parity bit in the frame (there is room: the valid bit's neighbour),
  and count dropped bytes against wrong ones as the noise rises.
- Swap Catmull-Rom for the parabolic interpolator in the model (one
  function) and plot MER against `mu`: the 13 dB dip is the band edge.
- Two boards: `qpsk_modem_test.py PORT_A PORT_B`, A's DAC to B's ADC. The
  loops' integrators should settle at the real +0.76 ppm and +4.75 Hz,
  which the board cannot report but `awgcap.bit` on a third board and the
  model can.
- Drive it from Linux: swap `modem.sv` for `qpsk_modem.sv` in
  [5.05](5_05_fsk_modem.md#505-a-modem)'s `make_modem_linux.py` and run
  `ping` across the cable at 3 Mbit/s instead of 115 kbaud.
- 3.125 Msymbol/s: two samples per symbol after the decimator, where no
  four-tap interpolator is good enough (the band edge would be at 0.34 of
  the sample rate). What has to change, and what does it cost?
