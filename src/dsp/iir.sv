// iir.sv -- two fixed IIR filters between the ADC and the DAC (7.02): filters with
// feedback, whose output depends on the outputs before it as well as on the inputs.
//
//   MODE 0  the one-tap "leaky integrator":    y <= y + (x - y) / 2^K
//           An RC low-pass in one line: every sample, y moves 1/2^K of the way from
//           where it is to the input.  Its impulse response is a decaying exponential
//           with a time constant of 2^K samples (2^K x 40 ns), its step response the
//           charging of a capacitor, and its cutoff
//                 f_c = fs / (2 pi 2^K):   K = 4: 249 kHz;  K = 6: 62 kHz;  K = 8: 15.5 kHz
//           (exactly, the pole sits at 1 - 2^-K and the -3 dB point is 3% above that
//           for K = 4, 1% for K = 6).   make iir_k4.bit, iir_k6.bit, ...
//
//   MODE 1  a resonator: a second-order band-pass (a "biquad") peaking at F0 Hz with
//           quality factor Q (bandwidth F0/Q), the coefficients exactly as
//           scipy.signal.iirpeak(F0, Q, fs=25e6) makes them, computed here from F0 and Q:
//                 y[n] = b0 (x[n] - x[n-2]) - a1 y[n-1] - a2 y[n-2]
//           with b0 = beta / (1 + beta), a1 = -2 cos(w0) / (1 + beta), a2 = (1 - beta) /
//           (1 + beta), beta = tan(w0 / 2Q), w0 = 2 pi F0 / fs; as 16-bit integers x 8192
//           (Q2.13, as filter.sv in 7.03).   make iir_peak.bit (2 MHz, Q = 10)
//
// Wordlength: why an IIR needs more bits than an FIR.  An FIR's sum is over N products
// of known size and that is the end of it.  An IIR feeds its output back, so three things
// bite that an FIR never meets:
//   1. Rounding feeds back.  If y had only the ADC's 8 bits, (x - y) >>> K would be zero
//      whenever |x - y| < 2^K, and the output would stop 2^K codes short of the input: a
//      dead zone, which GUARD = 0 shows (make iir_k6_g0.bit).  The cure is GUARD extra bits
//      of y below the ADC's lsb: 2^GUARD of them are worth one ADC code, and the dead
//      zone shrinks to 2^(K-GUARD) codes: a quarter of a code with the default K + 2.
//   2. The state rings.  A resonator's y can be Q times the input for a while, and its
//      sum of products is bigger still, so the state gets 18 bits (+-512 with 8 fraction
//      bits, which is also what one 18 x 18 hardware multiplier takes) and saturates
//      rather than wrapping: a wrapped IIR oscillates for ever, a saturated one recovers.
//   3. Coefficients are poles.  a2 = r^2 sets the pole radius; a1 = -2 r cos w0 its angle,
//      and the angle's sensitivity to a1 is 1 / (2 r sin w0): one step of 1/8192 moves a
//      2 MHz resonator's peak by 0.03% but a 20 kHz one by twice its own frequency.  The
//      lower the frequency, the more bits a pole needs (or a lower sample rate).
//
// LEDs: led[4] = the output clipped in the last 84 ms; led[3:1] = |y|; led[0] blinks.
module iir #(
    parameter integer MODE  = 0,        // 0 = the one-pole, 1 = the resonator
    parameter integer K     = 4,        // MODE 0: time constant 2^K samples
    parameter integer GUARD = K + 2,    // MODE 0: bits of y kept below the ADC's lsb (0: dead zone)
    parameter integer F0    = 2000000,  // MODE 1: the peak, Hz
    parameter integer Q     = 10        // MODE 1: the quality factor: bandwidth F0 / Q
) (
    input  logic       clk,             // 50 MHz
    output logic [7:0] dac_d = 128,
    output logic       dac_clk,
    input  logic [7:0] adc_d,
    output logic       adc_clk,
    output logic [4:0] led
);
    // ---- the ADC at 25 MS/s, as in capture.sv ---------------------------------------
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
    logic step = 0;                                 // one clock after new_sample
    always_ff @(posedge clk) step <= new_sample;

    logic signed [17:0] y_out;                      // the filter's output, in ADC codes

    generate if (MODE == 0) begin : onepole
        // ---- the one-pole: y, with GUARD bits below the lsb -------------------------
        localparam integer HALF = (GUARD > 0) ? (1 << (GUARD - 1)) : 0;    // for rounding
        logic signed [9+GUARD:0]  y = 0, xg;       // y x 2^GUARD; x in the same scale
        logic signed [10+GUARD:0] yr;              // y + 1/2 code
        assign xg = x <<< GUARD;
        always_ff @(posedge clk)
            if (new_sample)
                // ######################################################################
                // ##  KEY LINE: the whole filter.  Move 1/2^K of the way to the input.
                // ######################################################################
                y <= y + ((xg - y) >>> K);
        assign yr    = y + HALF;
        assign y_out = yr >>> GUARD;                // rounded to ADC codes
    end else begin : resonator
        // ---- the coefficients, as scipy.signal.iirpeak computes them ----------------
        localparam real    W0   = 6.283185307179586 * F0 / 25.0e6;   // radians per sample
        localparam real    BETA = $tan(W0 / (2.0 * Q));
        localparam real    G    = 1.0 / (1.0 + BETA);
        localparam integer B0   = $rtoi($floor((1.0 - G) * 8192.0 + 0.5));
        localparam integer A1   = $rtoi($floor(-2.0 * G * $cos(W0) * 8192.0 + 0.5));
        localparam integer A2   = $rtoi($floor((2.0 * G - 1.0) * 8192.0 + 0.5));
        logic signed [15:0] b0 = B0, a1 = A1, a2 = A2;       // Q2.13

        // ---- the state: y[n-1], y[n-2] in Q10.8 (8 fraction bits), x[n-1], x[n-2] ----
        localparam logic signed [17:0] WMAX = 18'sd131071, WMIN = -WMAX - 18'sd1;
        logic signed [17:0] w1 = 0, w2 = 0;
        logic signed [18:0] w1r;                    // w1 + 1/2, for rounding
        logic signed [8:0]  x1 = 0, x2 = 0;
        logic signed [25:0] pb  = 0;                // b0 (x[n] - x[n-2])      10 x 16 bits
        logic signed [33:0] pa1 = 0, pa2 = 0;       // a1 y[n-1], a2 y[n-2]    16 x 18 bits
        logic signed [39:0] acc, shifted;
        // The feedback must close within one sample, two clocks: multiply on the first
        // (new_sample), add and store on the second (step).  A deeper pipeline would be
        // using y[n-2] where y[n-1] belongs: a different filter.
        always_ff @(posedge clk)
            if (new_sample) begin
                // ######################################################################
                // ##  KEY LINE 1: the three products, one hardware multiplier each.
                // ######################################################################
                pb  <= b0 * (x - x2);
                pa1 <= a1 * w1;
                pa2 <= a2 * w2;
                x2  <= x1;
                x1  <= x;
            end
        assign acc     = (pb <<< 8) - pa1 - pa2;    // Q.21: the products' 13 + the state's 8
        assign shifted = acc >>> 13;                // back to Q10.8
        always_ff @(posedge clk)
            if (step) begin
                // ######################################################################
                // ##  KEY LINE 2: the new output, saturated, becomes y[n-1] for the next
                // ##  sample, and the old y[n-1] becomes y[n-2].
                // ######################################################################
                w1 <= (shifted > WMAX) ? WMAX : (shifted < WMIN) ? WMIN : 18'(shifted);
                w2 <= w1;
            end
        assign w1r   = w1 + 19'sd128;
        assign y_out = w1r >>> 8;                   // rounded to ADC codes
    end endgenerate

    // ---- the output: 128 + y, clipped to what the DAC can show -----------------------
    always_ff @(posedge clk)
        dac_d <= (y_out > 127) ? 8'd255 : (y_out < -128) ? 8'd0 : 8'(y_out + 128);
    assign dac_clk = ~clk;

    // ---- LEDs ------------------------------------------------------------------------
    logic [21:0] clip_timer = 0;
    logic [25:0] blink = 0;
    logic [7:0]  mag;
    assign mag = dac_d[7] ? dac_d - 8'd128 : 8'd128 - dac_d;
    always_ff @(posedge clk) begin
        blink <= blink + 1;
        if (y_out > 127 || y_out < -128) clip_timer <= '1;
        else if (clip_timer != 0) clip_timer <= clip_timer - 1;
    end
    assign led = {clip_timer != 0, mag[6:4], blink[25]};
endmodule
