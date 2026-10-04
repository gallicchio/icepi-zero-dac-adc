// fir_tb.sv -- simulate fir.sv, all four tap sets at once, with no hardware at all.
//
// The fake ADC sits at 128 and puts out one sample of 128 + 64: an impulse.  Each
// filter's DAC must then play 128 + (64 x h[k]) / 256 for its N taps, in order, and
// 128 everywhere else: a filter's response to an impulse IS its taps.  The expected
// values come from each design's own tap table (its h function), so what is checked is
// the delay line, the symmetric pairing, the multiply-accumulate and the scaling.
//
//   make sim-fir
`timescale 1ns/1ps
module fir_tb;
    logic clk = 0;
    always #10 clk = ~clk;

    logic [7:0] adc = 128;
    logic       adc_clk [0:3];
    logic [7:0] dac [0:3];
    logic       dac_clk [0:3];
    logic [4:0] led [0:3];
    fir #(.SET(0)) f0 (.clk(clk), .adc_d(adc), .adc_clk(adc_clk[0]), .dac_d(dac[0]), .dac_clk(dac_clk[0]), .led(led[0]));
    fir #(.SET(1)) f1 (.clk(clk), .adc_d(adc), .adc_clk(adc_clk[1]), .dac_d(dac[1]), .dac_clk(dac_clk[1]), .led(led[1]));
    fir #(.SET(2)) f2 (.clk(clk), .adc_d(adc), .adc_clk(adc_clk[2]), .dac_d(dac[2]), .dac_clk(dac_clk[2]), .led(led[2]));
    fir #(.SET(3)) f3 (.clk(clk), .adc_d(adc), .adc_clk(adc_clk[3]), .dac_d(dac[3]), .dac_clk(dac_clk[3]), .led(led[3]));

    // the impulse: one ADC sample of +64, 25 ns after the 10th rising edge (all four
    // designs clock the ADC identically; use the first's)
    int nedge = 0;
    always @(posedge adc_clk[0]) begin
        nedge++;
        adc <= #25 (nedge == 10) ? 8'd192 : 8'd128;
    end

    int dlog [0:3][0:31];
    int errors = 0, errs, i0, want, n;
    initial begin
        // log the DAC of each design at every sample (f0's new_sample marks the samples)
        for (int i = 0; i < 32; i++) begin
            do @(posedge clk); while (!f0.new_sample);
            for (int s = 0; s < 4; s++) dlog[s][i] = dac[s];
        end
        // all four share one pipeline, so the first change of SET 0 (whose first tap is
        // not 0) marks the latency for all; the low-pass's first two taps round to 0
        i0 = -1;
        for (int i = 0; i < 32; i++) if (i0 < 0 && dlog[0][i] != 128) i0 = i;
        for (int s = 0; s < 4; s++) begin
            n = (s == 0) ? 16 : (s == 2) ? 3 : 15;
            $write("SET %0d (%2d taps): DAC - 128 =", s, n);
            for (int i = i0; i < i0 + n && i < 32; i++) $write(" %0d", dlog[s][i] - 128);
            errs = 0;
            for (int i = 0; i < 32; i++) begin
                case (s)
                    0: want = (i >= i0 && i < i0 + n) ? (64 * f0.h(i - i0)) >>> 8 : 0;
                    1: want = (i >= i0 && i < i0 + n) ? (64 * f1.h(i - i0)) >>> 8 : 0;
                    2: want = (i >= i0 && i < i0 + n) ? (64 * f2.h(i - i0)) >>> 8 : 0;
                    3: want = (i >= i0 && i < i0 + n) ? (64 * f3.h(i - i0)) >>> 8 : 0;
                endcase
                if (want > 127) want = 127;         // the DAC clips (the edge detector's 2 x 64)
                if (dlog[s][i] - 128 != want) errs++;
            end
            if (errs == 0) $display("   from sample %0d: ok, 64 x the taps / 256", i0);
            else           $display("   from sample %0d: FAIL, %0d mismatches", i0, errs);
            errors += errs;
        end
        if (errors == 0) $display("PASS"); else $display("FAIL: %0d mismatches", errors);
        $finish;
    end
endmodule
