// fir.sv -- a fixed FIR filter between the ADC and the DAC (7.01).  Every ADC sample
// (25 MS/s) goes into a delay line; the output is a weighted sum of the last N samples,
// and the DAC plays it, once per ADC sample, as 128 + y, clipped to 0..255.
//
//     y[n] = h[0] x[n] + h[1] x[n-1] + ... + h[N-1] x[n-N+1]
//
// That sum is a convolution: a dot product of the taps h with the last N samples, slid
// along the signal one sample at a time.  The taps are fixed when the design is built,
// by SET (make fir_set1.bit):
//
//   SET 0  a 16-sample moving average: every tap 1/16.  The "slowly varying hump".
//   SET 1  a 15-tap windowed-sinc low-pass, 2 MHz cutoff: a sophisticated moving average.
//   SET 2  an edge detector, [-1, 2, -1]: the second difference, a high-pass.
//   SET 3  a 15-tap windowed-sinc band-pass, 3-5 MHz.
//
// The taps are integers x 256 (256 means 1.0), so the sum is divided by 256 at the end:
// a shift right by 8.  All four sets are symmetric, h[k] = h[N-1-k], so the two samples
// that share a tap are added first and multiplied once: 8 multiplies for 16 taps, not
// 16.  (Symmetric taps are also why these filters have a linear phase: every frequency
// comes out delayed by the same (N-1)/2 samples.)
//
// LEDs: led[4] = the output clipped in the last 84 ms; led[3:1] = |y| on a 3-bit scale
//       (a 16-code change lights one more); led[0] blinks: the design is alive.
module fir #(
    parameter integer SET = 1       // which taps: 0 average, 1 low-pass, 2 edge, 3 band-pass
) (
    input  logic       clk,         // 50 MHz
    output logic [7:0] dac_d = 128,
    output logic       dac_clk,
    input  logic [7:0] adc_d,
    output logic       adc_clk,
    output logic [4:0] led
);
    // ---- the taps, as integers x 256 ------------------------------------------------
    // SET 1 and 3 came from scipy (each list is h[0] .. h[N-1]; being symmetric, it reads
    // the same backwards):
    //   python3 -c "import numpy as np, scipy.signal as s
    //   print(np.round(256 * s.firwin(15, 2e6, fs=25e6)).astype(int))"
    //                               -> [0 0 3 9 20 32 42 46 42 32 20 9 3 0 0]
    //   print(np.round(256 * s.firwin(15, [3e6, 5e6], pass_zero=False, fs=25e6)).astype(int))"
    //                               -> [2 6 4 -17 -42 -25 37 73 37 -25 -42 -17 4 6 2]
    // (firwin's default Hamming window; the low-pass's outer taps round to 0, so it is
    // really an 11-tap filter.)  Yosys has no unpacked-array parameters, so the table is
    // one long word, 16 bits per tap, read by h(k) below.
    localparam integer N = (SET == 0) ? 16 : (SET == 2) ? 3 : 15;      // how many taps
    localparam logic [16*16-1:0] TAPS =
        (SET == 0) ? {16{16'd16}} :                                     // 16 x 1/16
        (SET == 1) ? {16'(0), 16'(0), 16'(3), 16'(9), 16'(20), 16'(32), 16'(42), 16'(46),
                      16'(42), 16'(32), 16'(20), 16'(9), 16'(3), 16'(0), 16'(0)} :
        (SET == 2) ? {16'(-256), 16'(512), 16'(-256)} :                 // [-1 2 -1] x 256
                     {16'(2), 16'(6), 16'(4), 16'(-17), 16'(-42), 16'(-25), 16'(37), 16'(73),
                      16'(37), 16'(-25), 16'(-42), 16'(-17), 16'(4), 16'(6), 16'(2)};
    function automatic logic signed [15:0] h(input integer k);        // tap k, x 256
        h = TAPS[16*k +: 16];
    endfunction

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

    // ---- the delay line: the last N samples, newest first ----------------------------
    logic signed [8:0] d [0:N-1];
    initial for (int k = 0; k < N; k++) d[k] = 0;
    always_ff @(posedge clk)
        if (new_sample) begin
            // ######################################################################
            // ##  KEY LINE: the delay line.  Each new sample pushes the older ones
            // ##  along by one: d[k] is the sample from k samples ago.
            // ######################################################################
            d[0] <= x;
            for (int k = 1; k < N; k++) d[k] <= d[k-1];
        end

    // ---- the sum of products, as an assembly line: one step per clock ----------------
    // A sample lasts two clocks and each step is registered, so each stage changes once
    // per sample and the DAC sees a clean value.  Step 1 pairs the samples that share a
    // tap; step 2 multiplies; step 3 adds up.
    localparam integer M = N / 2;                   // pairs; an odd N leaves a middle sample
    logic signed [9:0]  pair [0:M-1];               // d[k] + d[N-1-k]
    logic signed [8:0]  mid = 0;                    // d[M], when N is odd
    logic signed [25:0] prod [0:M];                 // pair[k] x h(k); prod[M] is the middle's
    logic signed [31:0] sum, acc = 0;
    initial for (int k = 0; k < M; k++) begin pair[k] = 0; prod[k] = 0; end
    initial prod[M] = 0;
    always_comb begin
        sum = 0;
        for (int k = 0; k <= M; k++) sum += prod[k];
    end
    always_ff @(posedge clk) begin
        for (int k = 0; k < M; k++) pair[k] <= d[k] + d[N-1-k];     // the symmetric trick
        mid <= d[M];
        // ##########################################################################
        // ##  KEY LINE: multiply-accumulate.  Each pair times its tap (a hardware
        // ##  multiplier each), then all the products added: the dot product.
        // ##########################################################################
        for (int k = 0; k < M; k++) prod[k] <= pair[k] * h(k);
        prod[M] <= (N % 2 == 1) ? mid * h(M) : 26'sd0;
        acc     <= sum;
    end

    // ---- the output: divide by 256 (the taps' scale), clip to what the DAC can show ---
    logic signed [31:0] y;
    assign y = acc >>> 8;
    always_ff @(posedge clk)
        // ##########################################################################
        // ##  KEY LINE: the taps were x 256, so the sum is y x 256: shift it back,
        // ##  and the DAC plays 128 + y, held until the next sample.
        // ##########################################################################
        dac_d <= (y > 127) ? 8'd255 : (y < -128) ? 8'd0 : 8'(y + 128);
    assign dac_clk = ~clk;

    // ---- LEDs ------------------------------------------------------------------------
    logic [21:0] clip_timer = 0;                    // holds the clip LED on for 2^22 clocks
    logic [25:0] blink = 0;
    logic [7:0]  mag;                               // |y| as the DAC shows it, 0..128
    assign mag = dac_d[7] ? dac_d - 8'd128 : 8'd128 - dac_d;
    always_ff @(posedge clk) begin
        blink <= blink + 1;
        if (y > 127 || y < -128) clip_timer <= '1;
        else if (clip_timer != 0) clip_timer <= clip_timer - 1;
    end
    assign led = {clip_timer != 0, mag[6:4], blink[25]};
endmodule
