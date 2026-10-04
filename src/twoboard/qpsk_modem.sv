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
