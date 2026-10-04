// iir_tb.sv -- simulate iir.sv, both modes, with no hardware at all.
//
//   MODE 0 (K = 4 with the default GUARD = 6, and with GUARD = 0): the ADC steps from
//          128 - 64 to 128 + 64.
//          The DAC must follow y <= y + (x - y) / 16 exactly as integers (the model is
//          three lines below), and the RC's 64 - 128 (15/16)^(n+1) within a code; with
//          GUARD = 0 it must stop short: the dead zone.
//   MODE 1 (2 MHz, Q = 10): a 50-code sine at 2 MHz must come out at about the same
//          amplitude (the peak gain is 1), one at 4 MHz about 20 dB smaller, and the
//          coefficients must be scipy's (201, -14005, 7790).
//
//   make sim-iir
`timescale 1ns/1ps
module iir_tb;
    logic clk = 0;
    always #10 clk = ~clk;

    logic [7:0] adc = 64;                       // 128 - 64
    logic       adc_clk [0:2], dac_clk [0:2];
    logic [7:0] dac [0:2];
    logic [4:0] led [0:2];
    iir #(.MODE(0), .K(4))             p4 (.clk(clk), .adc_d(adc), .adc_clk(adc_clk[0]), .dac_d(dac[0]), .dac_clk(dac_clk[0]), .led(led[0]));
    iir #(.MODE(0), .K(4), .GUARD(0))  g0 (.clk(clk), .adc_d(adc), .adc_clk(adc_clk[1]), .dac_d(dac[1]), .dac_clk(dac_clk[1]), .led(led[1]));
    iir #(.MODE(1), .F0(2000000), .Q(10)) rs (.clk(clk), .adc_d(adc), .adc_clk(adc_clk[2]), .dac_d(dac[2]), .dac_clk(dac_clk[2]), .led(led[2]));

    // the analog world: a step, then sines, as the ADC sees them (25 ns late)
    real ph = 0, freq = 0, amp = 0;
    int  mode = 0, nedge = 0;                   // 0: the step; 1: a sine
    always @(posedge adc_clk[0]) begin
        nedge++;
        if (mode == 0) adc <= #25 (nedge >= 200) ? 8'd192 : 8'd64;
        else begin
            adc <= #25 8'(128 + $rtoi($floor(amp * $sin(ph) + 0.5)));
            ph = ph + 6.283185307179586 * freq / 25.0e6;
        end
    end

    int  dlog [0:2][0:255];
    int  errors = 0, errs, i0, y, yg, lo, hi, n;
    real ideal, a_in, a_out;
    task automatic log_dacs(input int n);
        for (int i = 0; i < n; i++) begin
            do @(posedge clk); while (!p4.new_sample);
            for (int s = 0; s < 3; s++) dlog[s][i] = dac[s];
        end
    endtask
    initial begin
        // ---- MODE 0: the step ----
        do @(posedge clk); while (!(p4.new_sample && nedge == 199));
        log_dacs(100);
        i0 = -1;
        for (int i = 0; i < 100; i++) if (i0 < 0 && dlog[0][i] != 64) i0 = i;
        $display("MODE 0, K = 4: step -64 -> +64 (first change at sample %0d)", i0);
        $display("   n    DAC  model  ideal   GUARD=0");
        y = -64 * 64; yg = -64;                 // the models: y x 2^GUARD (GUARD = K + 2 = 6), and y in 8 bits
        errs = 0;
        for (int i = 0; i < 100; i++) begin
            if (i >= i0) begin
                y  = y + ((64 * 64 - y) >>> 4);
                yg = yg + ((64 - yg) >>> 4);
            end
            ideal = (i < i0) ? -64.0 : 64.0 - 128.0 * (0.9375 ** (i - i0 + 1));
            if (i < i0 + 8 || i % 10 == 0)
                $display("  %2d  %5d  %5d  %6.1f  %5d", i, dlog[0][i] - 128, (y + 32) >>> 6, ideal, dlog[1][i] - 128);
            if (dlog[0][i] - 128 != ((y + 32) >>> 6)) errs++;
            if (dlog[0][i] - 128 > ideal + 1.0 || dlog[0][i] - 128 < ideal - 1.0) errs++;
            if (dlog[1][i] - 128 != yg) errs++;
        end
        $display("   after 100 samples: y = %0d (ideal %.1f); with GUARD = 0: %0d, stuck %0d codes short (the dead zone)",
                 dlog[0][99] - 128, 64.0 - 128.0 * (0.9375 ** (99 - i0 + 1)), dlog[1][99] - 128, 64 - (dlog[1][99] - 128));
        if (dlog[1][99] - 128 > 50) errs++;
        if (errs == 0) $display("   ok: bit-exact with the integer model, within a code of the RC; GUARD = 0 shows the dead zone");
        else           $display("   FAIL: %0d mismatches", errs);
        errors += errs;

        // ---- MODE 1: sines ----
        $display("MODE 1, 2 MHz, Q = 10: b0 = %0d, a1 = %0d, a2 = %0d (scipy: 201, -14005, 7790)",
                 rs.resonator.B0, rs.resonator.A1, rs.resonator.A2);
        if (rs.resonator.B0 != 201 || rs.resonator.A1 != -14005 || rs.resonator.A2 != 7790) errors++;
        amp = 50.0;
        for (int t = 0; t < 2; t++) begin
            freq = (t == 0) ? 2.0e6 : 4.0e6;
            mode = 1;
            #40_000;                            // 1000 samples: the ring-up (Q / pi cycles) and more
            log_dacs(250);                      // 20 cycles at 2 MHz
            lo = 255; hi = 0;
            for (int i = 0; i < 250; i++) begin if (dlog[2][i] < lo) lo = dlog[2][i]; if (dlog[2][i] > hi) hi = dlog[2][i]; end
            a_out = (hi - lo) / 2.0;
            $display("   %0d MHz in at 50 codes: out %0d..%0d, amplitude %.1f codes, %.1f dB", $rtoi(freq / 1e6), lo, hi, a_out,
                     20.0 * $log10(a_out / 50.0));
            if (t == 0 && (a_out < 44.0 || a_out > 56.0)) errors++;
            if (t == 1 && (a_out > 10.0)) errors++;
        end
        if (errors == 0) $display("PASS"); else $display("FAIL: %0d checks failed", errors);
        $finish;
    end
endmodule
