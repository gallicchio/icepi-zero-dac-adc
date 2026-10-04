// filter.sv -- a filter whose coefficients the laptop loads over the serial port (7.03):
// a direct-form-I IIR with 16 feed-forward taps and 4 feedback taps between the ADC
// (25 MS/s) and the DAC, with built-in test signals and 1.06's capture.  filter.py
// designs a filter with scipy, quantizes it, loads it, and measures it.
//
//   y[n] = ( b_0 x[n] + ... + b_15 x[n-15]  -  a_1 y[n-1] - ... - a_4 y[n-4] ) / 8192
//
// The coefficients are 16-bit signed integers in Q2.13: the value x 8192, so |c| < 4 and
// the resolution is 1/8192.  With a = 0 it is an FIR; a_1..a_4 make it an IIR, up to
// 4th order (a 2nd-order Butterworth, a one-pole RC, a resonator: see 7.02).
//
// Arithmetic.  20 multiplies per sample, one hardware multiplier each (the ECP5-25F has
// 28; time-sharing 10 of them over the two clocks a sample lasts would halve that at the
// cost of a multiplexer in front of each, and nothing here needs the space).  The 16
// feed-forward products are summed in two steps (4 x 4, then 4) because a 16-input adder
// is too slow for one 20 ns clock; that is free latency.  The feedback cannot be
// pipelined that way: y[n] needs y[n-1], which was ready only a sample ago, so the loop
// is kept to one multiply (clock 1) plus one add-and-saturate (clock 2); the other three
// feedback products, which need older outputs, are computed and pre-summed a sample
// early.  y is kept in 18 bits, Q10.8 (8 bits below the ADC's lsb, saturating at +-512)
// so that rounding is not fed back (7.02); the DAC gets y rounded and clipped to -128..127,
// plus 128.
//
// The protocol (1,000,000 baud, 8N1; multi-byte integers big-endian):
//   'B' k hi lo      b_k (k = 0..15) = the signed 16-bit value hi:lo
//   'A' k hi lo      a_k (k = 1..4)
//   'S' src          the filter's input: 0 = the ADC; 1 = an impulse, one sample of +64
//                    every 2^14 samples; 2 = a step, -64 / +64, toggling every 2^14
//                    samples; 3 = white noise, -32..31, from a 32-bit xorshift
//                    (modem_noise.sv); 4 = a tone, 64 sin, from a DDS
//   'F' word(4)      the tone's tuning word, f / 25e6 x 2^32
//   'O' out          what the DAC plays: 0 = the filter's output, 1 = its input, with
//                    the same delay (so the two can be compared)
//   'C'              capture 16384 ADC samples, then send them as 16384 raw bytes, as
//                    capture.sv does.  Recording starts at the stimulus period's start
//                    (the impulse, the step's rising edge), and the noise generator is
//                    re-seeded there, so the laptop knows the stimulus sample by sample.
//   Unknown bytes are ignored.  Power-up: b_0 = 8192 (1.0), everything else 0, src 0, out 0.
//
// Latency: the DAC shows the response to an ADC sample 3 samples (120 ns) later, for
// out = 0 and out = 1 alike.
//
// LEDs: led[4] = the output clipped in the last 84 ms; led[3] = capturing or sending;
//       led[2] = a built-in stimulus is selected; led[1] = the DAC plays the input;
//       led[0] blinks.
module filter (
    input  logic       clk,         // 50 MHz
    input  logic       uart_rx,     // from the laptop
    output logic       uart_tx,     // to the laptop
    output logic [7:0] dac_d = 128,
    output logic       dac_clk,
    input  logic [7:0] adc_d,
    output logic       adc_clk,
    output logic [4:0] led
);
    localparam integer NB = 16, NA = 4;             // feed-forward and feedback taps
    localparam integer N  = 16384;                  // the capture's length

    // ---- the serial port, both directions (uart.sv) -----------------------------------
    logic [7:0] rx_data, tx_data = 0;
    logic       rx_valid, tx_start = 0, tx_busy;
    uart_rx #(.CLKS_PER_BIT(50)) urx (.clk(clk), .rx(uart_rx), .data(rx_data), .valid(rx_valid));
    uart_tx #(.CLKS_PER_BIT(50)) utx (.clk(clk), .data(tx_data), .start(tx_start),
                                      .busy(tx_busy), .tx(uart_tx));

    // ---- the settings, as the laptop left them ----------------------------------------
    logic signed [15:0] b [0:NB-1];                 // 'B': Q2.13
    logic signed [15:0] a [1:NA];                   // 'A'
    initial begin
        b[0] = 16'sd8192;                           // 1.0: the filter starts as a wire
        for (int k = 1; k < NB; k++) b[k] = 0;
        for (int k = 1; k <= NA; k++) a[k] = 0;
    end
    logic [2:0]  src     = 0;                       // 'S'
    logic        out_in  = 0;                       // 'O': 1 = play the input
    logic [31:0] tone_word = 32'h0a3d_70a4;         // 'F': 1 MHz until told otherwise
    logic        cap_req = 0;                       // 'C' arrived (one clock)

    // ---- the command parser: a command byte, then its arguments in order (ddc.sv) -----
    logic [7:0]  cmd  = 0;                          // the command being filled in; 0 = none
    logic [7:0]  left = 0;                          // argument bytes still to come
    logic [7:0]  idx  = 0;                          // 'B', 'A': which coefficient
    logic [31:0] arg  = 0;                          // the argument bytes so far, newest lowest
    always_ff @(posedge clk) begin
      cap_req <= 0;
      if (rx_valid) begin
        if (cmd == 0)
            case (rx_data)
                "B": begin cmd <= "B"; left <= 3; end
                "A": begin cmd <= "A"; left <= 3; end
                "S": begin cmd <= "S"; left <= 1; end
                "O": begin cmd <= "O"; left <= 1; end
                "F": begin cmd <= "F"; left <= 4; end
                "C": cap_req <= 1;
                default: ;                          // not a command: ignored
            endcase
        else begin
            arg  <= {arg[23:0], rx_data};
            left <= left - 1;
            if (left == 1) cmd <= 0;                // that was the last argument
            case (cmd)
                "B": if (left == 3) idx <= rx_data;
                     else if (left == 1 && idx < NB) b[idx[3:0]] <= {arg[7:0], rx_data};
                "A": if (left == 3) idx <= rx_data;
                     else if (left == 1 && idx >= 1 && idx <= NA) a[idx[2:0]] <= {arg[7:0], rx_data};
                "S": src    <= (rx_data <= 4) ? rx_data[2:0] : 3'd0;
                "O": out_in <= rx_data[0];
                "F": if (left == 1) tone_word <= {arg[23:0], rx_data};
                default: ;
            endcase
        end
      end
    end

    // ---- the ADC at 25 MS/s, as in capture.sv -------------------------------------------
    logic adc_clk_r = 0, new_sample = 0;
    logic signed [8:0] x = 0;                       // the sample, -128..127
    always_ff @(posedge clk) begin
        adc_clk_r  <= ~adc_clk_r;
        new_sample <= 0;
        if (adc_clk_r == 0) begin
            x <= $signed({1'b0, adc_d}) - 9'sd128;
            new_sample <= 1;
        end
    end
    assign adc_clk = adc_clk_r;
    logic step = 0;                                 // the clock after new_sample
    always_ff @(posedge clk) step <= new_sample;

    // ---- the built-in stimuli, one value per sample -------------------------------------
    logic [14:0] cnt = 0;                           // counts samples; the period is 2^14
    logic        period_start;                      // the next sample is cnt 0
    assign period_start = (cnt[13:0] == 14'h3fff);
    logic signed [8:0] impulse, stp, noise, tone = 0;
    assign impulse = (cnt[13:0] == 0) ? 9'sd64 : 9'sd0;
    assign stp     = cnt[14] ? 9'sd64 : -9'sd64;
    // noise: one step of a 32-bit xorshift per sample; the sum of its four bytes is
    // nearly Gaussian (modem_noise.sv), scaled to -32..31
    localparam logic [31:0] SEED = 32'h2545_f491;
    logic [31:0] r = SEED, r1, r2, r3;
    assign r1 = r ^ (r << 13);
    assign r2 = r1 ^ (r1 >> 17);
    assign r3 = r2 ^ (r2 << 5);
    logic signed [10:0] gsum;
    assign gsum  = $signed({3'b0, r[7:0]}) + $signed({3'b0, r[15:8]}) + $signed({3'b0, r[23:16]})
                 + $signed({3'b0, r[31:24]}) - 11'sd510;
    assign noise = 9'(gsum >>> 4);
    // the tone: a DDS at the ADC's rate, 64 x sin
    logic signed [7:0] sin64 [0:255];
    initial for (int i = 0; i < 256; i++)
        sin64[i] = $rtoi($floor(64.0 * $sin(6.283185307179586 * i / 256) + 0.5));
    logic [31:0] phase = 0;
    logic        syncing;                           // a capture is waiting for cnt 0
    always_ff @(posedge clk)
        if (new_sample) begin
            cnt   <= cnt + 1;
            r     <= (syncing && period_start) ? SEED : r3;     // the laptop knows the sequence
            phase <= phase + tone_word;
            tone  <= sin64[phase[31:24]];
        end
    logic signed [8:0] u;                           // the filter's input, this sample
    always_comb case (src)
        3'd1:    u = impulse;
        3'd2:    u = stp;
        3'd3:    u = noise;
        3'd4:    u = tone;
        default: u = x;
    endcase

    // ---- the filter ---------------------------------------------------------------------
    // The feed-forward half, a pipeline: delay line (clock 1) -> 16 products (clock 2)
    // -> four sums of four (clock 3) -> F, the sum of all 16 (clock 4), ready two
    // samples after the input it belongs to.
    logic signed [8:0]  xd [0:NB-1];                // x[n-k]: the delay line
    logic signed [24:0] pb [0:NB-1];                // b_k x[n-k], 9 x 16 bits
    logic signed [26:0] q  [0:3];                   // sums of four products
    logic signed [28:0] F = 0;                      // the sum of all sixteen
    initial for (int k = 0; k < NB; k++) begin xd[k] = 0; pb[k] = 0; end
    initial for (int j = 0; j < 4; j++) q[j] = 0;
    always_ff @(posedge clk) begin
        if (new_sample) begin
            // ######################################################################
            // ##  KEY LINE 1: the delay line.  Each new input pushes the rest along.
            // ######################################################################
            xd[0] <= u;
            for (int k = 1; k < NB; k++) xd[k] <= xd[k-1];
            for (int j = 0; j < 4; j++) q[j] <= pb[4*j] + pb[4*j+1] + pb[4*j+2] + pb[4*j+3];
        end
        if (step) begin
            // ######################################################################
            // ##  KEY LINE 2: sixteen multiplies at once, one hardware multiplier each.
            // ######################################################################
            for (int k = 0; k < NB; k++) pb[k] <= b[k] * xd[k];
            F <= q[0] + q[1] + q[2] + q[3];
        end
    end

    // The feedback half.  yd[1..4] are y[n-1..n-4] in Q10.8.  On `step` (clock 2 of a
    // sample): a_1 y[n-1] for this sample, and a_2..a_4 times y[n-1..n-3] for the NEXT
    // sample.  On `new_sample` (clock 1 of the next): G = F - those three, and the new
    // y = (G - a_1 y[n-1]) >>> 13, saturated, into yd[1].
    localparam logic signed [17:0] YMAX = 18'sd131071, YMIN = -YMAX - 18'sd1;
    logic signed [17:0] yd [1:NA];
    logic signed [33:0] pa1 = 0, pa2 = 0, pa3 = 0, pa4 = 0;    // 16 x 18 bits
    logic signed [39:0] G = 0, acc, shifted;
    logic               clip_y;
    initial for (int k = 1; k <= NA; k++) yd[k] = 0;
    always_ff @(posedge clk)
        if (step) begin
            pa1 <= a[1] * yd[1];
            pa2 <= a[2] * yd[1];
            pa3 <= a[3] * yd[2];
            pa4 <= a[4] * yd[3];
        end
    assign acc     = G - pa1;                       // Q.21: 13 from the coefficients, 8 from y
    assign shifted = acc >>> 13;                    // Q10.8
    assign clip_y  = (shifted > YMAX) || (shifted < YMIN);
    always_ff @(posedge clk)
        if (new_sample) begin
            G <= (F <<< 8) - pa2 - pa3 - pa4;
            // ######################################################################
            // ##  KEY LINE 3: the output, which is also the next sample's y[n-1].
            // ######################################################################
            yd[1] <= (shifted > YMAX) ? YMAX : (shifted < YMIN) ? YMIN : 18'(shifted);
            for (int k = 2; k <= NA; k++) yd[k] <= yd[k-1];
        end

    // ---- the output: y rounded to codes, or the input with the same delay -----------------
    logic signed [18:0] y_round;
    logic signed [10:0] y, mon = 0;
    assign y_round = yd[1] + 19'sd128;
    assign y       = 11'(y_round >>> 8);
    always_ff @(posedge clk) begin
        if (new_sample) mon <= xd[2];               // the input that yd[1] answers to
        if (out_in) dac_d <= 8'(mon + 128);
        else        dac_d <= (y > 127) ? 8'd255 : (y < -128) ? 8'd0 : 8'(y + 128);
    end
    assign dac_clk = ~clk;

    // ---- capture: 16384 ADC samples into block RAM, then out of the UART (capture.sv) ----
    logic [7:0]  mem [0:N-1];
    logic [13:0] addr = 0;
    typedef enum logic [1:0] {IDLE, WAIT, RECORD, SEND} state_t;
    state_t state = IDLE;
    assign syncing = (state == WAIT);
    always_ff @(posedge clk) begin
        tx_start <= 0;
        case (state)
            IDLE:   if (cap_req) begin addr <= 0; state <= WAIT; end
            WAIT:   if (new_sample && period_start) state <= RECORD;    // the next sample is cnt 0
            RECORD: if (new_sample) begin
                        mem[addr] <= 8'(x + 128);   // the ADC's code, as capture.sv stores it
                        addr <= addr + 1;
                        if (addr == N - 1) state <= SEND;
                    end
            SEND:   if (!tx_busy && !tx_start) begin
                        tx_data  <= mem[addr];
                        tx_start <= 1;
                        addr     <= addr + 1;
                        if (addr == N - 1) state <= IDLE;
                    end
        endcase
    end

    // ---- LEDs -----------------------------------------------------------------------------
    logic [21:0] clip_timer = 0;                    // holds the clip LED on for 2^22 clocks
    logic [25:0] blink = 0;
    always_ff @(posedge clk) begin
        blink <= blink + 1;
        if (new_sample && (clip_y || y > 127 || y < -128)) clip_timer <= '1;
        else if (clip_timer != 0) clip_timer <= clip_timer - 1;
    end
    assign led = {clip_timer != 0, state == RECORD || state == SEND, src != 0, out_in, blink[25]};
endmodule
