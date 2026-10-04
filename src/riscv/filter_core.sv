// filter_core.sv -- 7.03's filter.sv with the serial port replaced by registers (7.04).
//
// The same filter: direct form I, 16 feed-forward and 4 feedback taps in Q2.13 (the
// value x 8192), the same built-in stimuli and the same output select, line for line
// (the arithmetic, the pipeline and the 18-bit state are explained in filter.sv).
// What changed is where the settings come from: the coefficients, the source, the
// output select and the tone's tuning word are inputs, wired to CSRs by adda_litex.py,
// and the ADC's samples arrive from adda_io instead of the pins.
//
//   y[n] = ( b_0 x[n] + ... + b_15 x[n-15]  -  a_1 y[n-1] - ... - a_4 y[n-4] ) / 8192
//
// New, because a CPU wants to switch it on and off and ask how it is:
//   enable   low holds the filter's state at zero, so dac_value sits at 128.  Switching
//            a filter off and on clears it: an unstable set of a's saturates for ever
//            (7.02), and this is the way out.  The stimuli keep running.
//   running  high three samples after enable: the pipeline has filled, and dac_value is
//            the filter's answer to real input (filter.sv's latency, 120 ns).
//   clipped  the output saturated within the last 2^22 clocks (84 ms): filter.sv's led[4].
//
// One difference from filter.sv's stimuli: the noise re-seeds at every period start
// (every 2^14 samples) instead of only when a capture asks it to, so that the noise is
// periodic and a capture taken at any moment (2.04's peripheral, which knows nothing of
// this filter) holds exactly one period of it, which the laptop can line up by
// correlation.  The impulse and the step were periodic already.
module filter_core (
    input  logic             clk,           // 50 MHz
    input  logic [7:0]       sample,        // the ADC's code, from adda_io
    input  logic             sample_valid,  // one clock per sample: 25 MS/s
    // the settings, from CSRs
    input  logic [16*16-1:0] b_all,         // b_0..b_15, 16 bits each, b_0 lowest; Q2.13
    input  logic [16*4-1:0]  a_all,         // a_1..a_4, a_1 lowest
    input  logic [2:0]       src,           // 0 ADC; 1 impulse; 2 step; 3 noise; 4 tone
    input  logic             out_in,        // 1: the DAC plays the input, delayed to match
    input  logic [31:0]      tone_word,     // the tone: f / 25e6 x 2^32
    input  logic             enable,
    output logic             running,
    output logic             clipped,
    output logic [7:0]       dac_value = 128
);
    localparam integer NB = 16, NA = 4;             // feed-forward and feedback taps

    // ---- the settings, unpacked ------------------------------------------------------
    logic signed [15:0] b [0:NB-1];                 // Q2.13
    logic signed [15:0] a [1:NA];
    always_comb begin
        for (int k = 0; k < NB; k++) b[k] = b_all[16*k +: 16];
        for (int k = 1; k <= NA; k++) a[k] = a_all[16*(k-1) +: 16];
    end

    // ---- the ADC's samples, as filter.sv sees them ------------------------------------
    logic new_sample;
    logic signed [8:0] x;                           // the sample, -128..127
    assign new_sample = sample_valid;
    assign x = $signed({1'b0, sample}) - 9'sd128;
    logic step = 0;                                 // the clock after new_sample
    always_ff @(posedge clk) step <= new_sample;

    // ---- the built-in stimuli, one value per sample (filter.sv) ------------------------
    logic [14:0] cnt = 0;                           // counts samples; the period is 2^14
    logic        period_start;                      // the next sample is cnt 0
    assign period_start = (cnt[13:0] == 14'h3fff);
    logic signed [8:0] impulse, stp, noise, tone = 0;
    assign impulse = (cnt[13:0] == 0) ? 9'sd64 : 9'sd0;
    assign stp     = cnt[14] ? 9'sd64 : -9'sd64;
    localparam logic [31:0] SEED = 32'h2545_f491;
    logic [31:0] r = SEED, r1, r2, r3;
    assign r1 = r ^ (r << 13);
    assign r2 = r1 ^ (r1 >> 17);
    assign r3 = r2 ^ (r2 << 5);
    logic signed [10:0] gsum;
    assign gsum  = $signed({3'b0, r[7:0]}) + $signed({3'b0, r[15:8]}) + $signed({3'b0, r[23:16]})
                 + $signed({3'b0, r[31:24]}) - 11'sd510;
    assign noise = 9'(gsum >>> 4);
    logic signed [7:0] sin64 [0:255];
    initial for (int i = 0; i < 256; i++)
        sin64[i] = $rtoi($floor(64.0 * $sin(6.283185307179586 * i / 256) + 0.5));
    logic [31:0] phase = 0;
    always_ff @(posedge clk)
        if (new_sample) begin
            cnt   <= cnt + 1;
            r     <= period_start ? SEED : r3;      // periodic: see the header
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

    // ---- the filter: filter.sv's, with `enable` low clearing every register -----------
    logic signed [8:0]  xd [0:NB-1];                // x[n-k]: the delay line
    logic signed [24:0] pb [0:NB-1];                // b_k x[n-k], 9 x 16 bits
    logic signed [26:0] q  [0:3];                   // sums of four products
    logic signed [28:0] F = 0;                      // the sum of all sixteen
    initial for (int k = 0; k < NB; k++) begin xd[k] = 0; pb[k] = 0; end
    initial for (int j = 0; j < 4; j++) q[j] = 0;
    always_ff @(posedge clk)
        if (!enable) begin
            for (int k = 0; k < NB; k++) begin xd[k] <= 0; pb[k] <= 0; end
            for (int j = 0; j < 4; j++) q[j] <= 0;
            F <= 0;
        end else begin
            if (new_sample) begin
                // ##################################################################
                // ##  KEY LINE 1: the delay line.  Each new input pushes the rest along.
                // ##################################################################
                xd[0] <= u;
                for (int k = 1; k < NB; k++) xd[k] <= xd[k-1];
                for (int j = 0; j < 4; j++) q[j] <= pb[4*j] + pb[4*j+1] + pb[4*j+2] + pb[4*j+3];
            end
            if (step) begin
                // ##################################################################
                // ##  KEY LINE 2: sixteen multiplies at once, one hardware multiplier
                // ##  each; b[k] is a wire from a register the CPU writes.
                // ##################################################################
                for (int k = 0; k < NB; k++) pb[k] <= b[k] * xd[k];
                F <= q[0] + q[1] + q[2] + q[3];
            end
        end

    localparam logic signed [17:0] YMAX = 18'sd131071, YMIN = -YMAX - 18'sd1;
    logic signed [17:0] yd [1:NA];                  // y[n-1..n-4], Q10.8
    logic signed [33:0] pa1 = 0, pa2 = 0, pa3 = 0, pa4 = 0;    // 16 x 18 bits
    logic signed [39:0] G = 0, acc, shifted;
    logic               clip_y;
    initial for (int k = 1; k <= NA; k++) yd[k] = 0;
    always_ff @(posedge clk)
        if (!enable) begin
            pa1 <= 0; pa2 <= 0; pa3 <= 0; pa4 <= 0;
        end else if (step) begin
            pa1 <= a[1] * yd[1];
            pa2 <= a[2] * yd[1];
            pa3 <= a[3] * yd[2];
            pa4 <= a[4] * yd[3];
        end
    assign acc     = G - pa1;                       // Q.21: 13 from the coefficients, 8 from y
    assign shifted = acc >>> 13;                    // Q10.8
    assign clip_y  = (shifted > YMAX) || (shifted < YMIN);
    always_ff @(posedge clk)
        if (!enable) begin
            G <= 0;
            for (int k = 1; k <= NA; k++) yd[k] <= 0;
        end else if (new_sample) begin
            G <= (F <<< 8) - pa2 - pa3 - pa4;
            // ######################################################################
            // ##  KEY LINE 3: the output, which is also the next sample's y[n-1].
            // ######################################################################
            yd[1] <= (shifted > YMAX) ? YMAX : (shifted < YMIN) ? YMIN : 18'(shifted);
            for (int k = 2; k <= NA; k++) yd[k] <= yd[k-1];
        end

    // ---- the output: y rounded to codes, or the input with the same delay -------------
    logic signed [18:0] y_round;
    logic signed [10:0] y, mon = 0;
    assign y_round = yd[1] + 19'sd128;
    assign y       = 11'(y_round >>> 8);
    always_ff @(posedge clk) begin
        if (new_sample) mon <= xd[2];               // the input that yd[1] answers to
        if (out_in) dac_value <= 8'(mon + 128);
        else        dac_value <= (y > 127) ? 8'd255 : (y < -128) ? 8'd0 : 8'(y + 128);
    end

    // ---- status ----------------------------------------------------------------------
    logic [1:0]  primed = 0;                        // samples since enable, up to 3
    logic [21:0] clip_timer = 0;                    // holds `clipped` for 2^22 clocks
    always_ff @(posedge clk) begin
        if (!enable)                                 primed <= 0;
        else if (new_sample && primed != 2'd3)       primed <= primed + 1;
        if (new_sample && (clip_y || y > 127 || y < -128)) clip_timer <= '1;
        else if (clip_timer != 0)                    clip_timer <= clip_timer - 1;
    end
    assign running = (primed == 2'd3);
    assign clipped = (clip_timer != 0);
endmodule
